# API documentation

Base URL: `https://13-127-38-145.sslip.io/api/` (locally `http://localhost:8000/api/`)

All requests and responses are JSON, except file uploads which are `multipart/form-data`.

## Identifying the user

There are no accounts. The frontend generates a random id once (stored in localStorage) and sends it
with every request:

```
X-Client-Id: 3f6c1a2e-8d4b-4f7a-9c1e-2b5d7e9f0a13
```

It can also be sent as `client_id` in the JSON body or query string. 8-64 characters, letters, numbers
and dashes. Conversations, uploads, diagnoses, the profile and the API logs are only visible to the same
client id, anyone else gets a 404.

Optional: `X-Gemini-Key: <your key>` makes the backend use that Gemini key for this one request instead of
the server's key. The frontend only sends it when the visitor added their own key in the API logs panel
(because ours ran out of quota). It's never stored or logged.

## Errors

Every error has the same shape:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Please enter your name.",
    "fields": {
      "customer_name": ["Please enter your name."],
      "phone": ["Enter a valid phone number, e.g. 9876543210."]
    }
  }
}
```

`fields` is only there for validation errors. `message` is always safe to show to the user.

| Status | code | When |
|---|---|---|
| 400 | `validation_error` | bad or missing input |
| 404 | `not_found` | resource doesn't exist or belongs to another client |
| 409 | `conflict` | slot got fully booked, booking can't be cancelled |
| 429 | `throttled` | rate limit hit, response also has `retry_after` (seconds) |
| 500 | `server_error` | something broke on our side |

## Rate limits

Per IP: 120 requests/min overall, 20/min for chat and diagnosis, 15/min for uploads, 10/min for bookings.
Configurable with the `THROTTLE_*` env vars.

---

## POST /api/chat/

Send a message to the mechanic bot. Leave out `conversation_id` to start a new conversation.

**Request**

| Field | Type | |
|---|---|---|
| `conversation_id` | uuid | optional, continue an existing conversation |
| `message` | string | up to 2000 chars. Can be empty if attachments are sent |
| `attachment_ids` | uuid[] | optional, ids from `/api/upload/`, max 4. Each upload can only be sent once |
| `language` | string | optional, `en`, `hi` or `hinglish`: the language the bot replies in. Used when starting a conversation, later use `PATCH /api/conversations/{id}/` |

```json
{
  "message": "My brakes make a grinding noise when I stop"
}
```

**Response 201**

```json
{
  "conversation": {
    "id": "cede1c67-401e-46b3-b25d-80509076f1ae",
    "title": "Brakes",
    "stage": "gathering",
    "issue_category": "brakes",
    "language": "en",
    "vehicle": { "make": "", "model": "", "year": null, "odometer_km": null, "fuel_type": "", "registration_number": "" },
    "car_id": null,
    "latest_diagnosis": null,
    "last_message": "Brake problems are worth taking seriously, let's narrow it down...",
    "created_at": "2026-09-23T12:56:40.361359+05:30",
    "updated_at": "2026-09-23T12:56:40.414179+05:30"
  },
  "user_message": {
    "id": 1,
    "role": "user",
    "kind": "text",
    "content": "My brakes make a grinding noise when I stop",
    "quick_replies": [],
    "action": "",
    "attachments": [],
    "diagnosis": null,
    "booking": null,
    "used_ai": false,
    "ai_error": "",
    "created_at": "2026-09-23T12:56:40.376868+05:30"
  },
  "reply": {
    "id": 2,
    "role": "assistant",
    "kind": "question",
    "content": "Brake problems are worth taking seriously, let's narrow it down.\n\nWhich car is it? Make, model and year...",
    "quick_replies": ["I'd rather not say"],
    "action": "",
    "attachments": [],
    "diagnosis": null,
    "booking": null,
    "used_ai": false,
    "ai_error": "",
    "sources": [],
    "created_at": "2026-09-23T12:56:40.409066+05:30"
  }
}
```

**Message fields**

- `kind`: `text`, `question` (follow-up question), `diagnosis`, `rejection` (off-topic), `booking_prompt`,
  `booking_confirmed`, `error`
- `quick_replies`: suggested answers the UI shows as buttons
- `action`: `open_booking` when the customer agreed to book, the frontend opens the booking form
- `diagnosis`: full diagnosis object when `kind` is `diagnosis` (see below)
- `booking`: short booking summary when `kind` is `booking_confirmed`
- `used_ai`: `true` if Gemini was called to produce this reply
- `ai_error`: set when Gemini was needed but failed and the rules answered instead. One of `quota`,
  `overloaded`, `timeout`, `invalid_key`, `model_not_found`, `empty`, `error`. Empty otherwise
- `sources`: web pages a researched reply is based on, `[{"title": "economictimes.com", "url": "..."}]`.
  Set on answers that used Google Search (fuel news during the mileage questions, time-sensitive
  questions). Empty otherwise. See [AI_USAGE.md](AI_USAGE.md)

**Conversation `stage`:** `new` -> `gathering` (asking follow-up questions) -> `diagnosed` -> `booked`

**Conversation `car_id`:** id of the saved car (see Profile below) the conversation is about, once the
customer confirmed it ("Is this about your 2017 Maruti Suzuki Swift?" -> "Yes, my Swift").

**Conversation `language`:** `en`, `hi` (Hindi, Devanagari) or `hinglish`. The bot's replies and quick
replies come in this language. It changes by itself when the customer writes in Hindi / Hinglish or asks
for it in the chat ("hindi mein baat karo"). The customer can write in any of them either way.

**`vehicle.registration_number`:** from the saved car, a booking, or typed in the chat ("MH12AB1234"),
stored without spaces.

**Errors:** 400 if both message and attachments are empty, or an attachment id is invalid / already used.
404 if the conversation doesn't exist for this client.

---

## POST /api/upload/

Upload a photo, audio clip or video. Send the returned `id` in `attachment_ids` of the next chat message.
The bot analyses it at that point (with the conversation as context).

`multipart/form-data`:

| Field | |
|---|---|
| `file` | the file |
| `conversation_id` | optional |

Allowed types (checked from the file content, not the extension):

| Kind | Formats | Max size |
|---|---|---|
| image | JPG, PNG, WEBP, HEIC | 8 MB |
| audio | MP3, WAV, OGG, FLAC, AAC, M4A, WEBM | 10 MB |
| video | MP4, WEBM, MOV, 3GP | 15 MB |

```bash
curl -X POST https://13-127-38-145.sslip.io/api/upload/ \
  -H "X-Client-Id: 3f6c1a2e-8d4b-4f7a-9c1e-2b5d7e9f0a13" \
  -F "file=@dashboard.jpg"
