from rest_framework import serializers
from rest_framework.exceptions import NotFound

from bookings.serializers import BookingSummarySerializer
from diagnosis.serializers import DiagnosisSerializer

from .models import Attachment, Conversation, Message

MAX_ATTACHMENTS_PER_MESSAGE = 4


class AttachmentSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = Attachment
        fields = ["id", "kind", "mime_type", "size_bytes", "original_name", "url", "created_at"]

    def get_url(self, attachment):
        request = self.context.get("request")
        url = attachment.file.url
        return request.build_absolute_uri(url) if request else url


class MessageSerializer(serializers.ModelSerializer):
    attachments = AttachmentSerializer(many=True, read_only=True)
    diagnosis = DiagnosisSerializer(read_only=True)
    booking = BookingSummarySerializer(read_only=True)

    class Meta:
        model = Message
        fields = [
            "id", "role", "kind", "content", "quick_replies", "action", "attachments", "diagnosis", "booking",
            "used_ai", "ai_error", "created_at",
        ]


class VehicleSerializer(serializers.Serializer):
    make = serializers.CharField(source="vehicle_make")
    model = serializers.CharField(source="vehicle_model")
    year = serializers.IntegerField(source="vehicle_year", allow_null=True)
    odometer_km = serializers.IntegerField(allow_null=True)
    fuel_type = serializers.CharField()


class ConversationSerializer(serializers.ModelSerializer):
    vehicle = VehicleSerializer(source="*", read_only=True)
    latest_diagnosis = serializers.SerializerMethodField()
    last_message = serializers.CharField(read_only=True, default="")

    class Meta:
        model = Conversation
        fields = [
            "id", "title", "stage", "issue_category", "vehicle", "car_id", "latest_diagnosis", "last_message",
            "created_at", "updated_at",
        ]

    def get_latest_diagnosis(self, conversation):
        # uses the prefetched list when there is one (conversation list), otherwise one query
        diagnoses = getattr(conversation, "prefetched_diagnoses", None)
        diagnosis = diagnoses[0] if diagnoses else (None if diagnoses is not None else conversation.diagnoses.first())
        if diagnosis is None:
            return None
        return {"id": diagnosis.id, "title": diagnosis.title, "severity": diagnosis.severity}


class ConversationDetailSerializer(ConversationSerializer):
    messages = MessageSerializer(many=True, read_only=True)

    class Meta(ConversationSerializer.Meta):
        fields = ConversationSerializer.Meta.fields + ["messages"]


class ChatRequestSerializer(serializers.Serializer):
    conversation_id = serializers.UUIDField(required=False, allow_null=True)
    message = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")
    attachment_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, default=list, max_length=MAX_ATTACHMENTS_PER_MESSAGE
    )

    def validate(self, attrs):
        client_id = self.context["client_id"]
        attrs["message"] = attrs["message"].strip()

        conversation = None
        if attrs.get("conversation_id"):
            conversation = Conversation.objects.filter(pk=attrs["conversation_id"], client_id=client_id).first()
            if conversation is None:
                raise NotFound("Conversation not found.")
        attrs["conversation"] = conversation

        ids = list(dict.fromkeys(attrs["attachment_ids"]))
        attachments = list(Attachment.objects.filter(pk__in=ids, client_id=client_id, message__isnull=True))
        if len(attachments) != len(ids):
            raise serializers.ValidationError({"attachment_ids": "Some attachments were not found or were already sent."})
        if conversation and any(a.conversation_id not in (None, conversation.pk) for a in attachments):
            raise serializers.ValidationError({"attachment_ids": "Attachments belong to a different conversation."})
        attrs["attachments"] = attachments

        if not attrs["message"] and not attachments:
            raise serializers.ValidationError({"message": "Type a message or attach a file."})
        return attrs
