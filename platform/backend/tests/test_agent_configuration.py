import base64

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text

from app.core.config import Settings
from app.db.session import init_db
from app.main import create_app
from app.schemas.scheduling import ScheduleIntent
from app.services.agent_context import retrieve_agent_context


def test_database_initialization_preserves_legacy_agent_configurations(tmp_path):
    database_path = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE agent_configurations (
                    id VARCHAR(100) PRIMARY KEY,
                    tenant_id VARCHAR(100),
                    api_key VARCHAR(255)
                )
                """
            )
        )

    init_db(engine)

    tables = inspect(engine)
    assert "api_key" in {
        column["name"] for column in tables.get_columns("agent_configurations")
    }
    assert {
        "tenant_id",
        "agent_id",
        "configuration",
        "encrypted_model_key",
        "encrypted_erp_token",
    }.issubset(
        {column["name"] for column in tables.get_columns("studio_agent_configurations")}
    )
    engine.dispose()


@pytest.fixture
def configured_client(tmp_path):
    settings = Settings(
        agent_repository_path=tmp_path / "agent-repository",
        credential_encryption_key=Fernet.generate_key().decode("ascii"),
    )
    app = create_app(settings=settings, database_url="sqlite://")
    with TestClient(app) as client:
        yield client


def test_agent_configuration_is_saved_to_manifest_and_context_store(
    configured_client: TestClient,
):
    initial = configured_client.get("/api/v1/studio/agent/configuration").json()
    rule_text = "Prioritize pharmaceutical work before general commercial jobs."
    document_text = "An active maintenance alert blocks production on press 3."
    response = configured_client.put(
        "/api/v1/studio/agent/configuration",
        json={
            "base_version": initial["base_version"],
            "domain": "printing",
            "subdomain": "production/scheduling",
            "template_id": "printing-production-scheduling",
            "system_prompt": "Use plant-specific terminology.",
            "business_rules": rule_text,
            "enabled_tools": initial["enabled_tools"],
            "scenarios": ["A priority pharmaceutical order arrives."],
            "documents": [{"name": "plant-policy.txt", "text": document_text}],
        },
    )

    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["version"] == "0.1.1"
    loaded = configured_client.get("/api/v1/studio/agent/configuration").json()
    assert loaded["system_prompt"] == "Use plant-specific terminology."
    assert loaded["documents"] == [{"name": "plant-policy.txt", "text": document_text}]
    manifest = configured_client.get("/api/v1/studio/manifest").json()
    assert (
        manifest["manifest"]["customization"]["system_prompt"] == "Use plant-specific terminology."
    )
    assert document_text not in manifest["manifest_yaml"]
    assert (
        manifest["manifest"]["customization"]["knowledge_sources"][0]["name"] == "plant-policy.txt"
    )


def test_agent_configuration_rejects_stale_version_and_unknown_tool(
    configured_client: TestClient,
):
    initial = configured_client.get("/api/v1/studio/agent/configuration").json()
    payload = {
        "base_version": initial["base_version"],
        "domain": "printing",
        "subdomain": "production/scheduling",
        "template_id": "printing-production-scheduling",
        "system_prompt": "",
        "business_rules": "",
        "enabled_tools": initial["enabled_tools"],
        "scenarios": [],
        "documents": [],
    }
    saved = configured_client.put("/api/v1/studio/agent/configuration", json=payload)
    assert saved.status_code == 200
    stale = configured_client.put("/api/v1/studio/agent/configuration", json=payload)
    assert stale.status_code == 409

    payload["base_version"] = saved.json()["version"]
    payload["enabled_tools"] = ["run_arbitrary_sql@1.0.0"]
    unknown_tool = configured_client.put("/api/v1/studio/agent/configuration", json=payload)
    assert unknown_tool.status_code == 422


def test_model_key_override_is_encrypted_and_never_returned(
    configured_client: TestClient,
):
    api_key = "secret-anthropic-key-for-test"
    saved = configured_client.put("/api/v1/studio/model/credential", json={"api_key": api_key})
    assert saved.status_code == 200
    status = configured_client.get("/api/v1/studio/model/status")
    assert status.json()["configured"] is True
    assert status.json()["key_source"] == "agent-override"
    assert api_key not in status.text
    assert api_key not in configured_client.get("/api/v1/studio/agent/configuration").text

    cleared = configured_client.delete("/api/v1/studio/model/credential")
    assert cleared.status_code == 200
    assert cleared.json()["environment_key_configured"] is False
    assert configured_client.get("/api/v1/studio/model/status").json()["configured"] is False


def test_schedule_run_uses_saved_prompt_retrieval_and_encrypted_key(
    configured_client: TestClient, monkeypatch
):
    import app.api.routes.studio as studio_route

    initial = configured_client.get("/api/v1/studio/agent/configuration").json()
    document_text = (
        "Pharmaceutical jobs must be prioritized before all standard commercial work. "
        "Use the approved Heidelberg press for validated pharmaceutical carton production."
    )
    configured = configured_client.put(
        "/api/v1/studio/agent/configuration",
        json={
            "base_version": initial["base_version"],
            "domain": "printing",
            "subdomain": "production/scheduling",
            "template_id": "printing-production-scheduling",
            "system_prompt": "Use customer-approved production terminology.",
            "business_rules": "Never publish without planner approval.",
            "enabled_tools": initial["enabled_tools"],
            "scenarios": ["A validated pharmaceutical order arrives mid-shift."],
            "documents": [{"name": "pharma-policy.txt", "text": document_text}],
        },
    )
    assert configured.status_code == 200
    assert (
        configured_client.put(
            "/api/v1/studio/model/credential",
            json={"api_key": "not-returned-to-client"},
        ).status_code
        == 200
    )

    captured: dict[str, str | None] = {}

    async def interpret(request_text, settings, system_prompt=None, api_key_override=None):
        captured["intent_prompt"] = system_prompt
        captured["intent_key"] = api_key_override
        return ScheduleIntent(planning_horizon_days=5, objective="due_date")

    async def explain(result, settings, system_prompt=None, api_key_override=None):
        captured["explain_prompt"] = system_prompt
        captured["explain_key"] = api_key_override
        return "Schedule explained with retrieved policy context."

    monkeypatch.setattr(studio_route, "interpret_scheduling_request", interpret)
    monkeypatch.setattr(studio_route, "explain_schedule", explain)
    response = configured_client.post(
        "/api/v1/studio/schedule/run",
        json={
            "planning_horizon_days": 5,
            "objective": "balanced",
            "request_text": "Schedule urgent pharmaceutical carton orders first.",
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["result"]["explanation"].startswith("Schedule explained")
    assert "customer-approved production terminology" in captured["intent_prompt"]
    assert "approved Heidelberg press" in captured["intent_prompt"]
    assert "validated pharmaceutical order arrives mid-shift" in captured["intent_prompt"]
    assert captured["intent_key"] == "not-returned-to-client"
    run = configured_client.get(f"/api/v1/studio/runs/{response.json()['run_id']}").json()
    selected_context = next(event for event in run["events"] if event["type"] == "context.selected")
    assert selected_context["payload"]["context_sources"] == ["business_rules", "pharma-policy.txt"]
    assert "not-returned-to-client" not in response.text


def test_workflow_canvas_save_runs_manifest_graph_validation(
    configured_client: TestClient,
):
    manifest = configured_client.get("/api/v1/studio/manifest").json()
    graph = manifest["manifest"]["execution_graph"]
    graph["nodes"].append(
        {
            "id": "read_open_orders",
            "type": "tool",
            "tool_id": "get_open_orders@1.0.0",
            "inputs": {"type": "object", "properties": {}, "required": []},
            "outputs": {
                "type": "object",
                "properties": {"orders": {"type": "array"}},
                "required": ["orders"],
            },
        }
    )
    graph["edges"].append({"from": "read_open_orders", "to": "cp_sat_optimizer"})
    saved = configured_client.put(
        "/api/v1/studio/manifest/graph",
        json={
            "graph": graph,
            "base_version": manifest["manifest"]["agent"]["version"],
            "change_summary": "Add optional business context stage",
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["manifest"]["agent"]["version"] == "0.1.1"

    graph["nodes"] = [node for node in graph["nodes"] if node["id"] != "local_printing_context"]
    graph["edges"] = [edge for edge in graph["edges"] if edge["from"] != "local_printing_context"]
    invalid = configured_client.put(
        "/api/v1/studio/manifest/graph",
        json={
            "graph": graph,
            "base_version": "0.1.1",
            "change_summary": "Remove required context",
        },
    )
    assert invalid.status_code == 422
    assert any("required property machines" in error for error in invalid.json()["detail"])


def test_local_context_retrieval_ranks_matching_document_chunks():
    context = retrieve_agent_context(
        {
            "business_rules": "Never override approved hard optimizer constraints.",
            "documents": [
                {
                    "name": "shift-policy.md",
                    "text": (
                        "Press A is reserved for pharmaceutical cartons. "
                        "Standard work may use Press B."
                    ),
                },
                {
                    "name": "unrelated.md",
                    "text": "Use blue ink for the annual marketing brochure.",
                },
            ],
        },
        "pharmaceutical cartons on Press A",
    )
    assert context["sources"] == ["business_rules", "shift-policy.md"]
    assert "Press A is reserved" in context["context"]
    assert "annual marketing brochure" not in context["context"]


def test_document_extraction_accepts_markdown_and_rejects_unknown_type(
    configured_client: TestClient,
):
    extracted = configured_client.post(
        "/api/v1/studio/agent/documents/extract",
        json={
            "name": "shift-rules.md",
            "content_base64": base64.b64encode(b"Keep press B free for urgent work.").decode(),
        },
    )
    assert extracted.status_code == 200
    assert extracted.json()["text"] == "Keep press B free for urgent work."

    unsupported = configured_client.post(
        "/api/v1/studio/agent/documents/extract",
        json={
            "name": "secret.exe",
            "content_base64": base64.b64encode(b"not a policy file").decode(),
        },
    )
    assert unsupported.status_code == 422