```

**Response 201**

```json
{
  "id": "a17a1c4e-abd8-4329-88ea-26bd03ca35d9",
  "kind": "image",
  "mime_type": "image/png",
  "size_bytes": 184233,
  "original_name": "dashboard.png",
  "url": "https://13-127-38-145.sslip.io/media/uploads/2026/09/5189a03c3acc4759a02edef598bf4d03.png",
  "created_at": "2026-09-23T12:56:40.434665+05:30"
}
```

**Errors:** 400 for a missing file, unsupported type or file too large.

Uploads that are never sent in a message are deleted after 24h (`manage.py cleanup_uploads`, runs from cron).

---

## POST /api/diagnosis/

Diagnose now with whatever the customer has said so far, skipping any remaining follow-up questions
(the "Diagnose now" button). The normal chat flow diagnoses by itself once the questions are answered.

If the conversation is already diagnosed and nothing new was said since, the existing diagnosis is
returned with **200** instead of creating a new one.

**Request**

```json
{ "conversation_id": "cede1c67-401e-46b3-b25d-80509076f1ae" }
```

**Response 201**

```json
{
  "diagnosis": {
    "id": 1,
    "conversation_id": "cede1c67-401e-46b3-b25d-80509076f1ae",
    "category": "brakes",
    "category_label": "Brakes",
    "title": "Pads worn down to metal, damaging the discs",
    "summary": "From what you've described, my best guess for your 2017 Maruti Suzuki Swift: pads worn down to metal, damaging the discs. A proper inspection will confirm it.",
    "probable_causes": [
      { "name": "Pads worn down to metal, damaging the discs", "likelihood": 0.61 },
      { "name": "Worn brake pads", "likelihood": 0.14 },
      { "name": "Warped brake discs (rotors)", "likelihood": 0.08 }
    ],
    "severity": "high",
    "severity_label": "High - avoid driving until checked",
    "safe_to_drive": false,
    "advice": "Keep extra distance from the car in front and avoid hard braking until the brakes are inspected.",
    "recommended_service": {
      "code": "brake-service",
      "name": "Brake Service",
      "description": "Inspect pads, discs, calipers and brake fluid. Replace pads or resurface discs if needed.",
      "price_min": 1200,
      "price_max": 6500,
      "duration_minutes": 90
    },
    "estimated_cost_min": 1200,
    "estimated_cost_max": 6500,
    "source": "rules",
    "research": {
      "summary": "- No brake recalls for the 2017 Swift in India in the last year...",
      "sources": [{ "title": "cardekho.com", "url": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/..." }],
      "queries": ["Maruti Swift 2017 brake recall India"],
      "searched_at": "2026-09-24T15:39:12.842110+05:30"
    },
    "localized": {},
    "created_at": "2026-09-23T12:56:40.506445+05:30"
  },
  "message": { "id": 7, "role": "assistant", "kind": "diagnosis", "...": "same shape as chat messages" }
}
```

- `severity`: `low`, `medium`, `high`, `critical`
- `source`: `rules` (rule engine only) or `ai` (rule engine + Gemini second opinion)
- `probable_causes[].likelihood`: 0-1, rough share of the evidence, not a real probability
- `research`: web research for this problem on this car (recalls, known issues, fuel news) with its
  sources. `{}` when there was nothing to search (car model unknown, routine service), research is
  switched off, or the search failed
- `localized`: when the conversation isn't in English, a translated copy of the card text:
  `{"language", "title", "summary", "advice", "causes": [...same order...], "research_summary"}`. `{}` otherwise

**Errors:** 400 if there's nothing to diagnose yet (no problem described), 404 unknown conversation.

## GET /api/diagnosis/{id}/

Returns a single diagnosis (same object as above). 404 if it belongs to another client.

---

## GET /api/services/

Services that can be booked.

```json
{
  "results": [
    {
      "code": "brake-service",
      "name": "Brake Service",
      "description": "Inspect pads, discs, calipers and brake fluid...",
      "price_min": 1200,
      "price_max": 6500,
      "duration_minutes": 90
    }
  ]
}
```

## GET /api/booking/slots/?date=YYYY-MM-DD

Availability for a day. `remaining` is the number of free mechanics in that slot. Slots that already
started (or start within the next hour) and Sundays are not available.

```json
{
  "date": "2026-09-25",
  "slots": [
    { "value": "09-11", "label": "9:00 AM - 11:00 AM", "remaining": 4, "available": true },
    { "value": "11-13", "label": "11:00 AM - 1:00 PM", "remaining": 4, "available": true },
    { "value": "14-16", "label": "2:00 PM - 4:00 PM", "remaining": 3, "available": true },
    { "value": "16-18", "label": "4:00 PM - 6:00 PM", "remaining": 0, "available": false }
  ]
}
```

---

## POST /api/booking/

Book a mechanic. The least busy free mechanic for that slot is assigned automatically. If the booking
comes from a conversation, a confirmation message is added to the chat and the conversation moves to
`booked`.

**Request**

| Field | Type | |
|---|---|---|
| `service` | string | service `code` from `/api/services/` |
| `customer_name` | string | |
| `phone` | string | 10-13 digits, spaces and dashes are stripped |
| `email` | string | optional |
| `vehicle_make`, `vehicle_model` | string | |
| `vehicle_year` | int | optional, 1980 to next year |
| `registration_number` | string | optional, e.g. `MH12AB1234` |
| `service_mode` | string | `garage`, `doorstep` or `pickup` |
| `address` | string | required for `doorstep` and `pickup` |
| `scheduled_date` | date | today to 30 days ahead, not a Sunday |
| `time_slot` | string | `09-11`, `11-13`, `14-16`, `16-18` |
| `notes` | string | optional |
| `conversation_id` | uuid | optional, links the booking to the chat |
| `diagnosis_id` | int | optional, must belong to that conversation |
| `save_details` | bool | optional, saves name / phone / email and the car to the profile |

```json
{
  "service": "brake-service",
  "conversation_id": "cede1c67-401e-46b3-b25d-80509076f1ae",
  "diagnosis_id": 1,
  "customer_name": "Rahul Verma",
  "phone": "98765 43210",
  "vehicle_make": "Maruti Suzuki",
  "vehicle_model": "Swift",
  "vehicle_year": 2017,
  "registration_number": "MH12AB1234",
  "service_mode": "garage",
  "scheduled_date": "2026-09-25",
  "time_slot": "09-11",
  "notes": "Grinding noise from front left"
}
```

**Response 201**

```json
{
  "id": "9d7a20e0-8027-4b77-9e77-26492b71bf04",
  "reference": "GM-2SRPNJ",
  "status": "confirmed",
  "status_label": "Confirmed",
  "can_cancel": true,
  "service": { "code": "brake-service", "name": "Brake Service", "price_min": 1200, "price_max": 6500, "...": "" },
  "mechanic": { "name": "Rakesh Kumar", "phone": "+919000000101", "speciality": "Engine & transmission", "experience_years": 14 },
  "customer_name": "Rahul Verma",
  "phone": "9876543210",
  "email": "",
  "vehicle_make": "Maruti Suzuki",
  "vehicle_model": "Swift",
  "vehicle_year": 2017,
  "registration_number": "MH12AB1234",
  "service_mode": "garage",
  "service_mode_label": "Garage visit",
  "address": "",
  "scheduled_date": "2026-09-25",
  "time_slot": "09-11",
  "time_slot_label": "9:00 AM - 11:00 AM",
  "notes": "Grinding noise from front left",
  "conversation_id": "cede1c67-401e-46b3-b25d-80509076f1ae",
  "diagnosis_id": 1,
  "created_at": "2026-09-23T12:56:40.537213+05:30"
}
```

**Errors:** 400 validation (see error format above), 409 if every mechanic in that slot is already booked.

## GET /api/booking/{id}/

`id` is the booking UUID from the create response. Same object as above, except the customer's phone
number is masked (`987****210`) because this link can be shared.

404 if it doesn't exist.

## POST /api/booking/{id}/cancel/

Cancels a confirmed booking. Frees the mechanic's slot. Returns the updated booking.

409 if it's already cancelled/completed or the slot has already started.

---

## Conversation history

### GET /api/conversations/

Latest 50 conversations for this client, newest first. Same `conversation` object as in the chat
response, with `latest_diagnosis` (`id`, `title`, `severity`) and a `last_message` preview.

### GET /api/conversations/{id}/

The conversation plus all `messages` in order (same message shape as the chat response).

### PATCH /api/conversations/{id}/

Change the reply language of a conversation. Only `language` can be changed.

```json
{ "language": "hi" }
```

Returns the conversation (same object as in the chat response). 400 for anything other than `en`, `hi`,
`hinglish`.

### DELETE /api/conversations/{id}/

Deletes the conversation with its messages, diagnoses and uploaded files. Bookings are kept.
Returns 204.

---

## Profile ("My garage")

Optional. Used to personalise the chat (greeting by name, "is this about your Swift?") and to prefill
bookings.

### GET /api/profile/

Returns an empty profile (not a 404) if nothing was saved yet.

```json
{
  "name": "Rahul Verma",
  "phone": "9876543210",
  "email": "",
  "city": "Pune",
  "cars": [
    {
      "id": 2,
      "make": "Maruti Suzuki",
      "model": "Swift",
      "year": 2017,
      "fuel_type": "petrol",
      "odometer_km": 65000,
      "registration_number": "MH12AB1234",
      "is_primary": true,
      "label": "2017 Maruti Suzuki Swift",
      "created_at": "2026-09-23T16:35:51.574800+05:30"
    }
  ]
}
```

### PUT /api/profile/

Update any of `name`, `phone`, `email`, `city` (partial updates are fine). Returns the profile.

### POST /api/profile/cars/

| Field | Type | |
|---|---|---|
| `make`, `model` | string | required |
| `year` | int | optional, 1980 to next year |
| `fuel_type` | string | optional: `petrol`, `diesel`, `cng`, `electric`, `hybrid`, `lpg` |
| `odometer_km` | int | optional |
| `registration_number` | string | optional, uppercased |
| `is_primary` | bool | optional, the first car is primary automatically |

Up to 5 cars. Returns the car (201).

### PATCH /api/profile/cars/{id}/

Same fields, all optional. `{"is_primary": true}` makes it the primary car.

### DELETE /api/profile/cars/{id}/

204. If it was the primary car, the oldest remaining car becomes primary.

**How the bot uses it**

- greeting: "Hi Rahul! ... Tell me what's going on with your Swift"
- if the car isn't known yet, the first follow-up question is "Is this about your 2017 Maruti Suzuki Swift?"
  (`["Yes, my Swift", "A different car"]`), or "Which of your cars is this about?" with one button per car
- "my swift is overheating" picks the saved Swift straight away, no question needed

---

## API logs

### GET /api/logs/?limit=50

This browser's recent API calls (newest first, max 100) with the Gemini calls made during each one,
plus the status of the server's Gemini key. Polling this endpoint isn't logged itself.

```json
{
  "gemini": {
    "status": "ok",
    "reason": "",
    "last_call_at": "2026-09-23T16:35:54.248109+05:30",
    "model": "gemini-3.5-flash-lite",
    "fallback_model": "gemini-2.5-flash",
    "using_custom_key": false
  },
  "stats": { "requests": 5, "bot_replies": 1, "handled_by_rules": 1, "ai_calls": 1, "ai_failures": 0 },
  "results": [
    {
      "id": 45,
      "method": "POST",
      "path": "/api/ai/check/",
      "status_code": 200,
      "duration_ms": 2420,
      "error": "",
      "ai_calls": [
        {
          "purpose": "key check",
          "model": "gemini-3.5-flash-lite",
          "ok": true,
          "reason": "",
          "message": "",
          "duration_ms": 2295,
          "custom_key": false
        }
      ],
      "created_at": "2026-09-23T16:35:54.248109+05:30"
    }
  ]
}
```

- `gemini.status`: `ok`, `failing` (with `reason`), `unknown` (not called yet) or `not_configured`. Only
  calls made with the server's key count, calls with a visitor's own key don't change it
- `stats.handled_by_rules`: chat / diagnosis requests that were answered without any Gemini call
- `ai_calls[].purpose`: `open question`, `photo analysis`, `audio recording analysis`, `video analysis`,
  `diagnosis second opinion`, `key check`
- `error`: the error message for 4xx / 5xx responses

Only metadata is stored (no request bodies). Logs older than 7 days are deleted by `manage.py prune_logs`.

### POST /api/ai/check/

Makes one tiny Gemini call to see if it answers, with the server key or the `X-Gemini-Key` header.

```json
{ "ok": true, "reason": "", "using_custom_key": false, "duration_ms": 2389 }
```

---

## GET /api/health/

```json
{ "status": "ok", "database": "ok", "ai_enabled": true }
```

## Quick test with curl

```bash
API=http://localhost:8000/api
ID=my-test-client-001

curl -s -X POST $API/chat/ -H "X-Client-Id: $ID" -H "Content-Type: application/json" \
  -d '{"message": "AC is blowing warm air"}'

curl -s -X POST $API/chat/ -H "X-Client-Id: $ID" -H "Content-Type: application/json" \
  -d '{"message": "Can you write me a poem?"}'     # -> kind: rejection
```
