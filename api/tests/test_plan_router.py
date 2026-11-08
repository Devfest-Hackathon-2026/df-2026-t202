"""POST /trips/{id}/plan with the pipeline, limit and Firestore faked (no emulator, no network)."""

import asyncio

import httpx
import pytest
from fastapi import HTTPException

from app import auth, pipeline
from app.auth import require_user
from app.main import app
from app.routers import plan as plan_router
from app.services import firestore as fs
from app.services.llm import LLMError

OWNER, VIEWER = "owner-uid", "viewer-uid"


@pytest.fixture
def fake(monkeypatch):
    state = {"asking": "ready", "limit_ok": True, "run": None, "claimed": [], "writes": []}

    async def get_trip(trip_id):
        if trip_id != "t1":
            return None
        return {"members": {OWNER: "owner", VIEWER: "viewer"}, "asking": state["asking"], "status": "chatting"}

    async def claim(trip_id):
        state["claimed"].append(trip_id)

    async def check_plan_limit(uid):
        if not state["limit_ok"]:
            raise HTTPException(429, "plan_limit_reached")

    async def run(trip_id):
        if state["run"]:
            raise state["run"]
        return "plan-1"

    async def update_trip(trip_id, data):
        state["writes"].append(data)

    monkeypatch.setattr(auth, "get_trip", get_trip)
    monkeypatch.setattr(pipeline, "claim", claim)
    monkeypatch.setattr(pipeline, "run", run)
    monkeypatch.setattr(plan_router, "check_plan_limit", check_plan_limit)
    monkeypatch.setattr(fs, "update_trip", update_trip)
    yield state
    app.dependency_overrides.clear()


def post_plan(uid: str, trip_id: str = "t1") -> httpx.Response:
    app.dependency_overrides[require_user] = lambda: uid

    async def call():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            return await client.post(f"/trips/{trip_id}/plan")

    return asyncio.run(call())


def test_owner_gets_a_plan(fake):
    resp = post_plan(OWNER)
    assert resp.status_code == 200 and resp.json() == {"planId": "plan-1"}
    assert fake["claimed"] == ["t1"]


def test_viewer_stranger_and_missing_trip(fake):
    assert post_plan(VIEWER).status_code == 403
    assert post_plan("stranger").status_code == 403
    assert post_plan(OWNER, trip_id="nope").status_code == 404
    assert fake["claimed"] == []


def test_chat_not_finished(fake):
    fake["asking"] = "budget"
    resp = post_plan(OWNER)
    assert resp.status_code == 409 and resp.json()["detail"] == "chat_not_finished"
    assert fake["claimed"] == []


def test_daily_limit_releases_the_trip(fake):
    fake["limit_ok"] = False
    assert post_plan(OWNER).status_code == 429
    assert fake["writes"] == [{"status": "chatting", "progress": None}]


def test_gemini_or_maps_failure_is_502(fake):
    fake["run"] = LLMError("down")
    assert post_plan(OWNER).status_code == 502
    fake["run"] = httpx.ConnectError("down")
    assert post_plan(OWNER).status_code == 502
