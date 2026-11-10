"""Plan endpoints. PLAN.md 9.1 / 9.3.

POST /trips/{trip_id}/plan runs the plan pipeline and returns {"planId"}. When the trip already has a plan, it
updates that plan instead (pipeline.update, D27); an update counts as a plan generation too. The request stays open
until the plan is saved (it can take more than 30 s, D4); the front end shows trips.progress meanwhile.
"""

import json
import logging
from typing import Annotated

import httpx
from fastapi import APIRouter, HTTPException, Path, status

from app import pipeline
from app.auth import ID_PATTERN, CurrentAccount, require_owner
from app.services import firestore as fs
from app.services.limits import check_plan_limit, refund_plan
from app.services.llm import LLMError

router = APIRouter()
log = logging.getLogger(__name__)

TripId = Annotated[str, Path(pattern=ID_PATTERN)]


@router.post("/trips/{trip_id}/plan")
async def create_plan(trip_id: TripId, account: CurrentAccount) -> dict[str, str]:
    # Owner only: shared links are view only.
    trip = await require_owner(trip_id, account.uid)
    if trip.get("asking") != "ready":
        raise HTTPException(status.HTTP_409_CONFLICT, "chat_not_finished")

    await pipeline.claim(trip_id)  # 409 plan_already_running on a double tap
    try:
        day = await check_plan_limit(account)  # 429 plan_limit_reached / service_busy
    except HTTPException:
        await fs.update_trip(trip_id, {"status": trip.get("status") or "chatting", "progress": None})
        raise

    try:
        build = pipeline.update if trip.get("currentPlanId") else pipeline.run
        return {"planId": await build(trip_id)}
    except (LLMError, httpx.HTTPError) as e:  # Gemini or Google Maps failed: an upstream error
        await _refund(account.uid, day, trip_id)  # not the user's fault: don't count it
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "plan_failed") from e


async def _refund(uid: str, day: str, trip_id: str) -> None:
    try:
        await refund_plan(uid, day)
    except Exception:  # keep the original error
        log.warning(json.dumps({"msg": "plan_refund_failed", "tripId": trip_id}))
