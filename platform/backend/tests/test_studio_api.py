from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    app = create_app(database_url="sqlite://")
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
