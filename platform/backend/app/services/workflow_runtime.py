import heapq
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.services.scheduling import (
    SchedulingInputError,
    apply_scheduling_constraints,
    load_demo_data,
    optimize_schedule,
)


class WorkflowExecutionError(ValueError):
    pass


class ScheduleWorkflowState(TypedDict, total=False):
    request: dict[str, Any]
    data: dict[str, Any]
    orders: list[dict[str, Any]]
    machines: list[dict[str, Any]]
    materials: list[dict[str, Any]]
    policy_constraints: dict[str, Any]
    result: dict[str, Any]
    outcome_checked: bool
    approval_required: bool


def _execution_order(graph: dict[str, Any]) -> list[str]:
    nodes = graph["nodes"]
    indegree = {node["id"]: 0 for node in nodes}
    outgoing = {node["id"]: [] for node in nodes}
    for edge in graph["edges"]:
        outgoing[edge["from"]].append(edge["to"])
        indegree[edge["to"]] += 1

    ready = [node_id for node_id, degree in indegree.items() if degree == 0]
    heapq.heapify(ready)
    ordered = []
    while ready:
        node_id = heapq.heappop(ready)
        ordered.append(node_id)
        for target in outgoing[node_id]:
            indegree[target] -= 1
            if indegree[target] == 0:
                heapq.heappush(ready, target)
    if len(ordered) != len(nodes):
        raise WorkflowExecutionError("Workflow graph must be acyclic.")
    return ordered


def build_schedule_workflow(
    graph: dict[str, Any],
    enabled_tools: list[str],
    demo_data_path,
):
    nodes = graph["nodes"]
    nodes_by_id = {node["id"]: node for node in nodes}
    order = _execution_order(graph)
    type_counts: dict[str, int] = {}
    for node in nodes:
        node_type = node["type"]
        type_counts[node_type] = type_counts.get(node_type, 0) + 1

    required = {"request", "context", "policy", "optimizer", "outcome-check", "approval"}
    missing = required - set(type_counts)
    if missing:
        raise WorkflowExecutionError(
            "Workflow is missing required scheduling stages: " + ", ".join(sorted(missing))
        )
    repeated_required = sorted(node_type for node_type in required if type_counts[node_type] != 1)
    if repeated_required:
        raise WorkflowExecutionError(
            "The scheduling workflow requires exactly one of each core stage: "
            + ", ".join(repeated_required)
        )
    for node in nodes:
        if node["type"] not in required and node["type"] != "tool":
            raise WorkflowExecutionError(
                f"Workflow node {node['id']} uses unsupported executable type {node['type']}."
            )
        if node["type"] == "tool":
            tool_id = node.get("tool_id")
            if not isinstance(tool_id, str) or tool_id not in enabled_tools:
                raise WorkflowExecutionError(
                    f"Tool node {node['id']} must reference an enabled template tool."
                )
            if tool_id not in {
                "get_open_orders@1.0.0",
                "get_machine_capacity@1.0.0",
            }:
                raise WorkflowExecutionError(
                    f"Tool {tool_id} does not have an executable local handler."
                )

    optimizer_id = next(node["id"] for node in nodes if node["type"] == "optimizer")
    downstream: dict[str, set[str]] = {node["id"]: set() for node in nodes}
    for edge in graph["edges"]:
        downstream[edge["from"]].add(edge["to"])
    for node in nodes:
        if node["type"] != "tool":
            continue
        reachable = {node["id"]}
        frontier = [node["id"]]
        while frontier:
            current = frontier.pop()
            for target in downstream[current] - reachable:
                reachable.add(target)
                frontier.append(target)
        if optimizer_id not in reachable:
            raise WorkflowExecutionError(
                f"Tool node {node['id']} must connect to the optimizer so its output is used."
            )

    if (
        sum(node.get("tool_id") == "get_open_orders@1.0.0" for node in nodes) > 1
        or sum(node.get("tool_id") == "get_machine_capacity@1.0.0" for node in nodes) > 1
    ):
        raise WorkflowExecutionError("Each local data tool may appear only once.")

    def handler_for(node: dict[str, Any]):
        node_type = node["type"]
        if node_type == "request":
            return lambda state: {}
        if node_type == "context":
            return lambda state: {"data": load_demo_data(demo_data_path)}
        if node_type == "policy":
            return lambda state: {
                "policy_constraints": state.get(
                    "policy_constraints", {"machine_blackouts": [], "material_limits": {}}
                )
            }
        if node_type == "optimizer":

            def optimize(state: ScheduleWorkflowState) -> dict[str, Any]:
                data = apply_scheduling_constraints(
                    state["data"],
                    state.get("policy_constraints", {}),
                    state["request"]["planning_horizon_days"],
                )
                if "orders" in state:
                    data["orders"] = state["orders"]
                if "machines" in state:
                    data["machines"] = state["machines"]
                if "materials" in state:
                    data["materials"] = state["materials"]
                result = optimize_schedule(
                    data,
                    state["request"]["planning_horizon_days"],
                    state["request"]["objective"],
                )
                return {"result": result}

            return optimize
        if node_type == "outcome-check":

            def check_outcome(state: ScheduleWorkflowState) -> dict[str, bool]:
                result = state.get("result")
                if not result or not result["validation"]["passed"]:
                    raise SchedulingInputError(
                        "Workflow outcome check failed; planner approval is blocked."
                    )
                return {"outcome_checked": True}

            return check_outcome
        if node_type == "approval":
            return lambda state: {"approval_required": True}

        tool_id = node["tool_id"]
        if tool_id == "get_open_orders@1.0.0":

            def get_open_orders(state: ScheduleWorkflowState) -> dict[str, Any]:
                data = state.get("data") or load_demo_data(demo_data_path)
                return {"orders": data["orders"]}

            return get_open_orders
        if tool_id == "get_machine_capacity@1.0.0":

            def get_machine_capacity(state: ScheduleWorkflowState) -> dict[str, Any]:
                data = state.get("data") or load_demo_data(demo_data_path)
                return {"machines": data["machines"], "materials": data["materials"]}

            return get_machine_capacity
        raise WorkflowExecutionError(f"Tool node {node['id']} is not executable.")

    workflow = StateGraph(ScheduleWorkflowState)
    for node in nodes:
        workflow.add_node(node["id"], handler_for(node))

    incoming = {node["id"]: 0 for node in nodes}
    outgoing = {node["id"]: 0 for node in nodes}
    for edge in graph["edges"]:
        source = edge["from"]
        target = edge["to"]
        workflow.add_edge(source, target)
        outgoing[source] += 1
        incoming[target] += 1
    for node_id in nodes_by_id:
        if incoming[node_id] == 0:
            workflow.add_edge(START, node_id)
        if outgoing[node_id] == 0:
            workflow.add_edge(node_id, END)

    return workflow.compile(), order
