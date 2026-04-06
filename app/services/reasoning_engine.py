import json
import asyncio
from pathlib import Path
from groq import Groq, RateLimitError, APITimeoutError, APIConnectionError
from app.config import settings
from fastapi import HTTPException
from functools import lru_cache
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import structlog
logger = structlog.get_logger()

@lru_cache(maxsize=1)
def get_groq_client() -> Groq:
    return Groq(api_key=settings.groq_api_key)

PROMPTS = {
    name: Path(f"app/prompts/{name}.txt").read_text()
    for name in ["attending_physician", "evaluator"]
}

@retry(
    retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIConnectionError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    reraise=True
)
def _call_groq_sync(client: Groq, **kwargs):
    return client.chat.completions.create(**kwargs)

BLIND_OPENING = "A patient has come to see you. What would you like to know?"

async def get_next_response(case: dict, messages: list, blind_mode: bool = False) -> str:
    client = get_groq_client()

    # Blind mode opening: never call the LLM — return hardcoded sentence so the
    # model cannot possibly leak the case text on the first message.
    if blind_mode and len(messages) == 0:
        logger.info("reasoning_engine.blind_opening_hardcoded")
        return BLIND_OPENING

    if blind_mode:
        mode_instructions = (
            "BLIND MODE — you are answering a student's questions about a patient.\n"
            "The student does NOT know the case. They are gathering history by asking you questions.\n"
            "Rules:\n"
            "- Answer ONLY what the student directly asks about\n"
            "- If the finding is present in CASE INFORMATION: confirm or describe it naturally\n"
            "- If the finding is NOT in the case: say the patient denies it or it is normal\n"
            "- NEVER volunteer case details the student has not asked about\n"
            "- After answering, ask one focused question to advance their clinical reasoning\n"
            "When the student has gathered history and proposes differentials, probe their reasoning. "
            "Then guide through workup, then treatment & management."
        )
        history_phase = (
            "Blind mode — student is gathering history by asking questions. "
            "Answer based on CASE INFORMATION only when directly asked. Never volunteer anything."
        )
    else:
        mode_instructions = (
            "YOUR FIRST MESSAGE: Copy the CASE INFORMATION below word for word exactly as written. "
            "Then on a new line ask: 'What is your initial impression and top three differential diagnoses?'\n"
            "Do not skip this. Do not summarize. Copy the full case text exactly."
        )
        history_phase = "Full case has been presented to the student upfront."

    system_prompt = PROMPTS["attending_physician"].format(
        case_presentation=case["presentation"],
        expected_differentials=json.dumps(case["expected_differentials"]),
        gold_standard_workup=json.dumps(case["gold_standard_workup"]),
        mode_instructions=mode_instructions,
        history_phase=history_phase
    )

    logger.info(
        "reasoning_engine.prompt_assembled",
        blind_mode=blind_mode,
        message_count=len(messages),
        prompt_start=system_prompt[:500]
    )

    history = [{"role": "system", "content": system_prompt}]
    for m in messages:
        if m["role"] in ("user", "assistant"):
            history.append({"role": m["role"], "content": m["content"]})

    try:
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: _call_groq_sync(
                client,
                model="llama-3.3-70b-versatile",
                messages=history,
                temperature=0.7,
                max_tokens=500
            )
        )
        return response.choices[0].message.content
    except (RateLimitError, APITimeoutError, APIConnectionError) as e:
        logger.error("groq.rate_limit", error=str(e))
        raise HTTPException(status_code=503, detail="AI service temporarily unavailable. Please try again.")
    except Exception as e:
        logger.error("groq.error", error=str(e))
        raise HTTPException(status_code=502, detail="AI service unavailable. Please try again.")

async def evaluate_session(case: dict, messages: list, blind_mode: bool = False) -> dict:
    client = get_groq_client()

    transcript = "\n".join(
        f"{'Student' if m['role'] == 'user' else 'Dr. Chen'}: {m['content']}"
        for m in messages
        if m["role"] in ("user", "assistant")
    )

    if blind_mode:
        blind_mode_section = (
            "\n\nBLIND MODE SESSION — The student had to ask their own history and exam questions "
            "rather than receiving the case upfront. Evaluate what important history and exam questions "
            "they should have asked but did not, based on the case information above."
        )
        missed_questions_json = ',\n  "missed_questions": ["key question the student should have asked"]'
        blind_mode_scoring = (
            "- missed_questions: List the important history/exam questions the student failed to ask. "
            "Phrase each as a question (e.g., 'Did you ask about chest pain radiation?', "
            "'Did you ask about fever or chills?'). Include 3-6 questions."
        )
    else:
        blind_mode_section = ""
        missed_questions_json = ""
        blind_mode_scoring = ""

    prompt = PROMPTS["evaluator"].format(
        case_presentation=case["presentation"],
        expected_differentials=json.dumps(case["expected_differentials"]),
        gold_standard_workup=json.dumps(case["gold_standard_workup"]),
        session_transcript=transcript,
        blind_mode_section=blind_mode_section,
        missed_questions_json=missed_questions_json,
        blind_mode_scoring=blind_mode_scoring
    )

    try:
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: _call_groq_sync(
                client,
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=1200
            )
        )

        raw = response.choices[0].message.content
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]

        return json.loads(raw.strip())

    except (RateLimitError, APITimeoutError, APIConnectionError) as e:
        logger.error("groq.rate_limit", error=str(e))
        raise HTTPException(status_code=503, detail="AI service temporarily unavailable. Please try again.")
    except Exception as e:
        logger.error("groq.error", error=str(e))
        raise HTTPException(status_code=502, detail="AI service unavailable. Please try again.")

async def generate_case_summary(case: dict, evaluation: dict) -> str:
    client = get_groq_client()

    prompt = f"""You are a medical education expert. Generate a concise "Case Summary & High-Yield Review" for this clinical case.

CASE: {case['presentation']}
CORRECT DIAGNOSIS/DIFFERENTIALS: {json.dumps(case['expected_differentials'])}
KEY WORKUP: {json.dumps(case['gold_standard_workup'])}
STUDENT OVERALL SCORE: {evaluation.get('overall_score', 'N/A')}/100

Write exactly these 4 sections with these exact headers:

**Correct Diagnosis & Why**
Identify the primary diagnosis and explain in 2-3 sentences why this is correct based on the clinical features.

**Key History & Exam Findings**
List the 3-5 most important findings that pointed to this diagnosis. Use bullet points (- ).

**Pathophysiology**
Explain the underlying mechanism in 2-3 sentences at a resident level.

**Board & Exam Facts**
List 3-4 classic high-yield facts about this condition. Use bullet points (- ).

Be concise. No filler sentences. Medically accurate."""

    try:
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: _call_groq_sync(
                client,
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=800
            )
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error("groq.summary_error", error=str(e))
        return ""
