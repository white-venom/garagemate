"""
Checks for uploaded files. We look at the actual bytes (magic numbers) instead
of trusting the file extension or the Content-Type the browser sends.
"""

import hashlib

import filetype
from rest_framework.exceptions import ValidationError

from .models import Attachment

MB = 1024 * 1024

# keep the total under Gemini's ~20MB inline request limit
MAX_SIZE = {
    Attachment.Kind.IMAGE: 8 * MB,
    Attachment.Kind.AUDIO: 10 * MB,
    Attachment.Kind.VIDEO: 15 * MB,
}

ALLOWED_TYPES = {
    "image/jpeg": Attachment.Kind.IMAGE,
    "image/png": Attachment.Kind.IMAGE,
    "image/webp": Attachment.Kind.IMAGE,
    "image/heic": Attachment.Kind.IMAGE,
    "audio/mpeg": Attachment.Kind.AUDIO,
    "audio/x-wav": Attachment.Kind.AUDIO,
    "audio/ogg": Attachment.Kind.AUDIO,
    "audio/x-flac": Attachment.Kind.AUDIO,
    "audio/aac": Attachment.Kind.AUDIO,
    "audio/mp4": Attachment.Kind.AUDIO,
    "video/mp4": Attachment.Kind.VIDEO,
    "video/webm": Attachment.Kind.VIDEO,
    "video/quicktime": Attachment.Kind.VIDEO,
    "video/3gpp": Attachment.Kind.VIDEO,
}

# webm / mp4 are containers, a voice note recorded in the browser looks like a
# video to the sniffer. Trust the browser's audio/* type in that case.
AUDIO_CONTAINERS = {"video/webm": "audio/webm", "video/mp4": "audio/mp4", "video/3gpp": "audio/3gpp"}


def _human_size(size):
    return f"{size / MB:.0f} MB"


def inspect_upload(uploaded_file):
    """
    Validate the file and return (kind, mime_type, checksum).
    Raises ValidationError with a message that's safe to show the user.
    """
    if uploaded_file.size == 0:
        raise ValidationError({"file": "The file is empty."})

    head = uploaded_file.read(8192)
    uploaded_file.seek(0)
    guess = filetype.guess(head)
    if guess is None or guess.mime not in ALLOWED_TYPES:
        raise ValidationError(
            {"file": "Unsupported file type. Please send a photo (JPG, PNG, WEBP), audio (MP3, WAV, M4A, OGG) or video (MP4, WEBM, MOV)."}
        )

    mime_type = guess.mime
    kind = ALLOWED_TYPES[mime_type]
    declared = (getattr(uploaded_file, "content_type", "") or "").lower()
    if mime_type in AUDIO_CONTAINERS and declared.startswith("audio/"):
        mime_type = AUDIO_CONTAINERS[mime_type]
        kind = Attachment.Kind.AUDIO

    limit = MAX_SIZE[kind]
    if uploaded_file.size > limit:
        raise ValidationError({"file": f"That {kind} is too big. The limit is {_human_size(limit)}."})

    sha256 = hashlib.sha256()
    for chunk in uploaded_file.chunks():
        sha256.update(chunk)
    uploaded_file.seek(0)

    return kind, mime_type, sha256.hexdigest()
