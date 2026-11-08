"""Plan endpoints (Person B). BACKEND_PERSON_B.md T2: a stub until the real pipeline (T4) replaces it.

The stub saves the hand-written Kyushu plan (app/fixtures/demo_plan.json) so the front end can build the trip page
and the progress screen now. It calls no paid API (Gemini, Places, Routes, YouTube). It must never appear in the demo
video (hackathon rule: no fake demo). T4 replaces the body with pipeline.run(trip_id) and adds check_plan_limit.
"""

import asyncio
from pathlib import Path

from fastapi import APIRouter

from app.auth import User, require_owner
from app.models import Plan
from app.services.firestore import save_plan, update_trip

router = APIRouter()

DEMO_PLAN = Path(__file__).resolve().parents[1] / "fixtures" / "demo_plan.json"
STAGE_SECONDS = 1.0  # pause per progress stage, so the front end can see each one


@router.post("/trips/{trip_id}/plan")
async def create_plan(trip_id: str, uid: User) -> dict[str, str]:
    # Owner only: shared links are view only (PLAN.md F5), so a viewer can't replace the plan (decision 11).
    await require_owner(trip_id, uid)

    await update_trip(trip_id, {"status": "planning", "progress": "spots"})
    for stage in ("routes", "videos"):
        await asyncio.sleep(STAGE_SECONDS)
        await update_trip(trip_id, {"progress": stage})
    await asyncio.sleep(STAGE_SECONDS)

    plan = Plan.model_validate_json(DEMO_PLAN.read_text(encoding="utf-8"))
    # save_plan sets status "ready" and progress "done". reason "stub" marks this version as sample data.
    return {"planId": await save_plan(trip_id, plan, reason="stub")}
