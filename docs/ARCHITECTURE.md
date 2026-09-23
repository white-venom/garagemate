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
   |-- SQLite (WAL mode), also used as the cache (throttling, cached Gemini answers)
   '-- Gemini API (only for media, open questions, unsure diagnoses)
```

The frontend is a single chat page plus a booking status page. It talks to the API directly (CORS),
there's no Next.js API layer in between.

## How a message is handled

`POST /api/chat/` -> `chat/services.handle_user_message()` -> `MechanicBot.reply()` (`chat/bot/engine.py`)

1. Save the user's message and link any uploads to it.
2. Work out the car: if the customer has saved cars and names one ("my swift"), use it. Otherwise pull
   make / model / year / km out of the text with regex (`chat/bot/vehicle.py`).
3. Check for emergencies (fuel smell, smoke, brake failure, oil light) and add a safety warning first.
4. If photos/audio/video were attached, ask Gemini what it sees/hears. Results are stored on the
   attachment and reused if the same file (same sha256) is sent again.
5. Route the message, all rule based:
   - a follow-up question is pending -> store the answer, ask the next one or diagnose
   - already diagnosed -> handle "yes, book", "no", "how much?", "is it safe to drive?"
   - problem keywords found -> start that issue and ask its first question
   - vague ("weird noise") -> ask a clarifying question with options
   - greeting / thanks -> canned reply (with the customer's name if they have a profile)
   - off-topic -> polite rejection
   - car related question the rules can't answer -> Gemini
6. Save the bot's reply. If Gemini was needed but failed, the reply carries `ai_error` so the UI can say
   "the rule based checks answered this one". If anything else crashes, the customer still gets a
   "sorry, try again" message instead of a 500.

Conversation stages: `new -> gathering -> diagnosed -> booked`. The follow-up progress (pending
question, answers so far) is kept in `Conversation.state` (a JSON field), so the flow is stateless on
the server between requests.

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

## Keeping AI usage low (and visible)

- Rules first everywhere. Gemini is called in three places only (media, open questions, unsure diagnosis).
- Default model `gemini-3.5-flash-lite` (answers in 1-2s on the free tier). If it's out of quota,
  overloaded or times out, `gemini-2.5-flash` is tried next. The bigger flash models were 5-25s per answer
  in testing, too slow for a chat.
- Answers to open questions are cached for 24h (key = question + car + current diagnosis), media
  analysis is cached per file hash.
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
     |  client_id, stage, issue_category, vehicle fields, state (json)
     |
     |---*  Attachment (uuid, file, kind, sha256, analysis json)  --- linked to Message once sent
     |---*  Diagnosis (title, summary, probable_causes json, severity, safe_to_drive, cost range, source)
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
