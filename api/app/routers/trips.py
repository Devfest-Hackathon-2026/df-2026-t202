"""Trip, chat and sharing endpoints.

Writes that read-then-change the trip run in a Firestore transaction, so double taps and two tabs can't
overwrite each other. Gemini and Places calls happen before the transaction (it must stay short).
"""

import json
import logging
import secrets
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status
from google.cloud import firestore
from google.cloud.firestore_v1.field_path import FieldPath

from app import flow
from app.agents import concierge
from app.auth import ID_PATTERN, CurrentAccount, User, require_owner
from app.config import get_settings
from app.models import Budget, ConciergeOutput, CreateTripIn, MessageIn, PlaceRef, Slots
from app.services.firestore import add_message, db, now
from app.services.limits import check_message_limit, check_trip_limit, reserve_messages
from app.services.llm import LLMError

router = APIRouter()
log = logging.getLogger(__name__)

MAX_TEXT_LENGTH = 1000
MAX_AI_TEXT_LENGTH = 500  # cap on Gemini comment/clarify before storing
MAX_PENDING_EDITS = 10  # plan requests kept for the next update (D27)
MAX_PENDING_EDIT_LENGTH = 300

TripId = Annotated[str, Path(pattern=ID_PATTERN)]
ShareId = Annotated[str, Path(pattern=ID_PATTERN)]


def _new_slots(currency: str | None) -> Slots:
    if not currency:
        return Slots()
    return Slots(currency=currency, budget=Budget(currency=currency))


@router.post("/trips")
async def create_trip(body: CreateTripIn, account: CurrentAccount) -> dict:
    await check_trip_limit(account)  # 429 trip_limit_reached (10 a day, 3 for guests)
    uid = account.uid
    ref = db().collection("trips").document()
    await ref.set(
        {
            "ownerUid": uid,
            "members": {uid: "owner"},
            "language": body.language,
            # The currency from the user's settings is fixed for the whole trip (budget and costs).
            "slots": _new_slots(body.currency).model_dump(mode="json"),
            "asking": "dest",
            "status": "chatting",
            "progress": None,
            "currentPlanId": None,
            "shareId": None,
            "messageCount": 1,  # every message written counts, including this first question
            "createdAt": now(),
            "updatedAt": firestore.SERVER_TIMESTAMP,
        }
    )
    card = flow.card_for("dest", Slots())
    await add_message(ref.id, "ai", flow.question_for("dest", body.language), ui=card.model_dump(mode="json"))
    return {"tripId": ref.id}


@router.post("/trips/{trip_id}/messages")
async def post_message(trip_id: TripId, body: MessageIn, uid: User) -> dict:
    trip = await require_owner(trip_id, uid)
    if trip.get("status") == "planning":
        raise HTTPException(status.HTTP_409_CONFLICT, "planning_in_progress")

    if body.type == "answer":
        if body.step is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "step_required")
        return await _handle_answer(trip_id, trip, body.step, body.value)

    text = (body.text or "").strip()
    if not text or len(text) > MAX_TEXT_LENGTH:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "text_invalid")
    return await _handle_text(trip_id, trip, text)


async def _handle_answer(trip_id: str, trip: dict, step: str, value) -> dict:
    # Cheap checks first: a rejected answer must not cost a Places lookup. The transaction checks again.
    if not flow.can_answer(Slots.model_validate(trip["slots"]), trip["asking"], step):
        raise HTTPException(status.HTTP_409_CONFLICT, "step_not_asked")
    check_message_limit(trip)

    trip_ref = db().collection("trips").document(trip_id)
    value = await _resolve_place(step, value, trip.get("language", "en"))

    @firestore.async_transactional
    async def apply(tx: firestore.AsyncTransaction) -> str:
        snap = await trip_ref.get(transaction=tx)
        trip = snap.to_dict()
        slots = Slots.model_validate(trip["slots"])
        lang, asking = trip["language"], trip["asking"]

        if trip.get("status") == "planning":
            raise HTTPException(status.HTTP_409_CONFLICT, "planning_in_progress")
        if not flow.can_answer(slots, asking, step):
            raise HTTPException(status.HTTP_409_CONFLICT, "step_not_asked")
        try:
            new_slots = flow.apply_answer(slots, step, value)
        except flow.AnswerError as e:
            log.info(json.dumps({"msg": "invalid_answer", "tripId": trip_id, "step": step, "err": str(e)[:300]}))
            raise HTTPException(status.HTTP_400_BAD_REQUEST, e.code) from None  # e.g. trip_too_long
        if new_slots == slots and step != asking:
            return asking  # a repeated tap of an earlier answer: nothing changed, no new messages

        check_message_limit(trip)
        user_text = flow.answer_text(step, value, new_slots, lang)
        stored = "skip" if value == "skip" else flow.answer_value(step, new_slots)  # normalized, not the raw input
        answer = {"step": step, "value": stored}
        _write_turn(tx, trip_ref, trip, new_slots, user_text, answer, comment=None, count_messages=True)
        return flow.next_step(new_slots)

    return {"asking": await apply(db().transaction())}


