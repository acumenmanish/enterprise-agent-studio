import json
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.schemas.scheduling import ScheduleIntent


async def _complete(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    settings: Settings,
    api_key_override: str | None = None,
) -> str:
    if not settings.model_configured and api_key_override is None:
        raise RuntimeError("Hosted model configuration is incomplete")

    api_key = api_key_override or (
        settings.effective_model_api_key.get_secret_value()
        if settings.effective_model_api_key
        else None
    )
    if settings.effective_model_provider == "anthropic":
        if api_key is None:
            raise RuntimeError("Anthropic API key is not configured")
        endpoint = "https://api.anthropic.com/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
        payload = {
            "model": settings.effective_model_name,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
            "max_tokens": max_tokens,
        }
    elif settings.effective_model_provider == "openai-compatible":
        if not settings.model_api_base:
            raise RuntimeError("OpenAI-compatible model endpoint is not configured")
        endpoint = f"{settings.model_api_base.rstrip('/')}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "model": settings.effective_model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
        }
    else:
        raise RuntimeError(f"Unsupported model provider: {settings.effective_model_provider}")

    async with httpx.AsyncClient(timeout=20.0, follow_redirects=False) as client:
        response = await client.post(endpoint, headers=headers, json=payload)
        response.raise_for_status()
        body = response.json()

    if settings.effective_model_provider == "anthropic":
        content = body.get("content") if isinstance(body, dict) else None
        if not isinstance(content, list):
            raise RuntimeError("Configured model returned an invalid response shape")
        text_blocks = [
            block["text"]
            for block in content
            if isinstance(block, dict)
            and block.get("type") == "text"
            and isinstance(block.get("text"), str)
        ]
        if not text_blocks:
            raise RuntimeError("Configured model returned an empty response")
        return "\n".join(text_blocks).strip()

    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("Configured model returned an invalid response shape") from exc
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("Configured model returned an empty response")
    return content.strip()


async def interpret_scheduling_request(
    request_text: str,
    settings: Settings | None = None,
    system_prompt: str | None = None,
    api_key_override: str | None = None,
) -> ScheduleIntent:
    intent_contract = (
        "Convert the planner request to JSON with exactly these fields: "
        "planning_horizon_days (integer 1-5), objective (one of balanced, "
        "due_date, changeover). Use balanced unless the request clearly "
        "prioritizes one of the other objectives. Do not return prose."
    )
    content = await _complete(
        f"{system_prompt}\n\n{intent_contract}" if system_prompt else intent_contract,
        request_text,
        100,
        settings or get_settings(),
        api_key_override,
    )
    try:
        return ScheduleIntent.model_validate(json.loads(content))
    except (json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError("Configured model returned an invalid scheduling intent") from exc


async def explain_schedule(
    result: dict[str, Any],
    settings: Settings | None = None,
    system_prompt: str | None = None,
    api_key_override: str | None = None,
) -> str:
    settings = settings or get_settings()
    if not settings.model_configured and api_key_override is None:
        metrics = result["metrics"]
        return (
            f"All {metrics['orders_scheduled']} orders fit within the hard constraints. "
            f"The plan has {metrics['late_jobs']} late jobs and "
            f"{metrics['total_changeover_hours']} estimated changeover hours. "
            "Publishing remains blocked until planner approval."
        )

    return await _complete(
        system_prompt or (
            "Explain a production schedule using only the supplied metrics. "
            "Do not claim any hard constraint is satisfied unless the input "
            "says the schedule is feasible. Be concise."
        ),
        json.dumps(result, separators=(",", ":")),
        250,
        settings,
        api_key_override,
    )
