import re
from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from chat.models import Conversation
from diagnosis.models import Diagnosis

from .models import Booking, Mechanic, Service
from .services import MAX_DAYS_AHEAD, slot_has_passed

PHONE_RE = re.compile(r"^\+?\d{10,13}$")
REGISTRATION_RE = re.compile(r"^[A-Z0-9 -]{4,15}$")


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ["code", "name", "description", "price_min", "price_max", "duration_minutes"]


class MechanicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mechanic
        fields = ["name", "phone", "speciality", "experience_years"]


def mask_phone(phone):
    if len(phone) < 6:
        return phone
    return phone[:3] + "*" * (len(phone) - 6) + phone[-3:]


class BookingSerializer(serializers.ModelSerializer):
    service = ServiceSerializer(read_only=True)
    mechanic = MechanicSerializer(read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    time_slot_label = serializers.CharField(source="get_time_slot_display", read_only=True)
    service_mode_label = serializers.CharField(source="get_service_mode_display", read_only=True)
    conversation_id = serializers.UUIDField(read_only=True)
    diagnosis_id = serializers.IntegerField(read_only=True)
    can_cancel = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            "id", "reference", "status", "status_label", "can_cancel",
            "service", "mechanic",
            "customer_name", "phone", "email",
            "vehicle_make", "vehicle_model", "vehicle_year", "registration_number",
            "service_mode", "service_mode_label", "address",
            "scheduled_date", "time_slot", "time_slot_label", "notes",
            "conversation_id", "diagnosis_id", "created_at",
        ]

    def get_can_cancel(self, booking):
        return booking.status == Booking.Status.CONFIRMED and not slot_has_passed(booking.scheduled_date, booking.time_slot)

    def to_representation(self, booking):
        data = super().to_representation(booking)
        # the booking link is shareable, so don't show the full phone number on reads
        if self.context.get("mask_phone", True):
            data["phone"] = mask_phone(booking.phone)
        return data


class BookingSummarySerializer(serializers.ModelSerializer):
    """Small version used inside chat messages."""

    time_slot_label = serializers.CharField(source="get_time_slot_display", read_only=True)
    service_name = serializers.CharField(source="service.name", read_only=True)
    mechanic_name = serializers.CharField(source="mechanic.name", default=None, read_only=True)

    class Meta:
        model = Booking
        fields = ["id", "reference", "status", "service_name", "mechanic_name", "scheduled_date", "time_slot", "time_slot_label"]


class BookingCreateSerializer(serializers.ModelSerializer):
    service = serializers.SlugRelatedField(slug_field="code", queryset=Service.objects.filter(is_active=True))
    conversation_id = serializers.UUIDField(required=False, allow_null=True)
    diagnosis_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = Booking
        fields = [
            "service", "conversation_id", "diagnosis_id",
            "customer_name", "phone", "email",
            "vehicle_make", "vehicle_model", "vehicle_year", "registration_number",
            "service_mode", "address", "scheduled_date", "time_slot", "notes",
        ]
        extra_kwargs = {
            "email": {"required": False},
            "registration_number": {"required": False},
            "address": {"required": False},
            "notes": {"required": False},
        }

    def validate_customer_name(self, value):
        value = " ".join(value.split())
        if len(value) < 2:
            raise serializers.ValidationError("Please enter your name.")
        return value

    def validate_phone(self, value):
        cleaned = re.sub(r"[\s\-()]", "", value)
        if not PHONE_RE.match(cleaned):
            raise serializers.ValidationError("Enter a valid phone number, e.g. 9876543210.")
        return cleaned

    def validate_vehicle_year(self, value):
        if value is None:
            return value
        this_year = timezone.localdate().year
        if value < 1980 or value > this_year + 1:
            raise serializers.ValidationError(f"Year should be between 1980 and {this_year + 1}.")
        return value

    def validate_registration_number(self, value):
        value = value.strip().upper()
        if value and not REGISTRATION_RE.match(value):
            raise serializers.ValidationError("That doesn't look like a registration number (e.g. MH12AB1234).")
        return value

    def validate_scheduled_date(self, value):
        today = timezone.localdate()
        if value < today:
            raise serializers.ValidationError("The date can't be in the past.")
        if value > today + timedelta(days=MAX_DAYS_AHEAD):
            raise serializers.ValidationError(f"You can book up to {MAX_DAYS_AHEAD} days in advance.")
        if value.weekday() == 6:
            raise serializers.ValidationError("The garage is closed on Sundays, please pick another day.")
        return value

    def validate(self, attrs):
        if slot_has_passed(attrs["scheduled_date"], attrs["time_slot"]):
            raise serializers.ValidationError({"time_slot": "That slot has already started or is too soon. Pick a later one."})

        if attrs.get("service_mode") in (Booking.ServiceMode.DOORSTEP, Booking.ServiceMode.PICKUP):
            if len((attrs.get("address") or "").strip()) < 10:
                raise serializers.ValidationError({"address": "Please enter the full address so the mechanic can find you."})

        client_id = self.context["client_id"]
        conversation = None
        conversation_id = attrs.pop("conversation_id", None)
        if conversation_id:
            conversation = Conversation.objects.filter(pk=conversation_id, client_id=client_id).first()
            if conversation is None:
                raise serializers.ValidationError({"conversation_id": "Conversation not found."})
        attrs["conversation"] = conversation

        diagnosis_id = attrs.pop("diagnosis_id", None)
        diagnosis = None
        if diagnosis_id:
            diagnosis = Diagnosis.objects.filter(pk=diagnosis_id, conversation__client_id=client_id).first()
            if diagnosis is None or (conversation and diagnosis.conversation_id != conversation.pk):
                raise serializers.ValidationError({"diagnosis_id": "Diagnosis not found for this conversation."})
        attrs["diagnosis"] = diagnosis
        return attrs


class SlotQuerySerializer(serializers.Serializer):
    date = serializers.DateField()