async def _resolve_place(step: str, value, lang: str):
    """Card answers carry a label; the server always looks the place up, so the trip gets the real place id,
    coordinates and country (the country picks the currency, flow._sync_currency). Place ids or coordinates sent
    by the client are ignored. A destination that doesn't exist is a 400; if Places is down, the label is kept
    (the plan pipeline resolves places again anyway)."""
    if step == "transport":
        return await _resolve_start(value, lang)
    if step != "dest" or not isinstance(value, dict):
        return value
    label = str(value.get("label") or "").strip()
    if not label:
        return value
    try:
        place = await flow.search_place(label, lang)
    except flow.PlaceLookupError:
        return {"label": label}
    if place is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "place_not_found")
    return place.model_dump(mode="json")


async def _resolve_start(value, lang: str):
    """The transport card's start point. A specific place (airport, station, hotel) becomes the origin;
    an area (city, state), an unknown place or "not decided" leaves it empty, so Day 1 starts at the first
    attraction."""
    if not isinstance(value, dict) or not isinstance(value.get("origin"), dict):
        return value
    label = str(value["origin"].get("label") or "").strip()
    if not label:
        return {**value, "origin": None}
    try:
        origin = await flow.search_start(label, lang)
    except flow.PlaceLookupError:
        origin = None  # can't tell what it is: don't pin Day 1 to it
    return {**value, "origin": origin.model_dump(mode="json") if origin else None}


async def _handle_text(trip_id: str, trip: dict, text: str) -> dict:
    lang = trip["language"]
    slots = Slots.model_validate(trip["slots"])
    step = trip["asking"]

    await reserve_messages(trip_id)  # before Gemini, so parallel requests can't pass the limit

    # Slow work first, outside the transaction.
    out: ConciergeOutput | None = None
    if not any(ch.isalnum() for ch in text):
        # Only symbols or emoji: nothing to extract, so no Gemini call. The fallback shows the card again.
        log.info(json.dumps({"msg": "concierge_skipped", "tripId": trip_id, "reason": "no_letters"}))
    else:
        try:
            out = await concierge.run(slots, step, text, lang)
        except LLMError as e:
            log.warning(json.dumps({"msg": "concierge_failed", "tripId": trip_id, "err": str(e)[:200]}))

    dest: PlaceRef | None = None
    origin: PlaceRef | None = None
    clarify = out.clarify[:MAX_AI_TEXT_LENGTH] if out and out.clarify else None
    comment = out.comment[:MAX_AI_TEXT_LENGTH] or None if out else None
    try:
        if out and out.updates.dest:
            dest = await flow.search_place(out.updates.dest, lang)
            if dest is None:
                # Gemini's comment may claim the change ("Hokkaido it is!"): show only the ask-back.
                _log_place_ignored(trip_id, "dest")
                comment, clarify = None, flow.text_for("place_not_found", lang)
        if out and out.updates.origin:
            # Only a specific place (airport, station, hotel) is a start point; an area is ignored.
            origin = await flow.search_start(out.updates.origin, lang)
            if origin is None:
                _log_place_ignored(trip_id, "origin")
    except flow.PlaceLookupError:
        # Places is down: keep the other updates, ask again for the place (no 500).
        dest = origin = None
        comment, clarify = None, flow.text_for("place_lookup_failed", lang)

    trip_ref = db().collection("trips").document(trip_id)

    @firestore.async_transactional
    async def apply(tx: firestore.AsyncTransaction) -> str:
        snap = await trip_ref.get(transaction=tx)
        current = snap.to_dict()
        if current.get("status") == "planning":
            raise HTTPException(status.HTTP_409_CONFLICT, "planning_in_progress")
        current_slots = Slots.model_validate(current["slots"])
        if out is None:
            # Gemini failed: friendly message + the same card again.
            _write_turn(
                tx,
                trip_ref,
                current,
                current_slots,
                text,
                None,
                comment=flow.text_for("fallback", lang),
                repeat_card=True,
            )
            return current["asking"]
        new_slots = flow.merge_updates(current_slots, out.updates, dest=dest, origin=origin)
        pending = None
        request = (out.planRequest or "").strip()[:MAX_PENDING_EDIT_LENGTH]
        if request and current.get("currentPlanId"):  # before the first plan, the Planner reads the chat anyway
            pending = [*(current.get("pendingEdits") or []), request][-MAX_PENDING_EDITS:]
        return _write_turn(
            tx,
            trip_ref,
            current,
            new_slots,
            text,
            None,
            comment=comment,
            clarify=clarify,
            edit=out.edit,
            pending_edits=pending,
        )

    return {"asking": await apply(db().transaction())}


