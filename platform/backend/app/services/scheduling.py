import json
import math
from pathlib import Path
from typing import Any

import yaml
from ortools.sat.python import cp_model

from app.services.workflow_contracts import validate_workflow_graph


class SchedulingInputError(ValueError):
    pass


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as manifest_file:
        manifest = yaml.safe_load(manifest_file)
    if not isinstance(manifest, dict) or not isinstance(manifest.get("agent"), dict):
        raise SchedulingInputError("Agent manifest must contain an agent object")
    graph_errors = validate_workflow_graph(manifest.get("execution_graph"))
    if graph_errors:
        raise SchedulingInputError("Invalid execution graph: " + "; ".join(graph_errors))
    return manifest


def load_demo_data(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as data_file:
        data = json.load(data_file)
    for key in ("orders", "machines", "materials", "horizon_days"):
        if key not in data:
            raise SchedulingInputError(f"Demo scheduling data is missing {key}")
    return data


def optimize_schedule(
    data: dict[str, Any], horizon_days: int, objective: str = "balanced"
) -> dict[str, Any]:
    orders = data["orders"]
    machines = data["machines"]
    material_limits = {
        material["id"]: material["available_quantity"] for material in data["materials"]
    }
    if horizon_days > data["horizon_days"]:
        raise SchedulingInputError(
            f"Only {data['horizon_days']} days of local demo capacity are available"
        )
    if not orders or not machines:
        raise SchedulingInputError("Scheduling requires at least one order and one machine")

    model = cp_model.CpModel()
    assignments: dict[tuple[int, int, int], cp_model.IntVar] = {}
    starts: dict[tuple[int, int, int], cp_model.IntVar] = {}
    ends: dict[tuple[int, int, int], cp_model.IntVar] = {}
    durations: dict[tuple[int, int], int] = {}
    intervals_by_machine_day: dict[
        tuple[int, int], list[cp_model.IntervalVar]
    ] = {}
    changeover_objective_arcs: list[tuple[int, cp_model.IntVar]] = []

    for order_index, order in enumerate(orders):
        if order["required_material"] not in material_limits:
            raise SchedulingInputError(f"No inventory for order {order['id']}")
        eligible_options = []
        for machine_index, machine in enumerate(machines):
            if order["required_capability"] not in machine["capabilities"]:
                continue
            duration = max(
                1,
                math.ceil(order["quantity"] / machine["speed_units_per_hour"]),
            )
            durations[order_index, machine_index] = duration
            for day in range(horizon_days):
                if day not in machine["available_days"] or _has_maintenance(
                    data, machine["id"], day
                ):
                    continue
                key = (order_index, machine_index, day)
                assignment = model.new_bool_var(f"assign_{order_index}_{machine_index}_{day}")
                start = model.new_int_var(0, machine["hours_per_day"], f"start_{key}")
                end = model.new_int_var(0, machine["hours_per_day"], f"end_{key}")
                interval = model.new_optional_interval_var(
                    start, duration, end, assignment, f"job_{key}"
                )
                assignments[key] = assignment
                starts[key] = start
                ends[key] = end
                intervals_by_machine_day.setdefault((machine_index, day), []).append(interval)
                eligible_options.append(assignment)
        if not eligible_options:
            raise SchedulingInputError(f"No available machine for order {order['id']}")
        model.add_exactly_one(eligible_options)

    for material_id, available in material_limits.items():
        model.add(
            sum(
                orders[order_index]["quantity"] * assignment
                for (order_index, _, _), assignment in assignments.items()
                if orders[order_index]["required_material"] == material_id
            )
            <= available
        )

    for (machine_index, day), intervals in intervals_by_machine_day.items():
        machine = machines[machine_index]
        for maintenance in data.get("maintenance", []):
            if maintenance["machine_id"] == machine["id"] and maintenance["day"] == day:
                maintenance_interval = model.new_fixed_size_interval_var(
                    0, machine["hours_per_day"], f"maintenance_{machine['id']}_{day}"
                )
                intervals.append(maintenance_interval)
        model.add_no_overlap(intervals)
        _add_sequence_constraints(
            model,
            orders,
            machine_index,
            day,
            assignments,
            starts,
            ends,
            data.get("changeovers", {}),
            changeover_objective_arcs,
        )

    lateness_weight, priority_weight, changeover_weight = _objective_weights(objective)
    objective_terms = []
    for (order_index, _, day), assignment in assignments.items():
        order = orders[order_index]
        lateness = max(0, day + 1 - order["due_day"])
        objective_terms.append(lateness * order["priority"] * lateness_weight * assignment)
        objective_terms.append(day * order["priority"] * priority_weight * assignment)

    objective_terms.extend(
        hours * changeover_weight * literal
        for hours, literal in changeover_objective_arcs
    )

    model.minimize(sum(objective_terms))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 3.0
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise SchedulingInputError("No feasible schedule found for the provided constraints")

    entries = []
    for (order_index, machine_index, day), assignment in assignments.items():
        if not solver.boolean_value(assignment):
            continue
        order = orders[order_index]
        entries.append(
            {
                "order_id": order["id"],
                "customer": order["customer"],
                "product": order["product"],
                "quantity": order["quantity"],
                "machine_id": machines[machine_index]["id"],
                "machine_name": machines[machine_index]["name"],
                "day": day,
                "start_hour": solver.value(starts[order_index, machine_index, day]),
                "duration_hours": durations[order_index, machine_index],
                "due_day": order["due_day"],
                "late_by_days": max(0, day + 1 - order["due_day"]),
                "priority": order["priority"],
                "material": order["required_material"],
            }
        )
    entries.sort(
        key=lambda entry: (entry["day"], entry["machine_id"], entry["start_hour"])
    )

    validation = _validate_schedule(entries, data, horizon_days)
    if not validation["passed"]:
        raise SchedulingInputError(
            "Optimizer result failed hard-constraint validation: "
            + "; ".join(validation["violations"])
        )
    metrics = _schedule_metrics(entries, data, horizon_days)
    return {
        "status": "feasible",
        "solver_status": solver.status_name(status),
        "objective_value": solver.objective_value,
        "objective": objective,
        "planning_horizon_days": horizon_days,
        "metrics": metrics,
        "schedule": entries,
        "validation": validation,
        "approval_required": True,
        "publish_status": "awaiting_approval",
    }


def _add_sequence_constraints(
    model: cp_model.CpModel,
    orders: list[dict[str, Any]],
    machine_index: int,
    day: int,
    assignments: dict[tuple[int, int, int], cp_model.IntVar],
    starts: dict[tuple[int, int, int], cp_model.IntVar],
    ends: dict[tuple[int, int, int], cp_model.IntVar],
    changeovers: dict[str, int],
    objective_arcs: list[tuple[int, cp_model.IntVar]],
) -> None:
    order_indexes = [
        index
        for index in range(len(orders))
        if (index, machine_index, day) in assignments
    ]
    if len(order_indexes) < 2:
        return

    selected = [assignments[index, machine_index, day] for index in order_indexes]
    empty = model.new_bool_var(f"empty_{machine_index}_{day}")
    model.add(sum(selected) == 0).only_enforce_if(empty)
    model.add(sum(selected) >= 1).only_enforce_if(empty.negated())
    arcs: list[tuple[int, int, cp_model.IntVar]] = [(0, 0, empty)]

    for position, order_index in enumerate(order_indexes, start=1):
        chosen = assignments[order_index, machine_index, day]
        start_arc = model.new_bool_var(f"first_{order_index}_{machine_index}_{day}")
        end_arc = model.new_bool_var(f"last_{order_index}_{machine_index}_{day}")
        arcs.extend(
            [
                (0, position, start_arc),
                (position, 0, end_arc),
                (position, position, chosen.negated()),
            ]
        )

    for first_position, first_order in enumerate(order_indexes, start=1):
        for second_position, second_order in enumerate(order_indexes, start=1):
            if first_position == second_position:
                continue
            literal = model.new_bool_var(
                f"after_{first_order}_{second_order}_{machine_index}_{day}"
            )
            arcs.append((first_position, second_position, literal))
            hours = changeovers.get(
                f"{orders[first_order]['product']}->{orders[second_order]['product']}", 0
            )
            model.add(
                starts[second_order, machine_index, day]
                >= ends[first_order, machine_index, day] + hours
            ).only_enforce_if(literal)
            objective_arcs.append((hours, literal))

    model.add_circuit(arcs)


def _objective_weights(objective: str) -> tuple[int, int, int]:
    weights = {
        "balanced": (1000, 50, 10),
        "due_date": (5000, 150, 2),
        "changeover": (250, 5, 100),
    }
    try:
        return weights[objective]
    except KeyError as exc:
        raise SchedulingInputError(f"Unsupported scheduling objective: {objective}") from exc


def _has_maintenance(data: dict[str, Any], machine_id: str, day: int) -> bool:
    return any(
        item["machine_id"] == machine_id and item["day"] == day
        for item in data.get("maintenance", [])
    )


def _schedule_metrics(
    entries: list[dict[str, Any]], data: dict[str, Any], horizon_days: int
) -> dict[str, int | float]:
    by_machine_day: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for entry in entries:
        by_machine_day.setdefault((entry["machine_id"], entry["day"]), []).append(entry)

    changeover_hours = 0
    for key, group in by_machine_day.items():
        machine_id, day = key
        group.sort(key=lambda entry: entry["start_hour"])
        for first, second in zip(group, group[1:], strict=False):
            changeover_hours += data.get("changeovers", {}).get(
                f"{first['product']}->{second['product']}", 0
            )
            if second["start_hour"] < first["start_hour"] + first["duration_hours"]:
                raise SchedulingInputError(
                    f"Schedule has overlapping jobs on {machine_id} day {day + 1}"
                )

    available_hours = sum(
        machine["hours_per_day"]
        * sum(
            day in machine["available_days"] and not _has_maintenance(data, machine["id"], day)
            for day in range(horizon_days)
        )
        for machine in data["machines"]
    )
    scheduled_hours = sum(entry["duration_hours"] for entry in entries)
    return {
        "orders_scheduled": len(entries),
        "late_jobs": sum(entry["late_by_days"] > 0 for entry in entries),
        "total_changeover_hours": changeover_hours,
        "machine_utilization_percent": (
            round(scheduled_hours / available_hours * 100, 1) if available_hours else 0
        ),
    }


def _validate_schedule(
    entries: list[dict[str, Any]], data: dict[str, Any], horizon_days: int
) -> dict[str, Any]:
    violations = []
    orders = {order["id"]: order for order in data["orders"]}
    machines = {machine["id"]: machine for machine in data["machines"]}
    if len(entries) != len(orders) or {entry["order_id"] for entry in entries} != set(orders):
        violations.append("each order must be scheduled exactly once")

    material_usage: dict[str, int] = {}
    by_machine_day: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for entry in entries:
        order = orders.get(entry["order_id"])
        machine = machines.get(entry["machine_id"])
        if order is None or machine is None:
            violations.append("schedule references an unknown order or machine")
            continue
        if order["required_capability"] not in machine["capabilities"]:
            violations.append(f"{order['id']} is assigned to an incapable machine")
        if (
            entry["day"] not in machine["available_days"]
            or entry["day"] >= horizon_days
            or _has_maintenance(data, machine["id"], entry["day"])
        ):
            violations.append(f"{order['id']} is assigned outside machine availability")
        if entry["start_hour"] + entry["duration_hours"] > machine["hours_per_day"]:
            violations.append(f"{order['id']} exceeds the daily machine shift")
        material_usage[order["required_material"]] = (
            material_usage.get(order["required_material"], 0) + order["quantity"]
        )
        by_machine_day.setdefault((machine["id"], entry["day"]), []).append(entry)

    for material in data["materials"]:
        if material_usage.get(material["id"], 0) > material["available_quantity"]:
            violations.append(f"insufficient material: {material['id']}")

    for (machine_id, day), group in by_machine_day.items():
        group.sort(key=lambda entry: entry["start_hour"])
        for first, second in zip(group, group[1:], strict=False):
            required_changeover = data.get("changeovers", {}).get(
                f"{first['product']}->{second['product']}", 0
            )
            if second["start_hour"] < (
                first["start_hour"] + first["duration_hours"] + required_changeover
            ):
                violations.append(
                    f"overlap or missing changeover on {machine_id} day {day + 1}"
                )

    return {
        "passed": not violations,
        "checks": [
            "order assignment",
            "machine capability and availability",
            "shift capacity and non-overlap",
            "material inventory",
            "sequence-dependent changeover",
        ],
        "violations": violations,
    }
