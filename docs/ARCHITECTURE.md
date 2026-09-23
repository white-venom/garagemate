# Architecture

## Overview

```
 Browser (Next.js on Vercel)
   |  JSON over HTTPS, X-Client-Id header
   v
 nginx (EC2)  --- serves /media/ uploads directly
   |
   v
 gunicorn -> Django + DRF
   |-- chat/        conversations, messages, uploads, bot flow
   |-- diagnosis/   knowledge base + diagnosis engine
   |-- bookings/    services, mechanics, bookings
   |-- core/        Gemini wrapper, error handler, text helpers
   |
   |-- SQLite (WAL mode)
   '-- Gemini API (only for media, open questions, unsure diagnoses)
```

The frontend is a single chat page plus a booking status page. It talks to the API directly (CORS),
there's no Next.js API layer in between.

## How a message is handled

`POST /api/chat/` -> `chat/services.handle_user_message()` -> `MechanicBot.reply()` (`chat/bot/engine.py`)

1. Save the user's message and link any uploads to it.
2. Pull the car make/model/year/km out of the text with regex (`chat/bot/vehicle.py`).
3. Check for emergencies (fuel smell, smoke, brake failure, oil light) and add a safety warning first.
4. If photos/audio/video were attached, ask Gemini what it sees/hears. Results are stored on the
   attachment and reused if the same file (same sha256) is sent again.
5. Route the message, all rule based:
   - a follow-up question is pending -> store the answer, ask the next one or diagnose
   - already diagnosed -> handle "yes, book", "no", "how much?", "is it safe to drive?"
   - problem keywords found -> start that issue and ask its first question
   - vague ("weird noise") -> ask a clarifying question with options
   - greeting / thanks -> canned reply
   - off-topic -> polite rejection
   - car related question the rules can't answer -> Gemini
6. Save the bot's reply. If anything above crashes, the customer still gets a "sorry, try again" message
   instead of a 500.

Conversation stages: `new -> gathering -> diagnosed -> booked`. The follow-up progress (pending
question, answers so far) is kept in `Conversation.state` (a JSON field), so the flow is stateless on
the server between requests.

## Diagnosis

`diagnosis/knowledge_base.py` has 12 issue types (brakes, starting & battery, engine, overheating,
clutch & gearbox, suspension, tyres, AC, electrical, smoke, leaks, routine service). Each one has:

- weighted keywords to detect it
- 2-3 follow-up questions with quick reply options
- possible causes, each with a prior and signal words that make it more likely
- recommended service, default severity and escalation words (e.g. "grinding" -> high)

`diagnosis/engine.py` scores every cause against everything the customer said and ranks them. If the
top cause is clearly ahead, that's the diagnosis, no AI involved. If the evidence is weak or ambiguous,
or media was analysed, Gemini gets the evidence and the rule ranking and returns a structured JSON
diagnosis (validated with a schema). Two safety rules apply to the AI answer:

- it can raise the severity but can't lower a high/critical severity that the rules decided
- the recommended service always comes from the rules, so bookings stay consistent

If Gemini fails, times out or returns junk, the rule based diagnosis is used.

## Keeping AI usage low

- Rules first everywhere. Gemini is called in three places only (media, open questions, unsure diagnosis).
- Answers to open questions are cached for 24h (key = question + car + current diagnosis).
- Media analysis is cached per file hash.
- `GEMINI_FALLBACK_MODEL` is tried when the main model hits its free tier quota.
- Rate limits per IP protect the free quota from abuse.
- Every message stores `used_ai`, so usage can be checked in the admin.

## Database

```
Conversation (uuid)  1---*  Message  *---1  Diagnosis
     |  client_id, stage, issue_category,     (nullable)   *---1  Service
     |  vehicle fields, state (json)          Message *---1 Booking (nullable)
     |
     |---*  Attachment (uuid, file, kind, sha256, analysis json)  --- linked to Message once sent
     |---*  Diagnosis (title, summary, probable_causes json, severity, safe_to_drive, cost range, source)
     '---*  Booking (uuid, reference, service, mechanic, customer, vehicle, date, slot, mode, status)

Service (code, name, price range, duration)     Mechanic (name, speciality, experience)
```

A few decisions:

- UUID primary keys for conversations, uploads and bookings because they appear in URLs without login,
  so they shouldn't be guessable. Bookings also get a short reference (`GM-7KQ2XD`) for phone calls.
- `UniqueConstraint(mechanic, date, slot)` where status isn't cancelled, so a mechanic can never be
  double booked even if two requests race. The booking service just tries the next free mechanic if it
  loses the race.
- Diagnosis copies the price range from the service at the time, so old diagnoses don't change when
  prices are edited.
- Services and mechanics are seeded by a data migration and can be edited in the Django admin.
- SQLite runs in WAL mode with `IMMEDIATE` transactions so concurrent gunicorn workers don't hit
  "database is locked" errors.

## Error handling

- One error format for every endpoint (`core/exceptions.py`): `{"error": {"code", "message", "fields"}}`.
- Uploads are checked by their actual bytes (magic numbers), not by extension or the browser's
  content type, and size limited per type.
- Frontend: failed messages stay in the chat with a Retry button, uploads show progress and errors
  per file, booking form errors are shown under the matching field, network errors show a toast.

## Security notes

- No accounts, so every read/write is scoped by the client id. Other client ids get 404, not 403, so
  you can't even tell something exists.
- Booking detail masks the customer's phone number since the link is shareable.
- Uploaded files get random names, the original name is only stored in the DB.
- HTTPS via Let's Encrypt, secure cookies and HSTS when `DEBUG` is off.
