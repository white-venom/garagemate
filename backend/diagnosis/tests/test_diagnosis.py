from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from chat.models import Conversation
from diagnosis.engine import build_diagnosis, detect_issue, is_confident, rank_causes
from diagnosis.knowledge_base import ISSUE_TYPES, ISSUE_TYPES_BY_KEY
from diagnosis.models import Diagnosis

from chat.tests.test_chat_api import FakeGemini

CLIENT_ID = "diag-client-001"


class KnowledgeBaseTests(TestCase):
    def test_every_issue_points_to_a_seeded_service(self):
        from bookings.models import Service

        codes = set(Service.objects.values_list("code", flat=True))
        for issue in ISSUE_TYPES:
            self.assertIn(issue.service_code, codes, issue.key)

    def test_detect_issue(self):
        cases = {
            "my brakes squeal when stopping": "brakes",
            "car won't start in the morning": "starting",
            "temperature gauge goes into the red": "overheating",
            "clutch is slipping": "transmission",
            "AC is blowing warm air": "ac",
            "blue smoke from the silencer": "exhaust",
            "steering wheel shakes at high speed": "tyres",
            "time for an oil change": "routine",
        }
        for text, expected in cases.items():
            issue = detect_issue(text)
            self.assertIsNotNone(issue, text)
            self.assertEqual(issue.key, expected, text)

    def test_nothing_detected_for_vague_text(self):
        self.assertIsNone(detect_issue("something feels off"))

    def test_rank_causes_uses_signals(self):
        ranked = rank_causes(ISSUE_TYPES_BY_KEY["brakes"], "pedal feels soft and spongy")
        self.assertIn("brake fluid", ranked[0].name.lower())
        self.assertTrue(is_confident(ranked))

    def test_weak_evidence_is_not_confident(self):
        ranked = rank_causes(ISSUE_TYPES_BY_KEY["brakes"], "brakes feel a bit weird")
        self.assertFalse(is_confident(ranked))


