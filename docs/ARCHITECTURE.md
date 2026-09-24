# Architecture

## Overview

```
 Browser (Next.js on Vercel)
   |  JSON over HTTPS, X-Client-Id header (+ X-Gemini-Key only if the visitor added their own key)
   v
 nginx (EC2)  --- serves /media/ uploads directly
   |
   v
 gunicorn -> Django + DRF
   |-- apilogs/     middleware that logs every /api/ call + the Gemini calls inside it
   |-- chat/        conversations, messages, uploads, bot flow
   |-- diagnosis/   knowledge base + diagnosis engine
   |-- bookings/    services, mechanics, bookings
   |-- customers/   "My garage" profile and saved cars
   |-- core/        Gemini wrapper, error handler, text helpers
   |
   |-- SQLite (WAL mode), also used as the cache (throttling, cached Gemini answers, translations, research)
   '-- Gemini API (media, messages the rules can't read, Hindi replies, web research, open questions,
                   unsure diagnoses - see AI_USAGE.md)
```

The frontend is a single chat page plus a booking status page. It talks to the API directly (CORS),
there's no Next.js API layer in between.

## How a message is handled

`POST /api/chat/` -> `chat/services.handle_user_message()` -> `MechanicBot.reply()` (`chat/bot/engine.py`)

1. Save the user's message and link any uploads to it. A tapped quick reply in Hindi / Hinglish is mapped
   back to the original English option.
2. If the message isn't plain English, or the chat is in Hindi / Hinglish, Gemini turns it into English
   first (`chat/bot/understand.py`), so the rules below can work on it.
3. Work out the car: if the customer has saved cars and names one ("my swift"), use it. Otherwise pull
   make / model / year / km / registration out of the text with regex (`chat/bot/vehicle.py`).
4. Check for emergencies (fuel smell, smoke, brake failure, oil light) and add a safety warning first.
5. If photos/audio/video were attached, ask Gemini what it sees/hears. Results are stored on the
   attachment and reused if the same file (same sha256) is sent again.
