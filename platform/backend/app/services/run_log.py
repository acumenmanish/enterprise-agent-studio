from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import AgentRun, RunEvent


def append_event(
    session: Session, run: AgentRun, event_type: str, payload: dict[str, Any]
) -> RunEvent:
    sequence = session.scalar(
        select(func.max(RunEvent.sequence)).where(RunEvent.run_id == run.id)
    )
    event = RunEvent(
        run_id=run.id,
        sequence=(sequence or 0) + 1,
        event_type=event_type,
        payload=payload,
    )
    session.add(event)
    session.flush()
    return event
