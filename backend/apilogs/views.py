import time

from django.conf import settings
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from core.client import get_client_id
from core.gemini import GeminiClient, GeminiError, request_api_key

from .models import RequestLog

MAX_LOGS = 100
# requests where the bot had to think; if these ran without a Gemini call the rules handled them
BOT_PATHS = ("/api/chat/", "/api/diagnosis/")


def server_key_status():
    """
    Status of *our* Gemini key, based on the most recent calls that used it
    (calls made with a visitor's own key are ignored here).
    """
    if not settings.GEMINI_API_KEY:
        return {"status": "not_configured", "reason": "", "last_call_at": None}

    for log in RequestLog.objects.exclude(ai_calls=[]).only("ai_calls", "created_at")[:30]:
        calls = [call for call in log.ai_calls if not call.get("custom_key")]
        if not calls:
            continue
        worked = any(call.get("ok") for call in calls)
        return {
            "status": "ok" if worked else "failing",
            "reason": "" if worked else calls[-1].get("reason", "error"),
            "last_call_at": timezone.localtime(log.created_at),
        }
    return {"status": "unknown", "reason": "", "last_call_at": None}


class RequestLogView(APIView):
    """GET /api/logs/ - this browser's recent API calls plus the Gemini status."""

    def get(self, request):
        client_id = get_client_id(request)
        try:
            limit = min(max(int(request.query_params.get("limit", 50)), 1), MAX_LOGS)
        except ValueError:
            limit = 50

        own_logs = RequestLog.objects.filter(client_id=client_id)
        logs = list(own_logs[:limit])

        ai_calls = [call for log in own_logs.exclude(ai_calls=[]).only("ai_calls") for call in log.ai_calls]
        bot_requests = own_logs.filter(path__in=BOT_PATHS, status_code__lt=400)

        return Response(
            {
                "gemini": {
                    **server_key_status(),
                    "model": settings.GEMINI_MODEL,
                    "fallback_model": settings.GEMINI_FALLBACK_MODEL,
                    "using_custom_key": bool(request_api_key.get()),
                },
                "stats": {
                    "requests": own_logs.count(),
                    "bot_replies": bot_requests.count(),
                    "handled_by_rules": bot_requests.filter(ai_calls=[]).count(),
                    "ai_calls": len(ai_calls),
                    "ai_failures": sum(1 for call in ai_calls if not call.get("ok")),
                },
                "results": [
                    {
                        "id": log.id,
                        "method": log.method,
                        "path": log.path,
                        "status_code": log.status_code,
                        "duration_ms": log.duration_ms,
                        "error": log.error,
                        "ai_calls": log.ai_calls,
                        "created_at": timezone.localtime(log.created_at),
                    }
                    for log in logs
                ],
            }
        )


class GeminiCheckView(APIView):
    """
    POST /api/ai/check/ - tiny test call to see if Gemini answers, with our key or
    with the visitor's own key if they sent one in X-Gemini-Key.
    """

    throttle_scope = "chat"

    def post(self, request):
        get_client_id(request)
        gemini = GeminiClient()
        started = time.monotonic()
        try:
            gemini.generate_text("Reply with the single word OK.", max_tokens=256, purpose="key check")
            ok, reason = True, ""
        except GeminiError as exc:
            ok, reason = False, exc.reason
        return Response(
            {
                "ok": ok,
                "reason": reason,
                "using_custom_key": gemini.using_custom_key,
                "duration_ms": int((time.monotonic() - started) * 1000),
            }
        )
