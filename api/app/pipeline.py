"""Plan pipeline (Person B). BACKEND_PERSON_B.md T4, PLAN.md 9.3. Progress goes to the trip doc (no SSE).

1. claim the trip (status "planning")         2. planner.draft
3. verify stops with Places; missing ones get one Planner replacement round, then are dropped with a note
4. progress "routes": real legs from Routes    5. re-time each day
6. warnings: long driving, closed on arrival   7. >= 3 warnings -> planner.fix once, redo 3-6
8. progress "videos": YouTube Shorts         9. save_plan -> planId
On any error: status "error", then re-raise (the router turns it into an HTTP error).
Plan quality comes before speed (D44); every API call inside a step runs in parallel.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import time
from dataclasses import dataclass, field
from datetime import date, timedelta

from fastapi import HTTPException, status
from google.cloud import firestore as gfs

from app.agents import planner
from app.models import Leg, Plan, Slots, Stop
from app.services import firestore as fs
from app.services import places, routes, youtube

log = logging.getLogger(__name__)

MAX_DRIVE_MINUTES = 300  # per day, then warn (spec T4 step 6)
FIX_AT_WARNINGS = 3  # this many warnings -> one repair round (step 7)
WALK_UNDER_KM = 1.0  # short hops are walks
MAX_FROM_GUESS_KM = 30.0  # a Places match farther than this from the Planner's rough location is wrong (D50)
STALE_PLANNING = timedelta(minutes=10)  # a "planning" status older than this is a crashed run, not a running one
NO_VIDEO_KINDS = {"start", "end", "transport"}  # stations, ports, rental cars: weak videos (D52)
AREA_TYPES = {"country", "administrative_area_level_1", "administrative_area_level_2", "locality", "colloquial_area"}
PLACE_TYPES = {"point_of_interest", "establishment", "tourist_attraction"}  # a real place, even inside a town
TRANSPORT_MODE = {"car": "DRIVE", "train": "TRANSIT", "shinkansen": "TRANSIT", "bus": "TRANSIT"}

# Server-written text in the trip language (person_b_WHY.md: plan text follows trips.language).
TEXT = {
    "en": {
        "drive": "About {h} h {m} min of driving today. Consider fewer stops.",
        "closed": "May be closed when you arrive ({time}). Check the opening hours.",
        "dropped": "{name}: couldn't be found on Google Maps, so it was removed. Please check.",
        "missing": 'Day {day}: "{name}" couldn\'t be found on Google Maps in {country}. '
        "Replace it with a real place that fits the same time and purpose.",
    },
    "ja": {
        "drive": "この日の運転は約{h}時間{m}分です。立ち寄り先を減らすことも検討してください。",
        "closed": "到着時刻（{time}）に営業していない可能性があります。営業時間を確認してください。",
        "dropped": "{name}：Googleマップで見つからなかったため、プランから外しました。確認してください。",
        "missing": "{day}日目：「{name}」は{country}のGoogleマップで見つかりませんでした。"
        "同じ時間帯と目的に合う実在の場所に置き換えてください。",
    },
}


@dataclass
class Run:
    """Per-run state: settings plus memos, so a repair round only calls the APIs for changed stops."""

    lang: str
    near: tuple[float, float] | None
    country: str | None
    default_mode: str
    places: dict[str, dict | None] = field(default_factory=dict)  # query -> Places result
    legs: dict[tuple, dict | None] = field(default_factory=dict)  # (a, b, mode) -> Routes result
    hours: dict[str, dict | None] = field(default_factory=dict)  # stop id -> regularOpeningHours

    def text(self, key: str, **kw) -> str:
        return TEXT.get(self.lang, TEXT["en"])[key].format(**kw)


# ---------- 1. Claim ----------


async def claim(trip_id: str) -> None:
    """Mark the trip as planning, or raise 409 if a run is already in progress (double taps pay only once)."""
    ref = fs.db().collection("trips").document(trip_id)

    @gfs.async_transactional
    async def take(tx) -> bool:
        trip = (await ref.get(transaction=tx)).to_dict() or {}
        updated = trip.get("updatedAt")
        if trip.get("status") == "planning" and updated and fs.now() - updated < STALE_PLANNING:
            return False
        tx.update(ref, {"status": "planning", "progress": "spots", "updatedAt": gfs.SERVER_TIMESTAMP})
        return True

    if not await take(fs.db().transaction()):
        raise HTTPException(status.HTTP_409_CONFLICT, "plan_already_running")


# ---------- 3. Verify stops with Places ----------


async def _find(stop: Stop, run: Run) -> dict | None:
    query = stop.nameLocal or stop.name  # the local name is the most precise search
    guess = (stop.lat, stop.lng) if stop.lat is not None and stop.lng is not None else None
    if query not in run.places:
        run.places[query] = await places.search_text(query, run.lang, near=guess or run.near)
    found = run.places[query]
    if not found:
        return None
    if run.country and found.get("countryCode") and found["countryCode"] != run.country:
        return None  # same name in another country: a wrong match (D49)
    if guess and found.get("lat") is not None and km_between(guess, (found["lat"], found["lng"])) > MAX_FROM_GUESS_KM:
        return None  # same name, wrong town (D50)
    types = set(found.get("types") or [])
    if types & AREA_TYPES and not types & PLACE_TYPES:
        return None  # a whole city or region, not a place to visit (D56)
    return found


async def _verify_stop(stop: Stop, run: Run) -> bool:
    found = await _find(stop, run)
    if not found:
        return False
    stop.placeId, stop.lat, stop.lng = found["placeId"], found["lat"], found["lng"]
    # Official name in the trip language, except: keep Gemini's English name over a local-script one, and keep the
    # start/end names (Google may call the pickup branch "... Car Return") (D55).
    if found["name"] and stop.kind not in ("start", "end") and (run.lang != "en" or found["name"].isascii()):
        stop.name = found["name"]
    run.hours[stop.id] = found.get("openingHours")
    if not stop.nameLocal:
        stop.nameLocal = await places.local_name(found["placeId"], found.get("countryCode") or run.country or "")
    for name in (stop.name, stop.nameLocal):  # a repair round may search by either name: don't pay twice
        if name:
            run.places.setdefault(name, found)
    return True


async def verify(plan: Plan, run: Run) -> list[tuple[int, Stop]]:
    """Fill placeId, lat, lng, official name and nameLocal. Returns the (day, stop) pairs that weren't found."""
    pairs = [(day.day, stop) for day in plan.days for stop in day.stops]
    found = await asyncio.gather(*(_verify_stop(stop, run) for _, stop in pairs))
    return [pair for pair, ok in zip(pairs, found, strict=True) if not ok]


