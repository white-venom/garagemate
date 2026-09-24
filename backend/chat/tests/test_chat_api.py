from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from chat.models import Conversation, Message

CLIENT_ID = "test-client-0001"


class FakeGemini:
    enabled = True
    last_failure = None

    def __init__(self, text="", data=None, sources=None):
        self.text = text
        self.data = data or {}
        self.sources = sources or []
        self.calls = 0

    def generate_text(self, *args, **kwargs):
        self.calls += 1
        return self.text

    def generate_json(self, *args, **kwargs):
        self.calls += 1
        return self.data

    def research(self, *args, **kwargs):
        self.calls += 1
        return {"text": self.text, "sources": self.sources, "queries": []}


@override_settings(GEMINI_API_KEY="")
class ChatApiTests(TestCase):
    def setUp(self):
        self.client = APIClient(HTTP_X_CLIENT_ID=CLIENT_ID)

    def send(self, message, conversation_id=None):
        payload = {"message": message}
        if conversation_id:
            payload["conversation_id"] = conversation_id
        return self.client.post("/api/chat/", payload, format="json")

    def test_client_id_is_required(self):
        response = APIClient().post("/api/chat/", {"message": "hi"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "validation_error")

    def test_empty_message_is_rejected(self):
        response = self.send("   ")
        self.assertEqual(response.status_code, 400)
        self.assertIn("message", response.json()["error"]["fields"])

    def test_greeting_creates_conversation(self):
        response = self.send("hi")
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["user_message"]["role"], "user")
        self.assertEqual(body["reply"]["role"], "assistant")
        self.assertTrue(body["reply"]["quick_replies"])
        self.assertTrue(Conversation.objects.filter(pk=body["conversation"]["id"], client_id=CLIENT_ID).exists())

    def test_off_topic_is_rejected_without_ai(self):
        reply = self.send("Can you write me a poem about the moon?").json()["reply"]
        self.assertEqual(reply["kind"], "rejection")
        self.assertFalse(reply["used_ai"])

    def test_full_brake_flow_ends_in_diagnosis(self):
        first = self.send("My brakes make a grinding noise when I stop").json()
        conversation_id = first["conversation"]["id"]
        self.assertEqual(first["reply"]["kind"], "question")
        self.assertEqual(first["conversation"]["issue_category"], "brakes")

        # answer whatever gets asked, the order of questions can change as the knowledge base grows
        answers = {
            "Which car": "2016 Honda City, 70000 km",
            "pedal": "Feels normal",
            "pull to one side": "Neither",
            "brake pads last changed": "More than 2 years ago / never",
            "first notice": "In the last few days",
        }
        reply = first["reply"]
        for _ in range(8):
            if reply["kind"] != "question":
                break
            answer = next((text for hint, text in answers.items() if hint in reply["content"]), reply["quick_replies"][-1])
            reply = self.send(answer, conversation_id).json()["reply"]

        self.assertEqual(reply["kind"], "diagnosis")
        diagnosis = reply["diagnosis"]
        self.assertIn("metal", diagnosis["title"].lower())
        self.assertEqual(diagnosis["severity"], "high")
        self.assertFalse(diagnosis["safe_to_drive"])
        self.assertEqual(diagnosis["recommended_service"]["code"], "brake-service")
        self.assertEqual(diagnosis["source"], "rules")

        conversation = Conversation.objects.get(pk=conversation_id)
        self.assertEqual(conversation.stage, Conversation.Stage.DIAGNOSED)
        self.assertEqual(conversation.vehicle_make, "Honda")
        self.assertEqual(conversation.vehicle_year, 2016)

        booking_reply = self.send("yes, book a mechanic", conversation_id).json()["reply"]
        self.assertEqual(booking_reply["action"], "open_booking")

    def test_vague_noise_gets_triage_question(self):
        first = self.send("my car is making a strange noise").json()
        self.assertEqual(first["reply"]["kind"], "question")
        self.assertIn("When braking", first["reply"]["quick_replies"])

        second = self.send("When braking", first["conversation"]["id"]).json()
        self.assertEqual(second["conversation"]["issue_category"], "brakes")

    def test_off_topic_mid_flow_repeats_the_question(self):
        first = self.send("AC is not cooling").json()
        reply = self.send("tell me a joke", first["conversation"]["id"]).json()["reply"]
        self.assertEqual(reply["kind"], "rejection")
        self.assertIn("Coming back to your car", reply["content"])

    def test_safety_alert_for_fuel_smell(self):
        reply = self.send("there is a strong petrol smell near the car").json()["reply"]
        self.assertIn("fire risk", reply["content"])

    def test_other_clients_cannot_see_conversation(self):
        conversation_id = self.send("hi").json()["conversation"]["id"]
        other = APIClient(HTTP_X_CLIENT_ID="someone-else-99")
        self.assertEqual(other.get(f"/api/conversations/{conversation_id}/").status_code, 404)
        response = other.post("/api/chat/", {"message": "hi", "conversation_id": conversation_id}, format="json")
        self.assertEqual(response.status_code, 404)

    def test_history_list_and_delete(self):
        conversation_id = self.send("my clutch is slipping").json()["conversation"]["id"]
        history = self.client.get("/api/conversations/").json()["results"]
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["issue_category"], "transmission")
        self.assertTrue(history[0]["last_message"])

        detail = self.client.get(f"/api/conversations/{conversation_id}/").json()
        self.assertEqual(len(detail["messages"]), 2)

        self.assertEqual(self.client.delete(f"/api/conversations/{conversation_id}/").status_code, 204)
        self.assertFalse(Conversation.objects.exists())

    def test_bot_crash_still_returns_a_reply(self):
        with mock.patch("chat.services.MechanicBot.reply", side_effect=RuntimeError("boom")):
            response = self.send("my brakes squeal")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["reply"]["kind"], Message.Kind.ERROR)

    def test_general_question_without_ai_key(self):
        reply = self.send("which engine oil grade should I use in a Creta?").json()["reply"]
        self.assertEqual(reply["kind"], "text")
        self.assertFalse(reply["used_ai"])


class ChatWithAiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient(HTTP_X_CLIENT_ID=CLIENT_ID)

    def test_general_question_uses_ai_and_caches(self):
        fake = FakeGemini(text="For a Creta petrol, 0W-20 or 5W-30 synthetic is what Hyundai recommends.")
        question = {"message": "which engine oil is best for a creta?"}
        with mock.patch("chat.bot.engine.GeminiClient", return_value=fake):
            first = self.client.post("/api/chat/", question, format="json")
            second = self.client.post("/api/chat/", question, format="json")

        self.assertTrue(first.json()["reply"]["used_ai"])
        self.assertIn("5W-30", second.json()["reply"]["content"])
        self.assertEqual(fake.calls, 1)

    def test_ai_saying_off_topic_becomes_rejection(self):
        fake = FakeGemini(text="OFF_TOPIC")
        with mock.patch("chat.bot.engine.GeminiClient", return_value=fake):
            response = self.client.post("/api/chat/", {"message": "what car does elon musk drive?"}, format="json")
        self.assertEqual(response.json()["reply"]["kind"], "rejection")
