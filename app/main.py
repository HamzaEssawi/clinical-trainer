from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import sessions, cases, progress

app = FastAPI(
    title="Clinical Reasoning Trainer",
    description="AI-powered clinical reasoning trainer",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router)
app.include_router(cases.router)
app.include_router(progress.router)

@app.get("/health")
async def health():
    return {"status": "ok"}