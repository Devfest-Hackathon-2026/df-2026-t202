"""Auth and startup checks. No network: the Firebase verify calls are monkeypatched."""

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app import auth, config


def request(headers: dict[str, str]) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    return Request({"type": "http", "headers": raw})


async def call_require_user(headers: dict[str, str]) -> int:
    with pytest.raises(HTTPException) as exc:
        await auth.require_user(request(headers))
    return exc.value.status_code


@pytest.fixture
def no_firebase(monkeypatch):
    def reject(*args):
        raise ValueError("bad token")

    monkeypatch.setattr(auth, "firebase_app", lambda: None)
    monkeypatch.setattr(auth.auth, "verify_id_token", reject)
    monkeypatch.setattr(auth.app_check, "verify_token", reject)


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_missing_or_invalid_bearer_is_401(no_firebase, anyio_backend):
    assert await call_require_user({}) == 401
    assert await call_require_user({"Authorization": "Token abc"}) == 401
    assert await call_require_user({"Authorization": "Bearer forged"}) == 401


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_missing_app_check_is_401_when_not_skipped(no_firebase, monkeypatch, anyio_backend):
    monkeypatch.setattr(config.get_settings(), "skip_appcheck", False)
    with pytest.raises(HTTPException) as exc:
        await auth.require_user(request({"Authorization": "Bearer t"}))
    assert exc.value.status_code == 401 and exc.value.detail == "app_check_required"


@pytest.mark.parametrize(
    "env",
    [{"SKIP_APPCHECK": "1"}, {"SKIP_APPCHECK": "0", "FIREBASE_AUTH_EMULATOR_HOST": "127.0.0.1:9099"}],
)
def test_production_refuses_unsafe_env(monkeypatch, env):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("FIRESTORE_EMULATOR_HOST", raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    config.get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError):
            config.get_settings()
    finally:
        config.get_settings.cache_clear()
