from fastapi import APIRouter, HTTPException, Depends
from supabase import Client
from app.database import get_supabase

router = APIRouter(prefix="/progress", tags=["progress"])

def get_user(token: str, supabase: Client):
    try:
        user = supabase.auth.get_user(token).user
        supabase.postgrest.auth(token)
        return user
    except:
        raise HTTPException(status_code=401, detail="Not authenticated")

@router.get("/my-stats")
async def my_stats(token: str = "", supabase: Client = Depends(get_supabase)):
    user = get_user(token, supabase)

    results = supabase.table("evaluations")\
        .select("*, sessions(case_id, user_id)")\
        .execute()

    scores = [r for r in results.data if r["sessions"]["user_id"] == user.id]

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
async def completed_cases(token: str = "", supabase: Client = Depends(get_supabase)):
    user = get_user(token, supabase)
    sessions = supabase.table("sessions")\
        .select("case_id")\
        .eq("user_id", user.id)\
        .eq("status", "completed")\
        .execute()
    case_ids = [s["case_id"] for s in sessions.data]
    return {"case_ids": case_ids}