"""
Rule based intent checks. Cheap and predictable, so we only reach for Gemini
when none of these give a clear answer.
"""

import re

from core.text import mentions_any, word_count
from diagnosis.knowledge_base import ISSUE_TYPES, TRIAGE_QUESTIONS

from .vehicle import mentions_vehicle

GREETING_RE = re.compile(r"^(hi+|hello+|hey+|hii+|helo|namaste|namaskar|good (morning|afternoon|evening)|yo|hola|sup)\b")
THANKS_RE = re.compile(r"\b(thanks?|thank you|thankyou|thx|ty|cheers|appreciate it|great help|helpful)\b")
YES_RE = re.compile(r"^(yes|yeah|yep|yup|ya|sure|ok|okay|okk?|please|go ahead|haan|ha|of course|definitely|do it|lets do it)\b")
NO_RE = re.compile(r"^(no|nope|nah|not now|not right now|later|maybe later|no thanks|dont)\b")
QUESTION_RE = re.compile(r"^(what|why|how|which|when|where|should|can|could|is|are|do|does|will|would|shall|any)\b")

BOOKING_WORDS = ("book*", "appointment", "schedule", "send a mechanic", "send mechanic", "visit", "pick up", "pickup and drop")
SKIP_WORDS = ("skip", "diagnose now", "just tell me", "tell me whats wrong", "give me the diagnosis")
COST_WORDS = ("cost*", "price*", "charge*", "how much", "expensive", "rate", "budget", "estimate")
SAFETY_WORDS = ("safe", "drive it", "can i drive", "okay to drive", "ok to drive", "risky", "dangerous")

# general car vocabulary. The issue keywords from the knowledge base are checked too.
CAR_WORDS = (
    "car", "cars", "vehicle", "auto*", "engine", "motor", "mechanic*", "garage", "workshop", "servic*", "repair*",
    "fuel", "petrol", "diesel", "cng", "ev", "hybrid", "oil", "coolant", "radiator", "battery", "tyre*", "tire*",
    "wheel*", "brak*", "clutch", "gear*", "steering", "suspension", "exhaust", "silencer", "bonnet", "hood", "boot",
    "dashboard", "odometer", "speedometer", "km", "kmpl", "mileage", "horn", "wiper*", "headlight*", "bumper",
    "windshield", "windscreen", "spark plug*", "alternator", "starter", "transmission", "sedan", "suv", "hatchback",
    "noise", "sound", "vibrat*", "smell*", "leak*", "warning light*", "drive", "driving", "rpm", "obd", "insurance claim",
    "accident", "dent*", "scratch*", "paint",
)

# strong keywords from the knowledge base (weight 2+) also count as car talk
ISSUE_WORDS = tuple(pattern for issue in ISSUE_TYPES for pattern, weight in issue.keywords.items() if weight >= 2)

# requests that are never ours to answer, even if they mention a car ("write a poem about my car")
OFF_TOPIC_TASKS = ("poem*", "story", "stories", "joke*", "recipe*", "essay*", "homework", "lyrics", "song*", "rap")

# subjects that are clearly not about cars. Only used when nothing car related was said.
OFF_TOPIC_SUBJECTS = (
    "cook*", "weather", "movie*", "film*", "cricket", "football", "ipl", "stock*", "share market", "crypto*",
    "bitcoin", "math*", "equation*", "python", "javascript", "html", "translate", "politic*", "election*",
    "prime minister", "doctor", "medicine*", "fever", "headache", "diet", "relationship*", "girlfriend",
    "boyfriend", "horoscope", "capital of", "exam*", "resume", "bike*", "scooter*", "motorcycle*", "laptop*",
)


def is_greeting(text):
    return bool(GREETING_RE.match(text)) and word_count(text) <= 5


def is_thanks(text):
    return bool(THANKS_RE.search(text)) and word_count(text) <= 8


def is_yes(text):
    return bool(YES_RE.match(text)) and word_count(text) <= 8


def is_no(text):
    return bool(NO_RE.match(text)) and word_count(text) <= 8


def is_question(text, raw_text=""):
    return raw_text.strip().endswith("?") or bool(QUESTION_RE.match(text))


def wants_booking(text):
    return mentions_any(text, BOOKING_WORDS)


def wants_to_skip(text):
    return mentions_any(text, SKIP_WORDS)


def asks_about_cost(text):
    return mentions_any(text, COST_WORDS)


def asks_about_safety(text):
    return mentions_any(text, SAFETY_WORDS)


def is_car_related(text):
    return mentions_any(text, CAR_WORDS) or mentions_any(text, ISSUE_WORDS) or mentions_vehicle(text)


def is_off_topic(text):
    if mentions_any(text, OFF_TOPIC_TASKS):
        return True
    return mentions_any(text, OFF_TOPIC_SUBJECTS) and not is_car_related(text)


def triage_topic(text):
    """For vague complaints ("weird noise") figure out which clarifying question to ask."""
    for topic, question in TRIAGE_QUESTIONS.items():
        if mentions_any(text, question.patterns):
            return topic
    return None
