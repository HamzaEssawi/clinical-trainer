from fastapi import APIRouter, HTTPException, Header
from typing import Optional
from supabase import create_client
from app.config import settings

router = APIRouter(prefix="/cases", tags=["cases"])

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

@router.get("/")
async def list_cases(
    authorization: Optional[str] = Header(None),
):
    user, sb = get_user_and_client(authorization)
    cases = sb.table("cases")\
        .select("id, title, specialty, difficulty")\
        .eq("is_public", True)\
        .execute()
    return cases.data

@router.get("/{case_id}")
async def get_case(
    case_id: str,
    authorization: Optional[str] = Header(None),
):
    user, sb = get_user_and_client(authorization)
    case = sb.table("cases")\
        .select("id, title, specialty, difficulty, presentation")\
        .eq("id", case_id)\
        .single()\
        .execute()
    if not case.data:
        raise HTTPException(status_code=404, detail="Case not found")
    return case.data