# Where and how Gemini is used

The bot is rule based first. Gemini is only called when the rules genuinely can't do the job, every
call has a fallback, and every call is visible in the API logs panel (purpose, model, time, why it
failed). This page lists all of them.

| # | Call (`purpose` in the logs) | When | Model | Cached | If it fails |
|---|---|---|---|---|---|
| 1 | `understanding the message` | Hindi / Hinglish, typos, "none of these", replies that don't fit the question | flash-lite | no | the rules handle the text as it is |
| 2 | `translation` | the chat is set to Hindi or Hinglish | flash-lite | forever, per exact text | the reply goes out in English |
| 3 | `web research` | mileage problems (straight after the fuel question), and model specific issues in the background | 2.5-flash + Google Search | 24h per problem + car + fuel | built-in fuel notes, or the card simply has no research section |
| 4 | `open question` / `open question (web search)` | car questions the knowledge base can't answer | flash-lite, search only for time-sensitive questions | 24h | "couldn't look that up" message |
| 5 | `diagnosis second opinion` | the rule ranking isn't confident, or media was analysed | flash-lite | no | the rule based diagnosis |
| 6 | `photo / audio / video analysis` | an attachment is sent | flash-lite | per file hash | the file is kept for the mechanic |

Models: `GEMINI_MODEL` (default `gemini-3.5-flash-lite`, 1-2s per answer) with `GEMINI_FALLBACK_MODEL`
(`gemini-2.5-flash`) tried when the first one is out of quota or overloaded. Web search uses
`GEMINI_RESEARCH_MODELS` (default `gemini-2.5-flash`), see below for why.

## 1. Understanding messages the rules can't read

`chat/bot/understand.py`

The keyword rules only know English. Messages like *"gaadi ka avg kam ho gaya"*, *"can you talk in hinid"* or
*"not my issues listed"* used to be rejected as off-topic. Now, before the bot rejects or misfiles anything,
Gemini is asked what the message means. It gets the question the bot just asked (with its options) and
returns JSON:

| Field | Meaning |
|---|---|
| `intent` | `car_problem`, `car_question`, `answer`, `none_of_the_options`, `change_language`, `greeting`, `thanks`, `yes`, `no`, `off_topic` |
| `english` | the message in clear English, meaning kept exactly as the customer said it |
| `option` | the quick reply the answer clearly matches, empty if none clearly fits |
| `language` | what they wrote in (`en`, `hi`, `hinglish`) |
| `requested_language` | if they asked the bot to switch language |
| `category` | problem area (brakes, ac, fuel_economy...) or `unknown` |

It's called only when:

