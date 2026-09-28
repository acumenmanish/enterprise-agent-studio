from app.services.scheduling import optimize_schedule


def test_demo_schedule_obeys_material_machine_and_horizon_constraints():
    from app.core.config import get_settings
    from app.services.scheduling import load_demo_data

    data = load_demo_data(get_settings().demo_data_path)
    result = optimize_schedule(data, horizon_days=5)

    assert result["status"] == "feasible"
    assert result["validation"]["passed"] is True
    assert result["metrics"]["orders_scheduled"] == len(data["orders"])
    assert len(result["schedule"]) == len(data["orders"])
    assert all(0 <= row["day"] < 5 for row in result["schedule"])

    materials = {
        material["id"]: material["available_quantity"] for material in data["materials"]
    }
    consumed: dict[str, int] = {}
    daily_machine_hours: dict[tuple[str, int], int] = {}
    for row in result["schedule"]:
        consumed[row["material"]] = consumed.get(row["material"], 0) + row["quantity"]
        key = (row["machine_id"], row["day"])
        daily_machine_hours[key] = daily_machine_hours.get(key, 0) + row["duration_hours"]

    assert all(consumed[material] <= available for material, available in materials.items())
    machines = {machine["id"]: machine for machine in data["machines"]}
    for (machine_id, day), hours in daily_machine_hours.items():
        assert hours <= machines[machine_id]["hours_per_day"]
        assert not any(
            maintenance["machine_id"] == machine_id and maintenance["day"] == day
            for maintenance in data["maintenance"]
        )


def test_schedule_reports_missing_capability_as_input_error():
    import pytest

    from app.services.scheduling import SchedulingInputError

    data = {
        "orders": [
            {
                "id": "JOB-X",
                "customer": "Example",
                "product": "Book",
                "quantity": 100,
                "due_day": 1,
                "priority": 1,
                "required_material": "paper",
                "required_capability": "unavailable",
            }
        ],
        "machines": [
            {
                "id": "PRESS-X",
                "name": "Press X",
                "capabilities": ["sheetfed"],
                "hours_per_day": 8,
                "available_days": [0],
                "speed_units_per_hour": 100,
            }
        ],
        "materials": [{"id": "paper", "available_quantity": 1000}],
        "horizon_days": 1,
    }

    with pytest.raises(SchedulingInputError, match="No available machine"):
        optimize_schedule(data, horizon_days=1)


def test_manifest_workflow_contracts_are_valid():
    from app.core.config import get_settings
    from app.services.scheduling import load_manifest

    manifest = load_manifest(get_settings().manifest_path)

    assert manifest["quick_build_defaults"]["objective"] == "balanced"
    assert [node["id"] for node in manifest["execution_graph"]["nodes"]][-2:] == [
        "outcome_check",
        "planner_approval",
    ]


def test_workflow_contract_rejects_missing_input_and_cycles():
    from app.services.workflow_contracts import validate_workflow_graph

    graph = {
        "nodes": [
            {
                "id": "source",
                "inputs": {"type": "object", "properties": {}, "required": []},
                "outputs": {
                    "type": "object",
                    "properties": {"quantity": {"type": "string"}},
                    "required": ["quantity"],
                },
            },
            {
                "id": "optimizer",
                "inputs": {
                    "type": "object",
                    "properties": {
                        "quantity": {"type": "integer"},
                        "objective": {"type": "string"},
                    },
                    "required": ["quantity", "objective"],
                },
                "outputs": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        ],
        "edges": [
            {"from": "source", "to": "optimizer"},
            {"from": "optimizer", "to": "source"},
        ],
    }

    errors = validate_workflow_graph(graph)

    assert "workflow inputs for node optimizer are missing required property objective" in errors
    assert any("incompatible types" in error for error in errors)
    assert "execution_graph must be acyclic" in errors
