from fastapi import APIRouter, HTTPException, Header
from typing import Optional
from supabase import create_client
from app.config import settings

router = APIRouter(prefix="/progress", tags=["progress"])

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

@router.get("/my-stats")
async def my_stats(
    authorization: Optional[str] = Header(None),
):
    user, sb = get_user_and_client(authorization)
    results = sb.table("evaluations")\
        .select("*, sessions!inner(case_id, user_id)")\
        .eq("sessions.user_id", user.id)\
        .execute()
    scores = results.data
    if not scores:
        return {"message": "No sessions completed yet", "total_sessions": 0}
    avg = lambda key: round(sum(s[key] for s in scores) / len(scores))
    return {
        "total_sessions": len(scores),
        "average_overall": avg("overall_score"),
        "average_differential": avg("differential_score"),
        "average_workup": avg("workup_score"),
        "average_reasoning": avg("reasoning_score"),
        "weakest_area": min(
            ["differential", "workup", "reasoning"],
            key=lambda k: sum(s[f"{k}_score"] for s in scores)
        )
    }

@router.get("/completed-cases")
async def completed_cases(
    authorization: Optional[str] = Header(None),
):
    user, sb = get_user_and_client(authorization)
    sessions = sb.table("sessions")\
        .select("case_id")\
        .eq("user_id", user.id)\
        .eq("status", "completed")\
        .execute()
    case_ids = [s["case_id"] for s in sessions.data]
    return {"case_ids": case_ids}