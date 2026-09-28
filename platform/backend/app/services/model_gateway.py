import json
from typing import Any

import httpx

from app.core.config import get_settings
from app.schemas.scheduling import ScheduleIntent


async def _complete(system_prompt: str, user_prompt: str, max_tokens: int) -> str:
    settings = get_settings()
    if not settings.model_configured or not settings.model_name or not settings.model_api_base:
        raise RuntimeError(
            "Hosted model configuration requires MODEL_NAME and MODEL_API_BASE"
        )
    headers = {"Content-Type": "application/json"}
    if settings.model_api_key:
        headers["Authorization"] = f"Bearer {settings.model_api_key.get_secret_value()}"

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{settings.model_api_base.rstrip('/')}/chat/completions",
            headers=headers,
            json={
                "model": settings.model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": max_tokens,
            },
        )
        response.raise_for_status()
        body = response.json()

    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("Configured model returned an invalid response shape") from exc
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("Configured model returned an empty response")
    return content.strip()


async def interpret_scheduling_request(request_text: str) -> ScheduleIntent:
    content = await _complete(
        (
            "Convert a planner request to JSON with exactly these fields: "
            "planning_horizon_days (integer 1-5), objective (one of balanced, "
            "due_date, changeover). Use balanced unless the request clearly "
            "prioritizes one of the other objectives. Do not return prose."
        ),
        request_text,
        100,
    )
    try:
        return ScheduleIntent.model_validate(json.loads(content))
    except (json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError("Configured model returned an invalid scheduling intent") from exc


async def explain_schedule(result: dict[str, Any]) -> str:
    settings = get_settings()
    if not settings.model_configured:
        metrics = result["metrics"]
        return (
            f"All {metrics['orders_scheduled']} orders fit within the hard constraints. "
            f"The plan has {metrics['late_jobs']} late jobs and "
            f"{metrics['total_changeover_hours']} estimated changeover hours. "
            "Publishing remains blocked until planner approval."
        )

    return await _complete(
        (
            "Explain a production schedule using only the supplied metrics. "
            "Do not claim any hard constraint is satisfied unless the input "
            "says the schedule is feasible. Be concise."
        ),
        json.dumps(result, separators=(",", ":")),
        250,
    )
