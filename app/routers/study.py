from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Header, Request
from typing import Optional
from supabase import create_client
from app.config import settings
from functools import lru_cache
from groq import Groq
from pathlib import Path
import json
import asyncio
import io
from slowapi import Limiter
from slowapi.util import get_remote_address

try:
    import PyPDF2
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

router = APIRouter(prefix="/study", tags=["study"])
limiter = Limiter(key_func=get_remote_address)

@lru_cache(maxsize=1)
def get_groq_client() -> Groq:
    return Groq(api_key=settings.groq_api_key)

PROMPTS = {
    name: Path(f"app/prompts/{name}.txt").read_text()
    for name in ["case_generator", "mcq_generator"]
}

VALID_CONTENT_TYPES = {"mcq", "cases"}

def get_user_and_client(authorization: Optional[str] = None):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    actual_token = authorization.replace("Bearer ", "")
    try:
        sb = create_client(settings.supabase_url, settings.supabase_key)
        sb.postgrest.auth(actual_token)
        user = sb.auth.get_user(actual_token).user
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user, sb
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Authentication service unavailable")

def extract_text(file_bytes: bytes, filename: str) -> str:
    ext = filename.lower().split('.')[-1]
    if ext == 'pdf' and PDF_SUPPORT:
        try:
            reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
            text = ""
            max_pages = min(len(reader.pages), 50)
            for i in range(max_pages):
                text += reader.pages[i].extract_text() or ""
                if len(text) > 12000:
                    break
            if not text.strip():
                raise HTTPException(
                    status_code=400,
                    detail="Could not extract text from PDF. Make sure it contains selectable text, not just images."
                )
            return text[:12000]
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=400, detail="Could not read PDF")
    elif ext in ('txt', 'md'):
        return file_bytes.decode('utf-8', errors='ignore')[:12000]
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type. Use PDF or TXT.")

@router.post("/generate")
@limiter.limit("5/minute")
async def generate_study_content(
    request: Request,
    file: UploadFile = File(...),
    content_type: str = Form(...),
    num_items: int = Form(...),
    authorization: Optional[str] = Header(None),
):
    user, sb = get_user_and_client(authorization)
    client = get_groq_client()

    if content_type not in VALID_CONTENT_TYPES:
        raise HTTPException(status_code=422, detail="content_type must be 'mcq' or 'cases'")

    file_bytes = await file.read()

    if len(file_bytes) > 150 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large. Maximum size is 150MB.")

    notes_text = extract_text(file_bytes, file.filename)

    if not notes_text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from file")

    if content_type == 'cases':
        num_items = min(max(num_items, 1), 5)
        prompt = PROMPTS["case_generator"].format(
            notes_text=notes_text,
            num_cases=num_items
        )
    else:
        num_items = min(max(num_items, 5), 30)
        prompt = PROMPTS["mcq_generator"].format(
            notes_text=notes_text,
            num_questions=num_items
        )

    try:
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=4000
            )
        )

        raw = response.choices[0].message.content
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]

        generated = json.loads(raw.strip())

    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="AI returned invalid response. Please try again.")
    except Exception:
        raise HTTPException(status_code=502, detail="AI service unavailable. Please try again.")

    title = f"{file.filename.split('.')[0]} — {content_type.upper()}"

    if content_type == 'cases':
        case_ids = []
        for case in generated.get('cases', []):
            case['is_public'] = False
            case['created_by'] = user.id
            result = sb.table("cases").insert(case).execute()
            case_ids.append(result.data[0]['id'])
        generated['case_ids'] = case_ids

    study_set = sb.table("study_sets").insert({
        "user_id": user.id,
        "title": title,
        "file_name": file.filename,
        "content_type": content_type,
        "raw_text": notes_text[:2000],
        "generated_content": generated
    }).execute()

    study_set_id = study_set.data[0]["id"]

    return {
        "study_set_id": study_set_id,
        "content_type": content_type,
        "generated": generated
    }

@router.get("/my-sets")
async def get_my_sets(
    authorization: Optional[str] = Header(None),
):
    user, sb = get_user_and_client(authorization)
    sets = sb.table("study_sets")\
        .select("id, title, file_name, content_type, created_at")\
        .eq("user_id", user.id)\
        .order("created_at", desc=True)\
        .execute()
    return sets.data

@router.get("/sets/{set_id}")
async def get_study_set(
    set_id: str,
    authorization: Optional[str] = Header(None),
):
    user, sb = get_user_and_client(authorization)
    study_set = sb.table("study_sets")\
        .select("*")\
        .eq("id", set_id)\
        .eq("user_id", user.id)\
        .single()\
        .execute()
    if not study_set.data:
        raise HTTPException(status_code=404, detail="Study set not found")
    return study_set.data