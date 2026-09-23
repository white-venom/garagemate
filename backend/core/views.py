from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response


@api_view(["GET"])
@throttle_classes([])
def api_index(request):
    return Response(
        {
            "name": "GarageMate API",
            "docs": "see docs/API.md in the repository",
            "endpoints": {
                "chat": "POST /api/chat/",
                "upload": "POST /api/upload/",
                "diagnosis": "POST /api/diagnosis/, GET /api/diagnosis/{id}/",
                "booking": "POST /api/booking/, GET /api/booking/{id}/, POST /api/booking/{id}/cancel/",
                "slots": "GET /api/booking/slots/?date=YYYY-MM-DD",
                "services": "GET /api/services/",
                "conversations": "GET /api/conversations/, GET|DELETE /api/conversations/{id}/",
                "health": "GET /api/health/",
            },
        }
    )


@api_view(["GET"])
@throttle_classes([])
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        database = "ok"
    except Exception:
        database = "error"

    return Response(
        {
            "status": "ok" if database == "ok" else "degraded",
            "database": database,
            "ai_enabled": bool(settings.GEMINI_API_KEY),
        },
        status=200 if database == "ok" else 503,
    )


def not_found(request, exception=None):
    return JsonResponse({"error": {"code": "not_found", "message": "This endpoint does not exist."}}, status=404)


def server_error(request):
    return JsonResponse(
        {"error": {"code": "server_error", "message": "Something went wrong on our side. Please try again."}},
        status=500,
    )
