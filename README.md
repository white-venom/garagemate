# GarageMate - AI car mechanic chatbot

A web chatbot where a car owner can talk to a virtual mechanic. It asks follow-up questions the way a
technician at the service counter would, gives a diagnosis with likely causes, severity and a rough cost,
and can book a mechanic if the customer wants one.

Built for the Full-Stack Developer Intern task.

| | |
|---|---|
| Live app | https://YOUR-APP.vercel.app |
| Live API | https://YOUR-API-DOMAIN/api/ |
| API docs | [docs/API.md](docs/API.md) |
| Architecture | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |

## Features

- Chat by text, or attach photos, audio clips and videos. There's also a mic button to record the noise
  the car is making straight from the browser.
- Only handles car related stuff. Off-topic questions get a polite "sorry, I can only help with cars".
- Asks 2-4 follow-up questions (with tap-to-answer quick replies) before diagnosing. Questions the user
  already answered in their first message are skipped.
- Diagnosis card: most likely cause, other possible causes with a likelihood, severity, whether it's safe
  to drive, the recommended service with a price range, and what to do until the car is checked.
- Safety warnings straight away for things like fuel smell, smoke, brake failure or the oil pressure light.
- "Book Mechanic" from the diagnosis. The backend checks slot availability and assigns the least busy free
  mechanic. A mechanic can't be double booked (DB constraint).
- Sidebar with conversation / diagnosis history, booking status page with a cancel option.
- Works on mobile.

## Where AI is used (and where it isn't)

The task said to keep AI usage low, so most of the bot is plain Python. Gemini is only called when
there's no reasonable way to do it with rules.

| What | How |
|---|---|
| Is this about cars? greeting / thanks / yes / no | keyword and regex rules |
| Working out the problem area (brakes, AC, battery...) | weighted keywords from a knowledge base |
| Follow-up questions | knowledge base, one question at a time |
| Car make / model / year / km from free text | regex + list of Indian market models |
| Diagnosis | rule based scoring of possible causes |
| Diagnosis when the rules aren't confident, or photos/audio were sent | Gemini second opinion |
| Looking at photos, listening to recordings, watching videos | Gemini |
| Open questions like "which oil grade for a Creta?" | Gemini (answers cached for 24h) |
| Emergency warnings | rules |
| Booking, slots, mechanic assignment, prices | Django |

Every bot message has a `used_ai` flag, so it's easy to see how often Gemini was actually needed (it's
also shown in the UI). Without a `GEMINI_API_KEY` the whole flow still works, the bot just can't look at
media or answer open questions.

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
  deploy/          systemd service, nginx config, EC2 setup script
frontend/
  src/app/         pages (chat, booking status)
  src/components/  chat UI, diagnosis card, booking modal...
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
python manage.py migrate           # also seeds the services and mechanics
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
cd backend && python manage.py test      # 61 tests, Gemini is mocked
cd frontend && npm run lint && npm run build
```

## Deployment

### Backend on AWS (EC2 free tier)

1. Launch an Ubuntu 24.04 `t2.micro` (or `t3.micro`) instance. Open ports 22, 80 and 443 in the security group.
   Attach an Elastic IP so the address doesn't change.
2. Point a domain at the IP. If you don't have one, `<ip-with-dashes>.sslip.io` works (e.g. `13-233-10-20.sslip.io`).
3. SSH in and run:

   ```bash
   git clone https://github.com/YOUR-USER/YOUR-REPO.git /home/ubuntu/garagemate
   cd /home/ubuntu/garagemate/backend
   cp .env.example .env
   nano .env    # DJANGO_DEBUG=false, secret key, allowed hosts, CORS origin of the Vercel app, Gemini key,
                # MEDIA_ROOT=/var/www/garagemate/media
   sudo bash deploy/setup_ec2.sh api.yourdomain.com you@example.com
   ```

   The script installs nginx + certbot, sets up the venv, runs migrations, starts gunicorn as a systemd
   service, gets an HTTPS certificate and adds a daily cron job that removes unused uploads.
4. Later updates: `bash deploy/update.sh`

SQLite is fine here since there's a single server. The database file and uploads live on the instance's EBS volume.

### Frontend on Vercel

1. Import the GitHub repo in Vercel and set **Root Directory** to `frontend`.
2. Add the env var `NEXT_PUBLIC_API_URL=https://api.yourdomain.com`.
3. Deploy. Then add the Vercel URL to `CORS_ALLOWED_ORIGINS` in the backend `.env` and restart
   (`sudo systemctl restart garagemate`).

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
| `SQLITE_PATH`, `MEDIA_ROOT` | where the DB and uploads go |
| `THROTTLE_*` | per-IP rate limits |

Frontend: `NEXT_PUBLIC_API_URL` only.

## Things I'd improve with more time

- Real accounts (phone OTP) instead of an anonymous browser id.
- Move Gemini calls to a background worker (Celery/RQ) so a slow AI response doesn't hold a gunicorn worker.
- Postgres once there's more than one server.
- SMS / WhatsApp confirmation for bookings, and a small panel for mechanics to update job status.
- Tune the knowledge base weights with real workshop data instead of my own guesses.
