"""Contract tests: the shared models (BACKEND_PERSON_A.md 3.3) accept the demo fixtures."""

import json
from pathlib import Path

from app.models import STEP_ORDER, ConciergeOutput, Plan, Slots, UiCard

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def test_demo_slots_valid_and_complete():
    slots = Slots.model_validate(load("demo_slots.json"))
    assert slots.dest is not None and slots.dest.countryCode == "JP"
    assert all(slots.status[step] == "done" for step in STEP_ORDER)


def test_demo_plan_valid():
    plan = Plan.model_validate(load("demo_plan.json"))
    assert len(plan.days) == 4
    assert plan.cost is not None
    assert plan.cost.min == sum(i.min for i in plan.cost.items)
    assert plan.cost.max == sum(i.max for i in plan.cost.items)


def test_demo_plan_last_stop_of_each_day_has_no_leg():
    plan = Plan.model_validate(load("demo_plan.json"))
    for day in plan.days:
        assert day.stops[-1].leg is None, f"day {day.day}"
        assert all(s.leg is not None for s in day.stops[:-1]), f"day {day.day}"


def test_demo_plan_times_fit_legs():
    """Each stop starts no earlier than the previous stop's time + its leg."""
    plan = Plan.model_validate(load("demo_plan.json"))
    for day in plan.days:
        for prev, nxt in zip(day.stops, day.stops[1:], strict=False):
            assert prev.leg is not None
            assert minutes(nxt.time) >= minutes(prev.time) + prev.leg.minutes, f"{prev.id} → {nxt.id}"


def test_demo_plan_dates_match_slots():
    plan = Plan.model_validate(load("demo_plan.json"))
    slots = Slots.model_validate(load("demo_slots.json"))
    assert slots.dates is not None
    assert plan.days[0].date == slots.dates.start
    assert plan.days[-1].date == slots.dates.end


def test_new_slots_are_all_empty():
    assert Slots().status == {step: "empty" for step in STEP_ORDER}


def test_concierge_output_partial_updates():
    out = ConciergeOutput.model_validate(
        {"updates": {"people": {"adult": 4}, "budget": {"basis": "person", "amount": 50000}}, "comment": "Great!"}
    )
    assert out.updates.people is not None and out.updates.people.adult == 4
    assert out.updates.model_dump(exclude_unset=True).keys() == {"people", "budget"}
    assert out.clarify is None


def test_ui_card_defaults():
    assert UiCard(type="dest").options == []
