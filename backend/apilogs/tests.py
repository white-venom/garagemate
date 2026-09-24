from unittest import mock

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from google.genai import errors
from rest_framework.test import APIClient

from apilogs.models import RequestLog
from core.gemini import failure_reason

CLIENT_ID = "logs-client-001"
CUSTOM_KEY = "my-own-test-key-1234567890abcdef"


def quota_error():
    return errors.ClientError(429, {"error": {"code": 429, "message": "Resource exhausted", "status": "RESOURCE_EXHAUSTED"}})


def fake_genai(side_effect):
    client = mock.MagicMock()
    client.models.generate_content.side_effect = side_effect
    return mock.patch("core.gemini.genai.Client", return_value=client)


class FailureReasonTests(SimpleTestCase):
    def test_reasons(self):
        self.assertEqual(failure_reason(quota_error()), "quota")
        self.assertEqual(failure_reason(errors.ServerError(503, {"error": {"message": "overloaded"}})), "overloaded")
        self.assertEqual(failure_reason(errors.ServerError(504, {"error": {"message": "deadline"}})), "timeout")
        self.assertEqual(failure_reason(errors.ClientError(400, {"error": {"message": "API key not valid"}})), "invalid_key")
        self.assertEqual(failure_reason(TimeoutError("timed out")), "timeout")


@override_settings(GEMINI_API_KEY="")
class RequestLoggingTests(TestCase):
    def setUp(self):
        self.client = APIClient(HTTP_X_CLIENT_ID=CLIENT_ID)

    def test_requests_are_logged(self):
        self.client.post("/api/chat/", {"message": "my brakes squeal"}, format="json")
        self.client.post("/api/booking/", {"service": "nope"}, format="json")

        chat_log, booking_log = RequestLog.objects.order_by("id")
        self.assertEqual((chat_log.method, chat_log.path, chat_log.status_code), ("POST", "/api/chat/", 201))
        self.assertEqual(chat_log.client_id, CLIENT_ID)
        self.assertEqual(chat_log.ai_calls, [])
        self.assertEqual(booking_log.status_code, 400)
        self.assertTrue(booking_log.error)

    def test_logs_endpoint_only_shows_own_requests(self):
        self.client.get("/api/services/")
        APIClient(HTTP_X_CLIENT_ID="someone-else-22").get("/api/services/")

        body = self.client.get("/api/logs/").json()
        self.assertEqual(len(body["results"]), 1)
        self.assertEqual(body["results"][0]["path"], "/api/services/")
        self.assertEqual(body["gemini"]["status"], "not_configured")
        # polling the logs isn't logged itself
        self.assertFalse(RequestLog.objects.filter(path="/api/logs/").exists())

    def test_stats_count_rule_based_replies(self):
        self.client.post("/api/chat/", {"message": "hi"}, format="json")
        self.client.post("/api/chat/", {"message": "write me a poem"}, format="json")
        stats = self.client.get("/api/logs/").json()["stats"]
        self.assertEqual(stats["bot_replies"], 2)
        self.assertEqual(stats["handled_by_rules"], 2)
        self.assertEqual(stats["ai_calls"], 0)

    def test_check_without_key(self):
        body = self.client.post("/api/ai/check/").json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["reason"], "not_configured")


@override_settings(
    GEMINI_API_KEY="server-test-key", GEMINI_MODEL="model-a", GEMINI_FALLBACK_MODEL="model-b", RESEARCH_ENABLED=False
)
class GeminiFailureTests(TestCase):
    def setUp(self):
        cache.clear()  # answers to open questions are cached
        self.client = APIClient(HTTP_X_CLIENT_ID=CLIENT_ID)

    def test_quota_failure_is_logged_and_shown_on_the_reply(self):
        with fake_genai(quota_error()):
            reply = self.client.post("/api/chat/", {"message": "which engine oil is best for a creta?"}, format="json").json()["reply"]

        self.assertEqual(reply["ai_error"], "quota")
        self.assertFalse(reply["used_ai"])

        log = RequestLog.objects.get(path="/api/chat/")
        self.assertEqual([call["model"] for call in log.ai_calls], ["model-a", "model-b"])
        self.assertTrue(all(call["reason"] == "quota" for call in log.ai_calls))

        body = self.client.get("/api/logs/").json()
        self.assertEqual(body["gemini"]["status"], "failing")
        self.assertEqual(body["gemini"]["reason"], "quota")
        self.assertEqual(body["stats"]["ai_failures"], 2)

    def test_fallback_model_saves_the_day(self):
        answer = mock.MagicMock(text="Use 0W-20.")
        with fake_genai([quota_error(), answer]):
            reply = self.client.post("/api/chat/", {"message": "which engine oil is best for a creta?"}, format="json").json()["reply"]

        self.assertEqual(reply["ai_error"], "")
        self.assertTrue(reply["used_ai"])
        self.assertEqual(self.client.get("/api/logs/").json()["gemini"]["status"], "ok")

    def test_custom_key_is_used_but_never_stored(self):
        answer = mock.MagicMock(text="OK")
        with fake_genai([answer]) as client_class:
            body = self.client.post("/api/ai/check/", HTTP_X_GEMINI_KEY=CUSTOM_KEY).json()

        self.assertTrue(body["ok"])
        self.assertTrue(body["using_custom_key"])
        self.assertEqual(client_class.call_args.kwargs["api_key"], CUSTOM_KEY)
        log = RequestLog.objects.get(path="/api/ai/check/")
        self.assertTrue(log.ai_calls[0]["custom_key"])
        self.assertNotIn(CUSTOM_KEY, str(log.ai_calls))

    def test_custom_key_calls_dont_change_server_status(self):
        with fake_genai(quota_error()):
            self.client.post("/api/ai/check/")
        with fake_genai([mock.MagicMock(text="OK")]):
            self.client.post("/api/ai/check/", HTTP_X_GEMINI_KEY=CUSTOM_KEY)
        self.assertEqual(self.client.get("/api/logs/").json()["gemini"]["status"], "failing")
