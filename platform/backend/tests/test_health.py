from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_healthz_returns_ok():
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_readyz_returns_a_status_field():
    # In CI/local without postgres running, this may report
    # "degraded" with a 503 — that is the correct, intended behavior for
    # a readiness probe, not a test bug. We assert the *shape*, not that
    # dependencies are up.
    resp = client.get("/readyz")
    assert resp.status_code in (200, 503)
    body = resp.json()
    assert body["status"] in ("ok", "degraded")
    assert set(body["checks"].keys()) == {"database"}
