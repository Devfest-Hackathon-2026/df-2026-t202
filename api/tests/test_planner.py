"""Planner agent with Gemini faked (no network, no cost)."""

import asyncio
import json
from pathlib import Path

from app.agents import planner
from app.models import Cost, DayFix, People, Plan, PlanFix, PlanUpdate, Slots, Stop
from app.services import llm

ROOT = Path(__file__).parents[1]
SLOTS = Slots.model_validate_json((ROOT / "tests/fixtures/demo_slots.json").read_text(encoding="utf-8"))
PLAN_JSON = (ROOT / "app/fixtures/demo_plan.json").read_text(encoding="utf-8")


def fake_gemini(monkeypatch, plan: Plan | PlanFix):
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
    assert planner.trip_days(Slots(nights=60)) == 20  # trips saved before the 20-day cap


def test_plan_currency_comes_from_the_trip_not_gemini(monkeypatch):
    plan = Plan.model_validate_json(PLAN_JSON)
    plan.currency = "円"  # Intl.NumberFormat throws on this in the browser
    fake_gemini(monkeypatch, plan)
    out = asyncio.run(planner.draft(SLOTS, [], "en"))
    assert out.currency == SLOTS.budget.currency


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
    assert (first.placeId, first.videoIds, first.warn, first.leg.polyline) == (None, [], None, None)
    assert first.lat is not None  # rough location kept for the Places search (D8)
    assert all(day.stops[-1].leg is None for day in out.days)
    assert out.days[2].stops[0].leg.mode == "FERRY" and out.days[2].stops[0].leg.estimate
    assert out.language == "ja"


def test_fix_sends_a_trimmed_plan_and_merges_only_the_changed_days(monkeypatch):
    plan = Plan.model_validate_json(PLAN_JSON)
    plan.days[0].stops[0].leg.polyline = "long-polyline"
    plan.days[0].stops[0].videoIds = ["v1"]
    new_day2 = [s.model_copy(deep=True) for s in plan.days[1].stops[:2]]
    new_day2[0].placeId, new_day2[-1].leg = "made-up", new_day2[0].leg.model_copy()  # the model's mistakes
    out = PlanFix(days=[DayFix(day=2, stops=new_day2), DayFix(day=9, stops=new_day2), DayFix(day=3, stops=[])])
    calls = fake_gemini(monkeypatch, out)

    revised = asyncio.run(planner.fix(plan, ["Day 2: 6 h of driving"], "en"))

    sent = calls[0]
    assert sent["user"]["warnings"] == ["Day 2: 6 h of driving"]
    assert set(sent["user"]["plan"]) == {"days"}  # no title, cost or checks: the repair only touches days
    first = sent["user"]["plan"]["days"][0]["stops"][0]
    assert "polyline" not in first["leg"] and "videoIds" not in first and "placeId" not in first
    assert sent["thinking"] == "LOW" and sent["timeout"] == planner.FIX_TIMEOUT_SECONDS  # repairs are small

    assert [s.id for s in revised.days[1].stops] == ["s-201", "s-202"]
    assert revised.days[1].stops[0].placeId is None and revised.days[1].stops[-1].leg is None  # cleaned
    assert revised.days[0] == plan.days[0]  # unchanged days keep their verified data
    assert len(revised.days[2].stops) == len(plan.days[2].stops)  # an empty day is ignored, not deleted
    assert len(revised.days) == len(plan.days)  # an unknown day 9 is ignored
    assert len(plan.days[1].stops) > 2  # the input plan is not modified


def test_worst_case_gemini_time_fits_cloud_run():
    from app import pipeline

    # draft (2 attempts) alone, or a repair started just before the cut-off; Cloud Run allows 300 s
    assert 2 * planner.TIMEOUT_SECONDS <= 270
    assert pipeline.FIX_BEFORE_S + 2 * planner.FIX_TIMEOUT_SECONDS <= 240


def test_costs_are_always_ranges(monkeypatch):
    plan = Plan.model_validate_json(PLAN_JSON)
    plan.cost.min, plan.cost.max = 50000, 30000
    plan.cost.items[0].min = plan.cost.items[0].max = 3000
    fake_gemini(monkeypatch, plan)

    out = asyncio.run(planner.draft(SLOTS, [], "en"))

    assert (out.cost.min, out.cost.max) == (30000, 50000)  # swapped
    assert (out.cost.items[0].min, out.cost.items[0].max) == (2700, 3300)  # one price -> about +-10%


