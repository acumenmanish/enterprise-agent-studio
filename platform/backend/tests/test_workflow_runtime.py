import pytest

from app.core.config import Settings
from app.services.scheduling import load_demo_data, load_manifest
from app.services.seed import _ensure_approved_policy_stage
from app.services.workflow_contracts import validate_workflow_graph
from app.services.workflow_runtime import build_schedule_workflow


def test_workflow_observer_records_node_failure_without_leaking_error_text(monkeypatch):
    from app.services import workflow_runtime

    settings = Settings()
    manifest = load_manifest(settings.manifest_path)
    observed = []

    def fail_optimizer(*args, **kwargs):
        raise RuntimeError("sensitive backend details")

    monkeypatch.setattr(workflow_runtime, "optimize_schedule", fail_optimizer)
    workflow, _ = build_schedule_workflow(
        manifest["execution_graph"],
        manifest["tools"],
        settings.demo_data_path,
        node_observer=lambda node_id, node_type, status, duration_ms, summary: observed.append(
            (node_id, node_type, status, duration_ms, summary)
        ),
    )

    with pytest.raises(RuntimeError, match="sensitive backend details"):
        workflow.invoke(
            {
                "request": {"planning_horizon_days": 5, "objective": "balanced"},
                "policy_constraints": {"machine_blackouts": [], "material_limits": {}},
            }
        )

    failure = next(item for item in observed if item[2] == "failed")
    assert failure[:3] == ("cp_sat_optimizer", "optimizer", "failed")
    assert failure[4] == {"error_type": "RuntimeError"}


def test_manifest_workflow_executes_through_langgraph_and_uses_tool_outputs():
    settings = Settings()
    manifest = load_manifest(settings.manifest_path)
    graph = manifest["execution_graph"]
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

    assert validate_workflow_graph(graph) == []
    workflow, order = build_schedule_workflow(graph, manifest["tools"], settings.demo_data_path)
    state = workflow.invoke(
        {
            "request": {"planning_horizon_days": 5, "objective": "balanced"},
            "policy_constraints": {"machine_blackouts": [], "material_limits": {}},
        }
    )

    assert order.index("read_open_orders") < order.index("cp_sat_optimizer")
    assert state["orders"]
    assert state["result"]["validation"]["passed"] is True
    assert state["outcome_checked"] is True
    assert state["approval_required"] is True


def test_workflow_applies_approved_machine_blackout_before_optimization():
    settings = Settings()
    manifest = load_manifest(settings.manifest_path)
    graph = manifest["execution_graph"]
    workflow, _ = build_schedule_workflow(graph, manifest["tools"], settings.demo_data_path)
    data = load_demo_data(settings.demo_data_path)
    machine_id = data["machines"][0]["id"]

    state = workflow.invoke(
        {
            "request": {"planning_horizon_days": 5, "objective": "balanced"},
            "policy_constraints": {
                "machine_blackouts": [{"machine_id": machine_id, "day": 0}],
                "material_limits": {},
            },
        }
    )

    assert state["result"]["validation"]["passed"] is True
    assert all(
        not (entry["machine_id"] == machine_id and entry["day"] == 0)
        for entry in state["result"]["schedule"]
    )


def test_existing_manifest_gets_an_idempotent_policy_node_upgrade():
    manifest = load_manifest(Settings().manifest_path)
    graph = manifest["execution_graph"]
    graph["nodes"] = [node for node in graph["nodes"] if node["type"] != "policy"]
    graph["edges"] = [edge for edge in graph["edges"] if edge["from"] != "approved_business_policy"]

    upgraded = _ensure_approved_policy_stage(manifest)

    assert upgraded is not None
    assert upgraded["agent"]["version"] == "0.1.1"
    assert any(node["type"] == "policy" for node in upgraded["execution_graph"]["nodes"])
    assert _ensure_approved_policy_stage(upgraded) is None


def test_workflow_rejects_unregistered_or_disconnected_tool_nodes():
    settings = Settings()
    manifest = load_manifest(settings.manifest_path)
    graph = manifest["execution_graph"]
    graph["nodes"].append(
        {
            "id": "disconnected_orders",
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

    try:
        build_schedule_workflow(graph, manifest["tools"], settings.demo_data_path)
    except ValueError as error:
        assert "must connect to the optimizer" in str(error)
    else:
        raise AssertionError("Disconnected tool node should not be executable")
