import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
import yaml
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Agent, AgentConfiguration, AgentRun, Approval, RunEvent
from app.db.session import get_db
from app.schemas.scheduling import (
    AgentConfigurationUpdate,
    ApprovalDecision,
    ERPConnectionUpdate,
    KnowledgeDocumentUpload,
    ManifestSaveRequest,
    ManifestValidationRequest,
    ModelCredentialUpdate,
    ScheduleRequest,
    WorkflowGraphSaveRequest,
)
from app.services.agent_context import compose_agent_system_prompt, retrieve_agent_context
from app.services.credential_vault import (
    CredentialVaultError,
    decrypt_secret,
    encrypt_secret,
)
from app.services.document_parser import DocumentParseError, extract_document_text
from app.services.erp_connector import (
    ERPConnectorError,
    erp_connection_status,
    preview_erp_data,
    validate_erp_endpoint,
)
from app.services.manifest_repository import (
    LocalManifestRepository,
    ManifestRepositoryError,
)
from app.services.manifest_validation import parse_and_validate_manifest
from app.services.model_gateway import explain_schedule, interpret_scheduling_request
from app.services.run_log import append_event
from app.services.scheduling import SchedulingInputError, load_demo_data, optimize_schedule
from app.services.workflow_runtime import (
    WorkflowExecutionError,
    build_schedule_workflow,
)

router = APIRouter(prefix="/api/v1/studio", tags=["studio"])
log = structlog.get_logger()


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _repository(settings: Settings) -> LocalManifestRepository:
    return LocalManifestRepository(settings.agent_repository_path)


def _load_manifest(settings: Settings, tenant_id: str, agent_id: str) -> tuple[dict[str, Any], str]:
    try:
        manifest_yaml = _repository(settings).read(tenant_id, agent_id)
    except ManifestRepositoryError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    manifest, errors = parse_and_validate_manifest(manifest_yaml)
    if errors or manifest is None:
        log.error("studio.manifest_repository_invalid", errors=errors)
        raise HTTPException(
            status_code=500,
            detail="The local agent repository contains an invalid manifest.",
        )
    return manifest, yaml.safe_dump(manifest, sort_keys=False)


def _manifest_scope_errors(manifest: dict[str, Any], agent_id: str, tenant_id: str) -> list[str]:
    errors = []
    if manifest["agent"]["id"] != agent_id:
        errors.append("manifest.agent.id cannot be changed")
    if manifest["execution"]["tenant_id"] != tenant_id:
        errors.append("manifest.execution.tenant_id cannot be changed")
    return errors


def _revision_history(settings: Settings, tenant_id: str, agent_id: str) -> list[dict[str, str]]:
    try:
        repository = _repository(settings)
        revisions = repository.history(tenant_id, agent_id)
        for revision in revisions:
            revision_yaml = repository.read_revision(tenant_id, agent_id, revision["commit"])
            manifest, errors = parse_and_validate_manifest(revision_yaml)
            if errors or manifest is None:
                revision["version"] = "invalid"
            else:
                revision["version"] = manifest["agent"]["version"]
        return revisions
    except ManifestRepositoryError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _serialize_run(run: AgentRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "agent_id": run.agent_id,
        "status": run.status,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "result": run.result,
    }


def _agent_configuration(
    db: Session, tenant_id: str, agent_id: str, manifest: dict[str, Any]
) -> tuple[AgentConfiguration, dict[str, Any]]:
    record = db.get(AgentConfiguration, (tenant_id, agent_id))
    defaults = {
        "domain": manifest["agent"]["domain"],
        "subdomain": "production/scheduling",
        "template_id": manifest.get("quick_build_defaults", {}).get(
            "template_id", "printing-production-scheduling"
        ),
        "system_prompt": "",
        "business_rules": "",
        "enabled_tools": manifest.get("tools", []),
        "scenarios": [],
        "documents": [],
    }
    customization = manifest.get("customization")
    if isinstance(customization, dict):
        defaults.update({key: customization[key] for key in defaults if key in customization})
    if record is None:
        record = AgentConfiguration(
            tenant_id=tenant_id, agent_id=agent_id, configuration={"documents": []}
        )
        db.add(record)
        db.flush()
    stored_documents = record.configuration.get("documents", [])
    defaults["documents"] = stored_documents if isinstance(stored_documents, list) else []
    return record, defaults


