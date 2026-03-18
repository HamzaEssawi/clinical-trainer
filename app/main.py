from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.routers import sessions, cases, progress, study

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Medicai",
    description="AI-powered clinical reasoning trainer",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.middleware("http")
async def limit_upload_size(request: Request, call_next):
    if request.method == "POST" and "content-length" in request.headers:
        content_length = int(request.headers["content-length"])
        if content_length > 150 * 1024 * 1024:
            return JSONResponse(
                status_code=413,
                content={"detail": "File too large. Maximum size is 10MB."}
            )
    return await call_next(request)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://medicai.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(sessions.router)
app.include_router(cases.router)
app.include_router(progress.router)
app.include_router(study.router)

@app.get("/health")
async def health():
    return {"status": "ok"}