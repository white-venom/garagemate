"""
Looking at photos, recordings and videos.

This is one of the few places where we actually need AI, there's no sensible
rule based way to listen to an engine knock. Results are stored on the
attachment and reused if the exact same file (same sha256) comes in again.
"""

import logging

from core.gemini import GeminiError, MediaInput
from core.prompts import MECHANIC_PERSONA
from diagnosis.knowledge_base import ISSUE_TYPES_BY_KEY

from ..models import Attachment

logger = logging.getLogger(__name__)

# Gemini is picky about some mime types, map what browsers send to what it accepts
GEMINI_MIME_TYPES = {
    "audio/x-wav": "audio/wav",
    "audio/wave": "audio/wav",
    "audio/mpeg": "audio/mp3",
    "audio/x-flac": "audio/flac",
    "audio/mp4": "audio/aac",
    "audio/x-m4a": "audio/aac",
    "audio/webm": "video/webm",
    "audio/3gpp": "video/3gpp",
    "video/quicktime": "video/mov",
}

KIND_DESCRIPTIONS = {
    Attachment.Kind.IMAGE: "photo",
    Attachment.Kind.AUDIO: "audio recording",
    Attachment.Kind.VIDEO: "video",
}

WHAT_TO_LOOK_FOR = {
    Attachment.Kind.IMAGE: "visible damage, leaks and fluid colour, warning lights on the dashboard, tyre wear, corrosion, smoke, broken or worn parts",
    Attachment.Kind.AUDIO: "the type of noise (squeal, grind, knock, tick, whine, rattle, hiss, clunk), when it seems to happen and how bad it sounds",
    Attachment.Kind.VIDEO: "what you can see and hear: noises, smoke, leaks, warning lights, how the car behaves",
}

MEDIA_SCHEMA = {
    "type": "object",
    "properties": {
        "car_related": {"type": "boolean"},
        "observations": {"type": "string"},
        "system": {"type": "string", "enum": [*ISSUE_TYPES_BY_KEY.keys(), "unknown"]},
    },
    "required": ["car_related", "observations", "system"],
}


def gemini_mime_type(mime_type):
    return GEMINI_MIME_TYPES.get(mime_type, mime_type)


def _prompt(attachment, customer_text, issue_label):
    kind = KIND_DESCRIPTIONS[attachment.kind]
    return f"""The customer sent this {kind} while describing a problem with their car.
Problem area so far: {issue_label or "not known yet"}
What they wrote with it: "{customer_text or "(nothing)"}"

Look for things that matter for a diagnosis: {WHAT_TO_LOOK_FOR[attachment.kind]}.

Return JSON:
- car_related: false if this is not a car, car part, dashboard or car sound
- observations: 2-4 short sentences written to the customer ("I can see...", "I can hear..."). If the quality is too poor to tell, say that honestly
- system: the problem area it most likely relates to ({", ".join(ISSUE_TYPES_BY_KEY)}) or "unknown\""""


def analyse_attachment(attachment, gemini, customer_text="", issue_label=""):
    """
    Returns (analysis dict, called_ai). The dict is empty if we couldn't analyse
    the file (no API key, quota, error), callers should handle that.
    """
    if attachment.analysis:
        return attachment.analysis, False

    previous = (
        Attachment.objects.filter(checksum=attachment.checksum)
        .exclude(pk=attachment.pk)
        .exclude(analysis={})
        .only("analysis")
        .first()
    )
    if previous:
        attachment.analysis = previous.analysis
        attachment.save(update_fields=["analysis"])
        return attachment.analysis, False

    if not gemini.enabled:
        return {}, False

    try:
        with attachment.file.open("rb") as handle:
            data = handle.read()
        result = gemini.generate_json(
            _prompt(attachment, customer_text, issue_label),
            schema=MEDIA_SCHEMA,
            system=MECHANIC_PERSONA,
            media=[MediaInput(data=data, mime_type=gemini_mime_type(attachment.mime_type))],
            purpose=f"{KIND_DESCRIPTIONS[attachment.kind]} analysis",
        )
    except (GeminiError, OSError) as exc:
        logger.warning("Could not analyse attachment %s: %s", attachment.pk, exc)
        return {}, True

    system = result.get("system")
    attachment.analysis = {
        "car_related": bool(result.get("car_related")),
        "observations": str(result.get("observations", "")).strip()[:1500],
        "system": system if system in ISSUE_TYPES_BY_KEY else "unknown",
    }
    attachment.save(update_fields=["analysis"])
    return attachment.analysis, True
