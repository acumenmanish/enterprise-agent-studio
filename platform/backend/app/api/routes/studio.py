import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
import yaml
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Agent, AgentRun, Approval, RunEvent
from app.db.session import get_db
from app.schemas.scheduling import ApprovalDecision, ScheduleRequest
from app.services.model_gateway import explain_schedule, interpret_scheduling_request
from app.services.run_log import append_event
from app.services.scheduling import SchedulingInputError, load_demo_data, optimize_schedule

router = APIRouter(prefix="/api/v1/studio", tags=["studio"])
log = structlog.get_logger()


def _serialize_run(run: AgentRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "agent_id": run.agent_id,
        "status": run.status,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "result": run.result,
    }


@router.get("/manifest")
def get_manifest(db: Session = Depends(get_db)) -> dict[str, Any]:
    settings = get_settings()
    agent = db.get(Agent, "production-scheduling")
    if agent is None:
        raise HTTPException(status_code=404, detail="Scheduling agent manifest not found")
    return {
        "manifest": agent.manifest,
        "manifest_yaml": yaml.safe_dump(agent.manifest, sort_keys=False),
        "model_configured": settings.model_configured,
    }


@router.get("/demo-data")
def get_demo_data() -> dict[str, Any]:
    return load_demo_data(get_settings().demo_data_path)


@router.post("/schedule/run", status_code=201)
async def create_schedule_run(
    schedule_request: ScheduleRequest, db: Session = Depends(get_db)
) -> dict[str, Any]:
    settings = get_settings()
    agent = db.get(Agent, "production-scheduling")
    if agent is None or agent.tenant_id != settings.default_tenant_id:
        raise HTTPException(status_code=404, detail="Scheduling agent not found")
    effective_request = schedule_request
    if schedule_request.request_text:
        if not settings.model_configured:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Natural-language scheduling is not configured. Set MODEL_NAME "
                    "and MODEL_API_KEY (or MODEL_API_BASE), or clear the request text "
                    "and choose a structured objective."
                ),
            )
        try:
            intent = await interpret_scheduling_request(schedule_request.request_text)
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
        data = load_demo_data(get_settings().demo_data_path)
        append_event(
            db,
            run,
            "context.selected",
            {
                "orders": len(data["orders"]),
                "machines": len(data["machines"]),
                "data_source": "local-demo-data",
            },
        )
        result = optimize_schedule(
            data,
            effective_request.planning_horizon_days,
            effective_request.objective,
        )
        result["explanation"] = await explain_schedule(result)
        result["model"] = (
            get_settings().model_name if get_settings().model_configured else "deterministic-local"
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
def list_runs(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    tenant_id = get_settings().default_tenant_id
    runs = db.scalars(
        select(AgentRun)
        .where(AgentRun.tenant_id == tenant_id)
        .order_by(AgentRun.created_at.desc())
        .limit(50)
    )
    return [_serialize_run(run) for run in runs]


@router.get("/runs/{run_id}")
def get_run(run_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    run = db.scalar(
        select(AgentRun).where(
            AgentRun.id == run_id,
            AgentRun.tenant_id == get_settings().default_tenant_id,
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
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    run = db.scalar(
        select(AgentRun).where(
            AgentRun.id == run_id,
            AgentRun.tenant_id == get_settings().default_tenant_id,
        )
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    approval = db.scalar(select(Approval).where(Approval.run_id == run_id))
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    if approval.status != "pending":
        raise HTTPException(status_code=409, detail="Approval has already been decided")

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
def model_status() -> dict[str, Any]:
    settings = get_settings()
    return {
        "configured": settings.model_configured,
        "model": settings.model_name if settings.model_configured else None,
        "mode": "hosted-configured" if settings.model_configured else "deterministic-local",
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
def run_evaluations() -> dict[str, Any]:
    data = load_demo_data(get_settings().demo_data_path)
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