@router.get("/data/erp/status")
def get_erp_connection_status(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    settings = _settings(request)
    record = db.get(AgentConfiguration, (settings.default_tenant_id, "production-scheduling"))
    endpoint = (
        str(record.configuration.get("erp_endpoint"))
        if record and record.configuration.get("erp_endpoint")
        else None
    )
    token_configured = bool(record and record.encrypted_erp_token)
    return {
        **erp_connection_status(settings, endpoint, token_configured),
        "credential_encryption_available": settings.credential_encryption_key is not None,
    }


@router.put("/data/erp/connection")
def save_erp_connection(
    body: ERPConnectionUpdate,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    settings = _settings(request)
    agent = db.get(Agent, "production-scheduling")
    if agent is None or agent.tenant_id != settings.default_tenant_id:
        raise HTTPException(status_code=404, detail="Scheduling agent not found")
    try:
        validate_erp_endpoint(body.endpoint.strip(), body.api_token)
        encrypted_token = encrypt_secret(settings, body.api_token)
    except CredentialVaultError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ERPConnectorError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    record = db.get(AgentConfiguration, (agent.tenant_id, agent.id))
    if record is None:
        record = AgentConfiguration(
            tenant_id=agent.tenant_id,
            agent_id=agent.id,
            configuration={"documents": []},
        )
        db.add(record)
    record.configuration = {
        **record.configuration,
        "erp_endpoint": body.endpoint.strip(),
    }
    record.encrypted_erp_token = encrypted_token
    db.commit()
    return {"configured": True}


@router.delete("/data/erp/connection")
def clear_erp_connection(request: Request, db: Session = Depends(get_db)) -> dict[str, bool]:
    settings = _settings(request)
    record = db.get(AgentConfiguration, (settings.default_tenant_id, "production-scheduling"))
    if record is not None:
        record.encrypted_erp_token = None
        record.configuration = {
            key: value for key, value in record.configuration.items() if key != "erp_endpoint"
        }
        db.commit()
    return {"environment_connection_configured": settings.erp_api_configured}


@router.post("/data/erp/preview")
async def preview_erp_connection(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    settings = _settings(request)
    record = db.get(AgentConfiguration, (settings.default_tenant_id, "production-scheduling"))
    endpoint = (
        str(record.configuration.get("erp_endpoint"))
        if record and record.configuration.get("erp_endpoint")
        else None
    )
    try:
        token = (
            decrypt_secret(settings, record.encrypted_erp_token)
            if record and record.encrypted_erp_token
            else None
        )
    except CredentialVaultError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    try:
        return await preview_erp_data(settings, endpoint, token)
    except ERPConnectorError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/agent/documents/extract")
def extract_agent_document(body: KnowledgeDocumentUpload) -> dict[str, str]:
    try:
        text = extract_document_text(body.name, body.content_base64)
    except DocumentParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"name": body.name, "text": text}


@router.get("/agent/configuration")
def get_agent_configuration(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    settings = _settings(request)
    agent = db.get(Agent, "production-scheduling")
    if agent is None or agent.tenant_id != settings.default_tenant_id:
        raise HTTPException(status_code=404, detail="Scheduling agent not found")
    manifest, _ = _load_manifest(settings, agent.tenant_id, agent.id)
    record, configuration = _agent_configuration(db, agent.tenant_id, agent.id, manifest)
    db.commit()
    return {
        **configuration,
        "version": manifest["agent"]["version"],
        "base_version": manifest["agent"]["version"],
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        "model_key_override_configured": record.encrypted_model_key is not None,
        "model_key_override_can_be_saved": settings.credential_encryption_key is not None,
    }


@router.put("/agent/configuration")
def save_agent_configuration(
    body: AgentConfigurationUpdate,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    settings = _settings(request)
    agent = db.scalar(
        select(Agent)
        .where(
            Agent.id == "production-scheduling",
            Agent.tenant_id == settings.default_tenant_id,
        )
        .with_for_update()
    )
    if agent is None:
        raise HTTPException(status_code=404, detail="Scheduling agent not found")
    current_manifest, _ = _load_manifest(settings, agent.tenant_id, agent.id)
    if body.base_version != current_manifest["agent"]["version"]:
        raise HTTPException(
            status_code=409,
            detail="The agent changed since this draft was loaded. Reload before saving.",
        )

    record, _ = _agent_configuration(db, agent.tenant_id, agent.id, current_manifest)
    updated_manifest = dict(current_manifest)
    updated_manifest["customization"] = body.model_dump(exclude={"base_version", "documents"})
    updated_manifest["customization"]["knowledge_sources"] = [
        {
            "name": document.name,
            "sha256": hashlib.sha256(document.text.encode("utf-8")).hexdigest(),
        }
        for document in body.documents
    ]
    updated_manifest["tools"] = body.enabled_tools
    major, minor, patch = (int(part) for part in current_manifest["agent"]["version"].split("."))
    updated_manifest["agent"] = {
        **current_manifest["agent"],
        "version": f"{major}.{minor}.{patch + 1}",
    }
    manifest_yaml = yaml.safe_dump(updated_manifest, sort_keys=False)
    errors = parse_and_validate_manifest(manifest_yaml)[1]
    errors.extend(_manifest_scope_errors(updated_manifest, agent.id, agent.tenant_id))
    try:
        build_schedule_workflow(
            updated_manifest["execution_graph"],
            updated_manifest["tools"],
            settings.demo_data_path,
        )
    except WorkflowExecutionError as exc:
        errors.append(str(exc))
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    try:
        revision = _repository(settings).commit(
            agent.tenant_id,
            agent.id,
            manifest_yaml,
            "Update agent prompt and business context",
        )
    except ManifestRepositoryError as exc:
        log.exception("studio.agent_configuration_commit_failed", error=str(exc))
        raise HTTPException(
            status_code=500,
            detail="Agent configuration could not be committed to the local repository.",
        ) from exc

    record.configuration = {
        **{key: value for key, value in record.configuration.items() if key == "erp_endpoint"},
        "documents": [document.model_dump() for document in body.documents],
    }
    agent.manifest = updated_manifest
    agent.version = updated_manifest["agent"]["version"]
    agent.name = updated_manifest["agent"]["name"]
    db.commit()
    return {
        **body.model_dump(exclude={"base_version"}),
        "version": agent.version,
        "revision": revision,
        "model_key_override_configured": record.encrypted_model_key is not None,
        "model_key_override_can_be_saved": settings.credential_encryption_key is not None,
    }


@router.put("/model/credential")
def save_model_credential(
    body: ModelCredentialUpdate,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    settings = _settings(request)
    agent = db.get(Agent, "production-scheduling")
    if agent is None or agent.tenant_id != settings.default_tenant_id:
        raise HTTPException(status_code=404, detail="Scheduling agent not found")
    try:
        encrypted_key = encrypt_secret(settings, body.api_key)
    except CredentialVaultError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    record = db.get(AgentConfiguration, (agent.tenant_id, agent.id))
    if record is None:
        record = AgentConfiguration(
            tenant_id=agent.tenant_id,
            agent_id=agent.id,
            configuration={"documents": []},
        )
        db.add(record)
    record.encrypted_model_key = encrypted_key
    db.commit()
    return {"configured": True}


@router.delete("/model/credential")
def clear_model_credential(request: Request, db: Session = Depends(get_db)) -> dict[str, bool]:
    settings = _settings(request)
    record = db.get(AgentConfiguration, (settings.default_tenant_id, "production-scheduling"))
    if record is None:
        return {"environment_key_configured": settings.model_configured}
    record.encrypted_model_key = None
    db.commit()
    return {"environment_key_configured": settings.model_configured}


@router.get("/manifest")
def get_manifest(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    settings = _settings(request)
    agent = db.get(Agent, "production-scheduling")
    if agent is None:
        raise HTTPException(status_code=404, detail="Scheduling agent manifest not found")
    manifest, manifest_yaml = _load_manifest(settings, settings.default_tenant_id, agent.id)
    agent.name = manifest["agent"]["name"]
    agent.version = manifest["agent"]["version"]
    agent.manifest = manifest
    db.commit()
    return {
        "manifest": manifest,
        "manifest_yaml": manifest_yaml,
        "model_configured": settings.model_configured,
    }


@router.post("/manifest/validate")
def validate_manifest(
    body: ManifestValidationRequest, request: Request, db: Session = Depends(get_db)
) -> dict[str, Any]:
    settings = _settings(request)
    agent = db.get(Agent, "production-scheduling")
    if agent is None or agent.tenant_id != settings.default_tenant_id:
        raise HTTPException(status_code=404, detail="Scheduling agent not found")
    manifest, errors = parse_and_validate_manifest(body.manifest_yaml)
    if manifest is not None:
        errors.extend(_manifest_scope_errors(manifest, agent.id, agent.tenant_id))
        try:
            build_schedule_workflow(
                manifest["execution_graph"],
                manifest["tools"],
                settings.demo_data_path,
            )
        except WorkflowExecutionError as exc:
            errors.append(str(exc))
    return {"valid": not errors, "errors": errors}


@router.put("/manifest")
def save_manifest(
    body: ManifestSaveRequest, request: Request, db: Session = Depends(get_db)
) -> dict[str, Any]:
    settings = _settings(request)
    agent = db.scalar(
        select(Agent)
        .where(
            Agent.id == "production-scheduling",
            Agent.tenant_id == settings.default_tenant_id,
        )
        .with_for_update()
    )
    if agent is None:
        raise HTTPException(status_code=404, detail="Scheduling agent not found")

    current_manifest, _ = _load_manifest(settings, agent.tenant_id, agent.id)
    current_version = current_manifest["agent"]["version"]
    if body.base_version != current_version:
        raise HTTPException(
            status_code=409,
            detail="The manifest changed since this draft was loaded. Reload before saving.",
        )

    manifest, errors = parse_and_validate_manifest(body.manifest_yaml)
    if manifest is not None:
        errors.extend(_manifest_scope_errors(manifest, agent.id, agent.tenant_id))
        try:
            build_schedule_workflow(
                manifest["execution_graph"],
                manifest["tools"],
                settings.demo_data_path,
            )
        except WorkflowExecutionError as exc:
            errors.append(str(exc))
    if errors or manifest is None:
        raise HTTPException(status_code=422, detail=errors)

    major, minor, patch = (int(part) for part in current_version.split("."))
    manifest["agent"]["version"] = f"{major}.{minor}.{patch + 1}"
    manifest_yaml = yaml.safe_dump(manifest, sort_keys=False)
    try:
        commit = _repository(settings).commit(
            agent.tenant_id,
            agent.id,
            manifest_yaml,
            body.change_summary.strip(),
        )
    except ManifestRepositoryError as exc:
        log.exception("studio.manifest_commit_failed", error=str(exc))
        raise HTTPException(
            status_code=500,
            detail="The manifest could not be committed to the local agent repository.",
        ) from exc

    agent.name = manifest["agent"]["name"]
    agent.version = manifest["agent"]["version"]
    agent.manifest = manifest
    db.commit()
    return {
        "manifest": manifest,
        "manifest_yaml": manifest_yaml,
        "revision": commit,
    }


@router.put("/manifest/graph")
def save_workflow_graph(
    body: WorkflowGraphSaveRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    settings = _settings(request)
    agent = db.get(Agent, "production-scheduling")
    if agent is None or agent.tenant_id != settings.default_tenant_id:
        raise HTTPException(status_code=404, detail="Scheduling agent not found")
    current_manifest, _ = _load_manifest(settings, agent.tenant_id, agent.id)
    candidate = {**current_manifest, "execution_graph": body.graph}
    return save_manifest(
        ManifestSaveRequest(
            manifest_yaml=yaml.safe_dump(candidate, sort_keys=False),
            base_version=body.base_version,
            change_summary=body.change_summary,
        ),
        request,
        db,
    )


@router.get("/manifest/history")
def get_manifest_history(request: Request, db: Session = Depends(get_db)) -> list[dict[str, str]]:
    settings = _settings(request)
    agent = db.get(Agent, "production-scheduling")
    if agent is None or agent.tenant_id != settings.default_tenant_id:
        raise HTTPException(status_code=404, detail="Scheduling agent not found")
    return _revision_history(settings, agent.tenant_id, agent.id)


@router.get("/manifest/revisions/{revision}")
def get_manifest_revision(
    revision: str, request: Request, db: Session = Depends(get_db)
) -> dict[str, Any]:
    settings = _settings(request)
    agent = db.get(Agent, "production-scheduling")
    if agent is None or agent.tenant_id != settings.default_tenant_id:
        raise HTTPException(status_code=404, detail="Scheduling agent not found")
    history = _revision_history(settings, agent.tenant_id, agent.id)
    if not any(item["commit"] == revision for item in history):
        raise HTTPException(status_code=404, detail="Manifest revision not found")
    try:
        manifest_yaml = _repository(settings).read_revision(agent.tenant_id, agent.id, revision)
    except ManifestRepositoryError as exc:
        raise HTTPException(status_code=404, detail="Manifest revision not found") from exc
    manifest, errors = parse_and_validate_manifest(manifest_yaml)
    if errors or manifest is None:
        raise HTTPException(status_code=500, detail="Stored manifest revision is invalid.")
    return {"manifest": manifest, "manifest_yaml": manifest_yaml, "revision": revision}


@router.get("/manifest/compare")
def compare_manifest_revisions(
    request: Request,
    from_revision: str,
    to_revision: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    settings = _settings(request)
    agent = db.get(Agent, "production-scheduling")
    if agent is None or agent.tenant_id != settings.default_tenant_id:
        raise HTTPException(status_code=404, detail="Scheduling agent not found")
    known_revisions = {
        item["commit"] for item in _revision_history(settings, agent.tenant_id, agent.id)
    }
    if from_revision not in known_revisions or to_revision not in known_revisions:
        raise HTTPException(status_code=404, detail="Manifest revision not found")
    try:
        diff = _repository(settings).compare(agent.tenant_id, agent.id, from_revision, to_revision)
    except ManifestRepositoryError as exc:
        raise HTTPException(status_code=404, detail="Manifest revision not found") from exc
    return {"from_revision": from_revision, "to_revision": to_revision, "diff": diff}


@router.get("/demo-data")
def get_demo_data(request: Request) -> dict[str, Any]:
    return load_demo_data(_settings(request).demo_data_path)


@router.post("/schedule/run", status_code=201)
async def create_schedule_run(
    schedule_request: ScheduleRequest, request: Request, db: Session = Depends(get_db)
) -> dict[str, Any]:
    settings = _settings(request)
    agent = db.get(Agent, "production-scheduling")
    if agent is None or agent.tenant_id != settings.default_tenant_id:
        raise HTTPException(status_code=404, detail="Scheduling agent not found")
    effective_request = schedule_request
    configuration_row, configuration = _agent_configuration(
        db, agent.tenant_id, agent.id, agent.manifest
    )
    required_tools = {
        "get_open_orders@1.0.0",
        "get_machine_capacity@1.0.0",
        "simulate_schedule@1.0.0",
    }
    missing_tools = required_tools - set(configuration["enabled_tools"])
    if missing_tools:
        raise HTTPException(
            status_code=409,
            detail=(
                "Enable the required scheduling tools before running: "
                + ", ".join(sorted(missing_tools))
            ),
        )
    try:
        workflow, workflow_order = build_schedule_workflow(
            agent.manifest["execution_graph"],
            configuration["enabled_tools"],
            settings.demo_data_path,
        )
    except WorkflowExecutionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    retrieved = retrieve_agent_context(configuration, schedule_request.request_text or agent.name)
    system_prompt = compose_agent_system_prompt(
        agent.manifest,
        configuration,
        retrieved["context"],
        "Interpret planner requests only as scheduling preferences. Never bypass "
        "hard constraints or planner approval.",
    )
    try:
        key_override = (
            decrypt_secret(settings, configuration_row.encrypted_model_key)
            if configuration_row.encrypted_model_key
            else None
        )
    except CredentialVaultError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if schedule_request.request_text:
        if not settings.model_configured and key_override is None:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Natural-language scheduling is not configured. Set "
                    "ANTHROPIC_API_KEY or configure MODEL_NAME, MODEL_API_KEY, and "
                    "MODEL_API_BASE, or clear the request text and choose a "
                    "structured objective."
                ),
            )
        try:
            intent = await interpret_scheduling_request(
                schedule_request.request_text,
                settings,
                system_prompt=system_prompt,
                api_key_override=key_override,
            )
        except Exception as exc:
            log.exception("studio.intent_interpretation_failed", error_type=type(exc).__name__)
            raise HTTPException(
                status_code=502,
                detail="The configured model could not interpret the request.",
            ) from exc
        effective_request = ScheduleRequest(
            planning_horizon_days=intent.planning_horizon_days,
            objective=intent.objective,
            request_text=schedule_request.request_text,
        )

    run = AgentRun(
        id=str(uuid.uuid4()),
        tenant_id=settings.default_tenant_id,
        agent_id=agent.id,
        status="running",
        request=effective_request.model_dump(),
        result=None,
    )
    db.add(run)
    append_event(db, run, "run.started", {"request": effective_request.model_dump()})
    db.commit()

    try:
        append_event(db, run, "workflow.started", {"node_order": workflow_order})
        db.commit()
        state = workflow.invoke({"request": effective_request.model_dump()})
        data = state["data"]
        append_event(
            db,
            run,
            "context.selected",
            {
                "orders": len(state.get("orders", data["orders"])),
                "machines": len(state.get("machines", data["machines"])),
                "data_source": "local-demo-data",
                "context_chunks_retrieved": retrieved["chunks_retrieved"],
                "context_sources": retrieved["sources"],
            },
        )
        result = state["result"]
        if not state.get("outcome_checked") or not state.get("approval_required"):
            raise WorkflowExecutionError(
                "Workflow did not reach outcome validation and planner approval."
            )
        append_event(db, run, "workflow.completed", {"node_order": workflow_order})
        result["explanation"] = await explain_schedule(
            result,
            settings,
            system_prompt=compose_agent_system_prompt(
                agent.manifest,
                configuration,
                retrieved["context"],
                "Explain the schedule using only the supplied metrics and validated schedule. "
                "Do not claim text context changes deterministic optimizer constraints.",
            ),
            api_key_override=key_override,
        )
        result["model"] = (
            settings.effective_model_name
            if settings.model_configured or key_override is not None
            else "deterministic-local"
        )
        append_event(db, run, "optimizer.completed", result["metrics"])
        append_event(
            db,
            run,
            "schedule.explained",
            {"model": result["model"], "explanation": result["explanation"]},
        )
        append_event(
            db,
            run,
            "outcome.checked",
            result["validation"],
        )
        run.status = "awaiting_approval"
        run.result = result
        approval = Approval(
            id=str(uuid.uuid4()),
            tenant_id=run.tenant_id,
            run_id=run.id,
            status="pending",
        )
        db.add(approval)
        append_event(
            db,
            run,
            "approval.requested",
            {"approval_id": approval.id, "action": "publish_schedule"},
        )
        db.commit()
    except SchedulingInputError as exc:
        db.rollback()
        failed_run = db.get(AgentRun, run.id)
        if failed_run is not None:
            failed_run.status = "failed"
            append_event(db, failed_run, "run.failed", {"reason": str(exc)})
            db.commit()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        failed_run = db.get(AgentRun, run.id)
        if failed_run is not None:
            failed_run.status = "failed"
            append_event(
                db,
                failed_run,
                "run.failed",
                {"reason": "model_orchestration_failed", "error_type": type(exc).__name__},
            )
            db.commit()
        log.exception("studio.schedule_run_failed", run_id=run.id, error=str(exc))
        raise HTTPException(
            status_code=502,
            detail="Schedule could not be completed. Check model configuration or backend logs.",
        ) from exc

    return {"run_id": run.id, "status": run.status, "result": run.result}


@router.get("/runs")
def list_runs(request: Request, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    tenant_id = _settings(request).default_tenant_id
    runs = db.scalars(
        select(AgentRun)
        .where(AgentRun.tenant_id == tenant_id)
        .order_by(AgentRun.created_at.desc())
        .limit(50)
    )
    return [_serialize_run(run) for run in runs]


@router.get("/runs/{run_id}")
def get_run(run_id: str, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    run = db.scalar(
        select(AgentRun).where(
            AgentRun.id == run_id,
            AgentRun.tenant_id == _settings(request).default_tenant_id,
        )
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    events = db.scalars(
        select(RunEvent).where(RunEvent.run_id == run.id).order_by(RunEvent.sequence)
    )
    approval = db.scalar(select(Approval).where(Approval.run_id == run.id))
    return {
        **_serialize_run(run),
        "request": run.request,
        "events": [
            {
                "sequence": event.sequence,
                "type": event.event_type,
                "payload": event.payload,
                "created_at": event.created_at.isoformat() if event.created_at else None,
            }
            for event in events
        ],
        "approval": (
            {
                "id": approval.id,
                "status": approval.status,
                "decision_by": approval.decision_by,
                "comment": approval.comment,
            }
            if approval
            else None
        ),
    }


@router.post("/runs/{run_id}/approval")
def decide_approval(
    run_id: str,
    decision: ApprovalDecision,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    run = db.scalar(
        select(AgentRun).where(
            AgentRun.id == run_id,
            AgentRun.tenant_id == _settings(request).default_tenant_id,
        )
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    approval = db.scalar(select(Approval).where(Approval.run_id == run_id))
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    if approval.status != "pending":
        raise HTTPException(status_code=409, detail="Approval has already been decided")
    agent = db.get(Agent, run.agent_id)
    if agent is None or "publish_schedule@1.0.0" not in agent.manifest.get("tools", []):
        raise HTTPException(
            status_code=403,
            detail="Publishing is disabled because the publish_schedule tool is not enabled.",
        )

    now = datetime.now(UTC)
    approval.status = "approved" if decision.decision == "approve" else "rejected"
    approval.decision_by = "local_planner"
    approval.comment = decision.comment
    approval.decided_at = now
    run.status = "published" if decision.decision == "approve" else "rejected"
    if run.result is None:
        raise HTTPException(status_code=409, detail="Run has no schedule to approve")
    run.result = {
        **run.result,
        "publish_status": (
            "published_to_local_demo" if decision.decision == "approve" else "rejected"
        ),
    }
    append_event(
        db,
        run,
        "approval.decided",
        {
            "decision": decision.decision,
            "decision_by": approval.decision_by,
            "comment": decision.comment,
            "published_to": "local-demo-simulator" if decision.decision == "approve" else None,
        },
    )
    db.commit()
    return _serialize_run(run)


@router.get("/model/status")
def model_status(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    settings = _settings(request)
    record = db.get(AgentConfiguration, (settings.default_tenant_id, "production-scheduling"))
    override_configured = bool(record and record.encrypted_model_key)
    configured = settings.model_configured or override_configured
    return {
        "configured": configured,
        "model": settings.effective_model_name if configured else None,
        "provider": settings.effective_model_provider if configured else None,
        "key_source": (
            "agent-override"
            if override_configured
            else "environment"
            if settings.model_configured
            else None
        ),
        "mode": "hosted-configured" if configured else "deterministic-local",
    }


@router.get("/evaluations")
def list_evaluations() -> dict[str, Any]:
    return {
        "suite": "printing-scheduling-smoke",
        "version": "0.1.0",
        "cases": [
            {
                "id": objective,
                "name": name,
                "objective": objective,
                "planning_horizon_days": 5,
                "checks": ["hard constraints satisfied", "all demo orders assigned"],
            }
            for objective, name in (
                ("balanced", "Balanced schedule"),
                ("due_date", "Due-date priority"),
                ("changeover", "Changeover minimization"),
            )
        ],
    }


@router.post("/evaluations/run")
def run_evaluations(request: Request) -> dict[str, Any]:
    data = load_demo_data(_settings(request).demo_data_path)
    results = []
    for case in list_evaluations()["cases"]:
        result = optimize_schedule(
            data,
            case["planning_horizon_days"],
            case["objective"],
        )
        scheduled = result["metrics"]["orders_scheduled"]
        score = round(scheduled / len(data["orders"]) * 100)
        results.append(
            {
                "case_id": case["id"],
                "name": case["name"],
                "status": "passed" if score == 100 else "failed",
                "score": score,
                "metrics": result["metrics"],
                "solver_status": result["solver_status"],
            }
        )
    return {
        "suite": "printing-scheduling-smoke",
        "cases_run": len(results),
        "passed": sum(result["status"] == "passed" for result in results),
        "results": results,
    }
