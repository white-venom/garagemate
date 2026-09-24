"""
Conversation behaviour that came out of testing it like a customer would:
mileage complaints, Hinglish, "none of these", switching language, the engine light path.
"""

import ast
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from chat.models import Conversation

CLIENT_ID = "conversation-client-01"


class ScriptedGemini:
    """Fake Gemini that answers differently depending on what the call is for."""

    enabled = True
    last_failure = None

    def __init__(self, understood=None, research_text="", sources=None, answer=""):
        self.understood = understood or {}
        self.research_text = research_text
        self.sources = sources or []
        self.answer = answer
        self.purposes = []

    def generate_json(self, prompt, *, purpose="", **kwargs):
        self.purposes.append(purpose)
        if purpose == "understanding the message":
            return self.understood
        if purpose == "translation" and "Options:" in prompt:
            options = ast.literal_eval(prompt.rsplit("Options:", 1)[1].strip())
            return {"text": f"[hinglish] {prompt.split('Message:', 1)[1].split('Options:')[0].strip()}",
                    "options": [f"[hinglish] {option}" for option in options]}
        if purpose == "translation":
            return {"title": "t", "summary": "s", "advice": "a", "causes": [], "research_summary": ""}
        return {}

    def generate_text(self, prompt, *, purpose="", **kwargs):
        self.purposes.append(purpose)
        return self.answer

    def research(self, prompt, *, purpose="web research", **kwargs):
        self.purposes.append(purpose)
        return {"text": self.research_text or self.answer, "sources": self.sources, "queries": ["e20 mileage"]}


def understood(intent, english, language="en", category="unknown", requested="none"):
    return {"intent": intent, "english": english, "language": language, "requested_language": requested, "category": category}


class ConversationTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient(HTTP_X_CLIENT_ID=CLIENT_ID)
        self.conversation_id = None

    def send(self, message):
        payload = {"message": message}
        if self.conversation_id:
            payload["conversation_id"] = self.conversation_id
        body = self.client.post("/api/chat/", payload, format="json").json()
        self.conversation_id = body["conversation"]["id"]
        return body["reply"]

    def conversation(self):
        return Conversation.objects.get(pk=self.conversation_id)


@override_settings(GEMINI_API_KEY="")
class RuleFlowTests(ConversationTestCase):
    def test_avg_dropped_starts_the_mileage_flow_with_the_fuel_question(self):
        reply = self.send("the avg has dropped")
        self.assertEqual(self.conversation().issue_category, "fuel_economy")
        self.assertIn("Which fuel", reply["content"])
        self.assertIn("Petrol + CNG", reply["quick_replies"])

    def test_not_giving_mileage_is_a_complaint_not_a_negation(self):
        self.send("my car is not giving the mileage like it used to give what part needs replacemnt")
        self.assertEqual(self.conversation().issue_category, "fuel_economy")

    def test_fuel_answer_brings_general_fuel_notes_without_ai(self):
        self.send("mileage has dropped a lot")
        reply = self.send("Petrol")
        self.assertIn("E20", reply["content"])
        self.assertEqual(self.conversation().fuel_type, "petrol")
        self.assertEqual(reply["kind"], "question")

    def test_fuel_question_skipped_when_it_was_mentioned(self):
        reply = self.send("my diesel car avg dropped")
        self.assertNotIn("Which fuel", reply["content"])
        self.assertIn("diesel", reply["content"].lower())

    def test_dual_fuel_counts_as_cng(self):
        self.send("mileage is down")
        self.send("Petrol + CNG")
        self.assertEqual(self.conversation().fuel_type, "cng")

    def test_steady_engine_light_is_not_asked_when_it_is_worst(self):
        reply = self.send("check engine light is on")
        self.assertIn("steady", reply["content"].lower())
        asked = [reply["content"]]
        answers = {
            "steady": "Steady, stays on all the time",
            "drive any differently": "Drives normally",
            "Which car": "2019 Tata Tiago, 40000 km",
        }
        for _ in range(8):
            if reply["kind"] != "question":
                break
            answer = next((text for hint, text in answers.items() if hint in reply["content"]), reply["quick_replies"][-1])
            reply = self.send(answer)
            asked.append(reply["content"])

        self.assertEqual(reply["kind"], "diagnosis")
        self.assertFalse(any("When is it worst" in text for text in asked))
        self.assertTrue(any("other warning light" in text for text in asked))

    def test_poor_pickup_asks_when_it_is_worst_but_not_about_the_light(self):
        reply = self.send("engine has poor pickup and jerks")
        self.assertNotIn("steady", reply["content"].lower())
        self.assertNotIn("drive any differently", reply["content"])

    def test_unclear_message_mid_chat_is_not_rejected(self):
        self.send("hi")
        reply = self.send("none of those match what is going on honestly")
        self.assertNotEqual(reply["kind"], "rejection")

    def test_car_details_mid_question_are_noted_and_the_question_repeated(self):
        first = self.send("my brakes squeal")
        reply = self.send("maruti swift 2018, 60000 km")
        conversation = self.conversation()
        self.assertEqual(conversation.vehicle_model, "Swift")
        self.assertIn("noted the car", reply["content"])
        self.assertIn(first["content"].split("\n")[-1], reply["content"])
        self.assertEqual(conversation.state["answers"], {})

    def test_more_detail_after_diagnosis_updates_it_instead_of_starting_over(self):
        self.send("my brakes squeal")
        self.client.post("/api/diagnosis/", {"conversation_id": self.conversation_id}, format="json")
        reply = self.send("the brake pedal also feels soft and spongy now")
        self.assertEqual(reply["kind"], "diagnosis")
        self.assertIn("updated picture", reply["content"])
        self.assertIn("brake fluid", reply["diagnosis"]["title"].lower())

    def test_language_request_without_ai(self):
        reply = self.send("can you talk in hindi")
        self.assertIn("only reply in English", reply["content"])
        self.assertEqual(self.conversation().language, "en")


