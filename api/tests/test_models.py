"""Model contract tests. The fixtures are the Kyushu demo (PLAN.md section 17)."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.models import (
    STEP_ORDER,
    ConciergeOutput,
    Day,
    Plan,
    Slots,
    SlotStatuses,
    UiCard,
)

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def test_demo_slots_valid_and_complete():
    slots = Slots.model_validate(load("demo_slots.json"))
    assert slots.dest and slots.dest.countryCode == "JP"
    assert all(getattr(slots.status, step) == "done" for step in STEP_ORDER)


def test_demo_plan_valid():
    plan = Plan.model_validate(load("demo_plan.json"))
    assert len(plan.days) == 4
    assert plan.cost.min == sum(i.min for i in plan.cost.items)
    assert plan.cost.max == sum(i.max for i in plan.cost.items)


def test_demo_plan_times_fit_legs():
    """Each stop must start no earlier than the previous stop's time + its leg."""
    plan = Plan.model_validate(load("demo_plan.json"))
    for day in plan.days:
        for prev, nxt in zip(day.stops, day.stops[1:], strict=False):
            assert prev.leg is not None, f"{prev.id} needs a leg"
            assert minutes(nxt.time) >= minutes(prev.time) + prev.leg.minutes, f"{prev.id} → {nxt.id}"


def test_demo_plan_dates_match_slots():
    plan = Plan.model_validate(load("demo_plan.json"))
    slots = Slots.model_validate(load("demo_slots.json"))
    assert slots.dates is not None
    assert plan.days[0].date == slots.dates.start
    assert plan.days[-1].date == slots.dates.end


def test_round_trip_json_matches_fixture():
    raw = load("demo_plan.json")
    assert Plan.model_validate(raw).model_dump(mode="json") == raw


def test_last_stop_must_not_have_leg():
    raw = load("demo_plan.json")["days"][0]
    raw["stops"][-1]["leg"] = {"mode": "DRIVE", "minutes": 10}
    with pytest.raises(ValidationError, match="last stop"):
        Day.model_validate(raw)


def test_unknown_fields_rejected():
    raw = load("demo_plan.json")
    raw["days"][0]["stops"][0]["price"] = 1000
    with pytest.raises(ValidationError):
        Plan.model_validate(raw)


def test_dates_and_nights_are_exclusive():
    with pytest.raises(ValidationError, match="either dates or nights"):
        Slots.model_validate({"dates": {"start": "2027-03-10", "end": "2027-03-13"}, "nights": 3})


def test_bad_date_range_rejected():
    with pytest.raises(ValidationError):
        Slots.model_validate({"dates": {"start": "2027-03-13", "end": "2027-03-10"}})


def test_cost_range_rejected_when_inverted():
    raw = load("demo_plan.json")
    raw["cost"]["min"], raw["cost"]["max"] = 60000, 40000
    with pytest.raises(ValidationError):
        Plan.model_validate(raw)


def test_new_slots_are_empty():
    assert Slots().status == SlotStatuses()
    assert Slots().status.dest == "empty"


def test_concierge_output_example_from_plan():
    out = ConciergeOutput.model_validate(
        {
            "updates": {"people": {"adult": 4}, "budget": {"basis": "person", "amount": 50000}},
            "comment": "Great! March is a good season for onsen.",
            "clarify": "Which days in March?",
        }
    )
    assert out.updates.people and out.updates.people.adult == 4
    assert out.updates.model_dump(exclude_unset=True).keys() == {"people", "budget"}


def test_ui_card_defaults():
    card = UiCard(type="dest")
    assert card.allowSkip is True and card.chips == []
