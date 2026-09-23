import json
import logging
import re
import time

from core.gemini import recorded_calls, request_api_key

from .models import RequestLog

logger = logging.getLogger(__name__)

# the panel polls these, logging them would just flood the list
SKIP_PATHS = ("/api/logs/",)
KEY_RE = re.compile(r"^[A-Za-z0-9._\-]{20,200}$")


def _client_id(request):
    return (request.headers.get("X-Client-Id") or request.GET.get("client_id") or "")[:64]


def _error_message(response):
    if response.status_code < 400 or "json" not in response.get("Content-Type", ""):
        return ""
    try:
        return str(json.loads(response.content)["error"]["message"])[:255]
    except (ValueError, KeyError, TypeError):
        return ""


class RequestLogMiddleware:
    """
    Logs every API call (method, path, status, time) and the Gemini calls made
    during it. Also picks up the visitor's own Gemini key from the X-Gemini-Key
    header, which is used for that request only and never stored.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith("/api/") or request.method == "OPTIONS":
            return self.get_response(request)

        custom_key = request.headers.get("X-Gemini-Key", "").strip()
        key_token = request_api_key.set(custom_key if KEY_RE.match(custom_key) else "")
        calls_token = recorded_calls.set([])
        started = time.monotonic()
        try:
            response = self.get_response(request)
            ai_calls = recorded_calls.get()
        finally:
            request_api_key.reset(key_token)
            recorded_calls.reset(calls_token)

        if not request.path.startswith(SKIP_PATHS):
            try:
                RequestLog.objects.create(
                    client_id=_client_id(request),
                    method=request.method,
                    path=request.path[:255],
                    status_code=response.status_code,
                    duration_ms=int((time.monotonic() - started) * 1000),
                    error=_error_message(response),
                    ai_calls=ai_calls,
                )
            except Exception:
                # logging must never break the actual request
                logger.exception("Could not save request log")
        return response
