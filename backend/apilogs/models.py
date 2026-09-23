from django.db import models


class RequestLog(models.Model):
    """
    One row per /api/ request, shown in the "API logs" panel of the frontend.
    Only metadata is stored, never request bodies (they can contain phone numbers).
    """

    client_id = models.CharField(max_length=64, blank=True, db_index=True)
    method = models.CharField(max_length=8)
    path = models.CharField(max_length=255)
    status_code = models.PositiveSmallIntegerField()
    duration_ms = models.PositiveIntegerField()
    # error.message from our error format, for 4xx / 5xx responses
    error = models.CharField(max_length=255, blank=True)
    # every Gemini call made while handling the request:
    # [{"purpose", "model", "ok", "reason", "message", "duration_ms", "custom_key"}]
    ai_calls = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["client_id", "-created_at"])]

    def __str__(self):
        return f"{self.method} {self.path} {self.status_code}"
