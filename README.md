# Clinical Reasoning Trainer

An AI-powered clinical reasoning trainer that teaches medical students and residents through Socratic questioning. Practice real clinical cases with Dr. Chen, an AI attending physician who guides your thinking without giving away answers — then scores your performance at the end.

![Clinical Trainer](https://img.shields.io/badge/stack-FastAPI%20%7C%20Next.js%20%7C%20Supabase%20%7C%20Groq-red)
![License](https://img.shields.io/badge/license-MIT-green)

---

## What it does

- **Socratic teaching** — Dr. Chen never gives answers directly. He asks focused questions that guide you to the right diagnosis.
- **18+ clinical cases** across Emergency Medicine, Internal Medicine, Neurology, Surgery, Psychiatry, and Pediatrics
- **AI scoring** — at the end of each session your differential reasoning, workup choices, and clinical thinking are scored out of 100
- **Progress tracking** — track your average scores and weakest areas over time
- **User accounts** — full auth with profile, avatar, and specialty settings

---

## Tech stack

### Backend
- **Python + FastAPI** — REST API with async support
- **Supabase** — PostgreSQL database, JWT authentication, file storage
- **Groq API (LLaMA 3.3 70B)** — free AI model for Socratic responses and session evaluation
- **Row Level Security** — users can only access their own data

### Frontend
- **Next.js 14 (App Router)** — React framework
- **Supabase JS client** — auth and real-time data
- **DM Sans + Instrument Serif** — typography
- Pure CSS — no component library

---

## Project structure

```
clinical-trainer/
├── app/                          # FastAPI backend
│   ├── main.py                   # App entry point
│   ├── config.py                 # Environment settings
│   ├── database.py               # Supabase client
│   ├── routers/
│   │   ├── sessions.py           # Chat session endpoints
│   │   ├── cases.py              # Clinical cases endpoints
│   │   └── progress.py           # Student analytics
│   ├── services/
│   │   ├── reasoning_engine.py   # AI pipeline (Groq)
│   │   └── session_service.py
│   └── prompts/
│       ├── attending_physician.txt  # Dr. Chen's teaching persona
│       └── evaluator.txt            # Session scoring prompt
├── seed_cases/                   # JSON clinical cases
├── seed.py                       # Database seeder
├── frontend/                     # Next.js frontend
│   ├── app/
│   │   ├── page.js               # Login / signup
│   │   ├── cases/page.js         # Case browser
│   │   ├── chat/[sessionId]/     # Chat interface
│   │   └── settings/page.js      # Profile settings
│   └── lib/
│       └── supabase.js           # Supabase client
└── requirements.txt
```

---

## Getting started

### Prerequisites
- Python 3.10+
- Node.js 18+
- A [Supabase](https://supabase.com) account (free)
- A [Groq](https://console.groq.com) API key (free)

### 1. Clone the repo

```bash
git clone https://github.com/yourusername/clinical-trainer.git
cd clinical-trainer
```

### 2. Set up the backend

```bash
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Mac/Linux

pip install -r requirements.txt
```

Create a `.env` file in the root:

```env
SUPABASE_URL=https://yourproject.supabase.co
SUPABASE_KEY=your_anon_key
SUPABASE_SERVICE_KEY=your_service_role_key
GROQ_API_KEY=your_groq_key
```

### 3. Set up Supabase

Run the SQL schema in your Supabase SQL editor (see `schema.sql` or the setup guide in the wiki).

Create a public storage bucket called `avatars`.

### 4. Seed the database

```bash
python seed.py
```

### 5. Start the backend

```bash
python -m uvicorn app.main:app --reload
```

API docs available at `http://localhost:8000/docs`

### 6. Set up the frontend

```bash
cd frontend
npm install
```

Create `frontend/.env.local`:

```env
NEXT_PUBLIC_SUPABASE_URL=https://yourproject.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_anon_key
```

```bash
npm run dev
```

Open `http://localhost:3000`

---

## API endpoints

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/cases/` | List all public cases |
| GET | `/cases/{id}` | Get a specific case |
| POST | `/sessions/start/{case_id}` | Start a new session |
| POST | `/sessions/{id}/chat` | Send a message, get AI response |
| POST | `/sessions/{id}/end` | End session and trigger evaluation |
| GET | `/sessions/{id}/history` | Get full message history |
| GET | `/progress/my-stats` | Get student analytics |

---

## Clinical cases included

| Case | Specialty | Difficulty |
|------|-----------|------------|
| Chest pain — 58-year-old male (STEMI) | Emergency Medicine | Resident |
| Sudden dyspnea — post-partum female (PE) | Emergency Medicine | Resident |
| Fever and neck stiffness — 19-year-old (Meningitis) | Emergency Medicine | Intern |
| Thunderclap headache — 45-year-old (SAH) | Neurology | Resident |
| Sudden left-sided weakness — 67-year-old (Stroke) | Neurology | Resident |
| Abdominal pain — 22-year-old male (Appendicitis) | Surgery | Intern |
| Altered mental status — diabetic (DKA) | Internal Medicine | Intern |
| Agitation and mania — 28-year-old (Bipolar) | Psychiatry | Resident |
| Irritable infant with bulging fontanelle (Meningitis) | Pediatrics | Fellow |
| Decreased urine output — post-op (AKI) | Internal Medicine | Fellow |
| Confusion and fever — elderly female (Urosepsis) | Internal Medicine | Intern |
| Severe dyspnea — 16-year-old (Asthma) | Emergency Medicine | Intern |
| Vomiting blood — alcoholic (GI Bleed) | Internal Medicine | Resident |
| Pelvic pain — young female (Ectopic Pregnancy) | Emergency Medicine | Resident |
| Severe headache + vision changes (Hypertensive Emergency) | Internal Medicine | Resident |
| Tremors and agitation (Alcohol Withdrawal) | Internal Medicine | Resident |
| Extreme agitation — Graves disease (Thyroid Storm) | Internal Medicine | Fellow |
| Throat swelling after eating (Anaphylaxis) | Emergency Medicine | Intern |

---

## How the AI works

Every chat turn rebuilds the full conversation history from the database and passes it to the AI with the case details and teaching persona. The AI has no memory between calls — the database is the memory.

```
User message
    → Load full session history from Supabase
    → Build prompt: system persona + case + full history
    → Call Groq API (LLaMA 3.3 70B)
    → Parse response
    → Save to Supabase messages table
    → Return to frontend
```

At session end, a separate evaluator prompt scores the student's reasoning against the gold standard answer key stored in the case data.

---

## Environment variables

| Variable | Description |
|----------|-------------|
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_KEY` | Supabase anon/public key |
| `SUPABASE_SERVICE_KEY` | Supabase service role key (bypasses RLS) |
| `GROQ_API_KEY` | Groq API key for LLaMA model |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase URL for frontend |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon key for frontend |

---

## License

MIT
