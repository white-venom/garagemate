from datetime import datetime, timedelta
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from bookings.models import Booking, Mechanic
from bookings.services import slot_has_passed
from chat.models import Conversation, Message

CLIENT_ID = "booking-client-1"


def next_weekday(days_ahead=2):
    day = timezone.localdate() + timedelta(days=days_ahead)
    while day.weekday() == 6:
        day += timedelta(days=1)
    return day


def next_sunday():
    day = timezone.localdate() + timedelta(days=1)
    while day.weekday() != 6:
        day += timedelta(days=1)
    return day


@override_settings(GEMINI_API_KEY="")
class BookingApiTests(TestCase):
    def setUp(self):
        self.client = APIClient(HTTP_X_CLIENT_ID=CLIENT_ID)
        self.day = next_weekday()

    def payload(self, **overrides):
        data = {
            "service": "brake-service",
            "customer_name": "Rahul Verma",
            "phone": "98765 43210",
            "email": "rahul@example.com",
            "vehicle_make": "Maruti Suzuki",
            "vehicle_model": "Swift",
            "vehicle_year": 2017,
            "registration_number": "mh12ab1234",
            "service_mode": "garage",
            "scheduled_date": self.day.isoformat(),
            "time_slot": "09-11",
        }
        data.update(overrides)
        return data

    def book(self, **overrides):
        return self.client.post("/api/booking/", self.payload(**overrides), format="json")

    def test_create_and_fetch_booking(self):
        response = self.book()
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertTrue(body["reference"].startswith("GM-"))
        self.assertEqual(body["status"], "confirmed")
        self.assertIsNotNone(body["mechanic"])
        self.assertEqual(body["phone"], "9876543210")
        self.assertEqual(body["registration_number"], "MH12AB1234")

        detail = self.client.get(f"/api/booking/{body['id']}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["reference"], body["reference"])
        # phone is masked when reading the booking back
        self.assertNotEqual(detail.json()["phone"], "9876543210")

    def test_unknown_booking(self):
        response = self.client.get("/api/booking/7d8f6f5e-1a2b-4c3d-8e9f-0a1b2c3d4e5f/")
        self.assertEqual(response.status_code, 404)

    def test_validation_errors(self):
        cases = [
            ({"phone": "12345"}, "phone"),
            ({"scheduled_date": (timezone.localdate() - timedelta(days=1)).isoformat()}, "scheduled_date"),
            ({"scheduled_date": next_sunday().isoformat()}, "scheduled_date"),
            ({"scheduled_date": (timezone.localdate() + timedelta(days=60)).isoformat()}, "scheduled_date"),
            ({"service": "does-not-exist"}, "service"),
            ({"time_slot": "03-05"}, "time_slot"),
            ({"service_mode": "doorstep", "address": ""}, "address"),
            ({"vehicle_year": 1950}, "vehicle_year"),
            ({"customer_name": ""}, "customer_name"),
        ]
        for overrides, field in cases:
            response = self.book(**overrides)
            self.assertEqual(response.status_code, 400, overrides)
            self.assertIn(field, response.json()["error"]["fields"], overrides)

    def test_mechanics_are_spread_and_slot_fills_up(self):
        mechanic_count = Mechanic.objects.filter(is_active=True).count()
        assigned = set()
        for _ in range(mechanic_count):
            response = self.book()
            self.assertEqual(response.status_code, 201)
            assigned.add(response.json()["mechanic"]["name"])
        self.assertEqual(len(assigned), mechanic_count)

        full = self.book()
        self.assertEqual(full.status_code, 409)
        self.assertEqual(full.json()["error"]["code"], "conflict")

        slots = self.client.get(f"/api/booking/slots/?date={self.day.isoformat()}").json()["slots"]
        morning = next(slot for slot in slots if slot["value"] == "09-11")
        self.assertFalse(morning["available"])
        self.assertEqual(morning["remaining"], 0)

    def test_cancel_frees_the_slot(self):
        for _ in range(Mechanic.objects.filter(is_active=True).count()):
            booking_id = self.book().json()["id"]

        cancel = self.client.post(f"/api/booking/{booking_id}/cancel/")
        self.assertEqual(cancel.status_code, 200)
        self.assertEqual(cancel.json()["status"], "cancelled")
        self.assertEqual(self.client.post(f"/api/booking/{booking_id}/cancel/").status_code, 409)

        self.assertEqual(self.book().status_code, 201)

    def test_booking_from_conversation_posts_confirmation(self):
        chat = self.client.post("/api/chat/", {"message": "brakes are squealing"}, format="json").json()
        conversation_id = chat["conversation"]["id"]
        diagnosis = self.client.post("/api/diagnosis/", {"conversation_id": conversation_id}, format="json").json()

        response = self.book(conversation_id=conversation_id, diagnosis_id=diagnosis["diagnosis"]["id"])
        self.assertEqual(response.status_code, 201)

        conversation = Conversation.objects.get(pk=conversation_id)
        self.assertEqual(conversation.stage, Conversation.Stage.BOOKED)
        confirmation = conversation.messages.last()
        self.assertEqual(confirmation.kind, Message.Kind.BOOKING_CONFIRMED)
        self.assertIn(response.json()["reference"], confirmation.content)

    def test_cannot_book_on_someone_elses_conversation(self):
        conversation = Conversation.objects.create(client_id="not-me-at-all")
        response = self.book(conversation_id=str(conversation.pk))
        self.assertEqual(response.status_code, 400)
        self.assertIn("conversation_id", response.json()["error"]["fields"])

    def test_services_list(self):
        services = self.client.get("/api/services/").json()["results"]
        self.assertTrue(any(service["code"] == "periodic-service" for service in services))


class SlotTimingTests(TestCase):
    def test_slot_has_passed(self):
        today = timezone.localdate()
        ten_am = timezone.make_aware(datetime.combine(today, datetime.min.time()).replace(hour=10))
        with mock.patch("django.utils.timezone.now", return_value=ten_am):
            self.assertTrue(slot_has_passed(today, "09-11"))
            self.assertTrue(slot_has_passed(today, "11-13"))  # less than an hour away
            self.assertFalse(slot_has_passed(today, "14-16"))
            self.assertFalse(slot_has_passed(today + timedelta(days=1), "09-11"))
            self.assertTrue(slot_has_passed(today - timedelta(days=1), "16-18"))


class ReferenceTests(TestCase):
    def test_reference_format(self):
        from bookings.models import generate_reference

        reference = generate_reference()
        self.assertRegex(reference, r"^GM-[A-Z2-9]{6}$")
        self.assertNotRegex(reference[3:], r"[01IO]")
        self.assertTrue(Booking._meta.get_field("reference").unique)
