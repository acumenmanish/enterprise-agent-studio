import httpx
import pytest

from app.core.config import Settings
from app.services.model_gateway import interpret_scheduling_request


@pytest.mark.asyncio
async def test_anthropic_gateway_uses_default_model_and_messages_api(monkeypatch):
    requests = []

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            assert kwargs["follow_redirects"] is False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, *, headers, json):
            requests.append({"url": url, "headers": headers, "json": json})
            return httpx.Response(
                200,
                json={
                    "content": [
                        {
                            "type": "text",
                            "text": '{"planning_horizon_days": 3, "objective": "due_date"}',
                        }
                    ]
                },
                request=httpx.Request("POST", url),
            )

    monkeypatch.setattr("app.services.model_gateway.httpx.AsyncClient", FakeAsyncClient)
    settings = Settings(anthropic_api_key="test-anthropic-key")

    intent = await interpret_scheduling_request("Prioritize due dates for 3 days", settings)

    assert intent.planning_horizon_days == 3
    assert intent.objective == "due_date"
    assert requests[0]["url"] == "https://api.anthropic.com/v1/messages"
    assert requests[0]["headers"]["x-api-key"] == "test-anthropic-key"
    assert requests[0]["json"]["model"] == "claude-sonnet-4-5"
    assert requests[0]["json"]["system"]
    assert requests[0]["json"]["max_tokens"] == 100


@pytest.mark.asyncio
async def test_anthropic_gateway_rejects_non_json_intent(monkeypatch):
    class FakeAsyncClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, *, headers, json):
            return httpx.Response(
                200,
                json={"content": [{"type": "text", "text": "Here is a schedule"}]},
                request=httpx.Request("POST", url),
            )

    monkeypatch.setattr("app.services.model_gateway.httpx.AsyncClient", FakeAsyncClient)
    settings = Settings(anthropic_api_key="test-anthropic-key")

    with pytest.raises(RuntimeError, match="invalid scheduling intent"):
        await interpret_scheduling_request("Make a schedule", settings)
