"""Plan pipeline (Person B). BACKEND_PERSON_B.md T4, PLAN.md 9.3. Progress goes to the trip doc (no SSE).

1. claim the trip (status "planning")         2. planner.draft
3. verify stops with Places                    4. progress "routes": real legs from Routes (found stops only)
5. re-time each day                            6. warnings: long driving, closed on arrival, past midnight
7. any stop not found, >= 3 warnings or any "closed" -> ONE planner.fix with all of them (D83), then redo 3-6 for
   the changed stops; a stop still not found is dropped with a note
8. progress "videos": YouTube Shorts         9. cost check, save_plan -> planId
On any error (or a cancelled request): status "error", then re-raise (the router turns it into an HTTP error).
Plan quality comes before speed (D44); every API call inside a step runs in parallel. Repair rounds only start in the
first FIX_BEFORE_S seconds, so draft + repair + APIs stay under the Cloud Run request timeout (300 s).
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
FIX_AT_WARNINGS = 3  # this many warnings (or one "closed") -> one repair round (step 7)
FIX_BEFORE_S = 140  # no repair round starts later than this: a fix can take 2 x 45 s, then routes and videos
WALK_UNDER_KM = 1.0  # short hops are walks
TRANSIT_WALK_KM = 2.0  # no transit route (Routes has no transit data for Japan): walk if it is this close
MAX_WALK_MINUTES = 30  # a longer walk becomes a ride (a 3-hour "walk" between two towns is not a plan)
DAY_END = 23 * 60 + 55  # re-timed stops stay on the same day
MAX_FROM_GUESS_KM = 30.0  # a Places match farther than this from the Planner's rough location is wrong (D50)
STALE_PLANNING = timedelta(minutes=10)  # a "planning" status older than this is a crashed run, not a running one
YOUTUBE_PARALLEL = 4  # more at once and YouTube answers 429 "too many requests" (D57)
NO_VIDEO_KINDS = {"start", "end", "transport"}  # stations, ports, rental cars: weak videos (D52)
NO_VIDEO_TYPES = {  # Places types with weak Shorts: hotels, stations, rental cars
    "lodging", "hotel", "japanese_inn", "hostel", "resort_hotel", "motel", "bed_and_breakfast", "train_station",
    "transit_station", "subway_station", "bus_station", "light_rail_station", "airport", "ferry_terminal",
    "car_rental", "parking",
}  # fmt: skip
LODGING_TYPES = {"lodging", "hotel", "japanese_inn", "hostel", "resort_hotel", "motel", "bed_and_breakfast"}
NOT_LODGING_KINDS = {"food", "sight", "view", "night_view", "shop"}  # a hotel can't be these stops
VIDEO_PRIORITY = {"sight": 0, "view": 0, "night_view": 0, "onsen": 0, "activity": 1, "food": 1}  # others: 2
MAX_VIDEO_SEARCHES = 30  # stops searched per plan: every stop of a 5-day trip; cached stops are free
AREA_TYPES = {"country", "administrative_area_level_1", "administrative_area_level_2", "locality", "colloquial_area"}
PLACE_TYPES = {"point_of_interest", "establishment", "tourist_attraction"}  # a real place, even inside a town
TRANSPORT_MODE = {"car": "DRIVE", "train": "TRANSIT", "shinkansen": "TRANSIT", "bus": "TRANSIT"}

# Server-written text in the trip language (person_b_WHY.md: plan text follows trips.language).
TEXT = {
    "en": {
        "drive": "About {h} h {m} min of driving today. Consider fewer stops.",
        "closed": "May be closed when you arrive ({time}). Check the opening hours.",
        "late": "This day runs past midnight. Consider fewer stops.",
        "dropped": "{name}: couldn't be found on Google Maps, so it was removed. Please check.",
        "budget": "The estimate ({max:,} {currency}) may exceed your budget ({budget:,} {currency}). Please check.",
        "missing": 'Day {day}: "{name}" couldn\'t be found on Google Maps in {country}. '
        "Replace it with a real place that fits the same time and purpose.",
        "lodging": 'Day {day}: "{name}" is a hotel or ryokan, not a place to eat or visit. '
        "Replace it with a real restaurant or sight that fits the same time and purpose.",
    },
    "ja": {
        "drive": "この日の運転は約{h}時間{m}分です。立ち寄り先を減らすことも検討してください。",
        "closed": "到着時刻（{time}）に営業していない可能性があります。営業時間を確認してください。",
        "late": "この日の予定が深夜0時を過ぎます。立ち寄り先を減らすことも検討してください。",
        "dropped": "{name}：Googleマップで見つからなかったため、プランから外しました。確認してください。",
        "budget": "見積もり（最大{max:,} {currency}）がご予算（{budget:,} {currency}）を"
        "超える可能性があります。確認してください。",
        "missing": "{day}日目：「{name}」は{country}のGoogleマップで見つかりませんでした。"
        "同じ時間帯と目的に合う実在の場所に置き換えてください。",
        "lodging": "{day}日目：「{name}」はホテルか旅館で、食事や観光の立ち寄り先ではありません。"
        "同じ時間帯と目的に合う実在の飲食店や観光地に置き換えてください。",
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
    types: dict[str, set[str]] = field(default_factory=dict)  # stop id -> Places primaryType (or all types)
    lodging: set[str] = field(default_factory=set)  # stop ids rejected because Places says it is a hotel

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
    run.lodging.discard(stop.id)
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
    if stop.kind in NOT_LODGING_KINDS and _main_types(found) & LODGING_TYPES:
        run.lodging.add(stop.id)  # a ryokan as lunch: ask the Planner for a real restaurant
        return None
    return found


def _main_types(found: dict) -> set[str]:
    """What the place mainly is: Google's primary type, else all its types."""
    return {found["primaryType"]} if found.get("primaryType") else set(found.get("types") or [])