- the message isn't plain English (Devanagari, or two or more common Hinglish words), or the chat is
  already in Hindi / Hinglish (then every typed message goes through it, tapped buttons don't)
- the rules can't place the message at all (before rejecting it)
- the bot asked a question and the reply matches none of the options by the rules and isn't a short
  answer, e.g. "battery is 4 years old" to *"what happens when you turn the key?"*

What happens with the result:

- `answer` -> saved as the answer, as `"Option (their words)"` when an option fits, so the diagnosis rules
  see both
- more detail about the problem instead of an answer -> added to the problem description and the same
  question is asked again ("Got it, I've added that to your case."), at most once per question
- car details instead of an answer ("wagon r 2016, 1.1 lakh km") -> the car is saved, question asked again
- `car_question` in the middle of the questions -> answered, then *"Coming back to your car: ..."*
- `none_of_the_options` -> noted as "None of these" and the bot moves on
- `change_language` -> switches the reply language and repeats the open question
- `off_topic` -> polite rejection

Two mistakes from testing shaped this. First, Gemini was asked to reuse the option text as the English
version, and it mapped *"gas was never refilled"* to *"Right after a service or repair"*. The diagnosis
then told the customer the problem started after a service. Now the English stays faithful and the option
is a separate field with *"don't guess, a wrong option is worse than none"*. Second, related symptoms
mentioned halfway through ("pickup is also less" while talking about black smoke) used to start a new
problem. Now they're added to the current one. Only right at the start, before any answer, can a
different category replace the first guess.

A lot is still done without AI (`chat/bot/intents.py`): free text is matched to options by shared words
(negations and numbers have to agree, so "it doesn't blink" never picks "Blinking" and "3 years ago" never
picks "1 to 2 years ago"), "none of these" style replies, typos in "hindi"/"english" (fuzzy match),
registration numbers and "80k" / "1.2 lakh" km.

## 2. Replying in Hindi or Hinglish

`chat/bot/language.py`

All the logic and the knowledge base stay in English. When `Conversation.language` is `hi` or `hinglish`,
the finished reply and its quick reply buttons are translated in one call. It gets set:

- from the picker under the message box (sent as `language` on the first message, or `PATCH /api/conversations/{id}/`)
- when the customer writes in Hindi / Hinglish (the bot follows them)
- when they ask for it in the chat ("hindi mein baat karo", "talk in hinglish")

Most replies are the same canned questions, so translations are cached without expiry, keyed by the exact
text and language. A repeated question costs nothing. The lite model sometimes answered "Hindi" in Latin
letters, so a Hindi translation without Devanagari is retried once and never cached.

Tapping a translated button still works with the rules: the bot remembers which translated option maps to
which English one (`state.option_map`).

The diagnosis card gets a translated copy of its text in `Diagnosis.localized` (title, summary, advice,
causes, research summary). The English original stays in the normal fields.

## 3. Web research: fuel news, recalls, known issues

`diagnosis/research.py`, `core/gemini.py` (`GeminiClient.research`)

Some answers depend on what's going on right now: E20 petrol and what it does to mileage, adulteration
reports, a recall on a particular model. The knowledge base can't know that, so the bot searches the web
with Gemini's Google Search grounding. The answer comes back with the pages it was based on, and those are
shown to the customer.

### What gets searched

Each issue type has a `research_focus` in the knowledge base, for example:

| Issue | Looks for |
|---|---|
| Mileage & fuel economy | current fuel quality news in India (E20 ethanol blend, adulteration, CNG supply) and common mileage complaints for the model |
| Engine & check engine light | common faults, software updates, service campaigns and recalls for the model, plus fuel quality issues |
| Brakes | brake recalls, service campaigns and common complaints for the model |
| Starting, overheating, gearbox, suspension, tyres, AC, electrical, smoke, leaks | known problems and recalls for the model |
| Routine service | nothing, no search |

The prompt gives the car, fuel, problem area and what the customer said so far. It asks for news,
advisories and recall notices from the last 12-18 months, 2-4 short bullets, and *"never make up a recall,
a ban or a number that isn't in the sources"*. It uses its own short system prompt (not the chat persona).
With the persona the notes started with "Hello there!" and ended with "bring your car in" in the middle of
the questions. Any intro or outro that still slips in is trimmed off, only the bullets are kept.

### When it runs

**Mileage (right away).** For mileage the fuel matters most, so the flow is:

1. *"Which fuel does it run on?"* first (skipped if they already said, or the saved car has it).
2. As soon as the fuel is known, the research runs and the result is shown in the chat, with its sources:
   *"Before the next questions, here's what's worth knowing about petrol right now:"* followed by the
   bullets, e.g. E20 petrol lowering mileage by 3-5%.
3. Then the questions about the car itself: how much it dropped, when (right after a refuel?), how it's
   driven, other symptoms (pickup, check engine light, black smoke, burning smell / hot wheel), and when
   the tyre pressure and service were last done.
4. The diagnosis weighs fuel quality against the car. A drop of more than 30% is far more than E20
   explains, so it pushes the engine causes up. The research is also shown on the card.

If the search isn't available (no key, quota used up), a short built-in note is used instead
(`replies.FUEL_NOTES`: the official 2-6% estimate for E20, CNG kit tuning, diesel filters).

**Everything else (in the background).** A model specific search took 10-15s, too long to make the
customer wait at the end. So as soon as the problem and the car model are known, the search starts in a
background thread. The customer spends about that long answering the remaining questions, so by the
diagnosis it's usually in the cache already. If it's still running, the diagnosis waits for it (up to the
timeout) instead of starting a second search. If it failed, the diagnosis goes ahead without it. The card
shows it as **Worth knowing · from the web** with the sources and the date searched.

A real example from testing: a 2018 Swift with a soft brake pedal. The search found Maruti's 2018
service campaign that replaced a possibly faulty brake vacuum hose on Swift / Baleno cars built in a
certain window, and told the customer to check their chassis number.

**Open questions.** *"Which coolant should I use?"* gets a plain answer. Questions where the answer
changes over time (prices, news, recalls, E20, rules, challans...) use the web search version, and the
reply lists its sources.

### Speed and the free tier

| Setting | Why |
|---|---|
| Model `gemini-2.5-flash` | on the free tier the lite and "latest" models answered 404 / 429 for grounding |
| Thinking turned off (`thinking_budget=0`) | with thinking: 9-30s per search, sometimes timing out. Without: 5-6s, same sources |
| `RESEARCH_TIMEOUT_SECONDS=15` | a hung search doesn't hold up the chat |
| Cache `RESEARCH_CACHE_HOURS=24` | per problem + make + model + year + fuel, shared by all customers |
| Pause after a quota error | 2.5-flash has only **20 free requests a day**. After a 429 the bot stops trying for 10 minutes, instead of adding a failed call to every reply |

Research is a bonus, so a failed search never puts a warning on the reply (the failed call still shows
in the API logs). Results from social media (facebook, instagram, x, quora) aren't shown as sources.
The source links are Google's grounding redirect links; they open the original article.

### Where it's stored

- `Diagnosis.research`: `{"summary", "sources": [{"title", "url"}], "queries", "searched_at"}`
- `Message.sources`: the pages behind a researched chat message
- `Conversation.state.research`: the mileage research, so it isn't repeated for the same chat

## 4. Open questions

`MechanicBot._answer_general_question()` in `chat/bot/engine.py`

Car questions the knowledge base can't answer ("which engine oil for a Creta?", "what is E20?"). The
prompt includes the last few messages, the car and the latest diagnosis, and asks for under 150 words.
Not about cars -> the model answers `OFF_TOPIC` and the bot rejects politely. Answers are cached for 24h,
keyed by the question, car, fuel and diagnosis.

Information questions are answered even when they contain a problem keyword ("which coolant should I
use?" mentions coolant but nothing is wrong), while "why is my car overheating?" starts the diagnosis
questions. Without a Gemini key the questions go to the rules instead.

## 5. Diagnosis second opinion

`diagnosis/engine.py`

The rules score every possible cause against everything the customer said. If the top cause is clearly
ahead, that's the diagnosis and no AI is used. If it isn't, or photos / audio were analysed, Gemini gets the
evidence and the rule ranking and returns a structured diagnosis. It can raise the severity but never
lower a high / critical one, and the recommended service always comes from the rules.

Causes that can't apply to the car's fuel are left out before ranking (no glow plugs on a CNG car, no spark
plugs on a diesel).

## 6. Photos, audio and video

`chat/bot/media.py`: Gemini describes what it sees or hears, and whether it's a car at all. Cached per
file hash, so sending the same file again costs nothing.

## Failures

`core/gemini.py` sorts every failure into `quota`, `overloaded`, `timeout`, `invalid_key`,
`model_not_found`, `empty`, `bad_response` or `error`, tries the fallback model where that makes sense, and
never raises into the chat. If a reply needed Gemini and didn't get it, the message carries `ai_error` and
the UI says the rule based checks answered. The API logs panel shows every call made during a request.

## Settings

| Env var | Default | |
|---|---|---|
| `GEMINI_API_KEY` | empty | without it the bot runs on rules only |
| `GEMINI_MODEL` / `GEMINI_FALLBACK_MODEL` | `gemini-3.5-flash-lite` / `gemini-2.5-flash` | chat, understanding, translation, second opinion, media |
| `GEMINI_RESEARCH_MODELS` | `gemini-2.5-flash` | comma separated, tried in order |
| `RESEARCH_ENABLED` | `true` | turns off all web search |
| `RESEARCH_TIMEOUT_SECONDS` | `15` | per search |
| `RESEARCH_CACHE_HOURS` | `24` | |
| `RESEARCH_IN_BACKGROUND` | `true` (off in tests) | background search for model specific issues |
