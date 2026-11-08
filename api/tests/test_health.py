from fastapi.testclient import TestClient

from app.main import app


def test_healthz():
    assert TestClient(app).get("/healthz").json() == {"ok": True}


def test_health_alias_for_cloud_run():
    assert TestClient(app).get("/health").json() == {"ok": True}
