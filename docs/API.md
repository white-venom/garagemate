# API documentation

Base URL: `https://YOUR-API-DOMAIN/api/` (locally `http://localhost:8000/api/`)

All requests and responses are JSON, except file uploads which are `multipart/form-data`.

## Identifying the user

There are no accounts. The frontend generates a random id once (stored in localStorage) and sends it
with every request:

```
X-Client-Id: 3f6c1a2e-8d4b-4f7a-9c1e-2b5d7e9f0a13
```

It can also be sent as `client_id` in the JSON body or query string. 8-64 characters, letters, numbers
and dashes. Conversations, uploads and diagnoses are only visible to the same client id, anyone else
gets a 404.

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
    "vehicle": { "make": "", "model": "", "year": null, "odometer_km": null, "fuel_type": "" },
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

**Conversation `stage`:** `new` -> `gathering` (asking follow-up questions) -> `diagnosed` -> `booked`

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
curl -X POST https://YOUR-API-DOMAIN/api/upload/ \
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
  "url": "https://YOUR-API-DOMAIN/media/uploads/2026/09/5189a03c3acc4759a02edef598bf4d03.png",
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
    "created_at": "2026-09-23T12:56:40.506445+05:30"
  },
  "message": { "id": 7, "role": "assistant", "kind": "diagnosis", "...": "same shape as chat messages" }
}
```

- `severity`: `low`, `medium`, `high`, `critical`
- `source`: `rules` (rule engine only) or `ai` (rule engine + Gemini second opinion)
- `probable_causes[].likelihood`: 0-1, rough share of the evidence, not a real probability

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

### DELETE /api/conversations/{id}/

Deletes the conversation with its messages, diagnoses and uploaded files. Bookings are kept.
Returns 204.

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
