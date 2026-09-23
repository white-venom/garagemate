import uuid

from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from core.client import get_client_id

from .models import Attachment, Conversation
from .serializers import (
    AttachmentSerializer,
    ChatRequestSerializer,
    ConversationDetailSerializer,
    ConversationSerializer,
    MessageSerializer,
)
from .services import conversation_with_messages, conversations_for_client, handle_user_message
from .uploads import inspect_upload

MAX_CONVERSATIONS_LISTED = 50


class ChatView(APIView):
    """POST /api/chat/ - send a message (and optionally uploaded attachments) to the mechanic bot."""

    throttle_scope = "chat"

    def post(self, request):
        client_id = get_client_id(request)
        serializer = ChatRequestSerializer(data=request.data, context={"client_id": client_id})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        conversation = data["conversation"] or Conversation.objects.create(client_id=client_id)
        user_message, reply = handle_user_message(conversation, data["message"], data["attachments"])
        # same field the history list gets from its annotation
        conversation.last_message = reply.content

        context = {"request": request}
        return Response(
            {
                "conversation": ConversationSerializer(conversation, context=context).data,
                "user_message": MessageSerializer(user_message, context=context).data,
                "reply": MessageSerializer(reply, context=context).data,
            },
            status=status.HTTP_201_CREATED,
        )


class UploadView(APIView):
    """POST /api/upload/ - upload a photo, audio clip or video. Send the returned id with the next chat message."""

    parser_classes = [MultiPartParser, FormParser]
    throttle_scope = "upload"

    def post(self, request):
        client_id = get_client_id(request)
        uploaded = request.FILES.get("file")
        if uploaded is None:
            raise ValidationError({"file": "No file was sent. Use multipart/form-data with a 'file' field."})

        conversation = None
        conversation_id = request.data.get("conversation_id")
        if conversation_id:
            try:
                conversation_id = uuid.UUID(str(conversation_id))
            except ValueError:
                raise ValidationError({"conversation_id": "Must be a valid UUID."})
            conversation = Conversation.objects.filter(pk=conversation_id, client_id=client_id).first()
            if conversation is None:
                raise NotFound("Conversation not found.")

        kind, mime_type, checksum = inspect_upload(uploaded)
        attachment = Attachment.objects.create(
            client_id=client_id,
            conversation=conversation,
            file=uploaded,
            kind=kind,
            mime_type=mime_type,
            size_bytes=uploaded.size,
            original_name=(uploaded.name or "")[:255],
            checksum=checksum,
        )
        return Response(AttachmentSerializer(attachment, context={"request": request}).data, status=status.HTTP_201_CREATED)


class ConversationListView(APIView):
    """GET /api/conversations/ - chat history for this browser, newest first."""

    def get(self, request):
        client_id = get_client_id(request)
        conversations = conversations_for_client(client_id)[:MAX_CONVERSATIONS_LISTED]
        return Response({"results": ConversationSerializer(conversations, many=True).data})


class ConversationDetailView(APIView):
    """GET / DELETE /api/conversations/{id}/"""

    def get(self, request, pk):
        conversation = conversation_with_messages(get_client_id(request), pk)
        if conversation is None:
            raise NotFound("Conversation not found.")
        return Response(ConversationDetailSerializer(conversation, context={"request": request}).data)

    def delete(self, request, pk):
        deleted, _ = Conversation.objects.filter(pk=pk, client_id=get_client_id(request)).delete()
        if not deleted:
            raise NotFound("Conversation not found.")
        return Response(status=status.HTTP_204_NO_CONTENT)
