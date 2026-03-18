from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from supabase import Client
from app.database import get_supabase
from app.config import settings
from groq import Groq
from pathlib import Path
import json
import io

try:
    import PyPDF2
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

router = APIRouter(prefix="/study", tags=["study"])
client = Groq(api_key=settings.groq_api_key)

PROMPTS = {
    name: Path(f"app/prompts/{name}.txt").read_text()
    for name in ["case_generator", "mcq_generator"]
}

def get_user(token: str, supabase: Client):
    try:
        user = supabase.auth.get_user(token).user
        supabase.postgrest.auth(token)
        return user
    except:
        raise HTTPException(status_code=401, detail="Not authenticated")

def extract_text(file_bytes: bytes, filename: str) -> str:
    ext = filename.lower().split('.')[-1]
    if ext == 'pdf' and PDF_SUPPORT:
        try:
            reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
            return text[:12000]
        except:
            raise HTTPException(status_code=400, detail="Could not read PDF")
    elif ext in ('txt', 'md'):
        return file_bytes.decode('utf-8', errors='ignore')[:12000]
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type. Use PDF or TXT.")

@router.post("/generate")
async def generate_study_content(
    file: UploadFile = File(...),
    content_type: str = Form(...),
    num_items: int = Form(...),
    token: str = Form(...),
    supabase: Client = Depends(get_supabase)
):
    user = get_user(token, supabase)

    file_bytes = await file.read()
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

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=4000
    )

    raw = response.choices[0].message.content
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0]
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0]

    generated = json.loads(raw.strip())

    title = f"{file.filename.split('.')[0]} — {content_type.upper()}"

    if content_type == 'cases':
        case_ids = []
        for case in generated.get('cases', []):
            case['is_public'] = False
            case['created_by'] = user.id
            result = supabase.table("cases").insert(case).execute()
            case_ids.append(result.data[0]['id'])
        generated['case_ids'] = case_ids

    study_set = supabase.table("study_sets").insert({
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
async def get_my_sets(token: str = "", supabase: Client = Depends(get_supabase)):
    user = get_user(token, supabase)
    sets = supabase.table("study_sets")\
        .select("id, title, file_name, content_type, created_at")\
        .eq("user_id", user.id)\
        .order("created_at", desc=True)\
        .execute()
    return sets.data

@router.get("/sets/{set_id}")
async def get_study_set(set_id: str, token: str = "", supabase: Client = Depends(get_supabase)):
    user = get_user(token, supabase)
    study_set = supabase.table("study_sets")\
        .select("*")\
        .eq("id", set_id)\
        .eq("user_id", user.id)\
        .single()\
        .execute()
    if not study_set.data:
        raise HTTPException(status_code=404, detail="Study set not found")
    return study_set.data