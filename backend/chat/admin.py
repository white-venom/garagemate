from django.contrib import admin

from .models import Attachment, Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    fields = ["role", "kind", "content", "used_ai", "created_at"]
    readonly_fields = fields
    show_change_link = True


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ["title", "stage", "issue_category", "vehicle_label", "client_id", "updated_at"]
    list_filter = ["stage", "issue_category"]
    search_fields = ["title", "client_id", "vehicle_make", "vehicle_model"]
    readonly_fields = ["id", "created_at", "updated_at"]
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ["conversation", "role", "kind", "short_content", "used_ai", "created_at"]
    list_filter = ["role", "kind", "used_ai"]
    search_fields = ["content"]
    raw_id_fields = ["conversation", "diagnosis", "booking"]

    @admin.display(description="content")
    def short_content(self, message):
        return message.content[:80]


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ["original_name", "kind", "mime_type", "size_bytes", "conversation", "created_at"]
    list_filter = ["kind"]
    readonly_fields = ["checksum", "analysis", "created_at"]
    raw_id_fields = ["conversation", "message"]
