"""
Turns a conversation into a Diagnosis.

1. The rule engine scores every possible cause for the issue type using the
   signal words the customer used (see knowledge_base.py).
2. If the rules are confident we stop there, no AI call.
3. Only when the evidence is thin or ambiguous, or photos/audio were analysed,
   do we ask Gemini for a second opinion. If Gemini fails, the rule result is used.
"""

import logging
from dataclasses import dataclass

from bookings.models import Service
from core.gemini import GeminiClient, GeminiError
from core.prompts import MECHANIC_PERSONA
from core.text import keyword_score, mentions, normalize

from .knowledge_base import (
    HIGH,
    ISSUE_TYPES,
    ISSUE_TYPES_BY_KEY,
    LOW,
    MEDIUM,
    SEVERITY_ORDER,
    higher_severity,
    severity_rank,
)
from .models import Diagnosis
from .research import research_problem

logger = logging.getLogger(__name__)

MIN_ISSUE_SCORE = 2
# the top cause needs this much of the total score, and at least this many
# signal points, before we trust the rules on their own
CONFIDENT_SHARE = 0.4
CONFIDENT_MIN_SIGNAL = 3


@dataclass
class RankedCause:
    name: str
    score: float
    signal: int
    severity: str
    service_code: str = ""


def detect_issue(text):
    """Return the IssueType that best matches the text, or None."""
    normalized = normalize(text)
    best_issue, best_score = None, 0
    for issue in ISSUE_TYPES:
        score = keyword_score(normalized, issue.keywords)
        if score > best_score:
            best_issue, best_score = issue, score
    return best_issue if best_score >= MIN_ISSUE_SCORE else None


def collect_evidence(conversation):
    state = conversation.state or {}
    parts = [state.get("description", "")]
    parts.extend(state.get("answers", {}).values())
    parts.extend(state.get("media_notes", []))
    return "\n".join(part for part in parts if part)


def rank_causes(issue, evidence, fuel_type=""):
    normalized = normalize(evidence)
    ranked = []
    for cause in issue.causes:
        if fuel_type and cause.fuels and fuel_type not in cause.fuels:
            # no glow plugs on a CNG car, no spark plugs on a diesel
            continue
        signal = keyword_score(normalized, cause.signals)
        ranked.append(RankedCause(cause.name, cause.prior + signal, signal, cause.severity, cause.service_code))
    ranked.sort(key=lambda cause: cause.score, reverse=True)
    return ranked


def to_likelihoods(ranked, limit=3):
    total = sum(cause.score for cause in ranked) or 1
    return [{"name": cause.name, "likelihood": round(cause.score / total, 2)} for cause in ranked[:limit]]


def assess_severity(issue, top_cause, normalized_evidence):
    severity = top_cause.severity or issue.severity
    for pattern, level in issue.escalations.items():
        if mentions(normalized_evidence, pattern):
            severity = higher_severity(severity, level)
    return severity


def is_confident(ranked):
    total = sum(cause.score for cause in ranked) or 1
    top = ranked[0]
    clear_winner = len(ranked) == 1 or top.score - ranked[1].score >= 1
    return top.signal >= CONFIDENT_MIN_SIGNAL and top.score / total >= CONFIDENT_SHARE and clear_winner


def _lower_first(text):
    # keep acronyms like "ABS" or "AC" as they are
    if len(text) > 1 and text[1].isupper():
        return text
    return text[:1].lower() + text[1:]


def rules_summary(conversation, ranked):
    car = f"your {conversation.vehicle_label}" if conversation.vehicle_label else "your car"
    summary = f"From what you've described, my best guess for {car}: {_lower_first(ranked[0].name)}."
    others = [_lower_first(cause.name) for cause in ranked[1:3] if cause.signal > 0]
    if others:
        summary += f" It could also be {' or '.join(others)}, so the mechanic should rule that out too."
    else:
        summary += " A proper inspection will confirm it."
    return summary


DIAGNOSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "probable_causes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "likelihood": {"type": "number"}},
                "required": ["name", "likelihood"],
            },
        },
        "severity": {"type": "string", "enum": SEVERITY_ORDER},
        "advice": {"type": "string"},
    },
    "required": ["title", "summary", "probable_causes", "severity", "advice"],
}


