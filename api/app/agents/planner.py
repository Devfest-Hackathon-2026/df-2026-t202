"""Planner agent. PLAN.md 9.2 / 9.3 step 2.

slots + full chat -> draft Plan with Gemini (GEMINI_MODEL_PLANNER) and prompts/planner.md. No grounding tools and the
model's default thinking level for the draft: plan quality over speed. Repair
rounds only edit a few stops: LOW thinking, a shorter timeout, and the model returns only the days it changed
(`PlanFix`, D6), because writing out the whole plan again was most of a repair's ~30 s.
Outputs are validated by llm.generate_json (one retry on invalid JSON, then llm.LLMError).
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from functools import cache
from pathlib import Path

from app.flow import MAX_TRIP_DAYS, currency_for
from app.models import Day, Plan, PlanFix, PlanUpdate, Slots, Stop
from app.services import llm

PROMPT_FILE = Path(__file__).parent.parent / "prompts" / "planner.md"
LANGUAGE_NAMES = {"en": "English", "ja": "Japanese"}
TIMEOUT_SECONDS = 130  # per attempt; a 4-day draft takes ~30 s, a 20-day one 78 s (D22). 2nd try only on bad JSON
FIX_TIMEOUT_SECONDS = 45  # per attempt, LOW thinking
REVISE_TIMEOUT_SECONDS = 60  # per attempt, LOW thinking (D27)
MAX_CHAT_MESSAGES = 60  # the per-trip message limit

FIX_TASK = (
    "Revise the days in `plan` so they solve the problems in `warnings`. Change as little as possible: same must-visit "
    "places, same stop ids for stops that stay, and keep the rules for times, meals, pace and legs. A stop that is "
    "closed on arrival moves to a time inside its opening hours (given in the warning) or is swapped for a nearby "
    "place that is open then. A place that couldn't be found is replaced with a real place that fits the same time "
    "and purpose. "
    "Reply with only the days you changed: for each, its `day` number and its complete new list of `stops` in order, "
    "re-timed, unchanged stops included as they are. Leave out days you didn't change."
)
# What the repair call needs to see: the days and stops, without Routes polylines, videos or our warnings.
FIX_INPUT = {
    "days": {"__all__": {"stops": {"__all__": {"placeId": True, "videoIds": True, "warn": True, "leg": {"polyline"}}}}}
}

REVISE_TASK = (
    "The user changed their trip after this plan was made. Update `plan` for the conditions in `changes` and the "
    "user's `requests`. The new conditions are in `slots`; the plan must have exactly `days` days (dates in `dates`). "
    "Change as little as possible: keep every stop that still fits, with exactly the same name, and keep the rules "
    "for times, meals, pace and legs. "
    "Reply with only the days you changed: for each, its `day` number and its complete new list of `stops` in order, "
    "re-timed, unchanged stops included as they are. Leave out days you didn't change. When the number of days "
    "changes, reply with every day. Reply with a new `cost` only if the travellers, budget or number of days changed, "
    "and with new `checks` only if they need to change."
)
CHANGE_LABELS = {
    "dates": "Dates",
    "nights": "Nights",
    "people": "Travellers",
    "budget": "Budget",
    "transport": "Transport",
    "origin": "Start point",
    "prefs": "Interests",
    "musts": "Must-sees",
}


@cache
def _base_prompt() -> str:
    return PROMPT_FILE.read_text(encoding="utf-8")


def system_prompt(lang: str) -> str:
    return f"{_base_prompt()}\nWrite all user-facing text in {LANGUAGE_NAMES.get(lang, 'English')}."


def trip_days(slots: Slots) -> int:
    """Number of days to plan: from the dates, else nights + 1, else 2 (a 1-night trip when nothing is decided).
    Never more than MAX_TRIP_DAYS (flow.py rejects longer trips; this also covers trips saved before that)."""
    if slots.dates:
        span = (date.fromisoformat(slots.dates.end) - date.fromisoformat(slots.dates.start)).days
        return min(MAX_TRIP_DAYS, max(1, span + 1))
    if slots.nights is not None:
        return min(MAX_TRIP_DAYS, max(1, slots.nights + 1))
    return 2


def trip_currency(slots: Slots) -> str:
    """The plan's currency comes from the trip, never from the model: the web formats it with Intl.NumberFormat,
    which throws on codes that aren't 3 letters ("円")."""
    if slots.currency:
        return slots.currency
    if slots.budget:
        return slots.budget.currency
    return currency_for(slots.dest.countryCode if slots.dest else None)


