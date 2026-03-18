from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional
from supabase import Client
from app.database import get_supabase
from app.services.reasoning_engine import get_next_response, evaluate_session
from app.models.session import ChatMessage, CustomCase

router = APIRouter(prefix="/sessions", tags=["sessions"])

def get_user_and_client(
    supabase: Client,
    token: str = "",
    authorization: Optional[str] = None
):
    actual_token = token
    if authorization and authorization.startswith("Bearer "):
        actual_token = authorization.replace("Bearer ", "")
    if not actual_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        user = supabase.auth.get_user(actual_token).user
        supabase.postgrest.auth(actual_token)
        return user, supabase
    except:
        raise HTTPException(status_code=401, detail="Not authenticated")

@router.post("/start/{case_id}")
async def start_session(
    case_id: str,
    token: str = "",
    authorization: Optional[str] = Header(None),
    supabase: Client = Depends(get_supabase)
):
    user, sb = get_user_and_client(supabase, token, authorization)

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
async def start_custom_session(
    body: CustomCase,
    token: str = "",
    authorization: Optional[str] = Header(None),
    supabase: Client = Depends(get_supabase)
):
    user, sb = get_user_and_client(supabase, token, authorization)

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
async def chat(
    session_id: str,
    body: ChatMessage,
    token: str = "",
    authorization: Optional[str] = Header(None),
    supabase: Client = Depends(get_supabase)
):
    user, sb = get_user_and_client(supabase, token, authorization)

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
        return await end_session(session_id, token, supabase)

    return {"response": ai_response, "turn": turn, "max_turns": 10}

@router.post("/{session_id}/end")
async def end_session(
    session_id: str,
    token: str = "",
    authorization: Optional[str] = Header(None),
    supabase: Client = Depends(get_supabase)
):
    user, sb = get_user_and_client(supabase, token, authorization)

    session = sb.table("sessions")\
        .select("*, cases(*)")\
        .eq("id", session_id)\
        .eq("user_id", user.id)\
        .single().execute()

    case = session.data["cases"]

    messages = sb.table("messages")\
        .select("*")\
        .eq("session_id", session_id)\
        .order("turn_number").execute()

    user_messages = [m for m in messages.data if m["role"] == "user"]
    if len(user_messages) == 0:
        raise HTTPException(status_code=400, detail="You haven't answered anything yet.")

    evaluation = await evaluate_session(case, messages.data)

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
    token: str = "",
    authorization: Optional[str] = Header(None),
    supabase: Client = Depends(get_supabase)
):
    user, sb = get_user_and_client(supabase, token, authorization)

    messages = sb.table("messages")\
        .select("*")\
        .eq("session_id", session_id)\
        .order("turn_number").execute()

    return messages.data