def _better_name(ours: str, google: str) -> bool:
    """Use Google's name unless it looks like SEO padding: much longer, or not sharing a distinctive word with ours."""
    return len(google) <= len(ours) * 1.5 + 5 and (places.mentions(google, ours) or places.mentions(ours, google))


async def _verify_stop(stop: Stop, run: Run) -> bool:
    found = await _find(stop, run)
    if not found:
        return False
    stop.placeId, stop.lat, stop.lng = found["placeId"], found["lat"], found["lng"]
    # Official name in the trip language, except: keep Gemini's English name over a local-script one, keep the
    # start/end names (Google may call the pickup branch "... Car Return") (D55), and keep Gemini's name over an
    # SEO-padded one ("Sapporo's Secret Onsen Sanctuary Marukoma Onsen Ryokan").
    google = found["name"]
    if (
        google
        and stop.kind not in ("start", "end")
        and (run.lang != "en" or google.isascii())
        and _better_name(stop.name, google)
    ):
        stop.name = google
    run.hours[stop.id] = found.get("openingHours")
    run.types[stop.id] = _main_types(found)
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
    distance = km(a, b)
    mode = "WALK" if distance < WALK_UNDER_KM else leg.mode
    real = await _route(a, b, mode, run)
    if not real and mode == "TRANSIT" and distance <= TRANSIT_WALK_KM:
        mode = "WALK"  # Routes has no transit data for Japan; a real walk beats a guessed train ride
        real = await _route(a, b, mode, run)
    if real and mode == "WALK" and real["minutes"] > MAX_WALK_MINUTES:
        await _ride_instead(a, b, leg, run)
        return
    line = leg.line if mode == "TRANSIT" else None
    if real:
        a.leg = Leg(mode=mode, minutes=real["minutes"], polyline=real["polyline"], line=real.get("line") or line)
    else:
        a.leg = Leg(mode=mode, minutes=leg.minutes, estimate=True, line=line)  # keep the Planner's guess (D38)