def drop(plan: Plan, missing: list[tuple[int, Stop]], run: Run) -> None:
    gone = {id(stop) for _, stop in missing}
    for day in plan.days:
        day.stops = [s for s in day.stops if id(s) not in gone]
    plan.days = [day for day in plan.days if day.stops]
    plan.checks += [run.text("dropped", name=stop.name) for _, stop in missing]


# ---------- 4. Legs with Routes ----------


def km(a: Stop, b: Stop) -> float:
    return km_between((a.lat, a.lng), (b.lat, b.lng))


def km_between(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Straight-line distance (haversine)."""
    lat1, lng1, lat2, lng2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


async def _leg(a: Stop, b: Stop, run: Run) -> None:
    leg = a.leg or Leg(mode=run.default_mode, minutes=30, estimate=True)  # a dropped stop can leave a gap
    if leg.mode in ("FLIGHT", "FERRY"):
        a.leg = leg.model_copy(update={"estimate": True, "polyline": None})
        return
    mode = "WALK" if km(a, b) < WALK_UNDER_KM else leg.mode
    key = (a.lat, a.lng, b.lat, b.lng, mode)
    if key not in run.legs:
        run.legs[key] = await routes.leg((a.lat, a.lng), (b.lat, b.lng), mode, run.lang)
    real = run.legs[key]
    if real:
        a.leg = Leg(mode=mode, minutes=real["minutes"], polyline=real["polyline"], estimate=False)
    else:
        a.leg = Leg(mode=mode, minutes=leg.minutes, polyline=None, estimate=True)  # keep the Planner's guess (D38)


async def add_legs(plan: Plan, run: Run) -> None:
    jobs = []
    for day in plan.days:
        day.stops[-1].leg = None
        jobs += [_leg(a, b, run) for a, b in zip(day.stops, day.stops[1:], strict=False)]
    await asyncio.gather(*jobs)


# ---------- 5. Re-time ----------


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _hhmm(minutes: int) -> str:
    minutes = min(minutes, 23 * 60 + 55)  # stay on the same day
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def retime(plan: Plan) -> None:
    """Keep each day's first time; next = previous + stay + travel, rounded up to 5 minutes.

    A night view never moves earlier than the Planner's time (Gemini schedules it after sunset): when we'd arrive
    early, the stop before gets the extra time (D54).
    """
    for day in plan.days:
        t = _minutes(day.stops[0].time)
        for a, b in zip(day.stops, day.stops[1:], strict=False):
            t = math.ceil((t + a.stayMinutes + (a.leg.minutes if a.leg else 0)) / 5) * 5
            planned = _minutes(b.time)
            if b.kind == "night_view" and planned > t:
                a.stayMinutes += planned - t
                t = planned
            b.time = _hhmm(t)


# ---------- 6. Warnings ----------


def is_open(hours: dict | None, day: date, hhmm: str) -> bool | None:
    """Is the place open at that local time? None when we don't know (no hours or no date)."""
    periods = (hours or {}).get("periods")
    if not periods:
        return None
    week = 7 * 24 * 60
    at = ((day.weekday() + 1) % 7) * 1440 + _minutes(hhmm)  # Google counts days from Sunday = 0
    for p in periods:
        if "close" not in p:
            return True  # open 24 hours
        start = p["open"]["day"] * 1440 + p["open"].get("hour", 0) * 60 + p["open"].get("minute", 0)
        end = p["close"]["day"] * 1440 + p["close"].get("hour", 0) * 60 + p["close"].get("minute", 0)
        if end <= start:
            end += week  # closes after midnight on Saturday -> Sunday
        if start <= at < end or start <= at + week < end:
            return True
    return False


def add_warnings(plan: Plan, run: Run) -> list[str]:
    """Set stop.warn and return the warnings (with day and place, for the Planner's repair round)."""
    found = []
    for day in plan.days:
        for stop in day.stops:
            stop.warn = None
        drive = sum(s.leg.minutes for s in day.stops if s.leg and s.leg.mode == "DRIVE")
        if drive > MAX_DRIVE_MINUTES:
            day.stops[0].warn = run.text("drive", h=drive // 60, m=drive % 60)
            found.append(f"Day {day.day}: {day.stops[0].warn}")
        if not day.date:
            continue
        for stop in day.stops:
            if is_open(run.hours.get(stop.id), date.fromisoformat(day.date), stop.time) is False:
                stop.warn = run.text("closed", time=stop.time)
                found.append(f"Day {day.day}, {stop.name}: {stop.warn}")
    return found


# ---------- 8. Videos ----------


async def add_videos(plan: Plan, run: Run) -> None:
    """Up to 3 Shorts per stop with a placeId, except start/end/transport stops. Cached for 7 days."""
    stops = [s for day in plan.days for s in day.stops if s.placeId and s.kind not in NO_VIDEO_KINDS]
    found = await asyncio.gather(
        *(youtube.shorts_for(s.placeId, s.nameLocal or s.name, run.country or "") for s in stops)
    )
    for stop, ids in zip(stops, found, strict=True):
        stop.videoIds = ids


# ---------- The whole run ----------


async def _check(plan: Plan, run: Run, trip_id: str) -> list[str]:
    """Steps 4-6. Returns the warnings."""
    await fs.update_trip(trip_id, {"progress": "routes"})
    await add_legs(plan, run)
    retime(plan)
    return add_warnings(plan, run)


async def run(trip_id: str) -> str:
    """Run the pipeline for a claimed trip and return the saved planId. Sets status "error" on failure."""
    started, stage = time.perf_counter(), {}
    try:
        trip = await fs.get_trip(trip_id) or {}
        lang = trip.get("language", "en")
        slots = Slots.model_validate(trip.get("slots") or {})
        dest = slots.dest
        mode = next((TRANSPORT_MODE[t] for t in slots.transport if t in TRANSPORT_MODE), "DRIVE")
        r = Run(
            lang=lang,
            near=(dest.lat, dest.lng) if dest and dest.lat is not None else None,
            country=dest.countryCode if dest else None,
            default_mode=mode,
        )

        plan = await planner.draft(slots, await fs.list_messages(trip_id), lang)
        stage["draft"] = time.perf_counter() - started

        missing = await verify(plan, r)
        if missing:  # one replacement round, then drop what is still missing (D47)
            asks = [r.text("missing", day=d, name=s.name, country=r.country or "the destination") for d, s in missing]
            plan = await planner.fix(plan, asks, lang)
            drop(plan, await verify(plan, r), r)
        stage["spots"] = time.perf_counter() - started

        warnings = await _check(plan, r, trip_id)
        if len(warnings) >= FIX_AT_WARNINGS:  # one repair round (spec step 7)
            plan = await planner.fix(plan, warnings, lang)
            drop(plan, await verify(plan, r), r)
            await _check(plan, r, trip_id)
        stage["routes"] = time.perf_counter() - started

        await fs.update_trip(trip_id, {"progress": "videos"})
        await add_videos(plan, r)
        stage["videos"] = time.perf_counter() - started

        plan_id = await fs.save_plan(trip_id, plan)
        log.info(
            json.dumps({"msg": "plan_done", "tripId": trip_id, "seconds": {k: round(v, 1) for k, v in stage.items()}})
        )
        return plan_id
    except Exception as e:
        log.warning(json.dumps({"msg": "plan_failed", "tripId": trip_id, "err": type(e).__name__}))
        await fs.update_trip(trip_id, {"status": "error", "progress": None})
        raise
