"""
Thin wrapper around the Gemini SDK.

All Gemini calls go through GeminiClient so that:
- the rest of the code doesn't import the SDK directly
- every failure becomes a GeminiError that callers can fall back from
- the app keeps working when GEMINI_API_KEY isn't set
"""

import json
import logging
from dataclasses import dataclass

from django.conf import settings
from google import genai
from google.genai import errors, types

logger = logging.getLogger(__name__)

# these are worth retrying on the fallback model (quota hit, model retired, overloaded)
RETRYABLE_STATUS_CODES = {404, 429, 500, 503}


class GeminiError(Exception):
    pass


@dataclass
class MediaInput:
    data: bytes
    mime_type: str


class GeminiClient:
    def __init__(self, api_key=None, models=None):
        self.api_key = settings.GEMINI_API_KEY if api_key is None else api_key
        if models is None:
            models = [settings.GEMINI_MODEL, settings.GEMINI_FALLBACK_MODEL]
        # dedupe but keep order
        self.models = list(dict.fromkeys(m for m in models if m))
        self._client = None

    @property
    def enabled(self):
        return bool(self.api_key and self.models)

    def generate_text(self, prompt, *, system=None, media=None, temperature=0.5, max_tokens=2048):
        return self._generate(prompt, system=system, media=media, temperature=temperature, max_tokens=max_tokens)

    def generate_json(self, prompt, *, schema, system=None, media=None, temperature=0.2, max_tokens=2048):
        raw = self._generate(
            prompt,
            system=system,
            media=media,
            temperature=temperature,
            max_tokens=max_tokens,
            schema=schema,
        )
        return parse_json(raw)

    def _get_client(self):
        if self._client is None:
            self._client = genai.Client(
                api_key=self.api_key,
                http_options=types.HttpOptions(timeout=settings.GEMINI_TIMEOUT_SECONDS * 1000),
            )
        return self._client

    def _generate(self, prompt, *, system, media, temperature, max_tokens, schema=None):
        if not self.enabled:
            raise GeminiError("Gemini API key is not configured")

        contents = [types.Part.from_bytes(data=item.data, mime_type=item.mime_type) for item in media or []]
        contents.append(prompt)

        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            max_output_tokens=max_tokens,
            response_mime_type="application/json" if schema else None,
            response_json_schema=schema,
        )

        last_error = None
        for model in self.models:
            try:
                response = self._get_client().models.generate_content(model=model, contents=contents, config=config)
            except errors.APIError as exc:
                last_error = exc
                logger.warning("Gemini %s failed with %s: %s", model, exc.code, exc.message)
                if exc.code in RETRYABLE_STATUS_CODES:
                    continue
                break
            except Exception as exc:  # timeouts, connection errors etc.
                last_error = exc
                logger.warning("Gemini %s request error: %s", model, exc)
                continue

            text = (response.text or "").strip()
            if text:
                return text
            # empty text usually means the answer got blocked by safety filters
            last_error = GeminiError(f"{model} returned an empty response")

        raise GeminiError(str(last_error) if last_error else "Gemini request failed")


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
        raise GeminiError("Gemini returned invalid JSON") from exc
