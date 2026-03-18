import json
import asyncio
from pathlib import Path
from groq import Groq, RateLimitError, APITimeoutError, APIConnectionError
from app.config import settings
from fastapi import HTTPException
from functools import lru_cache
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

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

async def get_next_response(case: dict, messages: list) -> str:
    client = get_groq_client()
    current_turn = len([m for m in messages if m["role"] == "user"])

    system_prompt = PROMPTS["attending_physician"].format(
        case_presentation=case["presentation"],
        expected_differentials=json.dumps(case["expected_differentials"]),
        gold_standard_workup=json.dumps(case["gold_standard_workup"]),
        current_turn=current_turn,
        max_turns=10
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
        raise HTTPException(status_code=503, detail="AI service temporarily unavailable. Please try again.")
    except Exception as e:
        raise HTTPException(status_code=502, detail="AI service unavailable. Please try again.")

async def evaluate_session(case: dict, messages: list) -> dict:
    client = get_groq_client()

    transcript = "\n".join(
        f"{'Student' if m['role'] == 'user' else 'Dr. Chen'}: {m['content']}"
        for m in messages
        if m["role"] in ("user", "assistant")
    )

    prompt = PROMPTS["evaluator"].format(
        case_presentation=case["presentation"],
        expected_differentials=json.dumps(case["expected_differentials"]),
        gold_standard_workup=json.dumps(case["gold_standard_workup"]),
        session_transcript=transcript
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
                max_tokens=1000
            )
        )

        raw = response.choices[0].message.content
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]

        return json.loads(raw.strip())

    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="AI returned invalid response. Please try again.")
    except (RateLimitError, APITimeoutError, APIConnectionError):
        raise HTTPException(status_code=503, detail="AI service temporarily unavailable. Please try again.")
    except Exception:
        raise HTTPException(status_code=502, detail="AI service unavailable. Please try again.")