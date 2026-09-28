from app.core.config import Settings
from app.services.scheduling import load_manifest
from app.services.workflow_contracts import validate_workflow_graph
from app.services.workflow_runtime import build_schedule_workflow


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
    state = workflow.invoke({"request": {"planning_horizon_days": 5, "objective": "balanced"}})

    assert order.index("read_open_orders") < order.index("cp_sat_optimizer")
    assert state["orders"]
    assert state["result"]["validation"]["passed"] is True
    assert state["outcome_checked"] is True
    assert state["approval_required"] is True


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
