"""
Web research for a problem: fuel quality news, recalls and known issues for the model.

One Gemini call with Google Search grounding, so the answer comes with real
sources. Results are cached per (problem, car, fuel) for RESEARCH_CACHE_HOURS,
so the same thing isn't searched again for every customer. See docs/AI_USAGE.md.

Mileage research runs while the customer waits (it's shown straight after the fuel
question). Everything else is started in the background once the car is known and
picked up from the cache at diagnosis time.
"""

import copy
import hashlib
import logging
import re
import threading
import time
from types import SimpleNamespace

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.utils import timezone

from core.gemini import GeminiError

logger = logging.getLogger(__name__)

# not the chat persona: with that one the notes started with "Hello there!" and ended with
# "bring your car in", in the middle of the follow-up questions
RESEARCH_SYSTEM = """You write short research notes for GarageMate, a car mechanic chatbot in India.
Output only the bullet points. No greeting, no intro line, no sign-off, no "book a mechanic" advice and
no promises about what the garage will do, the chat around your notes takes care of that.
Plain language, Indian context (rupees, km)."""

BULLET_RE = re.compile(r"^\s*([-*•]|\d+[.)])\s+")


def clean_summary(text):
    """Keep just the bullet points if the model added an intro or an outro anyway."""
    lines = [line for line in text.strip().splitlines() if line.strip()]
    bullets = [index for index, line in enumerate(lines) if BULLET_RE.match(line)]
    if not bullets:
        return text.strip()
    kept = lines[bullets[0]: bullets[-1] + 1]
    return "\n".join(BULLET_RE.sub("- ", line, count=1) if BULLET_RE.match(line) else line for line in kept)


def _cache_key(issue, conversation):
    parts = [issue.key, conversation.vehicle_make, conversation.vehicle_model, str(conversation.vehicle_year or ""), conversation.fuel_type]
    return "research:" + hashlib.sha256("|".join(parts).lower().encode()).hexdigest()


def _prompt(issue, conversation, evidence):
    car = conversation.vehicle_label or "not known yet (skip model specific issues, don't mention that it's unknown)"
    return f"""Search the web for what a car owner in India should know right now about this problem.

Car: {car}
Fuel: {conversation.fuel_type or "not known"}
Problem area: {issue.label}
What the customer told us: {evidence[:600] or "(nothing yet)"}

Look for: {issue.research_focus}.
Prefer news, official advisories and recall notices from the last 12-18 months.

Reply with 2-4 short bullet points (under 90 words in total), written to the customer: what is relevant to
their situation and what it means for them. If nothing specific turns up for this car, say so in one bullet and
give the general facts instead. Never make up a recall, a ban or a number that isn't in the sources."""


# the search model has 20 free requests a day. Once they're used up every call just fails,
# so stop trying for a while instead of adding a failed call to every reply.
PAUSE_KEY = "research:paused"
PAUSE_SECONDS = 10 * 60


def search_paused():
    return bool(cache.get(PAUSE_KEY))


def note_search_failure(exc):
    if getattr(exc, "reason", "") == "quota":
        cache.set(PAUSE_KEY, True, PAUSE_SECONDS)


def _wanted(issue, gemini):
    return settings.RESEARCH_ENABLED and bool(issue.research_focus) and gemini.enabled and not search_paused()


def start_research(issue, conversation, gemini, evidence=""):
    """
    Search in the background as soon as we know the car and the problem. A model specific
    search took 10-15s, the customer spends about that long on the remaining questions,
    so by the diagnosis it's usually waiting in the cache.
    """
    if not _wanted(issue, gemini):
        return
    key = _cache_key(issue, conversation)
    # add() is atomic, so two requests (or workers) don't both start the same search
    if cache.get(key) or not cache.add(f"{key}:running", True, settings.RESEARCH_TIMEOUT_SECONDS + 5):
        return
    # a plain copy, the request keeps changing the real conversation object
    car = SimpleNamespace(
        vehicle_make=conversation.vehicle_make,
        vehicle_model=conversation.vehicle_model,
        vehicle_year=conversation.vehicle_year,
        fuel_type=conversation.fuel_type,
        vehicle_label=conversation.vehicle_label,
    )
    if not settings.RESEARCH_IN_BACKGROUND:
        _search_and_store(issue, car, gemini, evidence, key)
        return
    # its own copy, the request carries on using the original at the same time
    client = copy.copy(gemini)
    threading.Thread(target=_search_and_store, args=(issue, car, client, evidence, key), daemon=True).start()


def _search_and_store(issue, car, gemini, evidence, key):
    try:
        _search(issue, car, gemini, evidence, key)
    finally:
        cache.delete(f"{key}:running")
        if settings.RESEARCH_IN_BACKGROUND:
            # the thread got its own connection for the cache table
            connection.close()


def _wait_for_running(key):
    deadline = time.monotonic() + settings.RESEARCH_TIMEOUT_SECONDS
    while time.monotonic() < deadline and cache.get(f"{key}:running"):
        time.sleep(0.5)
    return cache.get(key)


def research_problem(issue, conversation, gemini, evidence=""):
    """
    Returns {"summary", "sources", "queries", "searched_at", "cached"} or None when research
    is off, not useful for this issue, or Gemini isn't available.
    """
    if not _wanted(issue, gemini):
        return None

    key = _cache_key(issue, conversation)
    cached = cache.get(key)
    if cached:
        return {**cached, "cached": True}
    if cache.get(f"{key}:running"):
        # started in the background during the questions, almost done. If that search
        # failed, don't make the customer wait for a second one.
        cached = _wait_for_running(key)
        return {**cached, "cached": True} if cached else None
    return _search(issue, conversation, gemini, evidence, key)


def _search(issue, conversation, gemini, evidence, key):
    # research is a bonus: if it fails, the reply it's part of still worked, so don't flag it
    # (the failed call still shows up in the API logs)
    failure_before = getattr(gemini, "last_failure", None)
    try:
        result = gemini.research(_prompt(issue, conversation, evidence), system=RESEARCH_SYSTEM)
    except GeminiError as exc:
        logger.warning("Research failed for %s: %s", issue.key, exc)
        gemini.last_failure = failure_before
        note_search_failure(exc)
        return None

    if not result["text"] or result["text"].upper().startswith("OFF_TOPIC"):
        return None

    data = {
        "summary": clean_summary(result["text"]),
        "sources": result["sources"],
        "queries": result["queries"],
        "searched_at": timezone.now().isoformat(),
    }
    cache.set(key, data, settings.RESEARCH_CACHE_HOURS * 3600)
    return {**data, "cached": False}
