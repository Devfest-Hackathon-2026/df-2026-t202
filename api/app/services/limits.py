"""Abuse limits (PLAN.md 9.6): 20 plan generations per user per day, 60 messages per trip."""

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from google.cloud import firestore

from app.config import get_settings
from app.services.firestore import db

TOKYO = ZoneInfo("Asia/Tokyo")


async def check_plan_limit(uid: str) -> None:
    """Count one plan generation for today (JST). Raises HTTP 429 once the daily limit is reached."""
    limit = get_settings().max_plans_per_user_per_day
    day = datetime.now(TOKYO).strftime("%Y-%m-%d")
    ref = db().collection("users").document(uid).collection("limits").document(day)

    @firestore.async_transactional
    async def bump(tx: firestore.AsyncTransaction) -> bool:
        snap = await ref.get(transaction=tx)
        count = int(snap.get("plans")) if snap.exists else 0
        if count >= limit:
            return False
        tx.set(ref, {"plans": count + 1, "updatedAt": firestore.SERVER_TIMESTAMP}, merge=True)
        return True

    if not await bump(db().transaction()):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "plan_limit_reached")


def check_message_limit(trip: dict, new: int = 2) -> None:
    """Raises HTTP 429 if writing `new` more messages would pass the per-trip limit.

    Call it inside a transaction that also adds `new` to `trips.messageCount`, so two requests can't both pass.
    """
    if int(trip.get("messageCount") or 0) + new > get_settings().max_messages_per_trip:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "message_limit_reached")


async def reserve_messages(trip_id: str, new: int = 2) -> None:
    """Reserve `new` message slots on the trip before slow work (Gemini). 409 while planning, 429 at the limit."""
    ref = db().collection("trips").document(trip_id)

    @firestore.async_transactional
    async def reserve(tx: firestore.AsyncTransaction) -> None:
        trip = (await ref.get(transaction=tx)).to_dict() or {}
        if trip.get("status") == "planning":
            raise HTTPException(status.HTTP_409_CONFLICT, "planning_in_progress")
        check_message_limit(trip, new)
        tx.update(ref, {"messageCount": firestore.Increment(new)})

    await reserve(db().transaction())
