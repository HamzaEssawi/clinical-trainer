from fastapi import APIRouter, HTTPException, Depends, Header, Request
from typing import Optional
from supabase import create_client, Client
from app.config import settings
from app.services.reasoning_engine import get_next_response, evaluate_session
from app.models.session import ChatMessage, CustomCase
from slowapi import Limiter
from slowapi.util import get_remote_address

router = APIRouter(prefix="/sessions", tags=["sessions"])
limiter = Limiter(key_func=get_remote_address)

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

@router.post("/start/{case_id}")
@limiter.limit("10/minute")
async def start_session(
    request: Request,
    case_id: str,
    authorization: Optional[str] = Header(None),
):
    user, sb = get_user_and_client(authorization)

    case = sb.table("cases").select("*").eq("id", case_id).single().execute()
    if not case.data:
        raise HTTPException(status_code=404, detail="Case not found")

    session = sb.table("sessions").insert({
        "user_id": user.id,
        "case_id": case_id,
        "status": "active"
    }).execute()

    session_id = session.data[0]["id"]
    opening = await get_next_response(case.data, [])

    sb.table("messages").insert({
        "session_id": session_id,
        "role": "assistant",
        "content": opening,
        "turn_number": 0
    }).execute()

    return {
        "session_id": session_id,
        "opening_message": opening,
        "case_title": case.data["title"]
    }

@router.post("/start-custom")
@limiter.limit("10/minute")
async def start_custom_session(
    request: Request,
    body: CustomCase,
    authorization: Optional[str] = Header(None),
):
    user, sb = get_user_and_client(authorization)

    case = {
        "title": "Custom case",
        "specialty": "general",
        "difficulty": "resident",
        "presentation": body.case_text,
        "expected_differentials": [],
        "gold_standard_workup": {
            "immediate": [],
            "urgent": [],
            "key_decision_point": "Use your clinical judgment based on the case provided."
        },
        "is_public": False,
        "created_by": user.id
    }

    case_result = sb.table("cases").insert(case).execute()
    case_id = case_result.data[0]["id"]

    session = sb.table("sessions").insert({
        "user_id": user.id,
        "case_id": case_id,
        "status": "active"
    }).execute()

    session_id = session.data[0]["id"]
    opening = await get_next_response(case, [])

    sb.table("messages").insert({
        "session_id": session_id,
        "role": "assistant",
        "content": opening,
        "turn_number": 0
    }).execute()

    return {
        "session_id": session_id,
        "opening_message": opening,
        "case_title": "Custom case"
    }

@router.post("/{session_id}/chat")
@limiter.limit("30/minute")
async def chat(
    request: Request,
    session_id: str,
    body: ChatMessage,
    authorization: Optional[str] = Header(None),
):
    user, sb = get_user_and_client(authorization)

    session = sb.table("sessions")\
        .select("*, cases(*)")\
        .eq("id", session_id)\
        .eq("user_id", user.id)\
        .single().execute()

    if not session.data or session.data["status"] != "active":
        raise HTTPException(status_code=404, detail="Active session not found")

    case = session.data["cases"]
    turn = session.data["turn_count"] + 1

    sb.table("messages").insert({
        "session_id": session_id,
        "role": "user",
        "content": body.content,
        "turn_number": turn
    }).execute()

    all_messages = sb.table("messages")\
        .select("*")\
        .eq("session_id", session_id)\
        .order("turn_number").execute()

    ai_response = await get_next_response(case, all_messages.data)

    sb.table("messages").insert({
        "session_id": session_id,
        "role": "assistant",
        "content": ai_response,
        "turn_number": turn
    }).execute()

    sb.table("sessions")\
        .update({"turn_count": turn})\
        .eq("id", session_id).execute()

    if turn >= 10:
        return await _end_session_internal(session_id, case, all_messages.data, sb)

    return {"response": ai_response, "turn": turn, "max_turns": 10}

@router.post("/{session_id}/end")
@limiter.limit("10/minute")
async def end_session(
    request: Request,
    session_id: str,
    authorization: Optional[str] = Header(None),
):
    user, sb = get_user_and_client(authorization)

    session = sb.table("sessions")\
        .select("*, cases(*)")\
        .eq("id", session_id)\
        .eq("user_id", user.id)\
        .single().execute()

    if not session.data:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.data["status"] == "completed":
        raise HTTPException(status_code=400, detail="Session already completed.")

    case = session.data["cases"]

    messages = sb.table("messages")\
        .select("*")\
        .eq("session_id", session_id)\
        .order("turn_number").execute()

    user_messages = [m for m in messages.data if m["role"] == "user"]
    if len(user_messages) == 0:
        raise HTTPException(status_code=400, detail="You haven't answered anything yet.")

    return await _end_session_internal(session_id, case, messages.data, sb)

async def _end_session_internal(session_id: str, case: dict, messages: list, sb: Client) -> dict:
    evaluation = await evaluate_session(case, messages)

    sb.table("evaluations").insert({
        "session_id": session_id,
        "overall_score": evaluation["overall_score"],
        "differential_score": evaluation["differential_score"],
        "workup_score": evaluation["workup_score"],
        "reasoning_score": evaluation["reasoning_score"],
        "ai_feedback": evaluation["ai_feedback"],
        "missed_diagnoses": evaluation["missed_diagnoses"]
    }).execute()

    sb.table("sessions")\
        .update({"status": "completed"})\
        .eq("id", session_id).execute()

    return {"evaluation": evaluation, "session_id": session_id}

@router.get("/{session_id}/history")
async def get_history(
    session_id: str,
    authorization: Optional[str] = Header(None),
):
    user, sb = get_user_and_client(authorization)

    session = sb.table("sessions")\
        .select("id")\
        .eq("id", session_id)\
        .eq("user_id", user.id)\
        .single().execute()

    if not session.data:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = sb.table("messages")\
        .select("*")\
        .eq("session_id", session_id)\
        .order("turn_number").execute()

    return messages.data