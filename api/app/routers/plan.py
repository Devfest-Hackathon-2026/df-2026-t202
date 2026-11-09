"""Plan endpoints. PLAN.md 9.1 / 9.3.

POST /trips/{trip_id}/plan runs the plan pipeline and returns {"planId"}. The request stays open until the plan
is saved (it can take more than 30 s, D44); the front end shows trips.progress meanwhile.
"""

import httpx
from fastapi import APIRouter, HTTPException, status

from app import pipeline
from app.auth import User, require_owner
from app.services import firestore as fs
from app.services.limits import check_plan_limit
from app.services.llm import LLMError

router = APIRouter()


@router.post("/trips/{trip_id}/plan")
async def create_plan(trip_id: str, uid: User) -> dict[str, str]:
    # Owner only: shared links are view only (D41).
    trip = await require_owner(trip_id, uid)
    if trip.get("asking") != "ready":
        raise HTTPException(status.HTTP_409_CONFLICT, "chat_not_finished")  # D48

    await pipeline.claim(trip_id)  # 409 plan_already_running on a double tap (D48)
    try:
        await check_plan_limit(uid)  # 429 after 20 plans a day
    except HTTPException:
        await fs.update_trip(trip_id, {"status": trip.get("status") or "chatting", "progress": None})
        raise

    try:
        return {"planId": await pipeline.run(trip_id)}
    except (LLMError, httpx.HTTPError) as e:  # Gemini or Google Maps failed: an upstream error
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "plan_failed") from e
