from fastapi.testclient import TestClient

from app.main import app


def test_healthz():
    assert TestClient(app).get("/healthz").json() == {"ok": True}


def test_health_alias_for_cloud_run():
    assert TestClient(app).get("/health").json() == {"ok": True}


def test_httpx_request_urls_are_not_logged():
    import logging

    import app.main  # noqa: F401  (sets the levels)

    assert not logging.getLogger("httpx").isEnabledFor(logging.INFO)
