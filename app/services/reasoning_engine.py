import json
from pathlib import Path
from groq import Groq
from app.config import settings

client = Groq(api_key=settings.groq_api_key)

PROMPTS = {
    name: Path(f"app/prompts/{name}.txt").read_text()
    for name in ["attending_physician", "evaluator"]
}

async def get_next_response(case: dict, messages: list) -> str:
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

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=history,
        temperature=0.7,
        max_tokens=500
    )

    return response.choices[0].message.content

async def evaluate_session(case: dict, messages: list) -> dict:
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

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=1000
    )

    raw = response.choices[0].message.content
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0]
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0]

    return json.loads(raw.strip())