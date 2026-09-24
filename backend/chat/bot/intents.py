"""
Rule based intent checks. Cheap and predictable, so we only reach for Gemini
when none of these give a clear answer.
"""

import re
from difflib import get_close_matches

from core.text import mentions, mentions_any, normalize, word_count
from diagnosis.knowledge_base import ISSUE_TYPES, TRIAGE_QUESTIONS

from .vehicle import mentions_vehicle

GREETING_RE = re.compile(r"^(hi+|hello+|hey+|hii+|helo|namaste|namaskar|good (morning|afternoon|evening)|yo|hola|sup)\b")
THANKS_RE = re.compile(r"\b(thanks?|thank you|thankyou|thx|ty|cheers|appreciate it|great help|helpful)\b")
YES_RE = re.compile(r"^(yes|yeah|yep|yup|ya|sure|ok|okay|okk?|please|go ahead|haan|ha|of course|definitely|do it|lets do it)\b")
NO_RE = re.compile(r"^(no|nope|nah|not now|not right now|later|maybe later|no thanks|dont)\b")
QUESTION_RE = re.compile(r"^(what|why|how|which|when|where|should|can|could|is|are|do|does|will|would|shall|any)\b")

BOOKING_WORDS = ("book*", "appointment", "schedule", "send a mechanic", "send mechanic", "visit", "pick up", "pickup and drop")
NONE_OF_THESE_WORDS = (
    "none of these", "none of those", "none of them", "none of the above", "none of the options", "none", "not listed",
    "not in the list", "not in list", "isnt listed", "not there", "not my issue*", "not my problem*", "something else",
    "some other*", "other issue*", "other problem*", "different issue*", "different problem*", "doesnt apply",
    "not applicable", "neither of these", "no option",
)
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
    "accident", "dent*", "scratch*", "paint", "avg", "average", "kmpl", "fuel efficiency", "pickup",
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


# "when" / "while" start most of the options, they don't tell them apart
FILLER_WORDS = {
    "a", "an", "the", "it", "its", "is", "was", "my", "i", "me", "to", "of", "and", "or", "just", "very", "really",
    "when", "while", "at", "on", "in", "for", "with", "from", "like", "are", "be", "been", "has", "have", "had",
    "bit", "this", "that", "there", "also", "but", "so", "some", "them", "they", "we", "you", "your",
}
NEGATION_WORDS = {"no", "not", "never", "dont", "doesnt", "didnt", "isnt", "nothing", "neither", "none", "nahi"}


def _stems(text):
    # the first 4 letters are enough to match "brake" with "braking", "grinds" with "grinding"
    return {word[:4] for word in text.split() if word not in FILLER_WORDS and word != "|"}


def match_option(text, options, question=""):
    """
    The option a free-text answer means: "it stays on all the time" -> "Steady, stays on all the time".
    None if no option clearly wins. Negations have to agree, so "it doesn't blink" never picks "Blinking",
    and so do numbers, so "3 years ago" doesn't pick "1 to 2 years ago".
    """
    exact = next((option for option in options if normalize(option) == text), None)
    if exact:
        return exact
    # words repeated from the question don't say anything ("pedal is soft" to "how does the pedal feel?"),
    # unless the question lists the options itself ("is it a manual or automatic?")
    option_words = set().union(*(_stems(normalize(option)) for option in options))
    words = _stems(text) - (_stems(normalize(question)) - option_words)
    negated = bool(NEGATION_WORDS & set(text.split()))
    numbers = set(re.findall(r"\d+", text))
    numbered = any(re.search(r"\d", option) for option in options)
    scores = []
    for option in options:
        normalized = normalize(option)
        # "More than 2 years ago / never" is two answers in one, either can agree with theirs
        alternatives = [set(normalize(part).split()) for part in option.split("/")]
        if all(negated != bool(NEGATION_WORDS & words_in) for words_in in alternatives):
            continue
        if numbers and numbered and not numbers & set(re.findall(r"\d+", normalized)):
            continue
        scores.append((len(words & _stems(normalized)), option))
    scores.sort(key=lambda item: item[0], reverse=True)
    if not scores or scores[0][0] == 0 or (len(scores) > 1 and scores[1][0] == scores[0][0]):
        return None
    # one shared word is only enough when that's all they said ("soft", "stays on").
    # "the lights are a bit dim" shares "lights" with "Lights or music were left on" but means something else.
    if scores[0][0] < 2 and len(words) > 1:
        return None
    return scores[0][1]