class UnderstandingTests(ConversationTestCase):
    def chat_with(self, fake, message):
        with mock.patch("chat.bot.engine.GeminiClient", return_value=fake):
            return self.send(message)

    def test_hinglish_problem_is_understood_and_answered_in_hinglish(self):
        fake = ScriptedGemini(
            understood("car_problem", "My car's mileage has dropped", "hinglish", "fuel_economy")
        )
        reply = self.chat_with(fake, "meri gaadi ka avg kam ho gaya hai")
        conversation = self.conversation()
        self.assertEqual(conversation.issue_category, "fuel_economy")
        self.assertEqual(conversation.language, "hinglish")
        self.assertTrue(reply["content"].startswith("[hinglish]"))
        self.assertIn("[hinglish] Petrol", reply["quick_replies"])

        # tapping a translated button still reaches the rules as the English option
        self.chat_with(ScriptedGemini(research_text="- E20 petrol lowers mileage by 2-6%"), "[hinglish] Petrol")
        conversation = self.conversation()
        self.assertEqual(conversation.fuel_type, "petrol")
        self.assertEqual(conversation.state["answers"]["fuel"], "Petrol")

    def test_typo_in_language_request(self):
        fake = ScriptedGemini(understood("change_language", "Can you talk in Hindi?", requested="hi"))
        reply = self.chat_with(fake, "can you talk in hinid")
        self.assertEqual(self.conversation().language, "hi")
        self.assertNotEqual(reply["kind"], "rejection")

    def test_language_request_mid_question_asks_the_question_again(self):
        self.chat_with(ScriptedGemini(), "my brakes squeal")
        reply = self.chat_with(ScriptedGemini(), "reply in hinglish please")
        self.assertEqual(self.conversation().language, "hinglish")
        self.assertIn("brake pedal", reply["content"])

    def test_none_of_these_moves_to_the_next_question(self):
        self.chat_with(ScriptedGemini(), "my brakes squeal")
        pending = self.conversation().state["pending"]
        fake = ScriptedGemini(understood("none_of_the_options", "None of these options match"))
        reply = self.chat_with(fake, "not my issues listed")
        state = self.conversation().state
        self.assertEqual(state["answers"][pending], "None of these")
        self.assertNotEqual(state["pending"], pending)
        self.assertEqual(reply["kind"], "question")

    def test_more_detail_instead_of_an_answer_repeats_the_question(self):
        self.chat_with(ScriptedGemini(), "ac is not cooling")
        pending = self.conversation().state["pending"]
        fake = ScriptedGemini(understood("car_problem", "It blows air but it isn't cold", category="ac"))
        reply = self.chat_with(fake, "it blows air but not cold")
        state = self.conversation().state
        self.assertNotIn(pending, state["answers"])
        self.assertEqual(state["pending"], pending)
        self.assertIn("isn't cold", state["description"])
        self.assertIn("Got it", reply["content"])

    def test_option_picked_by_ai_is_saved_with_their_words(self):
        self.chat_with(ScriptedGemini(), "ac is not cooling")
        fake = ScriptedGemini({**understood("answer", "It gets worse when stuck at signals"), "option": "Worse in traffic / idle"})
        self.chat_with(fake, "worst at signals")
        answers = self.conversation().state["answers"]
        self.assertIn("Worse in traffic / idle (It gets worse when stuck at signals)", answers.values())

    def test_off_topic_after_understanding_is_rejected(self):
        fake = ScriptedGemini(understood("off_topic", "Who will win the match today?"))
        reply = self.chat_with(fake, "aaj match kaun jeetega bhai")
        self.assertEqual(reply["kind"], "rejection")

    def test_fuel_research_is_shared_before_the_next_question(self):
        sources = [{"title": "E20 petrol and mileage", "url": "https://example.com/e20"}]
        fake = ScriptedGemini(research_text="- Most pumps sell E20 now, expect 2-6% lower mileage.", sources=sources)
        self.chat_with(fake, "avg has dropped")
        reply = self.chat_with(fake, "Petrol")

        self.assertIn("E20", reply["content"])
        self.assertEqual(reply["sources"], sources)
        self.assertTrue(reply["used_ai"])
        self.assertEqual(reply["kind"], "question")
        research = self.conversation().state["research"]
        self.assertEqual(research["sources"], sources)

        # researched once per conversation, not again for every answer
        searches = fake.purposes.count("web research")
        self.chat_with(fake, "A lot, more than 30%")
        self.assertEqual(fake.purposes.count("web research"), searches)


