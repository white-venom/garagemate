import shutil
import tempfile
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from chat.models import Attachment
from chat.uploads import MAX_SIZE

from .test_chat_api import FakeGemini

CLIENT_ID = "upload-client-01"

# smallest thing the sniffer accepts as a PNG / WAV
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
WAV_BYTES = b"RIFF\x24\x00\x00\x00WAVEfmt " + b"\x00" * 64

MEDIA_DIR = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA_DIR, GEMINI_API_KEY="")
class UploadApiTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_DIR, ignore_errors=True)

    def setUp(self):
        self.client = APIClient(HTTP_X_CLIENT_ID=CLIENT_ID)

    def upload(self, name, content, content_type):
        file = SimpleUploadedFile(name, content, content_type=content_type)
        return self.client.post("/api/upload/", {"file": file}, format="multipart")

    def test_image_upload(self):
        response = self.upload("dashboard.png", PNG_BYTES, "image/png")
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["kind"], "image")
        self.assertEqual(body["mime_type"], "image/png")
        self.assertTrue(body["url"].startswith("http"))

    def test_audio_upload(self):
        response = self.upload("engine.wav", WAV_BYTES, "audio/wav")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["kind"], "audio")

    def test_file_type_is_checked_by_content_not_extension(self):
        response = self.upload("totally-a-photo.png", b"MZ this is actually an exe", "image/png")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Unsupported file type", response.json()["error"]["message"])

    def test_missing_file(self):
        response = self.client.post("/api/upload/", {}, format="multipart")
        self.assertEqual(response.status_code, 400)

    def test_too_big(self):
        with mock.patch.dict(MAX_SIZE, {Attachment.Kind.IMAGE: 10}):
            response = self.upload("big.png", PNG_BYTES, "image/png")
        self.assertEqual(response.status_code, 400)
        self.assertIn("too big", response.json()["error"]["message"])

    def test_attachment_can_only_be_sent_once(self):
        attachment_id = self.upload("a.png", PNG_BYTES, "image/png").json()["id"]
        first = self.client.post("/api/chat/", {"message": "", "attachment_ids": [attachment_id]}, format="json")
        self.assertEqual(first.status_code, 201)
        # no API key -> the bot just keeps the photo with the case
        self.assertIn("attached your photo", first.json()["reply"]["content"])
        self.assertEqual(len(first.json()["user_message"]["attachments"]), 1)

        again = self.client.post("/api/chat/", {"message": "hi", "attachment_ids": [attachment_id]}, format="json")
        self.assertEqual(again.status_code, 400)

    def test_cannot_use_someone_elses_upload(self):
        attachment_id = self.upload("a.png", PNG_BYTES, "image/png").json()["id"]
        other = APIClient(HTTP_X_CLIENT_ID="another-client")
        response = other.post("/api/chat/", {"message": "look", "attachment_ids": [attachment_id]}, format="json")
        self.assertEqual(response.status_code, 400)


@override_settings(MEDIA_ROOT=MEDIA_DIR)
class MediaAnalysisTests(TestCase):
    def setUp(self):
        self.client = APIClient(HTTP_X_CLIENT_ID=CLIENT_ID)

    def test_photo_analysis_starts_the_right_issue(self):
        file = SimpleUploadedFile("leak.png", PNG_BYTES, content_type="image/png")
        attachment_id = self.client.post("/api/upload/", {"file": file}, format="multipart").json()["id"]

        fake = FakeGemini(
            data={
                "car_related": True,
                "observations": "I can see a green puddle under the front of the car, looks like coolant.",
                "system": "leaks",
            }
        )
        with mock.patch("chat.bot.engine.GeminiClient", return_value=fake):
            body = self.client.post("/api/chat/", {"attachment_ids": [attachment_id]}, format="json").json()

        self.assertEqual(body["conversation"]["issue_category"], "leaks")
        self.assertIn("green puddle", body["reply"]["content"])
        self.assertTrue(body["reply"]["used_ai"])
        self.assertEqual(Attachment.objects.get(pk=attachment_id).analysis["system"], "leaks")

    def test_same_file_is_not_analysed_twice(self):
        fake = FakeGemini(data={"car_related": True, "observations": "Worn tyre tread on the outer edge.", "system": "tyres"})
        with mock.patch("chat.bot.engine.GeminiClient", return_value=fake):
            for _ in range(2):
                file = SimpleUploadedFile("tyre.png", PNG_BYTES, content_type="image/png")
                attachment_id = self.client.post("/api/upload/", {"file": file}, format="multipart").json()["id"]
                self.client.post("/api/chat/", {"attachment_ids": [attachment_id]}, format="json")
        self.assertEqual(fake.calls, 1)
