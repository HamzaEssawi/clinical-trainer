from fastapi import APIRouter, HTTPException, Depends
from supabase import Client
from app.database import get_supabase

router = APIRouter(prefix="/cases", tags=["cases"])

@router.get("/")
async def list_cases(supabase: Client = Depends(get_supabase)):
    cases = supabase.table("cases")\
        .select("id, title, specialty, difficulty")\
        .eq("is_public", True)\
        .execute()
    return cases.data

@router.get("/{case_id}")
async def get_case(case_id: str, supabase: Client = Depends(get_supabase)):
    case = supabase.table("cases")\
        .select("id, title, specialty, difficulty, presentation")\
        .eq("id", case_id)\
        .single()\
        .execute()
    if not case.data:
        raise HTTPException(status_code=404, detail="Case not found")
    return case.data