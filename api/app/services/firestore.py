"""Firestore helpers. Person B imports these. Keep the signatures stable.

The API is the only writer of trips, messages, plans, shares and caches (the Admin SDK and the
server's credentials bypass the security rules). On Cloud Run the client uses the service account;
locally it uses `gcloud auth application-default login`, or the emulator if FIRESTORE_EMULATOR_HOST is set.
"""

from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
from typing import TYPE_CHECKING, Any

import firebase_admin
from google.cloud import firestore

from app.config import get_settings

if TYPE_CHECKING:
    from app.models import Plan

CACHE_NAMES = {"places", "videos"}  # → top-level collections cache_places, cache_videos


@lru_cache
def firebase_app() -> firebase_admin.App:
    """Firebase Admin app, used by auth.py to verify ID and App Check tokens."""
    project = get_settings().google_cloud_project
    return firebase_admin.initialize_app(options={"projectId": project} if project else None)


@lru_cache
def db() -> firestore.AsyncClient:
    return firestore.AsyncClient(project=get_settings().google_cloud_project)


def now() -> datetime:
    """Server clock. Used for message createdAt so the AI reply always sorts after the user message."""
    return datetime.now(UTC)


def _trip(trip_id: str) -> firestore.AsyncDocumentReference:
    return db().collection("trips").document(trip_id)


async def get_trip(trip_id: str) -> dict | None:
    snap = await _trip(trip_id).get()
    return {"id": snap.id, **snap.to_dict()} if snap.exists else None


async def update_trip(trip_id: str, data: dict) -> None:
    """Merge `data` into the trip and set updatedAt."""
    await _trip(trip_id).set({**data, "updatedAt": firestore.SERVER_TIMESTAMP}, merge=True)


async def list_messages(trip_id: str) -> list[dict]:
    """All messages of a trip, oldest first."""
    query = _trip(trip_id).collection("messages").order_by("createdAt")
    return [{"id": snap.id, **snap.to_dict()} async for snap in query.stream()]


async def add_message(trip_id: str, role: str, text: str, answer: dict | None = None, ui: dict | None = None) -> str:
    ref = _trip(trip_id).collection("messages").document()
    await ref.set({"role": role, "text": text, "answer": answer, "ui": ui, "createdAt": now()})
    return ref.id


async def save_plan(trip_id: str, plan: Plan, reason: str = "initial") -> str:
    """Save a new plan version and point the trip at it. Returns the planId."""
    trip_ref = _trip(trip_id)
    plan_ref = trip_ref.collection("plans").document()

    @firestore.async_transactional
    async def write(tx: firestore.AsyncTransaction) -> None:
        latest = trip_ref.collection("plans").order_by("version", direction=firestore.Query.DESCENDING).limit(1)
        version = 1
        async for snap in latest.stream(transaction=tx):
            version = int(snap.get("version")) + 1
        tx.set(
            plan_ref,
            {"version": version, "plan": plan.model_dump(mode="json"), "reason": reason, "createdAt": now()},
        )
        tx.set(
            trip_ref,
            {
                "currentPlanId": plan_ref.id,
                "status": "ready",
                "progress": "done",
                "updatedAt": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )

    await write(db().transaction())
    return plan_ref.id


def _cache(name: str, key: str) -> firestore.AsyncDocumentReference:
    if name not in CACHE_NAMES:
        raise ValueError(f"unknown cache {name!r}; use one of {sorted(CACHE_NAMES)}")
    return db().collection(f"cache_{name}").document(key)


async def cache_get(name: str, key: str) -> dict | None:
    """Cached document (with fetchedAt), or None. The caller decides if it is too old."""
    snap = await _cache(name, key).get()
    return snap.to_dict() if snap.exists else None


async def cache_set(name: str, key: str, data: dict[str, Any]) -> None:
    await _cache(name, key).set({**data, "fetchedAt": firestore.SERVER_TIMESTAMP})