async def _ride_instead(a: Stop, b: Stop, leg: Leg, run: Run) -> None:
    """Too far to walk: ride in the trip's mode. With no transit data (Japan), use the Planner's train time when it
    planned a train (D82), else time the ride by car; either way mark it as an estimate."""
    mode = "DRIVE" if run.default_mode == "WALK" else run.default_mode
    line = leg.line if leg.mode == mode == "TRANSIT" else None
    real = await _route(a, b, mode, run)
    if real:
        a.leg = Leg(mode=mode, minutes=real["minutes"], polyline=real["polyline"], line=real.get("line") or line)
        return
    if leg.mode == mode == "TRANSIT":
        a.leg = Leg(mode=mode, minutes=leg.minutes, estimate=True, line=line)  # the Planner's train guess (D38)
        return
    by_car = await _route(a, b, "DRIVE", run) if mode != "DRIVE" else None
    minutes = by_car["minutes"] + 10 if by_car else 30  # a train or bus is about a car ride plus waiting
    a.leg = Leg(mode=mode, minutes=minutes, estimate=True, line=line)


async def _route(a: Stop, b: Stop, mode: str, run: Run) -> dict | None:
    key = (a.lat, a.lng, b.lat, b.lng, mode)
    if key not in run.legs:
        run.legs[key] = await routes.leg((a.lat, a.lng), (b.lat, b.lng), mode, run.lang)
    return run.legs[key]


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
    minutes = min(minutes, DAY_END)  # stay on the same day; add_warnings flags a day that ends at DAY_END
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _round5(minutes: int) -> int:
    return math.ceil(minutes / 5) * 5


def retime(plan: Plan) -> None:
    """Keep each day's first time; next = previous + stay + travel, rounded up to 5 minutes.

    A night view or a meal never moves earlier than the Planner's time (Gemini schedules night views after sunset and
    meals at meal times): when we'd arrive early, the stop before gets the extra time (D54).
    """
    for day in plan.days:
        t = _round5(_minutes(day.stops[0].time))
        day.stops[0].time = _hhmm(t)
        for a, b in zip(day.stops, day.stops[1:], strict=False):
            t = _round5(t + a.stayMinutes + (a.leg.minutes if a.leg else 0))
            planned = _round5(_minutes(b.time))  # the Planner's own times can be "18:27"
            if b.kind in ("night_view", "food") and planned > t:
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


def _hours_on(hours: dict | None, day: date) -> str:
    """Google's opening-hours line for that weekday ("Monday: 9:00 AM – 5:00 PM"), or "" when unknown."""
    lines = (hours or {}).get("weekdayDescriptions") or []
    return f" Opening hours: {lines[day.weekday()]}" if len(lines) == 7 else ""  # Google lists Monday first