def is_yes(text):
    return bool(YES_RE.match(text)) and word_count(text) <= 8


def is_no(text):
    return bool(NO_RE.match(text)) and word_count(text) <= 8


def is_question(text, raw_text=""):
    return raw_text.strip().endswith("?") or bool(QUESTION_RE.match(text))


def wants_booking(text):
    return mentions_any(text, BOOKING_WORDS)


def is_none_of_these(text):
    # only short replies, a longer one usually explains what it is instead and is a better answer
    return word_count(text) <= 6 and mentions_any(text, NONE_OF_THESE_WORDS)


def wants_to_skip(text):
    return mentions_any(text, SKIP_WORDS)


def asks_about_cost(text):
    return mentions_any(text, COST_WORDS)


def asks_about_safety(text):
    return mentions_any(text, SAFETY_WORDS)


# questions where the answer changes over time, worth a (rationed) web search
FRESH_FACT_WORDS = (
    "price*", "cost*", "rate*", "how much", "news", "latest", "recent*", "recall*", "launch*", "new model*",
    "e20", "e27", "ethanol", "rule*", "law*", "challan*", "fine", "ban*", "banned", "policy", "subsid*", "fastag",
    "puc", "insurance", "this year", "today", "2025", "2026", "2027", "petrol pump*", "fuel quality",
)


# "which coolant should I use?" wants an answer, "why is my car overheating?" is a problem to diagnose
INFO_QUESTION_RE = re.compile(
    r"^(which|what is|what are|whats|what does|what do|how often|how long|how many|when should|when do|"
    r"should i|can i use|is it ok|is it okay|is it good|do i need|difference between|explain)\b"
)
COMPLAINT_WORDS = (
    "not", "wont", "doesnt", "didnt", "isnt", "cant", "problem*", "issue*", "noise*", "sound*", "smoke", "leak*",
    "overheat*", "stopped", "dead", "weird", "strange", "broken", "fault*", "warning", "light is on", "shak*",
    "vibrat*", "smell*", "dropped", "drop", "less", "low", "slipping", "squeal*", "grind*",
)


def is_info_question(text, raw_text=""):
    return is_question(text, raw_text) and bool(INFO_QUESTION_RE.match(text)) and not mentions_any(text, COMPLAINT_WORDS)


def needs_fresh_facts(text):
    return mentions_any(text, FRESH_FACT_WORDS)


def is_car_related(text):
    return mentions_any(text, CAR_WORDS) or mentions_any(text, ISSUE_WORDS) or mentions_vehicle(text)


def is_off_topic_task(text):
    """Things that are never ours to answer, even about a car ("write a poem about my car")."""
    return mentions_any(text, OFF_TOPIC_TASKS)


def is_off_topic(text):
    return is_off_topic_task(text) or (mentions_any(text, OFF_TOPIC_SUBJECTS) and not is_car_related(text))


LANGUAGE_WORDS = {"hindi": "hi", "hinglish": "hinglish", "english": "en"}
LANGUAGE_VERBS = ("talk*", "speak*", "reply", "answer*", "chat", "baat", "bolo", "write", "language", "please", "can you")


def language_request(text):
    """ "can you talk in hindi" -> "hi". None if the message isn't asking to switch language."""
    if word_count(text) > 10 or not (mentions_any(text, LANGUAGE_VERBS) or word_count(text) <= 3):
        return None
    for word in text.split():
        # typos too: "hinid", "hndi", "englsh"
        match = get_close_matches(word, LANGUAGE_WORDS, n=1, cutoff=0.75)
        if match:
            return LANGUAGE_WORDS[match[0]]
    return None


def triage_topic(text):
    """For vague complaints ("weird noise") figure out which clarifying question to ask."""
    for topic, question in TRIAGE_QUESTIONS.items():
        if mentions_any(text, question.patterns):
            return topic
    return None
