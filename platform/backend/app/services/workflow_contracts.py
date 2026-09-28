from collections import defaultdict, deque
from typing import Any

JSON_SCHEMA_TYPES = {"array", "boolean", "integer", "null", "number", "object", "string"}


def validate_workflow_graph(graph: Any) -> list[str]:
    if not isinstance(graph, dict):
        return ["execution_graph must be an object"]

    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if not isinstance(nodes, list) or not nodes:
        return ["execution_graph.nodes must contain at least one node"]
    if not isinstance(edges, list):
        return ["execution_graph.edges must be an array"]

    errors: list[str] = []
    nodes_by_id: dict[str, dict[str, Any]] = {}
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            errors.append(f"execution_graph.nodes[{index}] must be an object")
            continue
        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id:
            errors.append(f"execution_graph.nodes[{index}] requires a non-empty id")
            continue
        if node_id in nodes_by_id:
            errors.append(f"execution_graph contains duplicate node id {node_id}")
            continue
        nodes_by_id[node_id] = node
        for direction in ("inputs", "outputs"):
            _validate_object_schema(node.get(direction), f"node {node_id} {direction}", errors)

    incoming: dict[str, list[str]] = defaultdict(list)
    outgoing: dict[str, list[str]] = defaultdict(list)
    indegree = {node_id: 0 for node_id in nodes_by_id}
    for index, edge in enumerate(edges):
        if not isinstance(edge, dict):
            errors.append(f"execution_graph.edges[{index}] must be an object")
            continue
        source = edge.get("from")
        target = edge.get("to")
        if (
            not isinstance(source, str)
            or not isinstance(target, str)
            or source not in nodes_by_id
            or target not in nodes_by_id
        ):
            errors.append(f"execution_graph.edges[{index}] references an unknown node")
            continue
        if source == target:
            errors.append(f"execution_graph node {source} cannot connect to itself")
            continue
        incoming[target].append(source)
        outgoing[source].append(target)
        indegree[target] += 1

    for target_id, sources in incoming.items():
        supplied_properties: dict[str, Any] = {}
        for source_id in sources:
            source_schema = nodes_by_id[source_id].get("outputs", {})
            if not isinstance(source_schema, dict):
                continue
            source_properties = source_schema.get("properties", {})
            if isinstance(source_properties, dict):
                supplied_properties.update(source_properties)
        target_schema = nodes_by_id[target_id].get("inputs", {})
        if not isinstance(target_schema, dict):
            continue
        target_properties = target_schema.get("properties", {})
        required = target_schema.get("required", [])
        if not isinstance(target_properties, dict) or not isinstance(required, list):
            continue
        for property_name in required:
            if not isinstance(property_name, str) or property_name not in supplied_properties:
                errors.append(
                    f"workflow inputs for node {target_id} are missing required "
                    f"property {property_name}"
                )
        for property_name, input_property in target_properties.items():
            if not isinstance(property_name, str) or not isinstance(input_property, dict):
                continue
            output_property = supplied_properties.get(property_name)
            if (
                isinstance(output_property, dict)
                and not _types_are_compatible(
                    output_property.get("type"), input_property.get("type")
                )
            ):
                errors.append(
                    f"workflow property {property_name} has incompatible types between "
                    f"upstream nodes and node {target_id}"
                )

    roots = [node_id for node_id, count in indegree.items() if count == 0]
    queue = deque(roots)
    visited: set[str] = set()
    while queue:
        node_id = queue.popleft()
        visited.add(node_id)
        for target_id in outgoing[node_id]:
            indegree[target_id] -= 1
            if indegree[target_id] == 0:
                queue.append(target_id)
    if len(visited) != len(nodes_by_id):
        errors.append("execution_graph must be acyclic")

    reachable = set(roots)
    queue = deque(roots)
    while queue:
        node_id = queue.popleft()
        for target_id in outgoing[node_id]:
            if target_id not in reachable:
                reachable.add(target_id)
                queue.append(target_id)
    if len(reachable) != len(nodes_by_id):
        errors.append("every execution_graph node must be reachable from a root node")
    return errors


def _types_are_compatible(output_type: Any, input_type: Any) -> bool:
    return output_type == input_type or (output_type == "integer" and input_type == "number")


def _validate_object_schema(schema: Any, label: str, errors: list[str]) -> None:
    if not isinstance(schema, dict) or schema.get("type") != "object":
        errors.append(f"{label} must be a JSON Schema object contract")
        return
    properties = schema.get("properties")
    required = schema.get("required", [])
    if not isinstance(properties, dict) or not isinstance(required, list):
        errors.append(f"{label} must define properties and a required array")
        return
    for property_name, property_schema in properties.items():
        if (
            not isinstance(property_name, str)
            or not isinstance(property_schema, dict)
            or property_schema.get("type") not in JSON_SCHEMA_TYPES
        ):
            errors.append(f"{label} has an invalid schema for property {property_name}")
    unknown_required = [
        name for name in required if not isinstance(name, str) or name not in properties
    ]
    if unknown_required:
        errors.append(
            f"{label} requires properties not defined in properties: "
            + ", ".join(str(name) for name in unknown_required)
        )