def _chat(messages: list[dict]) -> list[dict]:
    """Only who said what. Card answers are already in the slots."""
    lines = [{"role": m.get("role"), "text": m.get("text")} for m in messages if m.get("text")]
    return lines[-MAX_CHAT_MESSAGES:]


def _range(item) -> None:
    """A cost is always a range: swap a reversed one, widen a single price by about 10%."""
    if item.min > item.max:
        item.min, item.max = item.max, item.min
    if item.min == item.max and item.max > 0:
        item.min, item.max = round(item.max * 0.9), round(item.max * 1.1)


def _clean(plan: Plan, lang: str) -> Plan:
    """Rules we enforce in code instead of trusting the model."""
    plan.language = lang
    if plan.cost:
        for item in [plan.cost, *plan.cost.items]:
            _range(item)
    for day in plan.days:
        _clean_day(day)
    return plan


def _clean_day(day: Day) -> None:
    """Fields the pipeline fills: never trust the model's values."""
    for i, stop in enumerate(day.stops):
        stop.placeId = None  # filled from Places by the pipeline; lat/lng stay as a rough guess (D8)
        stop.videoIds = []
        stop.warn = None
        if stop.leg:
            stop.leg.polyline = None  # filled from Routes by the pipeline
            stop.leg.estimate = stop.leg.estimate or stop.leg.mode in ("FLIGHT", "FERRY")
        if i == len(day.stops) - 1:
            stop.leg = None  # the last stop of a day goes nowhere


async def draft(slots: Slots, messages: list[dict], lang: str) -> Plan:
    """Return a draft Plan from the collected slots and the chat history. Raises llm.LLMError."""
    user = json.dumps(
        {
            "slots": slots.model_dump(mode="json"),
            "days": trip_days(slots),
            "dates": slots.dates.model_dump() if slots.dates else None,
            "chat": _chat(messages),
        },
        ensure_ascii=False,
    )
    plan = await llm.generate_json(llm.MODEL_PLANNER, system_prompt(lang), user, Plan, timeout=TIMEOUT_SECONDS)
    plan.currency = trip_currency(slots)
    return _clean(plan, lang)


async def fix(plan: Plan, warnings: list[str], lang: str) -> Plan:
    """One repair round: return a copy of `plan` with the days the Planner changed. Raises llm.LLMError."""
    user = json.dumps(
        {
            "task": FIX_TASK,
            "plan": plan.model_dump(mode="json", include={"days"}, exclude=FIX_INPUT),
            "warnings": warnings,
        },
        ensure_ascii=False,
    )
    out = await llm.generate_json(
        llm.MODEL_PLANNER, system_prompt(lang), user, PlanFix, thinking="LOW", timeout=FIX_TIMEOUT_SECONDS
    )
    return merge(plan, out)


def merge(plan: Plan, out: PlanFix) -> Plan:
    """Swap in the changed days. Unknown day numbers and empty days are ignored (a repair never deletes a day)."""
    revised = plan.model_copy(deep=True)
    days = {day.day: day for day in revised.days}
    for changed in out.days:
        day = days.get(changed.day)
        if day and changed.stops:
            day.stops = changed.stops
            for i, stop in enumerate(day.stops, 1):
                stop.id = f"s-{day.day}{i:02d}"  # unique: the pipeline keys opening hours and types by stop id
            _clean_day(day)
    return revised


def changes(old: Slots, new: Slots) -> list[str]:
    """What changed between the plan's snapshot and the current conditions, as short lines for the Planner (D27)."""
    lines = []
    for key, label in CHANGE_LABELS.items():
        a, b = getattr(old, key), getattr(new, key)
        if a == b:
            continue
        if key in ("prefs", "musts"):
            added, removed = [x for x in b if x not in a], [x for x in a if x not in b]
            if added:
                lines.append(f"{label} added: {', '.join(added)}")
            if removed:
                lines.append(f"{label} removed: {', '.join(removed)}")
        else:
            lines.append(f"{label}: {_show(a)} -> {_show(b)}")
    return lines