def add_warnings(plan: Plan, run: Run) -> tuple[list[str], int]:
    """Set stop.warn and return the warnings (with day, place and opening hours, for the Planner's repair round)
    and how many of them are "closed on arrival"."""
    found, closed = [], 0
    for day in plan.days:
        for stop in day.stops:
            stop.warn = None
        drive = sum(s.leg.minutes for s in day.stops if s.leg and s.leg.mode == "DRIVE")
        if drive > MAX_DRIVE_MINUTES:
            day.stops[0].warn = run.text("drive", h=drive // 60, m=drive % 60)
            found.append(f"Day {day.day}: {day.stops[0].warn}")
        late = next((s for s in day.stops[1:] if _minutes(s.time) >= DAY_END), None)
        if late:
            late.warn = run.text("late")
            found.append(f"Day {day.day}, {late.name}: {late.warn}")
        if not day.date:
            continue
        on = date.fromisoformat(day.date)
        for stop in day.stops:
            hours = run.hours.get(stop.id)
            if is_open(hours, on, stop.time) is False:
                stop.warn = run.text("closed", time=stop.time)
                found.append(f"Day {day.day}, {stop.name}: {stop.warn}{_hours_on(hours, on)}")
                closed += 1
    return found, closed


# ---------- 8. Videos ----------


async def add_videos(plan: Plan, run: Run, max_searches: int = MAX_VIDEO_SEARCHES) -> None:
    """Up to 3 Shorts per stop with a placeId, except start/end/transport stops and hotels or stations.

    Cached stops always get their videos; at most `max_searches` new searches, sights, views and onsen first.
    """
    stops = [
        s
        for day in plan.days
        for s in day.stops
        if s.placeId and s.kind not in NO_VIDEO_KINDS and not run.types.get(s.id, set()) & NO_VIDEO_TYPES
    ]
    hits = await asyncio.gather(*(youtube.cached(s.placeId) for s in stops))
    for stop, ids in zip(stops, hits, strict=True):
        stop.videoIds = ids or []
    todo = sorted(
        (s for s, ids in zip(stops, hits, strict=True) if ids is None), key=lambda s: VIDEO_PRIORITY.get(s.kind, 2)
    )
    limit = asyncio.Semaphore(YOUTUBE_PARALLEL)

    async def one(stop: Stop) -> None:
        async with limit:
            stop.videoIds = await youtube.shorts_for(
                stop.placeId, stop.nameLocal or stop.name, run.country or "", name=stop.name, lang=run.lang
            )

    await asyncio.gather(*(one(s) for s in todo[:max_searches]))


# ---------- 9. Cost ----------


def check_cost(plan: Plan, slots: Slots, run: Run) -> None:
    """Add a check when the estimate may exceed the budget (same basis and currency) and the Planner didn't say so."""
    budget, cost = slots.budget, plan.cost
    if not budget or not budget.amount or not cost:
        return
    if cost.basis != budget.basis or plan.currency != budget.currency or cost.max <= budget.amount:
        return
    if any("budget" in c.lower() or "予算" in c for c in plan.checks):
        return
    plan.checks.append(run.text("budget", max=cost.max, budget=budget.amount, currency=budget.currency))


# ---------- The whole run ----------


def _without(plan: Plan, missing: list[tuple[int, Stop]]) -> Plan:
    """The plan without the stops Places couldn't find. Shares the Stop objects, so legs and times land on `plan`."""
    gone = {id(stop) for _, stop in missing}
    days = [day.model_copy(update={"stops": [s for s in day.stops if id(s) not in gone]}) for day in plan.days]
    return plan.model_copy(update={"days": [day for day in days if day.stops]})


async def _check(plan: Plan, run: Run) -> tuple[list[str], int]:
    """Steps 4-6. Returns the warnings and how many are "closed on arrival". Routes calls are memoized in `run`."""
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
        stage["spots"] = time.perf_counter() - started

        # One repair round for everything at once (D83): unfound stops, and the warnings of the plan without them.
        await fs.update_trip(trip_id, {"progress": "routes"})
        warnings, closed = await _check(_without(plan, missing), r)
        if (missing or len(warnings) >= FIX_AT_WARNINGS or closed) and time.perf_counter() - started < FIX_BEFORE_S:
            plan = await planner.fix(plan, [*(_ask(d, s, r) for d, s in missing), *warnings], lang)
            missing = await verify(plan, r)
            stage["fix"] = time.perf_counter() - started
        drop(plan, missing, r)
        await _check(plan, r)  # only legs between changed stops call Routes again
        stage["routes"] = time.perf_counter() - started

        await fs.update_trip(trip_id, {"progress": "videos"})
        await add_videos(plan, r)
        stage["videos"] = time.perf_counter() - started

        check_cost(plan, slots, r)
        plan_id = await fs.save_plan(trip_id, plan)
        log.info(
            json.dumps({"msg": "plan_done", "tripId": trip_id, "seconds": {k: round(v, 1) for k, v in stage.items()}})
        )
        return plan_id
    except (Exception, asyncio.CancelledError) as e:  # a cancelled request must not leave the trip "planning"
        log.warning(json.dumps({"msg": "plan_failed", "tripId": trip_id, "err": type(e).__name__}))
        try:
            await fs.update_trip(trip_id, {"status": "error", "progress": None})
        except Exception:  # keep the original error
            log.warning(json.dumps({"msg": "plan_status_reset_failed", "tripId": trip_id}))
        raise


def _ask(day: int, stop: Stop, run: Run) -> str:
    if stop.id in run.lodging:
        return run.text("lodging", day=day, name=stop.name)
    return run.text("missing", day=day, name=stop.name, country=run.country or "the destination")
