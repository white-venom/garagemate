"""
The conversation flow. Basically a small state machine:

    new -> gathering (follow-up questions) -> diagnosed -> booked

Rules decide what to say next. Gemini only gets called for:
  - looking at photos / audio / video (media.py)
  - understanding a message the rules can't (Hindi / Hinglish, typos, "none of these") (understand.py)
  - open ended car questions the knowledge base can't answer
  - web research: fuel news, recalls, known issues for the model (diagnosis/research.py)
  - a second opinion on the diagnosis when the rules aren't sure (diagnosis/engine.py)
  - translating replies when the conversation isn't in English (language.py)
Everything is explained in docs/AI_USAGE.md.
"""

import hashlib
import logging
from dataclasses import dataclass, field
from functools import cached_property

from django.conf import settings
from django.core.cache import cache

from bookings.models import Service
from core.gemini import GeminiClient, GeminiError
from core.prompts import MECHANIC_PERSONA
from core.text import keyword_score, mentions_any, normalize, word_count
from customers.services import find_mentioned_car, get_customer
from diagnosis.engine import build_diagnosis, detect_issue, diagnosis_message, format_rupees
from diagnosis.knowledge_base import (
    ISSUE_TYPES_BY_KEY,
    SAFETY_ALERTS,
    TRIAGE_QUESTIONS,
    VEHICLE_QUESTION,
    Question,
)
from diagnosis.models import Diagnosis
from diagnosis.research import note_search_failure, research_problem, search_paused, start_research

from ..models import Conversation, Message
from . import intents, replies
from .language import localize_diagnosis, option_map, translate
from .media import analyse_attachment
from .understand import looks_non_english, understand
from .vehicle import extract_vehicle_details

logger = logging.getLogger(__name__)

AI_HISTORY_MESSAGES = 8
AI_ANSWER_CACHE_SECONDS = 60 * 60 * 24
MAX_MEDIA_NOTES = 5
# "Is this about your Swift?" - asked instead of the vehicle question when the customer saved cars
SAVED_CAR_KEY = "saved_car"

Stage = Conversation.Stage
Kind = Message.Kind


def gives_car_details(raw):
    """ "2016 wagon r, 1.1 lakh km" - the car, not an answer. Just "my swift" could still be an answer."""
    details = extract_vehicle_details(raw)
    return bool(details.keys() & {"make", "model"}) and bool(details.keys() & {"year", "odometer_km", "registration_number"})


def with_own_words(option, text):
    """ "Nothing else (but I filled at a new pump)" tells the mechanic more than just the button."""
    return option if normalize(option) == normalize(text) else f"{option} ({text})"


@dataclass
class BotReply:
    content: str
    kind: str = Kind.TEXT
    quick_replies: list = field(default_factory=list)
    action: str = ""
    diagnosis: Diagnosis = None
    used_ai: bool = False
    # why Gemini couldn't help with this reply (quota, overloaded...), empty if it wasn't needed or worked
    ai_error: str = ""
    # web pages a researched answer is based on
    sources: list = field(default_factory=list)


