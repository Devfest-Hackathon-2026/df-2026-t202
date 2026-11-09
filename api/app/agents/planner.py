"""Planner agent. PLAN.md 9.2 / 9.3 step 2.

slots + full chat -> draft Plan with Gemini (GEMINI_MODEL_PLANNER) and prompts/planner.md. No grounding tools and the
model's default thinking level for the draft: plan quality over speed (docs/decisions.md P16–P18). Repair
rounds only edit a few stops: LOW thinking, a shorter timeout, and the model returns only the days it changed
(`PlanFix`, D83), because writing out the whole plan again was most of a repair's ~30 s.
Outputs are validated by llm.generate_json (one retry on invalid JSON, then llm.LLMError).
"""

from __future__ import annotations

import json
from datetime import date
from functools import cache
from pathlib import Path

from app.models import Day, Plan, PlanFix, Slots
from app.services import llm

PROMPT_FILE = Path(__file__).parent.parent / "prompts" / "planner.md"
LANGUAGE_NAMES = {"en": "English", "ja": "Japanese"}
TIMEOUT_SECONDS = 90  # per attempt; a draft takes ~30 s. Two attempts only after invalid JSON
FIX_TIMEOUT_SECONDS = 45  # per attempt, LOW thinking
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


@cache
def _base_prompt() -> str:
    return PROMPT_FILE.read_text(encoding="utf-8")


def system_prompt(lang: str) -> str:
    return f"{_base_prompt()}\nWrite all user-facing text in {LANGUAGE_NAMES.get(lang, 'English')}."


def trip_days(slots: Slots) -> int:
    """Number of days to plan: from the dates, else nights + 1, else 2 (a 1-night trip when nothing is decided)."""
    if slots.dates:
        span = (date.fromisoformat(slots.dates.end) - date.fromisoformat(slots.dates.start)).days
        return max(1, span + 1)
    if slots.nights is not None:
        return max(1, slots.nights + 1)
    return 2


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
        stop.placeId = None  # filled from Places by the pipeline; lat/lng stay as a rough guess (D50)
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
