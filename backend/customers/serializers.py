import re

from django.utils import timezone
from rest_framework import serializers

from .models import MAX_CARS, Car, Customer

PHONE_RE = re.compile(r"^\+?\d{10,13}$")
REGISTRATION_RE = re.compile(r"^[A-Z0-9 -]{4,15}$")


def clean_phone(value):
    cleaned = re.sub(r"[\s\-()]", "", value or "")
    if cleaned and not PHONE_RE.match(cleaned):
        raise serializers.ValidationError("Enter a valid phone number, e.g. 9876543210.")
    return cleaned


def clean_registration(value):
    value = (value or "").strip().upper()
    if value and not REGISTRATION_RE.match(value):
        raise serializers.ValidationError("That doesn't look like a registration number (e.g. MH12AB1234).")
    return value


class CarSerializer(serializers.ModelSerializer):
    label = serializers.CharField(read_only=True)

    class Meta:
        model = Car
        fields = [
            "id", "make", "model", "year", "fuel_type", "odometer_km", "registration_number", "is_primary",
            "label", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate_make(self, value):
        return " ".join(value.split())

    def validate_model(self, value):
        return " ".join(value.split())

    def validate_year(self, value):
        if value is not None and not 1980 <= value <= timezone.localdate().year + 1:
            raise serializers.ValidationError("Year should be between 1980 and next year.")
        return value

    def validate_registration_number(self, value):
        return clean_registration(value)

    def validate(self, attrs):
        customer = self.context.get("customer")
        if self.instance is None and customer and customer.cars.count() >= MAX_CARS:
            raise serializers.ValidationError(f"You can save up to {MAX_CARS} cars.")
        return attrs


class ProfileSerializer(serializers.ModelSerializer):
    cars = CarSerializer(many=True, read_only=True)

    class Meta:
        model = Customer
        fields = ["name", "phone", "email", "city", "cars"]

    def validate_name(self, value):
        return " ".join(value.split())

    def validate_phone(self, value):
        return clean_phone(value)
