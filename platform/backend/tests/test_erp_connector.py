from typing import Any

import httpx
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_erp_connection_status_does_not_expose_credentials(tmp_path):
    settings = Settings(
        agent_repository_path=tmp_path / "agent-repository",
        erp_query_api_url="https://erp.example.com/ai_agent_query_api.php",
        erp_api_token="test-bearer-token",
    )
    app = create_app(settings=settings, database_url="sqlite://")
    with TestClient(app) as client:
        response = client.get("/api/v1/studio/data/erp/status")

    assert response.status_code == 200
    assert response.json() == {
        "configured": True,
        "endpoint_configured": True,
        "credential_configured": True,
        "endpoint": "https://erp.example.com/ai_agent_query_api.php",
        "key_source": "environment",
        "credential_encryption_available": False,
    }
    assert "test-bearer-token" not in response.text


def test_erp_connection_can_be_saved_encrypted_and_reverted(tmp_path):
    from cryptography.fernet import Fernet

    token = "private-erp-bearer-token"
    settings = Settings(
        agent_repository_path=tmp_path / "agent-repository",
        credential_encryption_key=Fernet.generate_key().decode("ascii"),
    )
    app = create_app(settings=settings, database_url="sqlite://")
    with TestClient(app) as client:
        saved = client.put(
            "/api/v1/studio/data/erp/connection",
            json={
                "endpoint": "https://erp.example.com/ai_agent_query_api.php",
                "api_token": token,
            },
        )
        assert saved.status_code == 200
        status = client.get("/api/v1/studio/data/erp/status")
        assert status.status_code == 200
        assert status.json()["configured"] is True
        assert status.json()["key_source"] == "agent-override"
        assert token not in status.text

        with app.state.session_factory() as session:
            from app.db.models import AgentConfiguration

            configuration = session.get(
                AgentConfiguration, ("default_tenant", "production-scheduling")
            )
            assert configuration is not None
            assert configuration.encrypted_erp_token is not None
            assert token.encode() not in configuration.encrypted_erp_token

        reset = client.delete("/api/v1/studio/data/erp/connection")
        assert reset.status_code == 200
        assert client.get("/api/v1/studio/data/erp/status").json()["configured"] is False


def test_erp_connection_rejects_non_https_remote_url(tmp_path):
    from cryptography.fernet import Fernet

    settings = Settings(
        agent_repository_path=tmp_path / "agent-repository",
        credential_encryption_key=Fernet.generate_key().decode("ascii"),
    )
    app = create_app(settings=settings, database_url="sqlite://")
    with TestClient(app) as client:
        response = client.put(
            "/api/v1/studio/data/erp/connection",
            json={
                "endpoint": "http://erp.example.com/ai_agent_query_api.php",
                "api_token": "private-token",
            },
        )
    assert response.status_code == 422
    assert "must use HTTPS" in response.json()["detail"]


def test_erp_preview_requires_backend_credentials(tmp_path):
    settings = Settings(agent_repository_path=tmp_path / "agent-repository")
    app = create_app(settings=settings, database_url="sqlite://")
    with TestClient(app) as client:
        response = client.post("/api/v1/studio/data/erp/preview")

    assert response.status_code == 503
    assert "ERP_QUERY_API_URL and ERP_API_TOKEN" in response.json()["detail"]


def test_erp_preview_uses_documented_read_only_aliases_and_redacts_fields(tmp_path, monkeypatch):
    requests: list[dict[str, Any]] = []

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            assert kwargs["follow_redirects"] is False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, *, headers, json):
            requests.append({"url": url, "headers": headers, "json": json})
            row: dict[str, Any] = {
                "order_id": "10",
                "order_no": "WO-10",
                "ord_cname": "Example Customer",
                "ord_cadd": "private address",
                "ord_qty": "100",
                "machine_id": "20",
                "machine_name": "Press A",
                "opt_id": "30",
                "opt_name": "Printing",
                "wo_id": "WO-10",
                "schedule_hrs": "4",
            }
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "table": json["table"],
                    "count": 30,
                    "total": 30,
                    "has_more": True,
                    "data": [row for _ in range(30)],
                },
            )

    monkeypatch.setattr("app.services.erp_connector.httpx.AsyncClient", FakeAsyncClient)
    settings = Settings(
        agent_repository_path=tmp_path / "agent-repository",
        erp_query_api_url="https://erp.example.com/ai_agent_query_api.php",
        erp_api_token="test-bearer-token",
    )
    app = create_app(settings=settings, database_url="sqlite://")
    with TestClient(app) as client:
        response = client.post("/api/v1/studio/data/erp/preview")

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["connected"] is True
    assert result["read_only"] is True
    assert [dataset["alias"] for dataset in result["datasets"]] == [
        "order",
        "machine",
        "operation",
        "schedule",
    ]
    assert all(dataset["count"] == 25 for dataset in result["datasets"])
    assert all(dataset["total"] == 30 for dataset in result["datasets"])
    assert all(dataset["has_more"] for dataset in result["datasets"])
    assert "ord_cadd" not in response.text
    assert all(
        request["headers"]["Authorization"] == "Bearer test-bearer-token" for request in requests
    )
    assert all(request["json"]["action"] == "select" for request in requests)
    assert all(request["json"]["limit"] == 25 for request in requests)
    order_request = next(request for request in requests if request["json"]["table"] == "order")
    assert order_request["json"]["filters"] == {"status": "open"}
    assert len(result["data_gaps"]) == 3


def test_erp_connector_refuses_remote_http_endpoint(tmp_path):
    settings = Settings(
        agent_repository_path=tmp_path / "agent-repository",
        erp_query_api_url="http://erp.example.com/ai_agent_query_api.php",
        erp_api_token="test-bearer-token",
    )
    app = create_app(settings=settings, database_url="sqlite://")
    with TestClient(app) as client:
        response = client.post("/api/v1/studio/data/erp/preview")

    assert response.status_code == 503
    assert response.json()["detail"].startswith("ERP_QUERY_API_URL must use HTTPS")
