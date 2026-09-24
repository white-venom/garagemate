"""
Replying in Hindi or Hinglish.

The bot's logic and knowledge base stay in English. When a conversation is set to
another language, the finished reply (text + quick reply buttons) is translated in
one Gemini call. Most replies are the same canned questions over and over, so
translations are cached without expiry and a repeated question costs nothing.

Quick replies are translated too, so we remember which translated button maps to
which original option; when the customer taps one, the rules get the English text back.
"""

import hashlib
import logging
import re

from django.core.cache import cache

from core.gemini import GeminiError
from core.text import normalize

logger = logging.getLogger(__name__)

LANGUAGES = {
    "en": "English",
    "hi": "Hindi, written in Devanagari script (not Latin letters)",
    "hinglish": "Hinglish (Hindi written in Latin letters, the way people text in India)",
}

TRANSLATION_SCHEMA = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "options": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["text", "options"],
}

DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")

STYLE = (
    "Keep car part names that Indians normally say in English (brake pad, clutch, AC, battery, spark plug). "
    "Keep markdown, numbers, km, and rupee amounts exactly as they are. Keep it friendly and natural, not formal."
)


def translate(gemini, text, options, language):
    """
    Returns (text, options, called_ai) in the target language, or None if it couldn't be done.
    called_ai is False when the translation came from the cache.
    """
    if language not in LANGUAGES or language == "en" or not (text or options):
        return None

    key = "translation:" + hashlib.sha256(f"{language}|{text}|{'||'.join(options)}".encode()).hexdigest()
    cached = cache.get(key)
    if cached:
        return cached["text"], cached["options"], False
    if not gemini.enabled:
        return None

    prompt = f"""Translate this message from a car mechanic chatbot into {LANGUAGES[language]}. {STYLE}
Translate each option too, keep them short and in the same order.

Message:
{text}

Options: {options}"""
    result = None
    # the lite model sometimes answers "Hindi" in Latin letters, one more try usually fixes it
    for _ in range(2):
        try:
            data = gemini.generate_json(prompt, schema=TRANSLATION_SCHEMA, purpose="translation", temperature=0.2)
        except GeminiError as exc:
            logger.warning("Translation failed: %s", exc)
            break
        translated_text = str(data.get("text", "")).strip()
        translated_options = [str(option).strip() for option in data.get("options") or []]
        if not translated_text or len(translated_options) != len(options):
            continue
        result = translated_text, translated_options
        if right_script(translated_text, language):
            cache.set(key, {"text": translated_text, "options": translated_options}, None)
            break
    # a reply in the wrong script is still better than English, but it isn't cached
    return (*result, True) if result else None


def right_script(text, language):
    return language != "hi" or bool(DEVANAGARI_RE.search(text))


def option_map(original, translated):
    """{normalized translated option: original English option} for mapping taps back."""
    return {normalize(new): old for old, new in zip(original, translated)}


LOCALIZE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "advice": {"type": "string"},
        "causes": {"type": "array", "items": {"type": "string"}},
        "research_summary": {"type": "string"},
    },
    "required": ["title", "summary", "advice", "causes", "research_summary"],
}


def localize_diagnosis(gemini, diagnosis, language):
    """Translated copy of the diagnosis card text, stored on the diagnosis. {} if it fails."""
    if language not in LANGUAGES or language == "en" or not gemini.enabled:
        return {}

    causes = [cause["name"] for cause in diagnosis.probable_causes]
    research = (diagnosis.research or {}).get("summary", "")
    prompt = f"""Translate the parts of this car diagnosis into {LANGUAGES[language]}. {STYLE}

title: {diagnosis.title}
summary: {diagnosis.summary}
advice: {diagnosis.advice}
causes (keep the same order): {causes}
research_summary: {research or "(empty, return an empty string)"}"""
    try:
        data = gemini.generate_json(prompt, schema=LOCALIZE_SCHEMA, purpose="translation", temperature=0.2)
    except GeminiError as exc:
        logger.warning("Diagnosis translation failed: %s", exc)
        return {}

    translated_causes = [str(cause).strip() for cause in data.get("causes") or []]
    if len(translated_causes) != len(causes):
        translated_causes = causes
    return {
        "language": language,
        "title": str(data.get("title", "")).strip() or diagnosis.title,
        "summary": str(data.get("summary", "")).strip() or diagnosis.summary,
        "advice": str(data.get("advice", "")).strip() or diagnosis.advice,
        "causes": translated_causes,
        "research_summary": str(data.get("research_summary", "")).strip(),
    }
