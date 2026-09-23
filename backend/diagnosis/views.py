from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from chat.models import Conversation, Message
from chat.serializers import MessageSerializer
from chat.services import diagnose_conversation
from core.client import get_client_id

from .models import Diagnosis
from .serializers import DiagnosisRequestSerializer, DiagnosisSerializer


class DiagnosisView(APIView):
    """
    POST /api/diagnosis/ - diagnose now with whatever the customer has told us so far,
    skipping any remaining follow-up questions.

    If the conversation was already diagnosed and nothing new was said since,
    the existing diagnosis is returned (200) instead of creating another one.
    """

    throttle_scope = "chat"

    def post(self, request):
        client_id = get_client_id(request)
        serializer = DiagnosisRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        conversation = get_object_or_404(Conversation, pk=serializer.validated_data["conversation_id"], client_id=client_id)

        if not conversation.issue_category:
            raise ValidationError(
                {"conversation_id": "There's nothing to diagnose yet. Describe the problem with the car first."}
            )

        latest = conversation.diagnoses.first()
        if latest and conversation.stage != Conversation.Stage.GATHERING:
            said_more = conversation.messages.filter(role=Message.Role.USER, created_at__gt=latest.created_at).exists()
            if not said_more:
                message = conversation.messages.filter(diagnosis=latest).first()
                return Response(self._payload(latest, message, request), status=status.HTTP_200_OK)

        message = diagnose_conversation(conversation)
        return Response(self._payload(message.diagnosis, message, request), status=status.HTTP_201_CREATED)

    @staticmethod
    def _payload(diagnosis, message, request):
        return {
            "diagnosis": DiagnosisSerializer(diagnosis).data,
            "message": MessageSerializer(message, context={"request": request}).data if message else None,
        }


class DiagnosisDetailView(APIView):
    """GET /api/diagnosis/{id}/"""

    def get(self, request, pk):
        diagnosis = get_object_or_404(
            Diagnosis.objects.select_related("recommended_service"),
            pk=pk,
            conversation__client_id=get_client_id(request),
        )
        return Response(DiagnosisSerializer(diagnosis).data)
