"""Local process and database readiness checks."""
import structlog
from fastapi import APIRouter, Request, Response, status

router = APIRouter(tags=["health"])
log = structlog.get_logger()


@router.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@router.get("/readyz")
def readyz(request: Request, response: Response) -> dict:
    checks = {"database": _check_database(request)}

    if not all(checks.values()):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        log.warning("readiness.failed", checks=checks)

    return {"status": "ok" if all(checks.values()) else "degraded", "checks": checks}


def _check_database(request: Request) -> bool:
    try:
        with request.app.state.engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("readiness.database_check_failed", error=str(exc))
        return False