def _log_place_ignored(trip_id: str, step: str) -> None:
    log.info(json.dumps({"msg": "concierge_value_ignored", "tripId": trip_id, "step": step, "err": "place_not_found"}))


def _write_turn(
    tx: firestore.AsyncTransaction,
    trip_ref,
    trip: dict,
    new_slots: Slots,
    user_text: str,
    answer: dict | None,
    *,
    comment: str | None,
    clarify: str | None = None,
    repeat_card: bool = False,
    count_messages: bool = False,
    edit: str | None = None,
    pending_edits: list[str] | None = None,
) -> str:
    """Write the user message, the AI reply (with its card) and the new slots, in one transaction.
    Returns the step now asked.

    `count_messages`: add the 2 messages to `messageCount` (the text path reserved them earlier instead).
    `edit`: the user wants to change this condition but gave no value: ask its card again, even if it is done.
    `pending_edits`: the new trips.pendingEdits (plan requests for the next update, D27)."""
    lang = trip["language"]
    if edit and not (clarify or repeat_card):
        asking = edit
        card_slots = new_slots
        question = flow.question_for(edit, lang)
        reply = f"{comment}\n{question}" if comment else question
    elif clarify or repeat_card:
        asking = trip["asking"]  # ask the same question again
        card_slots = Slots.model_validate(trip["slots"]) if repeat_card else new_slots
        if clarify:
            reply = f"{comment}\n{clarify}" if comment else clarify
        else:
            reply = comment or flow.text_for("fallback", lang)
    else:
        asking = flow.next_step(new_slots)
        card_slots = new_slots
        if asking == flow.READY and trip.get("currentPlanId"):
            question = flow.text_for("rebuild", lang)  # plan exists: keep it, offer to rebuild
        else:
            question = flow.question_for(asking, lang)
        reply = f"{comment}\n{question}" if comment else question

    card = flow.card_for(asking, card_slots)
    messages = trip_ref.collection("messages")
    tx.set(messages.document(), {"role": "user", "text": user_text, "answer": answer, "ui": None, "createdAt": now()})
    tx.set(
        messages.document(),
        {"role": "ai", "text": reply, "answer": None, "ui": card.model_dump(mode="json"), "createdAt": now()},
    )
    update = {"slots": new_slots.model_dump(mode="json"), "asking": asking, "updatedAt": firestore.SERVER_TIMESTAMP}
    if count_messages:
        update["messageCount"] = firestore.Increment(2)
    if pending_edits is not None:
        update["pendingEdits"] = pending_edits
    tx.update(trip_ref, update)
    return asking


@router.post("/trips/{trip_id}/share")
async def share_trip(trip_id: TripId, uid: User) -> dict:
    await require_owner(trip_id, uid)
    trip_ref = db().collection("trips").document(trip_id)

    @firestore.async_transactional
    async def create(tx: firestore.AsyncTransaction) -> str:
        trip = (await trip_ref.get(transaction=tx)).to_dict()
        share_id = trip.get("shareId")
        if share_id:
            share = await db().collection("shares").document(share_id).get(transaction=tx)
            if share.exists and share.get("active"):
                return share_id
        share_id = secrets.token_urlsafe(16)  # 22 characters, not guessable
        tx.set(
            db().collection("shares").document(share_id),
            {"tripId": trip_id, "mode": "view", "active": True, "createdAt": now()},
        )
        tx.update(trip_ref, {"shareId": share_id, "updatedAt": firestore.SERVER_TIMESTAMP})
        return share_id

    return {"shareId": await create(db().transaction())}


@router.post("/shares/{share_id}/join")
async def join_share(share_id: ShareId, uid: User) -> dict:
    """Anonymous users too. Adds the caller as a viewer; never downgrades an owner.
    403 share_full once the trip has max_members_per_trip members (keeps the trip doc small)."""
    share_ref = db().collection("shares").document(share_id)

    @firestore.async_transactional
    async def join(tx: firestore.AsyncTransaction) -> str:
        share = await share_ref.get(transaction=tx)
        if not share.exists or not share.get("active"):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "share_not_found")
        trip_id = share.get("tripId")
        trip_ref = db().collection("trips").document(trip_id)
        trip = await trip_ref.get(transaction=tx)
        if not trip.exists:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "trip_not_found")
        members = trip.get("members") or {}
        if uid not in members:
            if len(members) >= get_settings().max_members_per_trip:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "share_full")
            tx.update(trip_ref, {FieldPath("members", uid).to_api_repr(): "viewer"})
        return trip_id

    return {"tripId": await join(db().transaction())}