6. Route the message, rules first:
   - "talk in hindi" (typos too) -> switch the reply language
   - a follow-up question is pending -> work out what the reply is: a quick reply (matched from free text
     by the rules), "none of these", car details, more detail about the problem, or a side question. Only
     a reply the rules can't place goes to Gemini. Then ask the next question or diagnose
   - already diagnosed -> "yes, book", "no", "how much?", "is it safe to drive?", or new details that
     update the diagnosis
   - "which coolant should I use?" -> answered, even though it mentions coolant
   - problem keywords found -> start that issue and ask its first question
   - vague ("weird noise") -> ask a clarifying question with options
   - greeting / thanks -> canned reply (with the customer's name if they have a profile)
   - anything the rules don't understand -> Gemini reads it before anything is rejected
   - car related question the rules can't answer -> Gemini
7. Translate the reply if the chat is in Hindi / Hinglish, then save it. If Gemini was needed but failed,
   the reply carries `ai_error` so the UI can say "the rule based checks answered this one". If anything
   else crashes, the customer still gets a "sorry, try again" message instead of a 500.

Conversation stages: `new -> gathering -> diagnosed -> booked`. The follow-up progress (pending
question, answers so far, research done, translated button map) is kept in `Conversation.state` (a JSON
field), so the flow is stateless on the server between requests.

Which question comes next is decided per question in the knowledge base: `skip_if` (already answered in
something they said), `only_if` (only makes sense on one path, e.g. "is the light steady or blinking?"
only when a warning light was mentioned, "when is it worst?" only when the car drives badly) and
`skip_when_known` (the fuel question is skipped when the saved car has a fuel type).

## Personalisation

`customers.Customer` is an optional profile per client id (name, phone, email, city) with up to 5
`customers.Car`s, one of them primary.

- The greeting uses the first name and the primary car ("what's going on with your Swift").
- When the conversation's car isn't known, the first follow-up question becomes
  *"Is this about your 2017 Maruti Suzuki Swift?"* with `Yes, my Swift` / `A different car` (or a button per
  car if there are several). "A different car" falls back to the normal "which car is it?" question.
- The chosen car is copied onto the conversation and linked (`Conversation.car`), so the diagnosis text
  and the booking form know the exact car and registration number.
- A booking with `save_details: true` updates the profile and adds the car if it's new.

## Diagnosis

`diagnosis/knowledge_base.py` has 13 issue types (brakes, starting & battery, engine, mileage & fuel
economy, overheating, clutch & gearbox, suspension, tyres, AC, electrical, smoke, leaks, routine service).
Each one has:

- weighted keywords to detect it
- 2-7 follow-up questions with quick reply options
- possible causes, each with a prior and signal words that make it more likely (and the fuels it can
  happen on: no glow plugs on a CNG car)
- recommended service (a cause can have its own, a puncture needs a tyre repair, not wheel alignment),
  default severity and escalation words (e.g. "grinding" -> high)
- what to search the web for (`research_focus`)

Mileage asks the fuel first because fuel quality (E20 petrol) is half
the answer, see [AI_USAGE.md](AI_USAGE.md#3-web-research-fuel-news-recalls-known-issues).

`diagnosis/engine.py` scores every cause against everything the customer said and ranks them. If the
top cause is clearly ahead, that's the diagnosis, no AI involved. If the evidence is weak or ambiguous,
or media was analysed, Gemini gets the evidence and the rule ranking and returns a structured JSON
diagnosis (validated with a schema). Two safety rules apply to the AI answer:

- it can raise the severity but can't lower a high/critical severity that the rules decided
- the recommended service always comes from the rules, so bookings stay consistent

If Gemini fails, times out or returns junk, the rule based diagnosis is used.

Web research (recalls, known issues, fuel news) is attached to the diagnosis in `Diagnosis.research` with
its sources. For everything except mileage it's started in a background thread as soon as the problem and
the car model are known, so it's usually cached by the time the questions are done.

## Keeping AI usage low (and visible)

- Rules first everywhere. Gemini is called for media, messages the rules can't read, Hindi / Hinglish replies,
  web research, open questions and unsure diagnoses. [AI_USAGE.md](AI_USAGE.md) lists when exactly.
- Default model `gemini-3.5-flash-lite` (answers in 1-2s on the free tier). If it's out of quota,
  overloaded or times out, `gemini-2.5-flash` is tried next. The bigger flash models were 5-25s per answer
  in testing, too slow for a chat.
- Answers to open questions are cached for 24h (key = question + car + current diagnosis), media
  analysis per file hash, translations forever per exact text, web research for 24h per problem + car.
- Web search has only 20 free requests a day on `gemini-2.5-flash`: it's only used where current facts
  matter, and paused for 10 minutes after a quota error.
- Rate limits per IP protect the free quota.
- `apilogs.RequestLogMiddleware` records every API call with the Gemini calls made during it (via a
  context variable the Gemini wrapper appends to). The frontend's API logs panel shows these, the
  status of the server key and counters like "bot replies handled by rules only". Reviewers can see
  exactly when AI was used, and if the free quota runs out they see why instead of a broken app.
- If our key is failing, the panel lets a visitor use their own key. It's kept in their browser and sent
  in `X-Gemini-Key`, the middleware puts it in a context variable for that request only. It's never saved
  or logged, and calls made with it don't affect the server key status.

## Database

```
Customer (client_id unique, name, phone, email, city)
   '---*  Car (make, model, year, fuel, km, reg no, is_primary)
                  ^
                  | car (nullable)
Conversation (uuid)  1---*  Message  *---1  Diagnosis (nullable)   Message *---1 Booking (nullable)
     |  client_id, stage, issue_category, language, vehicle fields + reg no, state (json)
     |  (Message also keeps `sources` json: the web pages behind a researched reply)
     |
     |---*  Attachment (uuid, file, kind, sha256, analysis json)  --- linked to Message once sent
     |---*  Diagnosis (title, summary, probable_causes json, severity, safe_to_drive, cost range, source,
     |                 research json, localized json)
     '---*  Booking (uuid, reference, service, mechanic, customer, vehicle, date, slot, mode, status)

Service (code, name, price range, duration)     Mechanic (name, speciality, experience)
RequestLog (client_id, method, path, status, duration, error, ai_calls json)
django_cache (DB cache table)
```

A few decisions:

- UUID primary keys for conversations, uploads and bookings because they appear in URLs without login,
  so they shouldn't be guessable. Bookings also get a short reference (`GM-7KQ2XD`) for phone calls.
- `UniqueConstraint(mechanic, date, slot)` where status isn't cancelled, so a mechanic can never be
  double booked even if two requests race. The booking service just tries the next free mechanic if it
  loses the race.
- Diagnosis copies the price range from the service at the time, so old diagnoses don't change when
  prices are edited. Same idea for the conversation's vehicle fields vs the saved car.
- Services and mechanics are seeded by a data migration and can be edited in the Django admin. The cache
  table is also created by a migration, so `migrate` is the only setup step.
- SQLite runs in WAL mode with `IMMEDIATE` transactions so concurrent gunicorn workers don't hit
  "database is locked" errors. The cache lives in the DB too; the file based cache raced on parallel
  requests.
- Request logs only keep metadata, never bodies (bookings contain phone numbers), and are pruned after
  7 days.

## Error handling

- One error format for every endpoint (`core/exceptions.py`): `{"error": {"code", "message", "fields"}}`.
- Gemini failures are classified (`quota`, `overloaded`, `timeout`, `invalid_key`...) and never bubble up
  as errors. The rules answer instead and the reply says so.
- Uploads are checked by their actual bytes (magic numbers), not by extension or the browser's
  content type, and size limited per type.
- Frontend: failed messages stay in the chat with a Retry button, uploads show progress and errors
  per file, booking / profile form errors are shown under the matching field, network errors show a toast.

## Security notes

- No accounts, so every read/write is scoped by the client id. Other client ids get 404, not 403, so
  you can't even tell something exists.
- Booking detail masks the customer's phone number since the link is shareable.
- Uploaded files get random names, the original name is only stored in the DB.
- A visitor's own Gemini key is only held in memory for the request that sent it.
- HTTPS via Let's Encrypt, secure cookies and HSTS when `DEBUG` is off.
