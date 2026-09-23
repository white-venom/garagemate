from django.contrib import admin

from .models import RequestLog


@admin.register(RequestLog)
class RequestLogAdmin(admin.ModelAdmin):
    list_display = ["created_at", "method", "path", "status_code", "duration_ms", "ai_call_count", "client_id"]
    list_filter = ["method", "status_code"]
    search_fields = ["path", "client_id", "error"]
    readonly_fields = [field.name for field in RequestLog._meta.fields]

    @admin.display(description="gemini calls")
    def ai_call_count(self, log):
        return len(log.ai_calls)

    def has_add_permission(self, request):
        return False
