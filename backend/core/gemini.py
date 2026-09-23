"""
Thin wrapper around the Gemini SDK.

All Gemini calls go through GeminiClient so that:
- the rest of the code doesn't import the SDK directly
- every failure becomes a GeminiError that callers can fall back from
- the app keeps working when GEMINI_API_KEY isn't set
- every call gets recorded for the API logs panel (see apilogs/)
"""

import json
import logging
import time
from contextvars import ContextVar
from dataclasses import dataclass

from django.conf import settings
from google import genai
from google.genai import errors, types

logger = logging.getLogger(__name__)

# these are worth retrying on the fallback model (quota hit, model retired, overloaded)
RETRYABLE_STATUS_CODES = {404, 429, 500, 503, 504}

# Set per request by apilogs.middleware:
# - a key the visitor supplied themselves (X-Gemini-Key header), used instead of ours
# - a list every Gemini call of the request is appended to
request_api_key = ContextVar("request_api_key", default="")
recorded_calls = ContextVar("recorded_calls", default=None)


class GeminiError(Exception):
    def __init__(self, message, reason="error"):
        super().__init__(message)
        self.reason = reason


@dataclass
class MediaInput:
    data: bytes
    mime_type: str


def failure_reason(exc):
    """Short machine readable reason, shown in the API logs and under chat replies."""
    code = getattr(exc, "code", None)
    status = str(getattr(exc, "status", "") or "")
    message = str(getattr(exc, "message", "") or exc).lower()
    if code == 429 or status == "RESOURCE_EXHAUSTED":
        return "quota"
    if code in (401, 403) or "api key" in message or "api_key" in message:
        return "invalid_key"
    if code == 503:
        return "overloaded"
    if code == 504 or "timed out" in message or "timeout" in message or "deadline" in message:
        return "timeout"
    if code == 404:
        return "model_not_found"
    return "error"


class GeminiClient:
    def __init__(self, api_key=None, models=None):
        custom_key = request_api_key.get()
        if api_key is None:
            api_key = custom_key or settings.GEMINI_API_KEY
        self.api_key = api_key
        self.using_custom_key = bool(custom_key) and api_key == custom_key
        if models is None:
            models = [settings.GEMINI_MODEL, settings.GEMINI_FALLBACK_MODEL]
        # dedupe but keep order
        self.models = list(dict.fromkeys(m for m in models if m))
        # reason of the last call that failed on every model, None if all went fine
        self.last_failure = None
        self._client = None

    @property
    def enabled(self):
        return bool(self.api_key and self.models)

    def generate_text(self, prompt, *, system=None, media=None, temperature=0.5, max_tokens=2048, purpose="text"):
        return self._generate(
            prompt, system=system, media=media, temperature=temperature, max_tokens=max_tokens, purpose=purpose
        )

    def generate_json(self, prompt, *, schema, system=None, media=None, temperature=0.2, max_tokens=2048, purpose="json"):
        raw = self._generate(
            prompt,
            system=system,
            media=media,
            temperature=temperature,
            max_tokens=max_tokens,
            schema=schema,
            purpose=purpose,
        )
        return parse_json(raw)

    def _get_client(self):
        if self._client is None:
            self._client = genai.Client(
                api_key=self.api_key,
                http_options=types.HttpOptions(timeout=settings.GEMINI_TIMEOUT_SECONDS * 1000),
            )
        return self._client

    def _record(self, purpose, model, started, reason=None, message=""):
        calls = recorded_calls.get()
        if calls is None:
            return
        calls.append(
            {
                "purpose": purpose,
                "model": model,
                "ok": reason is None,
                "reason": reason or "",
                "message": message[:200],
                "duration_ms": int((time.monotonic() - started) * 1000),
                "custom_key": self.using_custom_key,
            }
        )

    def _generate(self, prompt, *, system, media, temperature, max_tokens, schema=None, purpose="text"):
        if not self.enabled:
            raise GeminiError("Gemini API key is not configured", reason="not_configured")

        contents = [types.Part.from_bytes(data=item.data, mime_type=item.mime_type) for item in media or []]
        contents.append(prompt)

        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            max_output_tokens=max_tokens,
            response_mime_type="application/json" if schema else None,
            response_json_schema=schema,
            # we never pass tools, no need for the SDK's function calling loop
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

        last_error, last_reason = None, "error"
        for model in self.models:
            started = time.monotonic()
            try:
                response = self._get_client().models.generate_content(model=model, contents=contents, config=config)
            except errors.APIError as exc:
                last_error, last_reason = exc, failure_reason(exc)
                self._record(purpose, model, started, last_reason, exc.message or "")
                logger.warning("Gemini %s failed with %s: %s", model, exc.code, exc.message)
                if exc.code in RETRYABLE_STATUS_CODES:
                    continue
                break
            except Exception as exc:  # timeouts, connection errors etc.
                last_error, last_reason = exc, failure_reason(exc)
                self._record(purpose, model, started, last_reason, str(exc))
                logger.warning("Gemini %s request error: %s", model, exc)
                continue

            text = (response.text or "").strip()
            if text:
                self._record(purpose, model, started)
                return text
            # empty text usually means the answer got blocked by safety filters
            last_error, last_reason = GeminiError(f"{model} returned an empty response"), "empty"
            self._record(purpose, model, started, last_reason, "empty response")

        self.last_failure = last_reason
        raise GeminiError(str(last_error) if last_error else "Gemini request failed", reason=last_reason)


def parse_json(raw):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # sometimes the model still wraps the json in ```json ... ``` fences
    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise GeminiError("Gemini returned invalid JSON", reason="bad_response") from exc
