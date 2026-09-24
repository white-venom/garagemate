"""
Second chance for messages the rules can't make sense of.

The rules only know English keywords. Hindi / Hinglish ("gaadi ka avg kam ho gaya"),
spelling mistakes ("hinid") or meta replies ("none of these", "my issue isn't listed")
would otherwise get rejected as off-topic. Before rejecting, we ask Gemini what the
message means and get back a cleaned-up English version the rules can work with.

Only called when the rules gave up, or the message clearly isn't plain English.
"""

import logging
import re

from core.gemini import GeminiError
from diagnosis.knowledge_base import ISSUE_TYPES_BY_KEY

logger = logging.getLogger(__name__)

INTENTS = [
    "car_problem",          # describing something wrong with the car
    "car_question",         # a question about cars / maintenance, not a specific fault
    "answer",               # answering the question the bot just asked
    "none_of_the_options",  # "my issue isn't listed", "none of these", "something else"
    "change_language",      # "talk in hindi", "english please"
    "greeting",
    "thanks",
    "yes",
    "no",
    "off_topic",
]

SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": INTENTS},
        "english": {"type": "string"},
        "option": {"type": "string"},
        "language": {"type": "string", "enum": ["en", "hi", "hinglish", "other"]},
        "requested_language": {"type": "string", "enum": ["en", "hi", "hinglish", "none"]},
        "category": {"type": "string", "enum": [*ISSUE_TYPES_BY_KEY.keys(), "unknown"]},
    },
    "required": ["intent", "english", "option", "language", "requested_language", "category"],
}

# common Hinglish words, if a message has a couple of these the rules won't understand it
HINGLISH_WORDS = {
    "hai", "hain", "nahi", "nahin", "nhi", "mera", "meri", "mere", "kya", "kyu", "kyun", "gaadi", "gadi", "kar",
    "karo", "raha", "rahi", "rhe", "hua", "hui", "aur", "bhi", "mein", "se", "ka", "ki", "ke", "wala",
    "wali", "kaise", "kab", "baat", "batao", "bata", "chal", "chalti", "aawaz", "awaz", "thik", "theek",
}


def looks_non_english(raw_text):
    if re.search(r"[^\x00-\x7F‘’“”₹]", raw_text or ""):
        return True
    words = re.findall(r"[a-z]+", (raw_text or "").lower())
    return sum(word in HINGLISH_WORDS for word in words) >= 2


def understand(gemini, text, question=None, options=(), last_bot_message=""):
    """Returns the interpretation dict, or None if Gemini isn't available / failed."""
    if not gemini.enabled:
        return None

    context = ""
    if question:
        context = f'The bot just asked: "{question}"'
        if options:
            context += f" with the options: {', '.join(options)}"
    elif last_bot_message:
        context = f'The bot\'s last message was: "{last_bot_message[:300]}"'

    prompt = f"""A customer is chatting with a car mechanic chatbot in India. Work out what their message means.
They may write in English, Hindi, Hinglish (Hindi in Latin letters), with typos or short forms
("avg" / "average" means fuel mileage, "pickup" means acceleration, "self" means the starter).

{context or "This is the start of the conversation."}
Customer's message: "{text}"

Return JSON:
- intent: what they're doing ({", ".join(INTENTS)}). A description of a car symptom is car_problem.
  If they answer the bot's question (even loosely), use answer. If they tell more about the problem instead of
  answering the question (e.g. the tyre age when asked about tyre pressure), use car_problem. If they say their problem isn't in the list, use none_of_the_options.
- english: their message in clear English with the spelling fixed. Keep the meaning exactly as they said it,
  don't replace it with one of the options.
- option: only when they answer the bot's question and the message clearly means one of the options: that
  option's exact text. Otherwise an empty string. Don't guess, a wrong option is worse than none.
- language: the language they wrote in
- requested_language: if they ask the bot to talk in a language, which one, else none
- category: which problem area it belongs to ({", ".join(ISSUE_TYPES_BY_KEY)}) or unknown"""

    try:
        data = gemini.generate_json(prompt, schema=SCHEMA, purpose="understanding the message", temperature=0.1)
    except GeminiError as exc:
        logger.warning("Could not interpret message: %s", exc)
        return None

    if data.get("intent") not in INTENTS or not str(data.get("english", "")).strip():
        return None
    if data.get("category") not in ISSUE_TYPES_BY_KEY:
        data["category"] = "unknown"
    data["english"] = str(data["english"]).strip()[:1000]
    return data