# ---------- Plan updates (D27) ----------


def verified_plan() -> Plan:
    """The demo plan as the pipeline saves it: every stop has a placeId, videos and real legs."""
    plan = Plan.model_validate_json(PLAN_JSON)
    for day in plan.days:
        for stop in day.stops:
            stop.placeId, stop.videoIds = f"p-{stop.id}", [f"v-{stop.id}"]
            if stop.leg:
                stop.leg.polyline = "poly"
    return plan


def test_changes_lists_what_changed():
    new = SLOTS.model_copy(deep=True)
    new.people = People(adult=4, child=1)
    new.musts = ["Takachiho Gorge", "Sakurajima"]
    lines = planner.changes(SLOTS, new)
    assert lines[0].startswith("Travellers: ") and '"child": 1' in lines[0]
    assert "Must-sees added: Sakurajima" in lines and "Must-sees removed: Mt. Inasa night view" in lines
    assert planner.changes(SLOTS, SLOTS) == []


def test_revise_sends_a_trimmed_plan_changes_and_requests(monkeypatch):
    calls = fake_gemini(monkeypatch, PlanUpdate(days=[]))
    asyncio.run(planner.revise(verified_plan(), ["Budget: a -> b"], ["more relaxed day 2"], SLOTS, "en"))
    sent = calls[0]["user"]
    assert set(sent["plan"]) == {"days", "cost", "checks"}
    first = sent["plan"]["days"][0]["stops"][0]
    assert "polyline" not in first["leg"] and "videoIds" not in first and "placeId" not in first
    assert sent["changes"] == ["Budget: a -> b"] and sent["requests"] == ["more relaxed day 2"]
    assert sent["days"] == 4 and sent["dates"] == {"start": "2027-03-10", "end": "2027-03-13"}
    assert calls[0]["thinking"] == "LOW" and calls[0]["timeout"] == planner.REVISE_TIMEOUT_SECONDS


def test_apply_update_carries_over_verified_stops_and_renumbers():
    old = verified_plan()
    kept = old.days[1].stops[0].model_copy(deep=True)
    kept.placeId, kept.videoIds, kept.lat = None, [], 1.0  # the model's copy: no ids, a rough location
    new_stop = Stop(id="x", time="15:00", name="Aso Shrine", lat=32.9, lng=131.1)
    out = PlanUpdate(days=[DayFix(day=2, stops=[kept, new_stop])], cost=Cost(min=10, max=10))

    plan, changed = planner.apply_update(old, out, SLOTS, "en")

    assert changed == {2}
    day2 = plan.days[1].stops
    assert [s.id for s in day2] == ["s-201", "s-202"]
    assert (day2[0].placeId, day2[0].lat, day2[0].videoIds) == ("p-s-201", old.days[1].stops[0].lat, ["v-s-201"])
    assert day2[1].placeId is None and day2[1].leg is None  # a new stop is searched by the pipeline
    assert plan.days[0] == old.days[0]  # an unchanged day keeps everything
    assert (plan.cost.min, plan.cost.max) == (9, 11)  # always a range
    assert plan.checks == old.checks  # no new checks: keep the old ones


def test_apply_update_moves_the_dates_and_trims_days():
    shifted = SLOTS.model_copy(deep=True)
    shifted.dates.start, shifted.dates.end = "2027-03-20", "2027-03-22"  # 3 days instead of 4
    plan, changed = planner.apply_update(verified_plan(), PlanUpdate(days=[]), shifted, "en")
    assert [d.date for d in plan.days] == ["2027-03-20", "2027-03-21", "2027-03-22"]
    assert changed == set()


def test_apply_update_with_a_missing_day_means_rebuild():
    longer = SLOTS.model_copy(deep=True)
    longer.dates.end = "2027-03-14"  # 5 days; the model returned no day 5
    assert planner.apply_update(verified_plan(), PlanUpdate(days=[]), longer, "en") is None
