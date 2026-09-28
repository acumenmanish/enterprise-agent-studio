
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import Agent, Tenant
from app.services.scheduling import load_manifest


def seed_local_demo(session: Session, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    tenant = session.get(Tenant, settings.default_tenant_id)
    if tenant is None:
        tenant = Tenant(id=settings.default_tenant_id, name="Local Printing Demo")
        session.add(tenant)
        session.flush()

    manifest = load_manifest(settings.manifest_path)
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
