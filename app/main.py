from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import sessions, cases, progress, study

app = FastAPI(
    title="Medicai",
    description="AI-powered clinical reasoning trainer",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://medicai.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(sessions.router)
app.include_router(cases.router)
app.include_router(progress.router)
app.include_router(study.router)

@app.get("/health")
async def health():
    return {"status": "ok"}