class BackgroundResearchTests(ConversationTestCase):
    def test_research_starts_once_the_car_is_known_and_is_reused_at_diagnosis(self):
        sources = [{"title": "Swift service campaign", "url": "https://example.com/swift"}]
        fake = ScriptedGemini(research_text="- Maruti checked brake vacuum hoses on some 2018 Swifts.", sources=sources)
        with mock.patch("chat.bot.engine.GeminiClient", return_value=fake):
            self.send("my brakes squeal")
            self.send("Feels normal")
            self.send("2018 Maruti Swift, 60000 km")
            self.assertEqual(fake.purposes.count("web research"), 1)
            self.assertTrue(self.conversation().state["research_started"])
            reply = self.client.post(
                "/api/diagnosis/", {"conversation_id": self.conversation_id}, format="json"
            ).json()

        self.assertEqual(reply["diagnosis"]["research"]["sources"], sources)
        # the diagnosis took it from the cache instead of searching again
        self.assertEqual(fake.purposes.count("web research"), 1)


class SearchQuotaTests(ConversationTestCase):
    def test_quota_pauses_web_search_for_a_while(self):
        from core.gemini import GeminiError
        from diagnosis.research import search_paused

        class OutOfQuota(ScriptedGemini):
            def research(self, prompt, **kwargs):
                self.purposes.append("web research")
                raise GeminiError("429", reason="quota")

        fake = OutOfQuota(answer="Petrol prices in Delhi are around 95 rupees a litre.")
        with mock.patch("chat.bot.engine.GeminiClient", return_value=fake):
            reply = self.send("what is the petrol price in delhi today?")
            self.assertIn("95", reply["content"])
            self.assertEqual(reply["ai_error"], "")
            self.assertTrue(search_paused())
            cache.delete("answer:" + "x")  # different question, still no search while paused
            self.send("any news about e20 petrol?")
        self.assertEqual(fake.purposes.count("web research"), 1)

    def test_plain_questions_dont_use_the_search_quota(self):
        fake = ScriptedGemini(answer="Use the coolant Hyundai specifies, usually a long-life OAT coolant.")
        with mock.patch("chat.bot.engine.GeminiClient", return_value=fake):
            self.send("which coolant should i use in my creta?")
        self.assertNotIn("open question (web search)", fake.purposes)
        self.assertIn("open question", fake.purposes)


class ConversationLanguageApiTests(ConversationTestCase):
    @override_settings(GEMINI_API_KEY="")
    def test_patch_language(self):
        self.send("hi")
        url = f"/api/conversations/{self.conversation_id}/"
        response = self.client.patch(url, {"language": "hi"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["language"], "hi")
        self.assertEqual(self.client.patch(url, {"language": "fr"}, format="json").status_code, 400)

    @override_settings(GEMINI_API_KEY="")
    def test_language_on_a_new_chat(self):
        body = self.client.post("/api/chat/", {"message": "hi", "language": "hinglish"}, format="json").json()
        self.assertEqual(body["conversation"]["language"], "hinglish")
