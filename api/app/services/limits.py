"""Abuse limits (PLAN.md 9.6).

Per user per day (JST): trips created and plan generations, lower for guests (anonymous sign-in).
Whole app per day: plan generations. Per trip: messages, and a short gap between free-text messages.
Counters live in `users/{uid}/limits/{day}` and `usage/{day}` (server only, firestore.rules).
"""

from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from google.cloud import firestore

from app.auth import Account
from app.config import get_settings
from app.services.firestore import db, now

TOKYO = ZoneInfo("Asia/Tokyo")


def _today() -> str:
    return datetime.now(TOKYO).strftime("%Y-%m-%d")


def _user_ref(uid: str, day: str):
    return db().collection("users").document(uid).collection("limits").document(day)


def _usage_ref(day: str):
    return db().collection("usage").document(day)


def _count(snap, field: str) -> int:
    if not snap.exists:
        return 0
    return int((snap.to_dict() or {}).get(field) or 0)


async def check_trip_limit(account: Account) -> None:
    """Count one new trip for today. HTTP 429 trip_limit_reached once the daily limit is reached."""
    s = get_settings()
    limit = s.max_trips_per_guest_per_day if account.guest else s.max_trips_per_user_per_day
    ref = _user_ref(account.uid, _today())

    @firestore.async_transactional
    async def bump(tx: firestore.AsyncTransaction) -> bool:
        count = _count(await ref.get(transaction=tx), "trips")
        if count >= limit:
            return False
        tx.set(ref, {"trips": count + 1, "updatedAt": firestore.SERVER_TIMESTAMP}, merge=True)
        return True

    if not await bump(db().transaction()):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "trip_limit_reached")


async def check_plan_limit(account: Account) -> str:
    """Count one plan generation for the user and for the whole app, today (JST).

    HTTP 429 plan_limit_reached (user) or service_busy (whole app). Returns the day, for refund_plan()."""
    s = get_settings()
    limit = s.max_plans_per_guest_per_day if account.guest else s.max_plans_per_user_per_day
    day = _today()
    user_ref, usage_ref = _user_ref(account.uid, day), _usage_ref(day)

    @firestore.async_transactional
    async def bump(tx: firestore.AsyncTransaction) -> Literal["ok", "user", "app"]:
        user_count = _count(await user_ref.get(transaction=tx), "plans")
        app_count = _count(await usage_ref.get(transaction=tx), "plans")
        if user_count >= limit:
            return "user"
        if app_count >= s.max_plans_per_day:
            return "app"
        tx.set(user_ref, {"plans": user_count + 1, "updatedAt": firestore.SERVER_TIMESTAMP}, merge=True)
        tx.set(usage_ref, {"plans": app_count + 1, "updatedAt": firestore.SERVER_TIMESTAMP}, merge=True)
        return "ok"

    result = await bump(db().transaction())
    if result == "user":
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "plan_limit_reached")
    if result == "app":
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "service_busy")
    return day


async def refund_plan(uid: str, day: str) -> None:
    """Give back a plan generation that failed upstream (Gemini or Maps), so the user isn't charged for it."""
    batch = db().batch()
    batch.set(_user_ref(uid, day), {"plans": firestore.Increment(-1)}, merge=True)
    batch.set(_usage_ref(day), {"plans": firestore.Increment(-1)}, merge=True)
    await batch.commit()


def check_message_limit(trip: dict, new: int = 2) -> None:
    """Raises HTTP 429 if writing `new` more messages would pass the per-trip limit.

    Call it inside a transaction that also adds `new` to `trips.messageCount`, so two requests can't both pass.
    """
    if int(trip.get("messageCount") or 0) + new > get_settings().max_messages_per_trip:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "message_limit_reached")


def check_text_gap(trip: dict) -> None:
    """HTTP 429 too_fast if the last free-text message on this trip was less than a moment ago."""
    last = trip.get("lastTextAt")
    if last and (now() - last).total_seconds() < get_settings().min_seconds_between_texts:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "too_fast")


async def reserve_messages(trip_id: str, new: int = 2) -> None:
    """Reserve `new` message slots on the trip before slow work (Gemini).

    409 while planning, 429 at the limit or when texts come too fast."""
    ref = db().collection("trips").document(trip_id)

    @firestore.async_transactional
    async def reserve(tx: firestore.AsyncTransaction) -> None:
        trip = (await ref.get(transaction=tx)).to_dict() or {}
        if trip.get("status") == "planning":
            raise HTTPException(status.HTTP_409_CONFLICT, "planning_in_progress")
        check_message_limit(trip, new)
        check_text_gap(trip)
        tx.update(ref, {"messageCount": firestore.Increment(new), "lastTextAt": now()})

    await reserve(db().transaction())
