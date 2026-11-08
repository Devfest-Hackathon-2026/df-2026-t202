"""Planner agent with Gemini faked (no network, no cost)."""

import asyncio
import json
from pathlib import Path

from app.agents import planner
from app.models import Plan, Slots
from app.services import llm

ROOT = Path(__file__).parents[1]
SLOTS = Slots.model_validate_json((ROOT / "tests/fixtures/demo_slots.json").read_text(encoding="utf-8"))
PLAN_JSON = (ROOT / "app/fixtures/demo_plan.json").read_text(encoding="utf-8")


def fake_gemini(monkeypatch, plan: Plan):
    calls = []

    async def generate_json(model, system, user, schema, **kwargs):
        calls.append({"system": system, "user": json.loads(user), **kwargs})
        return plan

    monkeypatch.setattr(llm, "generate_json", generate_json)
    return calls


def test_trip_days():
    assert planner.trip_days(SLOTS) == 4  # 2027-03-10 .. 03-13
    assert planner.trip_days(Slots(nights=2)) == 3
    assert planner.trip_days(Slots()) == 2


def test_draft_sends_slots_chat_and_language(monkeypatch):
    calls = fake_gemini(monkeypatch, Plan.model_validate_json(PLAN_JSON))
    chat = [
        {"role": "ai", "text": "Where to?"},
        {"role": "user", "text": "", "answer": {}},
        {"role": "user", "text": "Kyushu"},
    ]

    asyncio.run(planner.draft(SLOTS, chat, "ja"))

    sent = calls[0]
    assert sent["system"].endswith("Write all user-facing text in Japanese.")
    assert sent["user"]["days"] == 4
    assert sent["user"]["slots"]["musts"] == ["Takachiho Gorge", "Mt. Inasa night view"]
    assert sent["user"]["chat"] == [{"role": "ai", "text": "Where to?"}, {"role": "user", "text": "Kyushu"}]
    assert "thinking" not in sent  # model default: quality over speed


def test_draft_cleans_fields_the_pipeline_fills(monkeypatch):
    plan = Plan.model_validate_json(PLAN_JSON)
    stop = plan.days[0].stops[0]
    stop.placeId, stop.videoIds, stop.warn = "made-up", ["x"], "?"
    stop.leg.polyline = "abc"
    plan.days[0].stops[-1].leg = plan.days[0].stops[0].leg.model_copy()  # model forgot: last stop has a leg
    plan.days[2].stops[0].leg.estimate = False  # model forgot: ferry must be an estimate
    fake_gemini(monkeypatch, plan)

    out = asyncio.run(planner.draft(SLOTS, [], "ja"))

    first = out.days[0].stops[0]
    assert (first.placeId, first.lat, first.videoIds, first.warn, first.leg.polyline) == (None, None, [], None, None)
    assert all(day.stops[-1].leg is None for day in out.days)
    assert out.days[2].stops[0].leg.mode == "FERRY" and out.days[2].stops[0].leg.estimate
    assert out.language == "ja"


def test_fix_sends_plan_and_warnings(monkeypatch):
    plan = Plan.model_validate_json(PLAN_JSON)
    calls = fake_gemini(monkeypatch, plan)

    asyncio.run(planner.fix(plan, ["Day 2: 6 h of driving"], "en"))

    assert calls[0]["user"]["warnings"] == ["Day 2: 6 h of driving"]
    assert calls[0]["user"]["plan"]["title"] == plan.title
