# Medicai — AI Clinical Reasoning Trainer

Train smarter. Reason like a doctor.

Medicai is a full-stack AI-powered clinical reasoning trainer for medical students and residents. Practice real clinical cases with Dr. Chen, your AI attending physician who teaches through Socratic questioning — the same method real attendings use. Get scored on your differential diagnosis, workup, and clinical reasoning after every session.

---

## Features

- **33 clinical cases** across Emergency Medicine, Internal Medicine, Neurology, Surgery, Psychiatry, Pediatrics, Cardiology, Pulmonology, Gastroenterology, Endocrinology, Infectious Disease, Rheumatology, Hematology, Nephrology, Obstetrics, Dermatology, and Vascular Surgery
- **Socratic AI teaching** — Dr. Chen never gives answers, only targeted questions that force you to reason
- **AI scoring** — scored on differentials (0-100), workup (0-100), and reasoning (0-100) after every session
- **Custom cases** — paste any clinical scenario and practice with Dr. Chen
- **Study generator** — upload lecture notes (PDF/TXT up to 150MB) and generate MCQ questions or clinical cases
- **Progress tracking** — track sessions completed, average scores, and weakest areas
- **Completed case tracking** — browse available and completed cases with filters by specialty and difficulty
- **Profile and avatar** — customizable profile with specialty and photo

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI, Uvicorn |
| AI | Groq API (LLaMA 3.3 70B) |
| Database | Supabase (PostgreSQL + RLS) |
| Auth | Supabase Auth (JWT) |
| Storage | Supabase Storage (avatars) |
| Frontend | Next.js 14 (App Router), plain CSS |
| Fonts | Instrument Serif, DM Sans |
| Rate limiting | slowapi |
| Retry logic | tenacity |
| Logging | structlog |
| Deployment | Railway (backend), Vercel (frontend) |

---

## Project Structure
```
clinical-trainer/
├── app/
│   ├── main.py                    # FastAPI app, CORS, rate limiting, upload middleware
│   ├── config.py                  # Pydantic settings with validation
│   ├── database.py                # Supabase client factory
│   ├── models/
│   │   └── session.py             # Pydantic request models with validation
│   ├── routers/
│   │   ├── sessions.py            # Start, chat, end, history endpoints
│   │   ├── cases.py               # List and get cases
│   │   ├── progress.py            # Stats and completed cases
│   │   └── study.py               # Generate, list, and get study sets
│   ├── services/
│   │   └── reasoning_engine.py    # Groq AI calls with retry logic
│   └── prompts/
│       ├── attending_physician.txt
│       ├── evaluator.txt
│       ├── case_generator.txt
│       └── mcq_generator.txt
├── seed_cases/                    # 33 JSON clinical cases
├── seed.py                        # Database seeder
├── frontend/
│   ├── app/
│   │   ├── page.js                # Login / signup
│   │   ├── cases/page.js          # Case browser with filters and tabs
│   │   ├── chat/[sessionId]/page.js  # Chat interface with Dr. Chen
│   │   ├── study/page.js          # Study generator
│   │   ├── custom/page.js         # Custom case entry
│   │   ├── settings/page.js       # Profile, avatar, password
│   │   ├── about/page.js          # About page
│   │   └── components/
│   │       └── Navbar.js          # Shared navbar with hamburger menu
│   ├── lib/
│   │   ├── api.js                 # apiFetch helper (Authorization header)
│   │   └── supabase.js            # Supabase JS client
│   └── next.config.js             # Security headers, CSP
└── requirements.txt
```

---

## Database Schema
```sql
profiles        (id, email, full_name, specialty, avatar_url, role, created_at)
cases           (id, title, specialty, difficulty, presentation, expected_differentials, gold_standard_workup, is_public, created_by)
sessions        (id, user_id, case_id, status, turn_count, started_at, ended_at)
messages        (id, session_id, role, content, turn_number, created_at)
evaluations     (id, session_id, overall_score, differential_score, workup_score, reasoning_score, ai_feedback, missed_diagnoses)
study_sets      (id, user_id, title, file_name, content_type, raw_text, generated_content, created_at)
```

RLS enabled on all tables. Each user can only read and write their own data.

---

## Local Development

### Prerequisites

- Python 3.11+
- Node.js 18+
- Supabase project
- Groq API key (free tier works)

### Backend setup
```bash
cd clinical-trainer
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate

pip install -r requirements.txt
```

Create `app/.env`:
```env
SUPABASE_URL=https://yourproject.supabase.co
SUPABASE_KEY=your_anon_key
SUPABASE_SERVICE_KEY=your_service_role_key
GROQ_API_KEY=your_groq_key
```

Seed the database:
```bash
python seed.py
```

Start the backend:
```bash
uvicorn app.main:app --reload
```

Backend runs at `http://localhost:8000`

### Frontend setup
```bash
cd frontend
npm install
```

Create `frontend/.env.local`:
```env
NEXT_PUBLIC_SUPABASE_URL=https://yourproject.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_anon_key
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Start the frontend:
```bash
npm run dev
```

Frontend runs at `http://localhost:3000`

---

## API Endpoints

All endpoints require `Authorization: Bearer <token>` header.

| Method | Endpoint | Description | Rate limit |
|---|---|---|---|
| GET | `/cases/` | List all public cases | — |
| GET | `/cases/{id}` | Get case details | — |
| POST | `/sessions/start/{case_id}` | Start a session | 10/min |
| POST | `/sessions/start-custom` | Start a custom case session | 10/min |
| POST | `/sessions/{id}/chat` | Send a message to Dr. Chen | 30/min |
| POST | `/sessions/{id}/end` | End and evaluate a session | 10/min |
| GET | `/sessions/{id}/history` | Get session message history | — |
| GET | `/progress/my-stats` | Get user stats and averages | — |
| GET | `/progress/completed-cases` | Get completed case IDs | — |
| POST | `/study/generate` | Generate MCQs or cases from notes | 5/min |
| GET | `/study/my-sets` | List past study sets | — |
| GET | `/study/sets/{id}` | Get a specific study set | — |
| GET | `/health` | Health check | — |

---

## Deployment

### Backend — Railway

1. Push to GitHub
2. Create new Railway project → Deploy from GitHub repo
3. Set root directory to `/` (not `/app`)
4. Add environment variables: `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_KEY`, `GROQ_API_KEY`
5. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### Frontend — Vercel

1. Import GitHub repo to Vercel
2. Set root directory to `frontend`
3. Add environment variables: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_API_URL` (your Railway URL)
4. Deploy

After deploying, update `allow_origins` in `app/main.py` with your Vercel URL.

---

## Security

- JWT tokens sent via `Authorization: Bearer` header only — never in URL query params
- Per-request Supabase client — no shared mutable state between concurrent requests
- RLS policies on all Supabase tables
- Rate limiting on all AI-calling endpoints via slowapi
- Input validation on all request bodies via Pydantic
- File upload size limit — 150MB max
- PDF text extraction capped at 12,000 characters / 50 pages
- Security headers on all routes — CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy
- API docs disabled in production
- Structured logging via structlog with user ID and session ID on every event
- Groq API calls run in thread executor — non-blocking async
- Automatic retry on Groq rate limits and timeouts via tenacity (3 attempts, exponential backoff)

---

## How Scoring Works

At the end of every session Dr. Chen evaluates the full conversation against a gold standard answer key:

- **Differential score** — did you identify the key diagnoses including the most critical one?
- **Workup score** — did you order the right tests in the right priority without over-ordering?
- **Reasoning score** — did you connect clinical findings to your diagnoses explicitly?
- **Overall score** — weighted combination of all three

---

## License

MIT