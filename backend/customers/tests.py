from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from chat.models import Conversation
from customers.models import MAX_CARS, Car, Customer

CLIENT_ID = "profile-client-01"


def next_weekday():
    day = timezone.localdate() + timedelta(days=2)
    return day + timedelta(days=1) if day.weekday() == 6 else day


class ProfileApiTests(TestCase):
    def setUp(self):
        self.client = APIClient(HTTP_X_CLIENT_ID=CLIENT_ID)

    def test_empty_profile(self):
        body = self.client.get("/api/profile/").json()
        self.assertEqual(body, {"name": "", "phone": "", "email": "", "city": "", "cars": []})
        self.assertFalse(Customer.objects.exists())

    def test_update_profile_and_cars(self):
        response = self.client.put("/api/profile/", {"name": "  Rahul   Verma ", "phone": "98765 43210", "city": "Pune"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Rahul Verma")
        self.assertEqual(response.json()["phone"], "9876543210")

        swift = self.client.post("/api/profile/cars/", {"make": "Maruti Suzuki", "model": "Swift", "year": 2017, "registration_number": "mh12ab1234"}, format="json").json()
        self.assertTrue(swift["is_primary"])
        self.assertEqual(swift["label"], "2017 Maruti Suzuki Swift")
        self.assertEqual(swift["registration_number"], "MH12AB1234")

        creta = self.client.post("/api/profile/cars/", {"make": "Hyundai", "model": "Creta"}, format="json").json()
        self.assertFalse(creta["is_primary"])

        self.client.patch(f"/api/profile/cars/{creta['id']}/", {"is_primary": True}, format="json")
        cars = self.client.get("/api/profile/").json()["cars"]
        self.assertEqual([car["model"] for car in cars], ["Creta", "Swift"])
        self.assertEqual([car["is_primary"] for car in cars], [True, False])

        # deleting the primary car promotes the other one
        self.assertEqual(self.client.delete(f"/api/profile/cars/{creta['id']}/").status_code, 204)
        self.assertTrue(Car.objects.get(pk=swift["id"]).is_primary)

    def test_validation(self):
        self.assertEqual(self.client.put("/api/profile/", {"phone": "123"}, format="json").status_code, 400)
        self.assertEqual(self.client.post("/api/profile/cars/", {"make": "Honda"}, format="json").status_code, 400)
        self.assertEqual(self.client.post("/api/profile/cars/", {"make": "Honda", "model": "City", "year": 1900}, format="json").status_code, 400)

    def test_car_limit(self):
        for number in range(MAX_CARS):
            self.client.post("/api/profile/cars/", {"make": "Tata", "model": f"Nexon {number}"}, format="json")
        response = self.client.post("/api/profile/cars/", {"make": "Tata", "model": "Punch"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_cannot_touch_someone_elses_car(self):
        car = self.client.post("/api/profile/cars/", {"make": "Kia", "model": "Seltos"}, format="json").json()
        other = APIClient(HTTP_X_CLIENT_ID="another-client-9")
        self.assertEqual(other.delete(f"/api/profile/cars/{car['id']}/").status_code, 404)

    def test_booking_can_save_details(self):
        response = self.client.post(
            "/api/booking/",
            {
                "service": "general-inspection",
                "customer_name": "Priya Nair",
                "phone": "9123456780",
                "vehicle_make": "Honda",
                "vehicle_model": "City",
                "vehicle_year": 2019,
                "service_mode": "garage",
                "scheduled_date": next_weekday().isoformat(),
                "time_slot": "14-16",
                "save_details": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        profile = self.client.get("/api/profile/").json()
        self.assertEqual(profile["name"], "Priya Nair")
        self.assertEqual(profile["cars"][0]["label"], "2019 Honda City")


@override_settings(GEMINI_API_KEY="")
class PersonalisedChatTests(TestCase):
    def setUp(self):
        self.client = APIClient(HTTP_X_CLIENT_ID=CLIENT_ID)
        customer = Customer.objects.create(client_id=CLIENT_ID, name="Rahul Verma")
        self.swift = Car.objects.create(customer=customer, make="Maruti Suzuki", model="Swift", year=2017, is_primary=True)

    def send(self, message, conversation_id=None):
        return self.client.post("/api/chat/", {"message": message, "conversation_id": conversation_id}, format="json").json()

    def test_greeting_uses_name_and_car(self):
        content = self.send("hello")["reply"]["content"]
        self.assertTrue(content.startswith("Hi Rahul!"))
        self.assertIn("your Swift", content)

    def test_my_car_asks_about_the_saved_car(self):
        first = self.send("my car makes a grinding noise when braking")
        self.assertEqual(first["reply"]["content"].split("\n\n")[-1], "Is this about your 2017 Maruti Suzuki Swift?")
        self.assertEqual(first["reply"]["quick_replies"], ["Yes, my Swift", "A different car"])

        second = self.send("Yes, my Swift", first["conversation"]["id"])
        self.assertEqual(second["conversation"]["vehicle"]["model"], "Swift")
        self.assertEqual(second["conversation"]["car_id"], self.swift.id)

    def test_naming_the_saved_car_skips_the_question(self):
        body = self.send("my swift's AC is blowing warm air")
        self.assertEqual(body["conversation"]["car_id"], self.swift.id)
        self.assertNotIn("Is this about your", body["reply"]["content"])

    def test_a_different_car(self):
        first = self.send("my car won't start, just clicking")
        conversation_id = first["conversation"]["id"]
        reply = self.send("A different car", conversation_id)["reply"]
        self.assertIn("Which car is it?", reply["content"])

        body = self.send("2019 Hyundai Creta, 30000 km", conversation_id)
        self.assertEqual(body["conversation"]["vehicle"]["model"], "Creta")
        self.assertIsNone(Conversation.objects.get(pk=conversation_id).car_id)
