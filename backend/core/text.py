"""
Tiny text helpers used by the rule based parts of the bot.

Nothing fancy here, just lowercase + keyword matching with a very basic
negation check so "no grinding noise" doesn't count as "grinding".
"""

import re
from functools import lru_cache

NEGATIONS = {
    "no", "not", "never", "without", "dont", "doesnt", "didnt", "isnt", "arent",
    "wasnt", "werent", "cant", "cannot", "neither", "nor", "none", "nothing",
}

# words that start a new clause - a negation before these doesn't carry over
CLAUSE_BREAKS = {"|", "and", "but", "or", "so", "because", "when", "while", "though", "also"}

# "not giving the mileage" is a complaint about the mileage, not "no mileage".
# If one of these sits between the negation and the keyword, the keyword isn't negated.
COMPLAINT_VERBS = {
    "giving", "give", "gives", "getting", "get", "working", "work", "works", "starting", "cooling", "charging",
    "holding", "picking", "running", "doing", "coming", "taking", "going", "showing", "reaching",
}


def normalize(text):
    """
    Lowercase, drop apostrophes (won't -> wont) and turn punctuation into spaces.
    Sentence punctuation becomes a "|" token so negations don't leak across sentences.
    """
    text = (text or "").lower().replace("'", "").replace("’", "")
    text = re.sub(r"(?<=\d),(?=\d)", "", text)  # 60,000 -> 60000
    text = re.sub(r"[.!?;,\n]+", " | ", text)
    text = re.sub(r"[^a-z0-9|]+", " ", text)
    return re.sub(r"\s+", " ", text).strip(" |")


def word_count(normalized_text):
    return len([word for word in normalized_text.split() if word != "|"])


@lru_cache(maxsize=4096)
def _compile(pattern):
    # a word ending in * is a prefix ("brak*" -> brake, brakes, braking), other words
    # must match exactly. Works inside phrases too: "smell* petrol" -> "smells petrol"
    parts = []
    for word in pattern.split():
        cleaned = normalize(word.rstrip("*"))
        if cleaned:
            parts.append(re.escape(cleaned).replace(r"\ ", r"\s") + (r"\w*" if word.endswith("*") else ""))
    body = r"\s".join(parts)
    return re.compile(rf"\b{body}\b")


def _is_negated(text, start):
    preceding = text[:start].split()[-3:]
    for word in reversed(preceding):
        if word in CLAUSE_BREAKS or word in COMPLAINT_VERBS:
            return False
        if word in NEGATIONS:
            return True
    return False


def mentions(text, pattern):
    """True if `text` (already normalized) mentions `pattern` without it being negated."""
    for match in _compile(pattern).finditer(text):
        # "ac is not cooling" - the keyword is the complaint verb itself
        if match.group().split()[0] in COMPLAINT_VERBS or not _is_negated(text, match.start()):
            return True
    return False


def mentions_any(text, patterns):
    return any(mentions(text, pattern) for pattern in patterns)


def keyword_score(text, weighted_patterns):
    """Sum of weights for every pattern found in the text."""
    return sum(weight for pattern, weight in weighted_patterns.items() if mentions(text, pattern))
