
from copy import deepcopy
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import Agent, Tenant
from app.services.manifest_repository import LocalManifestRepository
from app.services.manifest_validation import parse_and_validate_manifest


def _ensure_approved_policy_stage(manifest: dict[str, Any]) -> dict[str, Any] | None:
    graph = manifest.get("execution_graph")
    if not isinstance(graph, dict) or not isinstance(graph.get("nodes"), list):
        return None
    if any(
        isinstance(node, dict) and node.get("type") == "policy" for node in graph["nodes"]
    ):
        return None
    optimizers = [
        node
        for node in graph["nodes"]
        if isinstance(node, dict) and node.get("type") == "optimizer"
    ]
    if len(optimizers) != 1:
        raise ValueError("Cannot upgrade a scheduling manifest without exactly one optimizer node")

    upgraded = deepcopy(manifest)
    execution_graph = upgraded["execution_graph"]
    used_ids = {
        node.get("id")
        for node in execution_graph["nodes"]
        if isinstance(node, dict) and isinstance(node.get("id"), str)
    }
    node_id = "approved_business_policy"
    suffix = 2
    while node_id in used_ids:
        node_id = f"approved_business_policy_{suffix}"
        suffix += 1
    execution_graph["nodes"].append(
        {
            "id": node_id,
            "type": "policy",
            "inputs": {"type": "object", "properties": {}, "required": []},
            "outputs": {
                "type": "object",
                "properties": {"policy_constraints": {"type": "object"}},
                "required": ["policy_constraints"],
            },
        }
    )
    execution_graph["edges"].append({"from": node_id, "to": optimizers[0]["id"]})
    version = upgraded["agent"]["version"].split(".")
    version[2] = str(int(version[2]) + 1)
    upgraded["agent"]["version"] = ".".join(version)
    return upgraded


def seed_local_demo(session: Session, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    tenant = session.get(Tenant, settings.default_tenant_id)
    if tenant is None:
        tenant = Tenant(id=settings.default_tenant_id, name="Local Printing Demo")
        session.add(tenant)
        session.flush()

    with settings.manifest_path.open(encoding="utf-8") as manifest_file:
        initial_yaml = manifest_file.read()
    repository = LocalManifestRepository(settings.agent_repository_path)
    manifest_yaml = repository.initialize(
        settings.default_tenant_id,
        "production-scheduling",
        initial_yaml,
    )
    manifest, errors = parse_and_validate_manifest(manifest_yaml)
    if errors or manifest is None:
        raise ValueError("Invalid manifest in local agent repository: " + "; ".join(errors))
    upgraded_manifest = _ensure_approved_policy_stage(manifest)
    if upgraded_manifest is not None:
        manifest_yaml = yaml.safe_dump(upgraded_manifest, sort_keys=False)
        upgraded_manifest, errors = parse_and_validate_manifest(manifest_yaml)
        if errors or upgraded_manifest is None:
            raise ValueError("Policy-stage manifest migration failed: " + "; ".join(errors))
        repository.commit(
            settings.default_tenant_id,
            "production-scheduling",
            manifest_yaml,
            "Add reviewed policy constraint stage",
        )
        manifest = upgraded_manifest
    agent_id = manifest["agent"]["id"]
    existing_agent = session.scalar(select(Agent).where(Agent.id == agent_id))
    if existing_agent is None:
        session.add(
            Agent(
                id=agent_id,
                tenant_id=tenant.id,
                name=manifest["agent"]["name"],
                version=manifest["agent"]["version"],
                manifest=manifest,
            )
        )
    else:
        existing_agent.tenant_id = tenant.id
        existing_agent.name = manifest["agent"]["name"]
        existing_agent.version = manifest["agent"]["version"]
        existing_agent.manifest = manifest
    session.commit()