def _show(value) -> str:
    if value is None or value == []:
        return "not set"
    if hasattr(value, "label"):
        return value.label
    if hasattr(value, "model_dump"):
        return json.dumps(value.model_dump(mode="json", exclude_none=True), ensure_ascii=False)
    return ", ".join(value) if isinstance(value, list) else str(value)


def day_dates(slots: Slots) -> list[str | None]:
    """The date of each plan day, or None when only the number of nights is known."""
    n = trip_days(slots)
    if not slots.dates:
        return [None] * n
    start = date.fromisoformat(slots.dates.start)
    return [(start + timedelta(days=i)).isoformat() for i in range(n)]


async def revise(plan: Plan, change_lines: list[str], requests: list[str], slots: Slots, lang: str) -> PlanUpdate:
    """Ask the Planner for only the days that must change (D27). Raises llm.LLMError."""
    user = json.dumps(
        {
            "task": REVISE_TASK,
            "plan": plan.model_dump(mode="json", include={"days", "cost", "checks"}, exclude=FIX_INPUT),
            "changes": change_lines,
            "requests": requests,
            "days": trip_days(slots),
            "dates": slots.dates.model_dump() if slots.dates else None,
            "slots": slots.model_dump(mode="json"),
        },
        ensure_ascii=False,
    )
    return await llm.generate_json(
        llm.MODEL_PLANNER, system_prompt(lang), user, PlanUpdate, thinking="LOW", timeout=REVISE_TIMEOUT_SECONDS
    )


def apply_update(old: Plan, out: PlanUpdate, slots: Slots, lang: str) -> tuple[Plan, set[int]] | None:
    """Merge the Planner's update into a copy of `old`. Returns the new plan and the day numbers whose stops changed,
    or None when the result has a gap (a day the Planner didn't return): then the caller rebuilds the whole plan.

    Changed days are cleaned like a draft, then stops whose name matches a stop of the old plan get back its
    verified place (placeId, coordinates, local name, videos), so the pipeline doesn't search for it again."""
    dates = day_dates(slots)
    n = len(dates)
    new = old.model_copy(deep=True)
    days = {day.day: day for day in new.days if 1 <= day.day <= n}
    changed: set[int] = set()
    for fix in out.days:
        if 1 <= fix.day <= n and fix.stops:
            day = days.get(fix.day) or Day(day=fix.day, stops=[])
            day.stops = fix.stops
            _clean_day(day)
            days[fix.day] = day
            changed.add(fix.day)
    if sorted(days) != list(range(1, n + 1)):
        return None
    new.days = [days[i] for i in range(1, n + 1)]
    known: dict[tuple[int, str], Stop] = {}  # (day, name) -> verified stop; day 0 = any day
    for day in old.days:
        for stop in day.stops:
            for name in filter(None, (stop.name, stop.nameLocal)):
                if stop.placeId:
                    known.setdefault((day.day, name), stop)
                    known.setdefault((0, name), stop)
    for day, when in zip(new.days, dates, strict=True):
        day.date = when
        for i, stop in enumerate(day.stops, 1):
            stop.id = f"s-{day.day}{i:02d}"  # unique: the pipeline keys opening hours and types by stop id
            keys = [(d, n) for d in (day.day, 0) for n in filter(None, (stop.name, stop.nameLocal))]
            was = next((known[k] for k in keys if k in known), None)
            if day.day in changed and was:
                stop.name, stop.nameLocal, stop.placeId = was.name, was.nameLocal, was.placeId
                stop.lat, stop.lng, stop.videoIds = was.lat, was.lng, list(was.videoIds)
    if out.cost:
        new.cost = out.cost
    if out.checks is not None:
        new.checks = out.checks
    new.currency = trip_currency(slots)
    return _clean_costs(new, lang), changed


def _clean_costs(plan: Plan, lang: str) -> Plan:
    plan.language = lang
    if plan.cost:
        for item in [plan.cost, *plan.cost.items]:
            _range(item)
    return plan
