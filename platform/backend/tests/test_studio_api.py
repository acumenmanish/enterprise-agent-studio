from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def client(tmp_path) -> Generator[TestClient, None, None]:
    settings = Settings(agent_repository_path=tmp_path / "agent-repository")
    app = create_app(settings=settings, database_url="sqlite://")
    with TestClient(app) as test_client:
        yield test_client


def test_schedule_requires_approval_and_records_ordered_events(client: TestClient):
    response = client.post(
        "/api/v1/studio/schedule/run",
        json={
            "planning_horizon_days": 5,
            "objective": "due_date",
        },
    )
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["status"] == "awaiting_approval"
    assert result["result"]["approval_required"] is True
    run_id = result["run_id"]

    run = client.get(f"/api/v1/studio/runs/{run_id}")
    assert run.status_code == 200
    body = run.json()
    assert body["approval"]["status"] == "pending"
    assert [event["sequence"] for event in body["events"]] == list(
        range(1, len(body["events"]) + 1)
    )
    assert body["events"][-1]["type"] == "approval.requested"

    approved = client.post(
        f"/api/v1/studio/runs/{run_id}/approval",
        json={"decision": "approve"},
    )
    assert approved.status_code == 200
    approved_run = client.get(f"/api/v1/studio/runs/{run_id}").json()
    assert approved_run["status"] == "published"
    assert approved_run["result"]["publish_status"] == "published_to_local_demo"
    assert approved_run["approval"]["decision_by"] == "local_planner"

    repeated = client.post(
        f"/api/v1/studio/runs/{run_id}/approval",
        json={"decision": "approve"},
    )
    assert repeated.status_code == 409


def test_schedule_request_rejects_horizon_out_of_range(client: TestClient):
    response = client.post(
        "/api/v1/studio/schedule/run",
        json={"planning_horizon_days": 0},
    )
    assert response.status_code == 422


def test_manifest_exposes_the_same_validated_graph_used_for_authoring(client: TestClient):
    response = client.get("/api/v1/studio/manifest")

    assert response.status_code == 200
    body = response.json()
    assert body["manifest"]["execution_graph"]["nodes"][0]["id"] == "schedule_request"
    assert body["manifest"]["quick_build_defaults"]["objective"] == "balanced"
    assert "execution_graph:" in body["manifest_yaml"]


def test_manifest_is_validated_versioned_and_compared_in_local_git(client: TestClient):
    import yaml

    initial = client.get("/api/v1/studio/manifest").json()
    candidate = initial["manifest"]
    candidate["agent"]["objective"] = "Prioritize due dates without violating constraints."
    candidate_yaml = yaml.safe_dump(candidate, sort_keys=False)

    validation = client.post(
        "/api/v1/studio/manifest/validate",
        json={"manifest_yaml": candidate_yaml},
    )
    assert validation.status_code == 200
    assert validation.json() == {"valid": True, "errors": []}

    saved = client.put(
        "/api/v1/studio/manifest",
        json={
            "manifest_yaml": candidate_yaml,
            "base_version": initial["manifest"]["agent"]["version"],
            "change_summary": "Clarify scheduling objective",
        },
    )
    assert saved.status_code == 200, saved.text
    saved_body = saved.json()
    assert saved_body["manifest"]["agent"]["version"] == "0.1.1"

    history = client.get("/api/v1/studio/manifest/history").json()
    assert len(history) == 2
    assert history[0]["version"] == "0.1.1"
    assert history[0]["message"] == "Clarify scheduling objective"
    assert history[1]["version"] == "0.1.0"

    compared = client.get(
        "/api/v1/studio/manifest/compare",
        params={
            "from_revision": history[1]["commit"],
            "to_revision": history[0]["commit"],
        },
    )
    assert compared.status_code == 200
    assert "Prioritize due dates" in compared.json()["diff"]

    stale_save = client.put(
        "/api/v1/studio/manifest",
        json={
            "manifest_yaml": candidate_yaml,
            "base_version": "0.1.0",
            "change_summary": "Stale update",
        },
    )
    assert stale_save.status_code == 409


def test_manifest_validation_rejects_invalid_yaml_graph_and_credential_fields(
    client: TestClient,
):
    import yaml

    invalid_yaml = client.post(
        "/api/v1/studio/manifest/validate",
        json={"manifest_yaml": "agent: [unterminated"},
    )
    assert invalid_yaml.status_code == 200
    assert invalid_yaml.json()["valid"] is False

    current = client.get("/api/v1/studio/manifest").json()["manifest"]
    current["api_key"] = "must-not-be-persisted"
    invalid_secret = client.post(
        "/api/v1/studio/manifest/validate",
        json={"manifest_yaml": yaml.safe_dump(current, sort_keys=False)},
    )
    assert invalid_secret.status_code == 200
    assert any("credential material" in error for error in invalid_secret.json()["errors"])
