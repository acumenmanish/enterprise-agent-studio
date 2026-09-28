import re
from typing import Any

import yaml

from app.services.workflow_contracts import validate_workflow_graph

REQUIRED_MANIFEST_KEYS = {
    "agent",
    "semantic_contract",
    "tools",
    "policies",
    "model_policy",
    "optimizer",
    "execution",
    "quick_build_defaults",
    "execution_graph",
    "outcomes",
    "sandbox_profile",
}
OBJECTIVES = {"balanced", "due_date", "changeover"}
SECRET_FIELD_NAMES = {
    "api_key",
    "client_secret",
    "model_api_key",
    "password",
    "secret",
    "token",
}


def parse_and_validate_manifest(manifest_yaml: str) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        manifest = yaml.safe_load(manifest_yaml)
    except yaml.YAMLError as exc:
        return None, [f"manifest YAML is invalid: {exc.problem or 'parse error'}"]

    if not isinstance(manifest, dict):
        return None, ["manifest must be a YAML object"]

    errors = [
        f"manifest is missing required section {key}"
        for key in sorted(REQUIRED_MANIFEST_KEYS - manifest.keys())
    ]
    agent = manifest.get("agent")
    if not isinstance(agent, dict):
        errors.append("manifest.agent must be an object")
    else:
        for field in ("id", "name", "version", "domain", "objective"):
            if not isinstance(agent.get(field), str) or not agent[field].strip():
                errors.append(f"manifest.agent.{field} must be a non-empty string")
        if isinstance(agent.get("version"), str) and not re.fullmatch(
            r"\d+\.\d+\.\d+", agent["version"]
        ):
            errors.append("manifest.agent.version must use semantic versioning (MAJOR.MINOR.PATCH)")

    for key in ("semantic_contract", "model_policy", "optimizer", "execution", "quick_build_defaults"):
        if not isinstance(manifest.get(key), dict):
            errors.append(f"manifest.{key} must be an object")
    for key in ("tools", "policies", "outcomes"):
        if not isinstance(manifest.get(key), list):
            errors.append(f"manifest.{key} must be an array")

    defaults = manifest.get("quick_build_defaults")
    if isinstance(defaults, dict):
        horizon = defaults.get("planning_horizon_days")
        if not isinstance(horizon, int) or isinstance(horizon, bool) or not 1 <= horizon <= 5:
            errors.append("quick_build_defaults.planning_horizon_days must be between 1 and 5")
        if defaults.get("objective") not in OBJECTIVES:
            errors.append("quick_build_defaults.objective is not a supported objective")

    execution = manifest.get("execution")
    if isinstance(execution, dict) and not isinstance(execution.get("tenant_id"), str):
        errors.append("execution.tenant_id must be a string")

    errors.extend(validate_workflow_graph(manifest.get("execution_graph")))
    errors.extend(_find_secret_fields(manifest))
    return (manifest if not errors else None), errors


def _find_secret_fields(value: Any, path: str = "manifest") -> list[str]:
    if isinstance(value, dict):
        errors = []
        for key, child in value.items():
            key_name = str(key).lower()
            child_path = f"{path}.{key}"
            if key_name in SECRET_FIELD_NAMES:
                errors.append(f"{child_path} cannot contain credential material; use a vault reference")
            else:
                errors.extend(_find_secret_fields(child, child_path))
        return errors
    if isinstance(value, list):
        return [
            error
            for index, child in enumerate(value)
            for error in _find_secret_fields(child, f"{path}[{index}]")
        ]
    return []