class BuildDiagnosisTests(TestCase):
    def make_conversation(self, category, description, answers=None):
        return Conversation.objects.create(
            client_id=CLIENT_ID,
            issue_category=category,
            state={"description": description, "answers": answers or {}},
        )

    def test_rules_only_when_confident(self):
        conversation = self.make_conversation("overheating", "temperature goes into the red, coolant is low and there is a puddle")
        fake = FakeGemini()
        diagnosis = build_diagnosis(conversation, gemini=fake)
        self.assertEqual(diagnosis.source, Diagnosis.Source.RULES)
        self.assertEqual(diagnosis.severity, "critical")
        self.assertFalse(diagnosis.safe_to_drive)
        self.assertEqual(fake.calls, 0)

    def test_ai_second_opinion_when_unsure(self):
        conversation = self.make_conversation("engine", "engine feels a bit off")
        fake = FakeGemini(
            data={
                "title": "Dirty throttle body",
                "summary": "Probably a dirty throttle body causing the uneven running.",
                "probable_causes": [{"name": "Dirty throttle body", "likelihood": 0.5}],
                "severity": "low",
                "advice": "Get it cleaned at the next service.",
            }
        )
        diagnosis = build_diagnosis(conversation, gemini=fake)
        self.assertEqual(diagnosis.source, Diagnosis.Source.AI)
        self.assertEqual(diagnosis.title, "Dirty throttle body")
        self.assertEqual(fake.calls, 1)

    def test_ai_cannot_downgrade_safety_severity(self):
        conversation = self.make_conversation("overheating", "car feels hot")
        fake = FakeGemini(
            data={
                "title": "Thermostat",
                "summary": "Could be the thermostat.",
                "probable_causes": [{"name": "Thermostat", "likelihood": 0.6}],
                "severity": "low",
                "advice": "Keep an eye on it.",
            }
        )
        diagnosis = build_diagnosis(conversation, gemini=fake)
        self.assertEqual(diagnosis.severity, "high")

    def test_known_car_gets_researched_once(self):
        cache.clear()
        conversation = self.make_conversation("brakes", "brakes squeal, pads never changed")
        conversation.vehicle_make, conversation.vehicle_model = "Maruti Suzuki", "Swift"
        conversation.save()
        sources = [{"title": "Swift recall", "url": "https://example.com/recall"}]
        fake = FakeGemini(text="- No brake recalls for the Swift in India.", sources=sources)

        diagnosis = build_diagnosis(conversation, gemini=fake)
        self.assertEqual(diagnosis.research["sources"], sources)
        self.assertIn("recalls", diagnosis.research["summary"])

        # same problem on the same car is served from the cache
        build_diagnosis(conversation, gemini=fake)
        self.assertEqual(fake.calls, 1)

    @override_settings(RESEARCH_ENABLED=False)
    def test_research_can_be_switched_off(self):
        conversation = self.make_conversation("brakes", "brakes squeal, pads never changed")
        conversation.vehicle_model = "Swift"
        conversation.save()
        fake = FakeGemini(text="anything")
        diagnosis = build_diagnosis(conversation, gemini=fake)
        self.assertEqual(diagnosis.research, {})
        self.assertEqual(fake.calls, 0)

    def test_causes_that_dont_fit_the_fuel_are_left_out(self):
        conversation = self.make_conversation("starting", "won't start in the morning, cranks normally, cold")
        conversation.fuel_type = "cng"
        conversation.save()
        names = [cause["name"] for cause in build_diagnosis(conversation).probable_causes]
        self.assertFalse(any("Glow plugs" in name for name in names))

        conversation.fuel_type = "diesel"
        conversation.save()
        ranked = rank_causes(ISSUE_TYPES_BY_KEY["starting"], "cranks normally cold morning diesel", "diesel")
        self.assertIn("Glow plugs (diesel cold start)", [cause.name for cause in ranked])

    def test_broken_ai_response_falls_back_to_rules(self):
        conversation = self.make_conversation("engine", "engine feels a bit off")
        diagnosis = build_diagnosis(conversation, gemini=FakeGemini(data={"nonsense": True}))
        self.assertEqual(diagnosis.source, Diagnosis.Source.RULES)
        self.assertTrue(diagnosis.probable_causes)


@override_settings(GEMINI_API_KEY="")
class DiagnosisApiTests(TestCase):
    def setUp(self):
        self.client = APIClient(HTTP_X_CLIENT_ID=CLIENT_ID)

    def start_chat(self, message):
        return self.client.post("/api/chat/", {"message": message}, format="json").json()["conversation"]["id"]

    def test_diagnose_early(self):
        conversation_id = self.start_chat("my brakes squeal a lot")
        response = self.client.post("/api/diagnosis/", {"conversation_id": conversation_id}, format="json")
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["diagnosis"]["title"], "Worn brake pads")
        self.assertEqual(body["message"]["kind"], "diagnosis")

        # asking again without new info returns the same diagnosis
        again = self.client.post("/api/diagnosis/", {"conversation_id": conversation_id}, format="json")
        self.assertEqual(again.status_code, 200)
        self.assertEqual(again.json()["diagnosis"]["id"], body["diagnosis"]["id"])

        detail = self.client.get(f"/api/diagnosis/{body['diagnosis']['id']}/")
        self.assertEqual(detail.status_code, 200)

    def test_nothing_to_diagnose(self):
        conversation_id = self.start_chat("hello")
        response = self.client.post("/api/diagnosis/", {"conversation_id": conversation_id}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_other_client_gets_404(self):
        conversation_id = self.start_chat("my brakes squeal")
        other = APIClient(HTTP_X_CLIENT_ID="someone-else-1")
        response = other.post("/api/diagnosis/", {"conversation_id": conversation_id}, format="json")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "not_found")
