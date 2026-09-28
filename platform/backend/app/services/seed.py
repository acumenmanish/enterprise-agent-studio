
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import Agent, Tenant
from app.services.manifest_repository import LocalManifestRepository
from app.services.manifest_validation import parse_and_validate_manifest


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
