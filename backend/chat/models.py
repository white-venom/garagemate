import uuid
from pathlib import Path

from django.db import models
from django.utils import timezone


class Conversation(models.Model):
    class Stage(models.TextChoices):
        NEW = "new", "New"
        GATHERING = "gathering", "Asking follow-up questions"
        DIAGNOSED = "diagnosed", "Diagnosed"
        BOOKED = "booked", "Mechanic booked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # there are no user accounts, the browser generates a random id and keeps it in localStorage
    client_id = models.CharField(max_length=64, db_index=True)
    title = models.CharField(max_length=120, blank=True)
    stage = models.CharField(max_length=12, choices=Stage.choices, default=Stage.NEW)
    issue_category = models.CharField(max_length=40, blank=True)

    vehicle_make = models.CharField(max_length=40, blank=True)
    vehicle_model = models.CharField(max_length=60, blank=True)
    vehicle_year = models.PositiveSmallIntegerField(null=True, blank=True)
    odometer_km = models.PositiveIntegerField(null=True, blank=True)
    fuel_type = models.CharField(max_length=12, blank=True)
    # set when the customer confirmed it's one of the cars saved in their profile
    car = models.ForeignKey(
        "customers.Car", on_delete=models.SET_NULL, null=True, blank=True, related_name="conversations"
    )

    # where we are in the follow-up questions for the current issue
    # {"description": "...", "answers": {...}, "pending": "noise", "media_notes": [...]}
    state = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [models.Index(fields=["client_id", "-updated_at"])]

    def __str__(self):
        return self.title or f"Conversation {self.id}"

    @property
    def vehicle_label(self):
        parts = [str(self.vehicle_year or ""), self.vehicle_make, self.vehicle_model]
        return " ".join(part for part in parts if part)


class Message(models.Model):
    class Role(models.TextChoices):
        USER = "user", "Customer"
        ASSISTANT = "assistant", "Mechanic bot"

    class Kind(models.TextChoices):
        TEXT = "text", "Text"
        QUESTION = "question", "Follow-up question"
        DIAGNOSIS = "diagnosis", "Diagnosis"
        REJECTION = "rejection", "Off-topic rejection"
        BOOKING_PROMPT = "booking_prompt", "Booking prompt"
        BOOKING_CONFIRMED = "booking_confirmed", "Booking confirmed"
        ERROR = "error", "Error"

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=Role.choices)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.TEXT)
    content = models.TextField(blank=True)
    quick_replies = models.JSONField(default=list, blank=True)
    # tells the frontend to do something, e.g. "open_booking" opens the booking form
    action = models.CharField(max_length=30, blank=True)
    diagnosis = models.ForeignKey(
        "diagnosis.Diagnosis", on_delete=models.SET_NULL, null=True, blank=True, related_name="messages"
    )
    booking = models.ForeignKey(
        "bookings.Booking", on_delete=models.SET_NULL, null=True, blank=True, related_name="messages"
    )
    used_ai = models.BooleanField(default=False)
    # set when Gemini was needed but failed (quota, overloaded...) and the rules answered instead
    ai_error = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.role}: {self.content[:50]}"


def attachment_upload_path(instance, filename):
    extension = Path(filename).suffix.lower()[:10]
    return f"uploads/{timezone.now():%Y/%m}/{uuid.uuid4().hex}{extension}"


class Attachment(models.Model):
    class Kind(models.TextChoices):
        IMAGE = "image", "Image"
        AUDIO = "audio", "Audio"
        VIDEO = "video", "Video"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client_id = models.CharField(max_length=64, db_index=True)
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, null=True, blank=True, related_name="attachments"
    )
    # stays empty until the file is actually sent with a chat message
    message = models.ForeignKey(Message, on_delete=models.CASCADE, null=True, blank=True, related_name="attachments")
    file = models.FileField(upload_to=attachment_upload_path)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    mime_type = models.CharField(max_length=100)
    size_bytes = models.PositiveIntegerField()
    original_name = models.CharField(max_length=255, blank=True)
    checksum = models.CharField(max_length=64, db_index=True, help_text="sha256 of the file")
    # what Gemini made of the file: {"car_related": bool, "observations": str, "system": str}
    analysis = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.kind}: {self.original_name or self.file.name}"
