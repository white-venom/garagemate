import secrets
import uuid

from django.db import models
from django.db.models import Q

# no 0/O/1/I so references are easy to read out over the phone
REFERENCE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_reference():
    return "GM-" + "".join(secrets.choice(REFERENCE_ALPHABET) for _ in range(6))


class Service(models.Model):
    """Services the garage offers. Seeded by a data migration, editable in admin."""

    code = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price_min = models.PositiveIntegerField(help_text="Rough starting price in INR")
    price_max = models.PositiveIntegerField(help_text="Rough upper price in INR")
    duration_minutes = models.PositiveSmallIntegerField(default=60)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Mechanic(models.Model):
    name = models.CharField(max_length=80)
    phone = models.CharField(max_length=20)
    speciality = models.CharField(max_length=100, blank=True)
    experience_years = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Booking(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = "confirmed", "Confirmed"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    class TimeSlot(models.TextChoices):
        SLOT_9_11 = "09-11", "9:00 AM - 11:00 AM"
        SLOT_11_13 = "11-13", "11:00 AM - 1:00 PM"
        SLOT_14_16 = "14-16", "2:00 PM - 4:00 PM"
        SLOT_16_18 = "16-18", "4:00 PM - 6:00 PM"

    class ServiceMode(models.TextChoices):
        GARAGE = "garage", "Garage visit"
        DOORSTEP = "doorstep", "Doorstep service"
        PICKUP = "pickup", "Pickup and drop"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=12, unique=True, editable=False)

    conversation = models.ForeignKey(
        "chat.Conversation", on_delete=models.SET_NULL, null=True, blank=True, related_name="bookings"
    )
    diagnosis = models.ForeignKey(
        "diagnosis.Diagnosis", on_delete=models.SET_NULL, null=True, blank=True, related_name="bookings"
    )
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="bookings")
    mechanic = models.ForeignKey(Mechanic, on_delete=models.PROTECT, null=True, blank=True, related_name="bookings")

    customer_name = models.CharField(max_length=80)
    phone = models.CharField(max_length=16)
    email = models.EmailField(blank=True)

    vehicle_make = models.CharField(max_length=40)
    vehicle_model = models.CharField(max_length=60)
    vehicle_year = models.PositiveSmallIntegerField(null=True, blank=True)
    registration_number = models.CharField(max_length=15, blank=True)

    service_mode = models.CharField(max_length=10, choices=ServiceMode.choices, default=ServiceMode.GARAGE)
    address = models.TextField(blank=True)
    scheduled_date = models.DateField()
    time_slot = models.CharField(max_length=5, choices=TimeSlot.choices)
    notes = models.TextField(blank=True)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.CONFIRMED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["scheduled_date", "time_slot"])]
        constraints = [
            # a mechanic can only be in one place per slot (cancelled ones don't count)
            models.UniqueConstraint(
                fields=["mechanic", "scheduled_date", "time_slot"],
                condition=~Q(status="cancelled"),
                name="one_active_booking_per_mechanic_slot",
            ),
        ]

    def __str__(self):
        return f"{self.reference} - {self.customer_name} ({self.scheduled_date} {self.time_slot})"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = generate_reference()
            while Booking.objects.filter(reference=self.reference).exists():
                self.reference = generate_reference()
        super().save(*args, **kwargs)

    @property
    def slot_start_hour(self):
        return int(self.time_slot.split("-")[0])