def _review_prompt(conversation, issue, ranked, evidence):
    ranking = "\n".join(f"{i}. {cause.name} (score {cause.score:.1f})" for i, cause in enumerate(ranked[:5], start=1))
    return f"""A customer described a problem with their car. Our rule engine already narrowed it down.
Review the evidence and give your final diagnosis.

Vehicle: {conversation.vehicle_label or "unknown"}
Fuel: {conversation.fuel_type or "unknown"}
Odometer: {f"{conversation.odometer_km} km" if conversation.odometer_km else "unknown"}
Problem area: {issue.label}

What the customer told us (and what we saw in any photos / recordings):
{evidence}

Rule engine ranking (keyword based, may be wrong):
{ranking}

Return JSON with:
- title: the single most likely cause, max 8 words, without the car name
- summary: 2-3 sentences to the customer explaining what is probably wrong and why you think so
- probable_causes: up to 4 causes, most likely first. Likelihoods are between 0 and 1 and should add up to about 1. Prefer causes from the ranking, only add a new one if the evidence clearly points to it
- severity: low, medium, high or critical
- advice: 1-2 sentences on what to do until a mechanic inspects the car
Only use facts from the evidence above, don't assume symptoms the customer didn't mention."""


def _ai_review(gemini, conversation, issue, ranked, evidence, rules_severity):
    data = gemini.generate_json(
        _review_prompt(conversation, issue, ranked, evidence),
        schema=DIAGNOSIS_SCHEMA,
        system=MECHANIC_PERSONA,
        purpose="diagnosis second opinion",
    )

    causes = []
    for item in data.get("probable_causes") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()[:120]
        try:
            likelihood = min(max(float(item.get("likelihood", 0)), 0.0), 1.0)
        except (TypeError, ValueError):
            continue
        if name:
            causes.append({"name": name, "likelihood": round(likelihood, 2)})

    title = str(data.get("title", "")).strip()[:150]
    summary = str(data.get("summary", "")).strip()
    if not causes or not title or not summary:
        raise GeminiError("Gemini diagnosis was missing fields")

    severity = data.get("severity") if data.get("severity") in SEVERITY_ORDER else rules_severity
    # the model is allowed to raise severity, but never to talk down a safety flag from the rules
    if severity_rank(rules_severity) >= severity_rank(HIGH):
        severity = higher_severity(severity, rules_severity)

    return {
        "title": title,
        "summary": summary,
        "probable_causes": causes[:4],
        "severity": severity,
        "advice": str(data.get("advice", "")).strip() or issue.advice,
    }


def build_diagnosis(conversation, gemini=None, research=None):
    """
    Create and return a Diagnosis for the conversation's current issue.
    `research` is web research already done during the questions (mileage), otherwise
    it's looked up here when we know the car model (recalls / known issues).
    """
    issue = ISSUE_TYPES_BY_KEY.get(conversation.issue_category)
    if issue is None:
        raise ValueError("Conversation doesn't have an issue category yet")

    evidence = collect_evidence(conversation)
    ranked = rank_causes(issue, evidence, conversation.fuel_type)
    severity = assess_severity(issue, ranked[0], normalize(evidence))

    result = {
        "title": ranked[0].name,
        "summary": rules_summary(conversation, ranked),
        "probable_causes": to_likelihoods(ranked),
        "severity": severity,
        "advice": issue.advice,
    }
    source = Diagnosis.Source.RULES

    has_media = bool((conversation.state or {}).get("media_notes"))
    gemini = gemini or GeminiClient()
    if gemini.enabled and (has_media or not is_confident(ranked)):
        try:
            result = _ai_review(gemini, conversation, issue, ranked, evidence, severity)
            source = Diagnosis.Source.AI
        except GeminiError as exc:
            logger.warning("AI review failed, using rule based diagnosis: %s", exc)

    if research is None and not issue.research_early and conversation.vehicle_model:
        found = research_problem(issue, conversation, gemini, evidence)
        if found:
            research = {key: found[key] for key in ("summary", "sources", "queries", "searched_at")}

    # the top cause from the rules decides the service, even when Gemini reworded the diagnosis
    service_code = ranked[0].service_code or issue.service_code
    service = Service.objects.filter(code=service_code, is_active=True).first()
    return Diagnosis.objects.create(
        conversation=conversation,
        category=issue.key,
        recommended_service=service,
        estimated_cost_min=service.price_min if service else None,
        estimated_cost_max=service.price_max if service else None,
        safe_to_drive=result["severity"] in (LOW, MEDIUM),
        source=source,
        research=research or {},
        **result,
    )


def format_rupees(amount):
    return f"₹{amount:,}"


def diagnosis_message(diagnosis):
    """Plain text version of a diagnosis, stored as the chat message content."""
    lines = [f"**Diagnosis: {diagnosis.title}**", "", diagnosis.summary]
    service = diagnosis.recommended_service
    if service:
        lines += [
            "",
            f"**What I'd recommend:** {service.name} "
            f"(roughly {format_rupees(diagnosis.estimated_cost_min)} - {format_rupees(diagnosis.estimated_cost_max)}, "
            "final price after inspection).",
        ]
    if diagnosis.advice:
        lines += ["", diagnosis.advice]
    lines += ["", "Would you like me to book a mechanic for this?"]
    return "\n".join(lines)