class MechanicBot:
    def __init__(self, conversation, gemini=None):
        self.conversation = conversation
        self.gemini = gemini or GeminiClient()
        self.state = dict(conversation.state or {})
        self.used_ai = False
        # set once Gemini has interpreted the current message, so it's never asked twice
        self.understood = None

    @property
    def issue(self):
        return ISSUE_TYPES_BY_KEY.get(self.conversation.issue_category)

    @cached_property
    def customer(self):
        return get_customer(self.conversation.client_id)

    @cached_property
    def saved_cars(self):
        return list(self.customer.cars.all()) if self.customer else []

    def reply(self, text, attachments=()):
        typed = (text or "").strip()
        raw = self._untranslate_option(typed)
        tapped_button = raw != typed

        # Hindi / Hinglish: get an English version first so the rules can do their job. Once the chat
        # is in Hindi / Hinglish every typed message goes this way, the keyword rules only know English.
        in_english = self.conversation.language == Conversation.Language.ENGLISH
        if raw and not tapped_button and (looks_non_english(raw) or not in_english):
            self.understood = self._understand(raw)
            if self.understood:
                self._follow_language(self.understood)
                raw = self.understood["english"]

        normalized = normalize(raw)
        preface = []

        self._remember_vehicle(raw)

        alert = self._safety_alert(normalized)
        if alert:
            preface.append(alert)

        media_notes = self._look_at_media(attachments, raw, preface)
        if self.understood and self.understood["intent"] in ("change_language", "none_of_the_options", "off_topic"):
            reply = self._act_on(self.understood)
        else:
            reply = self._route(raw, normalized, media_notes)

        if preface:
            reply.content = "\n\n".join([*preface, reply.content])
        return self._finish(reply)

    def diagnose_now(self):
        """Skip whatever follow-up questions are left and diagnose (POST /api/diagnosis/)."""
        return self._finish(self._diagnose())

    def _finish(self, reply):
        self._translate(reply)
        reply.used_ai = reply.used_ai or self.used_ai
        reply.ai_error = getattr(self.gemini, "last_failure", None) or ""
        self._save()
        return reply

    # ---- routing -------------------------------------------------------

    def _route(self, raw, normalized, media_notes):
        pending = self.state.get("pending")
        media_text = " ".join(note["observations"] for note in media_notes)

        if not normalized:
            return self._handle_media_only(pending, media_notes, media_text)

        language = intents.language_request(normalized)
        if language:
            return self._switch_language(language)

        if pending:
            return self._handle_answer(pending, raw, normalized)

        if self.conversation.stage in (Stage.DIAGNOSED, Stage.BOOKED):
            reply = self._handle_after_diagnosis(raw, normalized)
            if reply:
                return reply

        issue = detect_issue(f"{raw} {media_text}")
        if issue and intents.asks_about_cost(normalized) and intents.is_question(normalized, raw):
            return self._price_answer(issue)
        if issue and not media_text and intents.is_info_question(normalized, raw) and self.gemini.enabled:
            # "which coolant should I use?" mentions coolant but nothing is wrong with the car
            return self._answer_general_question(raw)
        if issue and issue.key == self.conversation.issue_category and self.conversation.stage in (Stage.DIAGNOSED, Stage.BOOKED):
            return self._add_after_diagnosis(f"{raw} {media_text}".strip())
        if issue:
            return self._start_issue(issue, f"{raw} {media_text}".strip())

        if intents.wants_booking(normalized):
            return self._offer_booking()
        if intents.is_greeting(normalized):
            customer = self.customer
            car = self.saved_cars[0].short_name if self.saved_cars else ""
            return BotReply(
                replies.greeting(customer.first_name if customer else "", car), quick_replies=replies.STARTER_PROMPTS
            )
        if intents.is_thanks(normalized):
            return BotReply(replies.THANKS)
        if intents.is_off_topic_task(normalized):
            # "write me a poem" - never ours, no need to ask the AI
            return self._reject()

        topic = intents.triage_topic(normalized)
        if topic:
            return self._ask_triage(topic, raw)

        if intents.is_car_related(normalized) or media_text:
            if intents.is_question(normalized, raw):
                return self._answer_general_question(raw)
            return self._second_chance(raw) or BotReply(replies.NEED_MORE_DETAIL, quick_replies=replies.STARTER_PROMPTS)

        # the rules don't get it - maybe a typo, Hindi, or "none of these". Ask before rejecting.
        second = self._second_chance(raw)
        if second:
            return second
        if intents.is_off_topic(normalized):
            return self._reject()
        if word_count(normalized) <= 3:
            return BotReply(replies.NUDGE, quick_replies=replies.STARTER_PROMPTS)
        if self.conversation.messages.count() > 1:
            # we're already talking about a car, don't shut the door on an unclear message
            return BotReply(replies.NONE_OF_THESE, quick_replies=replies.STARTER_PROMPTS)
        return self._reject()

    def _second_chance(self, raw):
        """Ask Gemini what an unclear message means and act on it. None if that didn't help."""
        if self.understood is not None or not self.gemini.enabled:
            return None
        self.understood = self._understand(raw) or {}
        if not self.understood:
            return None
        self._follow_language(self.understood)
        return self._act_on(self.understood)

    def _act_on(self, understood):
        intent = understood["intent"]
        english = understood["english"]
        requested = understood.get("requested_language")

        if intent == "change_language" and requested in ("en", "hi", "hinglish"):
            return self._switch_language(requested)
        pending = self.state.get("pending")
        if intent == "off_topic":
            return self._reject(reprompt=pending)
        if intent == "none_of_the_options":
            return self._none_of_these(pending)
        if intent == "car_question":
            return self._reask(self._answer_general_question(english), pending)
        same_problem = understood.get("category") in ("unknown", self.conversation.issue_category)
        if self.conversation.stage in (Stage.DIAGNOSED, Stage.BOOKED) and intent in ("answer", "car_problem") and same_problem:
            # "it stood unused for 3 days" after the diagnosis: more to go on, not a new problem
            normalized = normalize(english)
            after = self._handle_after_diagnosis(english, normalized)
            if after:
                return after
            if intent == "car_problem" or self._adds_evidence(english):
                return self._add_after_diagnosis(english)
            # "can't remember", "ok" - nothing to update the diagnosis with
            return BotReply(replies.NOTED, quick_replies=["Book a mechanic"])
        if intent == "car_problem":
            issue = ISSUE_TYPES_BY_KEY.get(understood.get("category")) or detect_issue(english)
            if issue:
                return self._start_issue(issue, english)
            # a real problem outside our checklist - let the AI mechanic answer it
            return self._answer_general_question(english)
        # greeting / thanks / yes / no / answer: the English version goes through the rules again
        return self._route(english, normalize(english), [])

    def _none_of_these(self, pending):
        if pending == SAVED_CAR_KEY:
            return self._handle_car_choice("A different car", "a different car")
        if pending and not pending.startswith("triage:"):
            # "none of these" is a perfectly good answer, note it and move on
            self.state.setdefault("answers", {})[pending] = "None of these"
            return self._next_step(intro=replies.NOTED_NONE)
        # nothing asked, or the noise/smell/light doesn't fit the groups we offered
        self.state["pending"] = None
        if self.conversation.stage == Stage.GATHERING and not self.issue:
            self.conversation.stage = Stage.NEW
        return BotReply(replies.NONE_OF_THESE)

    def _handle_media_only(self, pending, media_notes, media_text):
        if pending:
            return self._ask_again(pending)
        hinted = next((note["system"] for note in media_notes if note["system"] in ISSUE_TYPES_BY_KEY), None)
        issue = ISSUE_TYPES_BY_KEY.get(hinted) or detect_issue(media_text)
        if issue:
            return self._start_issue(issue, media_text)
        return BotReply(replies.ASK_WHAT_PROBLEM, quick_replies=replies.STARTER_PROMPTS)

    def _handle_answer(self, pending, raw, normalized):
        if intents.is_off_topic_task(normalized) or (
            intents.is_off_topic(normalized) and not self._second_chance_is_answer(raw, pending)
        ):
            return self._reject(reprompt=pending)

        if intents.is_none_of_these(normalized):
            return self._none_of_these(pending)

        question = self._question_by_key(pending)
        if question:
            resolved = self._resolve_answer(pending, question, raw, normalized)
            if isinstance(resolved, BotReply):
                return resolved
            raw, normalized = resolved, normalize(resolved)

        if pending.startswith("triage:"):
            return self._handle_triage_answer(pending.split(":", 1)[1], raw)

        if pending == SAVED_CAR_KEY:
            return self._handle_car_choice(raw, normalized)

        if intents.wants_booking(normalized) and not detect_issue(raw):
            return self._offer_booking()

        if intents.wants_to_skip(normalized):
            self.state["pending"] = None
            return self._diagnose()

        if pending == VEHICLE_QUESTION.key and not extract_vehicle_details(raw, answering=True):
            # they skipped the car question and told us more about the problem instead,
            # keep it with the description so we don't ask about it again
            self.state["description"] = f"{self.state.get('description', '')}. {raw}".strip(". ")

        self.state.setdefault("answers", {})[pending] = raw
        return self._next_step()

    @staticmethod
    def _looks_like_answer(question, raw, normalized):
        options = [normalize(option) for option in question.options]
        if any(option and (option in normalized or (len(normalized) > 3 and normalized in option)) for option in options):
            return True
        if intents.is_question(normalized, raw):
            return False
        if question.key == VEHICLE_QUESTION.key:
            return bool(extract_vehicle_details(raw, answering=True)) or mentions_any(normalized, ("rather not", "dont know", "not sure"))
        # a sentence that fits none of the options might be an answer, more detail about the problem, or a
        # question for us. Mentioning the car doesn't settle it ("battery is 4 years old" to "what happens
        # when you turn the key?"), so let Gemini look at it. Without AI it's kept as the answer anyway.
        return word_count(normalized) <= 2

    def _interpret(self, raw, question):
        """Gemini's reading of the message, asked at most once per message. None without AI."""
        if self.understood is None and self.gemini.enabled:
            self.understood = self._understand(raw, question) or {}
            self._follow_language(self.understood)
        return self.understood or None

    def _resolve_answer(self, pending, question, raw, normalized):
        """
        What to save as the answer to `question`, or a reply when the message isn't an answer at all
        ("can you talk in hindi", "what is e20?", more detail about the problem).
        """
        option = intents.match_option(normalized, question.options, question.text)
        if option:
            return with_own_words(option, raw)
        if question.key != VEHICLE_QUESTION.key and gives_car_details(raw):
            # "wagon r 2016 cng, 1.1 lakh km" while we asked about the lights: the car is saved
            # already (_remember_vehicle), the question still needs an answer
            return self._more_detail(pending, raw, intro=replies.CAR_NOTED)

        understood = self.understood
        if not understood and not self._looks_like_answer(question, raw, normalized):
            understood = self._interpret(raw, question)
        if not understood:
            return raw

        intent, english = understood["intent"], understood["english"]
        same_problem = understood.get("category") in ("unknown", self.conversation.issue_category)
        answered = set(self.state.get("answers", {})) - {VEHICLE_QUESTION.key, SAVED_CAR_KEY}
        # a related symptom halfway through ("pickup is also less" while we talk about black smoke) belongs
        # to this case. Only right at the start can it mean we guessed the wrong problem.
        if intent == "car_problem" and (same_problem or answered):
            if self.state.get("reasked") == pending:
                # asked twice already, take what they said as the answer
                return english
            return self._more_detail(pending, english)
        if intent not in ("answer", "yes", "no", "greeting", "thanks"):
            # a question for us, a language switch, off topic, or a different problem altogether
            return self._act_on(understood)
        picked = understood.get("option")
        return with_own_words(picked, english) if picked in question.options else english

    def _more_detail(self, pending, text, intro=replies.GOT_IT):
        # they told us more about the problem instead of answering: keep it and ask again,
        # the extra detail might even answer this question (skip_if) and move us on
        self.state["description"] = f"{self.state.get('description', '')}. {text}".strip(". ")
        self.state["reasked"] = pending
        return self._next_step(intro=intro)

    def _second_chance_is_answer(self, raw, pending):
        """The rules think it's off-topic. Could it still be an answer to the question we asked?"""
        if self.understood is not None or not self.gemini.enabled:
            return bool(self.understood and self.understood.get("intent") == "answer")
        question = self._question_by_key(pending)
        self.understood = self._understand(raw, question) or {}
        return self.understood.get("intent") in ("answer", "none_of_the_options", "car_problem")

    def _handle_car_choice(self, raw, normalized):
        self.state.setdefault("answers", {})[SAVED_CAR_KEY] = raw
        conversation = self.conversation
        # "Yes, my Swift" / picking one of the cars is already handled by _remember_vehicle,
        # and so is typing a different car's details straight away
        if conversation.car_id or conversation.vehicle_make or conversation.vehicle_model:
            return self._next_step()
        if len(self.saved_cars) == 1 and intents.is_yes(normalized):
            self._use_car(self.saved_cars[0])
            return self._next_step()
        # "A different car"
        self.state["pending"] = VEHICLE_QUESTION.key
        return BotReply(VEHICLE_QUESTION.text, kind=Kind.QUESTION, quick_replies=list(VEHICLE_QUESTION.options))

    def _adds_evidence(self, text):
        """True if the text matches anything the rules score for this problem."""
        issue = self.issue
        normalized = normalize(text)
        return bool(issue) and any(keyword_score(normalized, cause.signals) for cause in issue.causes)

    def _add_after_diagnosis(self, text):
        self.state["description"] = f"{self.state.get('description', '')}. {text}".strip(". ")
        if self.conversation.stage == Stage.BOOKED:
            return BotReply(replies.ADDED_FOR_MECHANIC)
        reply = self._diagnose()
        reply.content = f"{replies.UPDATED_DIAGNOSIS}\n\n{reply.content}"
        return reply

    def _handle_after_diagnosis(self, raw, normalized):
        diagnosis = self._latest_diagnosis()
        if intents.wants_booking(normalized) or intents.is_yes(normalized):
            return self._offer_booking(diagnosis)
        if intents.is_no(normalized):
            return BotReply(replies.BOOKING_DECLINED)
        if intents.is_thanks(normalized):
            return BotReply(replies.THANKS)
        if diagnosis and intents.asks_about_cost(normalized) and not detect_issue(raw):
            return self._cost_answer(diagnosis)
        if diagnosis and intents.asks_about_safety(normalized):
            return self._safety_answer(diagnosis)
        return None

    # ---- follow-up questions ---------------------------------------------

    def _start_issue(self, issue, description):
        conversation = self.conversation
        first_issue = not conversation.issue_category
        conversation.issue_category = issue.key
        conversation.stage = Stage.GATHERING
        self.state = {
            "description": description,
            "answers": {},
            "pending": None,
            "media_notes": self.state.get("media_notes", []),
            "vehicle_asked": self.state.get("vehicle_asked", False),
        }
        if first_issue or not conversation.title:
            conversation.title = self._make_title(issue)
        return self._next_step(intro=issue.intro)

    def _next_step(self, intro=""):
        # mileage and the like: look things up as soon as we know the fuel, before more questions
        notes, sources = self._early_research()
        self._prefetch_research()
        lead = "\n\n".join(part for part in (intro, *notes) if part)

        question = self._next_question()
        if question is None:
            self.state["pending"] = None
            reply = self._diagnose()
            if lead:
                reply.content = f"{lead}\n\n{reply.content}"
            reply.sources = sources or reply.sources
            return reply

        self.state["pending"] = question.key
        if question.key in (VEHICLE_QUESTION.key, SAVED_CAR_KEY):
            self.state["vehicle_asked"] = True
        content = f"{lead}\n\n{question.text}" if lead else question.text
        return BotReply(content, kind=Kind.QUESTION, quick_replies=list(question.options), sources=sources)

    def _evidence(self):
        state = self.state
        parts = [state.get("description", ""), *state.get("answers", {}).values(), *state.get("media_notes", [])]
        return normalize(" | ".join(part for part in parts if part))

    def _next_question(self):
        issue = self.issue
        if issue is None:
            return None
        answers = self.state.get("answers", {})
        evidence = self._evidence()
        remaining = [question for question in issue.questions if self._should_ask(question, answers, evidence)]

        vehicle_known = self.conversation.vehicle_make or self.conversation.vehicle_model
        if not vehicle_known and not self.state.get("vehicle_asked"):
            if self.saved_cars:
                # one tap to confirm, so ask it first
                remaining.insert(0, self._saved_car_question())
            else:
                # ask about the car after the first symptom question, feels less like a form that way
                symptom_answered = any(question.key in answers for question in issue.questions)
                remaining.insert(0 if symptom_answered else 1, VEHICLE_QUESTION)
        return remaining[0] if remaining else None

    def _should_ask(self, question, answers, evidence):
        if question.key in answers:
            return False
        if question.skip_when_known and getattr(self.conversation, question.skip_when_known):
            return False
        if question.skip_if and mentions_any(evidence, question.skip_if):
            return False
        return not question.only_if or mentions_any(evidence, question.only_if)

    def _early_research(self):
        issue = self.issue
        if not issue or not issue.research_early or self.state.get("research_done") or not self.conversation.fuel_type:
            return [], []
        self.state["research_done"] = True
        found = research_problem(issue, self.conversation, self.gemini, self.state.get("description", ""))
        if found:
            self.used_ai = self.used_ai or not found.get("cached")
            self.state["research"] = {key: found[key] for key in ("summary", "sources", "queries", "searched_at")}
            intro = replies.RESEARCH_INTRO.format(fuel=self.conversation.fuel_type)
            return [f"{intro}\n\n{found['summary']}\n\n{replies.RESEARCH_OUTRO}"], found["sources"]
        # no AI / quota gone: fall back to what we know without searching
        note = replies.FUEL_NOTES.get(self.conversation.fuel_type)
        return ([note] if note else []), []

    def _prefetch_research(self):
        # recalls / known issues for this model, ready by the time we diagnose
        issue = self.issue
        if not issue or issue.research_early or self.state.get("research_started") or not self.conversation.vehicle_model:
            return
        self.state["research_started"] = True
        start_research(issue, self.conversation, self.gemini, self.state.get("description", ""))

    def _saved_car_question(self):
        cars = self.saved_cars
        if len(cars) == 1:
            car = cars[0]
            return Question(SAVED_CAR_KEY, f"Is this about your {car.label}?", (f"Yes, my {car.short_name}", "A different car"))
        return Question(SAVED_CAR_KEY, "Which of your cars is this about?", (*[car.label for car in cars[:4]], "A different car"))

    def _question_by_key(self, key):
        if key == VEHICLE_QUESTION.key:
            return VEHICLE_QUESTION
        if key == SAVED_CAR_KEY:
            return self._saved_car_question()
        issue = self.issue
        if issue:
            for question in issue.questions:
                if question.key == key:
                    return question
        return None

    def _ask_again(self, pending):
        if pending.startswith("triage:"):
            triage = TRIAGE_QUESTIONS[pending.split(":", 1)[1]]
            return BotReply(triage.text, kind=Kind.QUESTION, quick_replies=[label for label, _ in triage.options])
        question = self._question_by_key(pending)
        if question is None:
            self.state["pending"] = None
            return BotReply(replies.NEED_MORE_DETAIL)
        return BotReply(f"Thanks. {question.text}", kind=Kind.QUESTION, quick_replies=list(question.options))

    def _reask(self, reply, pending):
        """A side question got answered in the middle of the follow-ups, put the open question back."""
        question = self._question_by_key(pending) if pending and not pending.startswith("triage:") else None
        if question is None or reply.kind == Kind.REJECTION:
            return reply
        reply.content = f"{reply.content}\n\nComing back to your car: {question.text}"
        reply.kind = Kind.QUESTION
        reply.quick_replies = list(question.options)
        return reply

    def _ask_triage(self, topic, raw):
        triage = TRIAGE_QUESTIONS[topic]
        self.conversation.stage = Stage.GATHERING
        self.state.update({"description": raw, "answers": {}, "pending": f"triage:{topic}"})
        return BotReply(
            f"{replies.TRIAGE_INTRO} {triage.text}",
            kind=Kind.QUESTION,
            quick_replies=[label for label, _ in triage.options],
        )

    def _handle_triage_answer(self, topic, raw):
        self.state["pending"] = None
        description = f"{self.state.get('description', '')}. {raw}".strip(". ")

        triage = TRIAGE_QUESTIONS.get(topic)
        picked = normalize(raw)
        issue = None
        if triage:
            labels = dict(triage.options)
            issue = ISSUE_TYPES_BY_KEY.get(labels.get(intents.match_option(picked, labels, triage.text)))
        issue = issue or detect_issue(raw) or detect_issue(description)

        if issue:
            return self._start_issue(issue, description)
        self.conversation.stage = Stage.NEW
        return BotReply(replies.NEED_MORE_DETAIL, quick_replies=replies.STARTER_PROMPTS)

    # ---- language ----------------------------------------------------------

    def _understand(self, raw, question=None):
        pending = self.state.get("pending")
        if question is None and pending and not pending.startswith("triage:"):
            question = self._question_by_key(pending)
        last_bot = self.conversation.messages.filter(role=Message.Role.ASSISTANT).order_by("-created_at").first()
        understood = understand(
            self.gemini,
            raw,
            question=question.text if question else None,
            options=question.options if question else (),
            last_bot_message=last_bot.content if last_bot else "",
        )
        self.used_ai = self.used_ai or bool(understood)
        return understood

    def _follow_language(self, understood):
        # somebody writing in Hindi / Hinglish gets answers in the same language
        written_in = understood.get("language")
        if written_in in ("hi", "hinglish") and self.conversation.language == Conversation.Language.ENGLISH:
            self.conversation.language = written_in

    def _switch_language(self, language):
        if language != "en" and not self.gemini.enabled:
            return BotReply(replies.ENGLISH_ONLY)
        self.conversation.language = language
        content = replies.LANGUAGE_SWITCHED.format(language=replies.LANGUAGE_NAMES[language])
        pending = self.state.get("pending")
        question = self._question_by_key(pending) if pending and not pending.startswith("triage:") else None
        if question:
            return BotReply(f"{content}\n\n{question.text}", kind=Kind.QUESTION, quick_replies=list(question.options))
        return BotReply(content, quick_replies=replies.STARTER_PROMPTS)

    def _translate(self, reply):
        language = self.conversation.language
        if language == Conversation.Language.ENGLISH or not reply.content:
            self.state.pop("option_map", None)
            return
        result = translate(self.gemini, reply.content, list(reply.quick_replies), language)
        if not result:
            self.state.pop("option_map", None)
            return
        text, options, fresh = result
        self.used_ai = self.used_ai or fresh
        self.state["option_map"] = option_map(reply.quick_replies, options)
        reply.content, reply.quick_replies = text, options

    def _untranslate_option(self, raw):
        """Tapped a translated quick reply? Give the rules the original English option."""
        return self.state.get("option_map", {}).get(normalize(raw), raw)

    # ---- diagnosis & booking ---------------------------------------------

    def _diagnose(self):
        # the diagnosis reads the evidence from the conversation, give it what we have right now
        # (the latest answer / detail isn't saved to it until the end of the request)
        self.conversation.state = self.state
        diagnosis = build_diagnosis(self.conversation, gemini=self.gemini, research=self.state.get("research"))
        if self.conversation.language != Conversation.Language.ENGLISH:
            diagnosis.localized = localize_diagnosis(self.gemini, diagnosis, self.conversation.language)
            if diagnosis.localized:
                diagnosis.save(update_fields=["localized"])
        self.conversation.stage = Stage.DIAGNOSED
        self.state["pending"] = None
        researched = bool(diagnosis.research) and not self.state.get("research")
        return BotReply(
            diagnosis_message(diagnosis),
            kind=Kind.DIAGNOSIS,
            diagnosis=diagnosis,
            quick_replies=["Yes, book a mechanic", "Not right now"],
            used_ai=diagnosis.source == Diagnosis.Source.AI or researched,
        )

    def _latest_diagnosis(self):
        return self.conversation.diagnoses.select_related("recommended_service").first()

    def _offer_booking(self, diagnosis=None):
        if diagnosis and diagnosis.recommended_service:
            content = (
                f"Great, let's get a mechanic on it. I've pre-selected **{diagnosis.recommended_service.name}**. "
                "Just pick a date, a time slot and whether you want to bring the car in or have us come to you."
            )
        else:
            content = (
                "Sure. If you're not sure what's wrong, a general inspection is a good start. You can also describe "
                "the problem first and I'll suggest the right service."
            )
        return BotReply(content, kind=Kind.BOOKING_PROMPT, action="open_booking")

    def _cost_answer(self, diagnosis):
        service = diagnosis.recommended_service
        if not service:
            return BotReply("The mechanic will give you an exact quote after inspecting the car, before starting any work.")
        car = self.conversation.vehicle_label or "your car"
        return BotReply(
            f"For {service.name.lower()} you're usually looking at {format_rupees(diagnosis.estimated_cost_min)} - "
            f"{format_rupees(diagnosis.estimated_cost_max)}. The final price depends on the parts needed for {car}, "
            "and the mechanic confirms it with you before starting any work.\n\nWant me to book it?",
            quick_replies=["Yes, book a mechanic", "Not right now"],
        )

    def _price_answer(self, issue):
        service = self._service_for(issue)
        if not service:
            return self._start_issue(issue, "")
        return BotReply(
            f"{service.name} usually costs between {format_rupees(service.price_min)} and "
            f"{format_rupees(service.price_max)} with us. The exact amount depends on the car and the parts needed.\n\n"
            "Is something wrong with the car right now? Describe it and I'll help figure out what's needed.",
            quick_replies=["Book a mechanic"],
        )

    def _safety_answer(self, diagnosis):
        if diagnosis.safe_to_drive:
            content = "It should be okay for short, gentle drives, but don't leave it too long."
        else:
            content = (
                "Honestly, I wouldn't drive it until it's been checked. We can send a mechanic to you or pick the car up."
            )
        if diagnosis.advice:
            content += f" {diagnosis.advice}"
        return BotReply(content, quick_replies=["Book a mechanic"])

    @staticmethod
    def _service_for(issue):
        return Service.objects.filter(code=issue.service_code, is_active=True).first()

    # ---- AI answers ------------------------------------------------------

    def _answer_general_question(self, raw):
        if not self.gemini.enabled:
            return BotReply(replies.NO_AI_FOR_QUESTIONS, quick_replies=replies.STARTER_PROMPTS)

        diagnosis = self._latest_diagnosis()
        car = self.conversation.vehicle_label
        cache_key = "answer:" + hashlib.sha256(
            f"{normalize(raw)}|{car}|{self.conversation.fuel_type}|{diagnosis.title if diagnosis else ''}".encode()
        ).hexdigest()

        answer = cache.get(cache_key)
        if answer is None:
            answer = self._ask_ai(self._question_prompt(raw, car, diagnosis), search=intents.needs_fresh_facts(normalize(raw)))
            if answer is None:
                return BotReply(replies.AI_UNAVAILABLE)
            self.used_ai = True
            cache.set(cache_key, answer, AI_ANSWER_CACHE_SECONDS)

        if answer["text"].strip().upper().startswith("OFF_TOPIC"):
            return self._reject()
        return BotReply(answer["text"].strip(), sources=answer.get("sources", []))

    def _ask_ai(self, prompt, search=False):
        """
        Answer with web search when the question needs current facts (prices, fuel news, rules...), a plain
        answer otherwise. The search model only gets 20 free requests a day, so it's not used for "which coolant?".
        """
        if search and settings.RESEARCH_ENABLED and not search_paused():
            try:
                result = self.gemini.research(prompt, system=MECHANIC_PERSONA, purpose="open question (web search)")
                if result["text"]:
                    return {"text": result["text"], "sources": result["sources"]}
            except GeminiError as exc:
                logger.info("Web search answer failed, trying a plain answer: %s", exc)
                note_search_failure(exc)
        try:
            text = self.gemini.generate_text(prompt, system=MECHANIC_PERSONA, purpose="open question")
        except GeminiError as exc:
            logger.warning("General question failed: %s", exc)
            return None
        # a failed web search shouldn't leave a warning on an answer that worked
        self.gemini.last_failure = None
        return {"text": text, "sources": []}

    def _question_prompt(self, raw, car, diagnosis):
        recent = list(self.conversation.messages.order_by("-created_at")[:AI_HISTORY_MESSAGES])
        history = "\n".join(
            f"{'Customer' if message.role == Message.Role.USER else 'Mechanic'}: {message.content[:500]}"
            for message in reversed(recent)
            if message.content
        )
        return f"""Conversation so far:
{history or "(none)"}

Customer's car: {car or "unknown"} ({self.conversation.fuel_type or "fuel not known"})
Latest diagnosis: {diagnosis.title if diagnosis else "none yet"}

Customer's question: {raw}

Answer in under 150 words, specific to their car where it matters. If current facts help (prices in India,
fuel quality news, recalls, specs), look them up. If it sounds like a fault that needs hands-on inspection,
say what you'd check and suggest booking a mechanic."""

    # ---- helpers ---------------------------------------------------------

    def _reject(self, reprompt=None):
        question = self._question_by_key(reprompt) if reprompt and not reprompt.startswith("triage:") else None
        if question:
            return BotReply(
                f"{replies.OFF_TOPIC}\n\nComing back to your car: {question.text}",
                kind=Kind.REJECTION,
                quick_replies=list(question.options),
            )
        return BotReply(replies.OFF_TOPIC, kind=Kind.REJECTION)

    def _look_at_media(self, attachments, raw, preface):
        if not attachments:
            return []

        issue = self.issue
        notes, unanalysed = [], []
        for attachment in attachments:
            analysis, called_ai = analyse_attachment(attachment, self.gemini, raw, issue.label if issue else "")
            self.used_ai = self.used_ai or called_ai
            kind_name = replies.KIND_NAMES.get(attachment.kind, "file")
            if not analysis:
                unanalysed.append(kind_name)
            elif not analysis.get("car_related"):
                preface.append(replies.MEDIA_NOT_CAR.format(kind=kind_name))
            elif analysis.get("observations"):
                notes.append(analysis)
                preface.append(f"About your {kind_name}: {analysis['observations']}")

        if unanalysed:
            preface.append(replies.MEDIA_SAVED.format(kinds=" and ".join(dict.fromkeys(unanalysed))))

        if notes:
            saved = self.state.get("media_notes", []) + [note["observations"] for note in notes]
            self.state["media_notes"] = saved[-MAX_MEDIA_NOTES:]
        return notes

    def _use_car(self, car):
        conversation = self.conversation
        conversation.car = car
        conversation.vehicle_make = car.make
        conversation.vehicle_model = car.model
        conversation.vehicle_year = car.year
        conversation.fuel_type = car.fuel_type
        conversation.odometer_km = car.odometer_km
        conversation.registration_number = car.registration_number
        self.state["vehicle_asked"] = True

    def _remember_vehicle(self, raw):
        conversation = self.conversation
        # "my swift" when a Swift is saved in the profile -> that car, no need to ask
        if not conversation.car_id and self.saved_cars and self.state.get("pending") != VEHICLE_QUESTION.key:
            car = find_mentioned_car(self.saved_cars, raw)
            if car:
                self._use_car(car)

        # an explicit answer to "which car is it?" can overwrite, anything else only fills gaps
        overwrite = self.state.get("pending") == VEHICLE_QUESTION.key
        details = extract_vehicle_details(raw, answering=overwrite)
        if not details:
            return
        if overwrite:
            conversation.car = None
        fields = {
            "make": "vehicle_make",
            "model": "vehicle_model",
            "year": "vehicle_year",
            "odometer_km": "odometer_km",
            "fuel_type": "fuel_type",
            "registration_number": "registration_number",
        }
        for key, attribute in fields.items():
            if key in details and (overwrite or not getattr(conversation, attribute)):
                setattr(conversation, attribute, details[key])

    @staticmethod
    def _safety_alert(normalized):
        for patterns, message in SAFETY_ALERTS:
            if mentions_any(normalized, patterns):
                return message
        return None

    def _make_title(self, issue):
        car = " ".join(part for part in (self.conversation.vehicle_make, self.conversation.vehicle_model) if part)
        return f"{issue.label} - {car}"[:120] if car else issue.label

    def _save(self):
        conversation = self.conversation
        # title was set before we knew the car, add it now
        if self.issue and conversation.title == self.issue.label and conversation.vehicle_make:
            conversation.title = self._make_title(self.issue)
        conversation.state = self.state
        conversation.save()
