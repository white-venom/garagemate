# GarageMate - AI car mechanic chatbot

A web chatbot where a car owner can talk to a virtual mechanic. It asks follow-up questions the way a
technician at the service counter would, gives a diagnosis with likely causes, severity and a rough cost,
and can book a mechanic if the customer wants one.

Built for the Full-Stack Developer Intern task.

## Links

| | |
|---|---|
| Live app (frontend, Vercel) | https://garagemate-beta.vercel.app |
| GitHub repo | https://github.com/white-venom/garagemate |
| Live API (AWS EC2), lists every endpoint | https://13-127-38-145.sslip.io/api/ |
| Health check (DB + Gemini status) | https://13-127-38-145.sslip.io/api/health/ |
| Services with prices | https://13-127-38-145.sslip.io/api/services/ |

**Docs**

| | |
|---|---|
| API docs (requests, responses, errors) | [docs/API.md](docs/API.md) |
| Try the API with curl | [docs/API.md#quick-test-with-curl](docs/API.md#quick-test-with-curl) |
| Architecture and database design | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| How Gemini is used (incl. web research) | [docs/AI_USAGE.md](docs/AI_USAGE.md) |

**Required APIs on the live server**

| Method | Endpoint | Live URL |
|---|---|---|
| POST | `/api/chat/` | https://13-127-38-145.sslip.io/api/chat/ |
| POST | `/api/upload/` | https://13-127-38-145.sslip.io/api/upload/ |
| POST | `/api/diagnosis/` | https://13-127-38-145.sslip.io/api/diagnosis/ |
| POST | `/api/booking/` | https://13-127-38-145.sslip.io/api/booking/ |
| GET | `/api/booking/{id}/` | `https://13-127-38-145.sslip.io/api/booking/{id}/` |

These need an `X-Client-Id` header (any random 8-64 character id, the frontend makes one per browser),
see [identifying the user](docs/API.md#identifying-the-user). After booking in the app, the booking status
page is at `https://garagemate-beta.vercel.app/booking/{id}`.

## Features

**Chat**
- Chat by text, or attach photos, audio clips and videos. There's also a mic button to record the noise
  the car is making straight from the browser (converted to WAV in the browser before upload).
- Only handles car related stuff. Off-topic questions get a polite "sorry, I can only help with cars".
- Asks follow-up questions (tap-to-answer quick replies, or answer in your own words) before diagnosing,
  the way a mechanic would. Questions already answered earlier are skipped, and questions that only make
  sense on one path are only asked there (a steady check engine light doesn't get "when is it worst?").
- Understands the way people actually type: "avg has dropped", "not giving the mileage", typos,
  "none of these", "my issue isn't listed", Hinglish and Hindi. Extra details or a side question in the
  middle of the questions are handled instead of being saved as the answer.
- Replies in **English, Hindi or Hinglish**. Pick it under the message box, or just write in Hindi / ask
  "hindi mein baat karo". Buttons and the diagnosis card are translated too.
- **Mileage problems start with the fuel**: once it knows petrol / diesel / CNG it searches current fuel news
  (E20 ethanol petrol, adulteration) and shares what's relevant with sources, then asks about the car
  itself (drop %, after a refuel?, driving, pickup, tyres, service).
- Safety warnings straight away for things like fuel smell, smoke, brake failure or the oil pressure light.
- Progress stepper in the header: Describe -> Questions -> Diagnosis -> Booking.

**Diagnosis & booking**
- Diagnosis card ("inspection report"): most likely cause, other possible causes with a likelihood, a
  severity gauge, whether it's safe to drive, the recommended service with a price range, and what to do
  until the car is checked.
- **Worth knowing · from the web** on the card: recalls, service campaigns and known issues for that exact
  model, found with Google Search while the customer answers the questions, with the sources linked.
- More details after the diagnosis ("the pedal is also soft now") update it instead of starting over.
- "Book a mechanic" from the diagnosis. Live slot availability, the least busy free mechanic is assigned
  automatically, and a mechanic can't be double booked (DB constraint). Booking status page with cancel.

**Personalised ("My garage")**
- Optional profile with the customer's name, phone and their cars (make, model, year, fuel, km, reg no).
  It opens by itself on the first visit until it's filled in (or skipped).
- The bot greets them by name. When they say "my car" it asks *"Is this about your 2017 Maruti Suzuki Swift?"*
  with one-tap answers instead of making them type the car again. Saying "my swift" picks the saved car
  directly.
- The booking form is prefilled from the profile, and a "save my details" tick stores new details for next time.
- The header shows the car as a number plate with its registration (UP 37 U 2004) once it's known.

**Transparency for reviewers**
- **API logs panel** (header button): every GET/POST this browser made, with status code and timing, plus
  every Gemini call made inside it (purpose, model, time, and why it failed if it did).
- Gemini status card with counters: total API calls, bot replies, replies handled by rules only, Gemini calls.
- If Gemini fails (free tier quota, overloaded, timeout...) the reply gets a small note saying the rule based
  fallback answered, so the app never looks broken. If our key keeps failing, the panel offers a field to
  use your own Gemini key (stored only in your browser, sent per request, never saved on the server).

## Where AI is used (and where it isn't)

The task said to keep AI usage low, so most of the bot is plain Python. Gemini is only called when
there's no reasonable way to do it with rules.

| What | How |
|---|---|
| Is this about cars? greeting / thanks / yes / no / "none of these" | keyword and regex rules |
| Working out the problem area (brakes, AC, battery, mileage...) | weighted keywords from a knowledge base |
| Follow-up questions, which ones to skip or ask | knowledge base, one question at a time |
| Free text answer -> the matching quick reply | word matching (negations and numbers must agree) |
| Car make / model / year / km / reg no from free text, matching saved cars | regex + list of Indian market models |
| Diagnosis | rule based scoring of possible causes |
| Hindi / Hinglish, typos, replies the rules can't place | Gemini, with the open question as context |
| Replying in Hindi / Hinglish | Gemini translation, cached forever per exact text |
| Fuel news, recalls, known issues for the model | Gemini + Google Search, cached 24h per problem + car |
| Diagnosis when the rules aren't confident, or photos/audio were sent | Gemini second opinion |
| Looking at photos, listening to recordings, watching videos | Gemini |
| Open questions like "which oil grade for a Creta?" | Gemini (web search only for time-sensitive ones), cached 24h |
| Emergency warnings, booking, slots, prices, profile | plain Django |

Default model is `gemini-3.5-flash-lite` (1-2s answers on the free tier) with `gemini-2.5-flash` as the
fallback when the first one is out of quota or overloaded. Web search runs on `gemini-2.5-flash`, which has
only 20 free requests a day, so it's rationed and cached. All configurable. Without a `GEMINI_API_KEY` the
whole flow still works in English, the bot just can't look at media, search, translate or answer open questions.
Every call, when it happens and what happens if it fails: [docs/AI_USAGE.md](docs/AI_USAGE.md).

## Tech stack

- **Frontend:** Next.js 16 (App Router, TypeScript), Tailwind CSS 4, lucide-react, react-markdown. Hosted on Vercel.
- **Backend:** Python 3.12, Django 5.2 LTS, Django REST Framework, SQLite, google-genai SDK. Gunicorn + nginx on an AWS EC2 free tier instance.

## Project structure

```
backend/
  config/          settings, urls
  core/            shared bits: error handler, Gemini wrapper, text matching, client id
  chat/            conversations, messages, uploads, the bot itself (chat/bot/)
  diagnosis/       symptom knowledge base + diagnosis engine
  bookings/        services, mechanics, bookings, slot logic
  customers/       "My garage" profile and saved cars
  apilogs/         request logging middleware, logs endpoint, Gemini key check
  deploy/          systemd service, nginx config, EC2 setup script
frontend/
  src/app/         pages (chat, booking status)
  src/components/  chat UI, diagnosis card, booking / profile modals, API logs panel
  src/lib/         API client, types, helpers
docs/              API docs and architecture notes
```

## Running locally

You need Python 3.12+ and Node 20+.

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # add GEMINI_API_KEY if you have one (optional)
python manage.py migrate           # also seeds services + mechanics and creates the cache table
python manage.py createsuperuser   # optional, for /admin
python manage.py runserver
```

API is now on http://localhost:8000/api/

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local         # NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

Open http://localhost:3000

### Tests

```bash
cd backend && python manage.py test      # 114 tests, Gemini is mocked
cd frontend && npm run lint && npm run build
```

## Deployment

### Backend on AWS (EC2 free tier)

1. Create the server with the CloudFormation template (Ubuntu 24.04 `t3.small`, security group with SSH only
   from your IP, encrypted gp3 disk, Elastic IP):

   ```bash
   aws ec2 create-key-pair --key-name garagemate-key --key-type ed25519 \
     --query KeyMaterial --output text > ~/.ssh/garagemate-key.pem
   aws cloudformation deploy --stack-name garagemate-api --template-file backend/deploy/ec2-stack.yaml \
     --parameter-overrides KeyName=garagemate-key SshCidr=<your ip>/32
   aws cloudformation describe-stacks --stack-name garagemate-api --query "Stacks[0].Outputs"
   ```

   The outputs include the IP, an `sslip.io` domain for it (e.g. `13-127-38-145.sslip.io`) and the SSH command.
   (Doing it by hand in the console works too: launch the instance, open ports 22/80/443, attach an Elastic IP.)
2. No domain needed, `<ip-with-dashes>.sslip.io` resolves to the IP and works with Let's Encrypt.
3. SSH in and run:

   ```bash
   git clone https://github.com/white-venom/garagemate.git /home/ubuntu/garagemate
   cd /home/ubuntu/garagemate/backend
   cp .env.example .env
   nano .env    # DJANGO_DEBUG=false, secret key, allowed hosts, CORS origin of the Vercel app, Gemini key,
                # MEDIA_ROOT=/var/www/garagemate/media
   sudo bash deploy/setup_ec2.sh 13-127-38-145.sslip.io     # email for Let's Encrypt is optional
   ```

   The script installs nginx + certbot, sets up the venv, runs migrations, starts gunicorn as a systemd
   service, gets an HTTPS certificate and adds daily cron jobs that remove unused uploads and old API logs.
4. Later updates: `bash deploy/update.sh`

SQLite is fine here since there's a single server. The database file and uploads live on the instance's EBS volume.

### Frontend on Vercel

With the Vercel CLI, from the `frontend` folder:

```bash
vercel link --project garagemate
printf 'https://13-127-38-145.sslip.io' | vercel env add NEXT_PUBLIC_API_URL production
vercel deploy --prod
```

(Or import the GitHub repo in the Vercel dashboard with **Root Directory** set to `frontend` and the same env var.)
Then allow the Vercel URL in the backend: `CORS_ALLOWED_ORIGINS`, or `CORS_ALLOWED_ORIGIN_REGEXES` to also cover
preview deployments, and `sudo systemctl restart garagemate`.

## Environment variables

Backend (`backend/.env`, see `.env.example` for all of them):

| Name | What it's for |
|---|---|
| `DJANGO_DEBUG` | `false` in production |
| `DJANGO_SECRET_KEY` | required when debug is off |
| `DJANGO_ALLOWED_HOSTS` | API domain(s), comma separated |
| `CORS_ALLOWED_ORIGINS` | frontend URL(s) |
| `GEMINI_API_KEY` | optional, free key from Google AI Studio |
| `GEMINI_MODEL` / `GEMINI_FALLBACK_MODEL` | fallback is used if the first one hits its quota |
| `GEMINI_TIMEOUT_SECONDS` | per call, default 25 |
| `GEMINI_RESEARCH_MODELS` | models with Google Search grounding, default `gemini-2.5-flash` |
| `RESEARCH_ENABLED` | `false` turns off all web search |
| `RESEARCH_TIMEOUT_SECONDS` / `RESEARCH_CACHE_HOURS` | 15s per search, results reused for 24h |
| `SQLITE_PATH`, `MEDIA_ROOT` | where the DB and uploads go |
| `THROTTLE_*` | per-IP rate limits |

Frontend: `NEXT_PUBLIC_API_URL` only.

## Things I'd improve with more time

- Real accounts (phone OTP) instead of an anonymous browser id, so the garage profile follows you across devices.
- Move Gemini calls to a background worker (Celery/RQ) so a slow AI response doesn't hold a gunicorn worker.
- Postgres once there's more than one server.
- SMS / WhatsApp confirmation for bookings, and a small panel for mechanics to update job status.
- Service history per saved car (last service date, km) so the bot can say "you're due for a service".
- Tune the knowledge base weights with real workshop data instead of my own guesses.
- Run the web research on a paid key or a model with more free searches, 20 a day runs out fast.
