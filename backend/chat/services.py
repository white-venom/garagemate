import logging

from django.db.models import OuterRef, Prefetch, Subquery

from diagnosis.models import Diagnosis

from .bot import BotReply, MechanicBot, replies
from .models import Attachment, Conversation, Message

logger = logging.getLogger(__name__)

TITLE_LENGTH = 60


def _short_title(text):
    text = " ".join(text.split())
    if len(text) <= TITLE_LENGTH:
        return text
    return text[:TITLE_LENGTH].rsplit(" ", 1)[0] + "..."


def _save_reply(conversation, reply):
    return Message.objects.create(
        conversation=conversation,
        role=Message.Role.ASSISTANT,
        kind=reply.kind,
        content=reply.content,
        quick_replies=reply.quick_replies,
        action=reply.action,
        diagnosis=reply.diagnosis,
        used_ai=reply.used_ai,
        ai_error=reply.ai_error,
    )


def handle_user_message(conversation, text, attachments=()):
    """Save the customer's message, run the bot and save its reply. Returns both messages."""
    user_message = Message.objects.create(conversation=conversation, role=Message.Role.USER, content=text)
    if attachments:
        Attachment.objects.filter(pk__in=[a.pk for a in attachments]).update(
            message=user_message, conversation=conversation
        )
        for attachment in attachments:
            attachment.message = user_message
            attachment.conversation = conversation

    try:
        reply = MechanicBot(conversation).reply(text, attachments)
    except Exception:
        # don't leave the customer hanging without an answer
        logger.exception("Bot failed on conversation %s", conversation.pk)
        conversation.refresh_from_db()
        reply = BotReply(replies.SOMETHING_WENT_WRONG, kind=Message.Kind.ERROR)

    assistant_message = _save_reply(conversation, reply)

    if not conversation.title:
        # "hi" or an off-topic question makes a useless title, the bot renames it once it knows the problem
        useful = len(text.split()) >= 3 and reply.kind != Message.Kind.REJECTION
        conversation.title = _short_title(text) if useful else "New conversation"
    conversation.save(update_fields=["title", "updated_at"])
    return user_message, assistant_message


def diagnose_conversation(conversation):
    """Diagnose straight away with whatever we know. Returns the new assistant message."""
    reply = MechanicBot(conversation).diagnose_now()
    return _save_reply(conversation, reply)


def record_booking(conversation, booking):
    """Called after a booking is created from a conversation, so it shows up in the chat."""
    mechanic = f" {booking.mechanic.name} will be your mechanic." if booking.mechanic else ""
    content = (
        f"Booking confirmed! Your reference is **{booking.reference}**.\n\n"
        f"{booking.service.name} on {booking.scheduled_date:%A, %d %B} between {booking.get_time_slot_display()}."
        f"{mechanic} We'll call you on the number you gave us before the visit."
    )
    message = Message.objects.create(
        conversation=conversation,
        role=Message.Role.ASSISTANT,
        kind=Message.Kind.BOOKING_CONFIRMED,
        content=content,
        booking=booking,
    )
    conversation.stage = Conversation.Stage.BOOKED
    conversation.save(update_fields=["stage", "updated_at"])
    return message


def conversations_for_client(client_id):
    last_message = Message.objects.filter(conversation=OuterRef("pk")).order_by("-created_at", "-id").values("content")[:1]
    return (
        Conversation.objects.filter(client_id=client_id)
        .annotate(last_message=Subquery(last_message))
        .prefetch_related(
            Prefetch("diagnoses", queryset=Diagnosis.objects.order_by("-created_at"), to_attr="prefetched_diagnoses")
        )
    )


def conversation_with_messages(client_id, conversation_id):
    messages = Message.objects.select_related(
        "diagnosis__recommended_service", "booking__service", "booking__mechanic"
    ).prefetch_related("attachments")
    return (
        Conversation.objects.filter(client_id=client_id, pk=conversation_id)
        .prefetch_related(
            Prefetch("messages", queryset=messages),
            Prefetch("diagnoses", queryset=Diagnosis.objects.order_by("-created_at"), to_attr="prefetched_diagnoses"),
        )
        .first()
    )
