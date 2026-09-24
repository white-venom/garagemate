from rest_framework import serializers

from bookings.serializers import ServiceSerializer

from .knowledge_base import ISSUE_TYPES_BY_KEY
from .models import Diagnosis


class DiagnosisSerializer(serializers.ModelSerializer):
    recommended_service = ServiceSerializer(read_only=True)
    category_label = serializers.SerializerMethodField()
    severity_label = serializers.CharField(source="get_severity_display", read_only=True)
    conversation_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = Diagnosis
        fields = [
            "id", "conversation_id", "category", "category_label", "title", "summary", "probable_causes",
            "severity", "severity_label", "safe_to_drive", "advice", "recommended_service",
            "estimated_cost_min", "estimated_cost_max", "source", "research", "localized", "created_at",
        ]

    def get_category_label(self, diagnosis):
        issue = ISSUE_TYPES_BY_KEY.get(diagnosis.category)
        return issue.label if issue else diagnosis.category


class DiagnosisRequestSerializer(serializers.Serializer):
    conversation_id = serializers.UUIDField()
