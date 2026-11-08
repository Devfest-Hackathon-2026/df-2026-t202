"""POST /trips/{id}/plan stub (T2) with faked Firestore helpers (no emulator, no network)."""

import asyncio

import httpx
import pytest

from app import auth
from app.auth import require_user
from app.main import app
from app.models import Plan
from app.routers import plan as plan_router

OWNER, VIEWER = "owner-uid", "viewer-uid"


@pytest.fixture
def fake_db(monkeypatch):
    writes: list[dict] = []
    saved: list[tuple[str, Plan, str]] = []

    async def get_trip(trip_id):
        return {"members": {OWNER: "owner", VIEWER: "viewer"}} if trip_id == "t1" else None

    async def update_trip(trip_id, data):
        writes.append(data)

    async def save_plan(trip_id, plan, reason="initial"):
        saved.append((trip_id, plan, reason))
        return "plan-1"

    monkeypatch.setattr(auth, "get_trip", get_trip)
    monkeypatch.setattr(plan_router, "update_trip", update_trip)
    monkeypatch.setattr(plan_router, "save_plan", save_plan)
    monkeypatch.setattr(plan_router, "STAGE_SECONDS", 0)
    yield writes, saved
    app.dependency_overrides.clear()


def post_plan(uid: str, trip_id: str = "t1") -> httpx.Response:
    app.dependency_overrides[require_user] = lambda: uid

    async def call():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            return await client.post(f"/trips/{trip_id}/plan")

    return asyncio.run(call())


def test_owner_gets_demo_plan_with_progress(fake_db):
    writes, saved = fake_db
    resp = post_plan(OWNER)

    assert resp.status_code == 200 and resp.json() == {"planId": "plan-1"}
    assert writes == [{"status": "planning", "progress": "spots"}, {"progress": "routes"}, {"progress": "videos"}]
    trip_id, plan, reason = saved[0]
    assert (trip_id, reason) == ("t1", "stub")
    assert len(plan.days) == 4


def test_viewer_cannot_replace_the_plan(fake_db):
    writes, saved = fake_db
    assert post_plan(VIEWER).status_code == 403
    assert writes == [] and saved == []


def test_missing_trip_or_stranger(fake_db):
    assert post_plan(OWNER, trip_id="nope").status_code == 404
    assert post_plan("stranger").status_code == 403


def test_demo_plan_ships_inside_app():
    assert plan_router.DEMO_PLAN.parent.parent.name == "app"  # Cloud Run only copies app/
    Plan.model_validate_json(plan_router.DEMO_PLAN.read_text(encoding="utf-8"))
