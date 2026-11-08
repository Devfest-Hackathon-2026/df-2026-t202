"""Step machine tests (pure, no network)."""

import json
from pathlib import Path

import pytest

from app import flow
from app.models import STEP_ORDER, PlaceRef, Slots, SlotUpdates

FIXTURES = Path(__file__).parent / "fixtures"
KYUSHU = {"label": "Kyushu, Japan", "countryCode": "JP", "lat": 32.59, "lng": 130.8}
FUKUOKA = {"label": "Fukuoka", "countryCode": "JP", "lat": 33.59, "lng": 130.42}

DEMO_ANSWERS = [
    ("dest", KYUSHU),
    ("dates", {"start": "2027-03-10", "end": "2027-03-13"}),
    ("people", {"adult": 4, "child": 0, "infant": 0}),
    ("budget", {"basis": "person", "amount": 50000}),
    ("transport", {"transport": ["car"], "origin": FUKUOKA}),
    ("prefs", ["onsen", "views", "night_view"]),
    ("musts", ["Takachiho Gorge", "Mt. Inasa night view"]),
]


def test_card_answers_walk_dest_to_ready_and_match_demo_fixture():
    slots = Slots()
    for step, value in DEMO_ANSWERS:
        assert flow.next_step(slots) == step
        slots = flow.apply_answer(slots, step, value)
    assert flow.next_step(slots) == "ready"
    expected = json.loads((FIXTURES / "demo_slots.json").read_text(encoding="utf-8"))
    assert slots.model_dump(mode="json") == Slots.model_validate(expected).model_dump(mode="json")


def test_skip_sets_status_and_moves_on():
    slots = flow.apply_answer(Slots(), "dest", "skip")
    assert slots.status["dest"] == "skip"
    assert flow.next_step(slots) == "dates"


def test_dest_sets_budget_currency():
    slots = flow.apply_answer(Slots(), "dest", {"label": "Seoul", "countryCode": "KR"})
    assert slots.budget is not None and slots.budget.currency == "KRW"
    assert slots.status["budget"] == "empty"
    assert flow.card_for("budget", slots).options[0] == "300000"


def test_changing_dest_keeps_a_budget_the_user_already_set():
    slots = Slots()
    for step, value in DEMO_ANSWERS[:4]:
        slots = flow.apply_answer(slots, step, value)
    slots = flow.apply_answer(slots, "dest", {"label": "Paris", "countryCode": "FR"})
    assert slots.budget.currency == "JPY" and slots.budget.amount == 50000


@pytest.mark.parametrize(
    ("code", "currency"), [("JP", "JPY"), ("us", "USD"), ("DE", "EUR"), ("FR", "EUR"), ("BR", "USD"), (None, "USD")]
)
def test_currency_for(code, currency):
    assert flow.currency_for(code) == currency


def test_nights_instead_of_dates():
    slots = flow.apply_answer(Slots(), "dates", {"nights": 3})
    assert slots.nights == 3 and slots.dates is None and slots.status["dates"] == "done"


@pytest.mark.parametrize(
    ("step", "value"),
    [
        ("dest", {"countryCode": "JP"}),
        ("dates", {"start": "2027-03-13", "end": "2027-03-10"}),
        ("dates", {"start": "13/03/2027", "end": "2027-03-10"}),
        ("dates", {"nights": 99}),
        ("people", {"adult": 0, "child": 0}),
        ("people", {"adult": 500}),
        ("budget", 50000),
        ("transport", ["rocket"]),
        ("prefs", "onsen"),
    ],
)
def test_bad_answers_raise(step, value):
    with pytest.raises(flow.AnswerError):
        flow.apply_answer(Slots(), step, value)


def test_musts_none_means_empty_list():
    slots = flow.apply_answer(Slots(), "musts", "none")
    assert slots.musts == [] and slots.status["musts"] == "done"


def test_string_lists_are_trimmed_and_deduplicated():
    slots = flow.apply_answer(Slots(), "prefs", [" onsen ", "onsen", "", "food"])
    assert slots.prefs == ["onsen", "food"]


def test_can_answer_current_or_edit_but_not_future():
    slots = flow.apply_answer(Slots(), "dest", KYUSHU)
    assert flow.can_answer(slots, "dates", "dates")  # current
    assert flow.can_answer(slots, "dates", "dest")  # edit
    assert not flow.can_answer(slots, "dates", "budget")  # not asked yet


def test_merge_updates_fills_several_steps_and_keeps_currency():
    slots = flow.apply_answer(Slots(), "dest", KYUSHU)
    updates = SlotUpdates.model_validate({"people": {"adult": 4}, "budget": {"basis": "person", "amount": 50000}})
    new = flow.merge_updates(slots, updates)
    assert new.people.adult == 4 and new.budget.amount == 50000 and new.budget.currency == "JPY"
    assert new.status["people"] == new.status["budget"] == "done"
    assert flow.next_step(new) == "dates"


def test_merge_updates_resolved_dest_and_skip():
    dest = PlaceRef.model_validate({"label": "Bangkok", "countryCode": "TH"})
    new = flow.merge_updates(Slots(), SlotUpdates(dest="bangkok", skip=["budget"]), dest=dest)
    assert new.dest.label == "Bangkok" and new.budget.currency == "THB"
    assert new.status["dest"] == "done" and new.status["budget"] == "skip"


def test_merge_updates_ignores_invalid_values():
    updates = SlotUpdates.model_validate({"dates": {"start": "2027-03-13", "end": "2027-03-10"}})
    new = flow.merge_updates(Slots(), updates)
    assert new.dates is None and new.status["dates"] == "empty"


def test_skip_does_not_override_done():
    slots = flow.apply_answer(Slots(), "people", {"adult": 2})
    new = flow.merge_updates(slots, SlotUpdates(skip=["people"]))
    assert new.status["people"] == "done"


@pytest.mark.parametrize("lang", ["en", "ja"])
def test_every_step_has_question_and_card(lang):
    for step in [*STEP_ORDER, "ready"]:
        assert flow.question_for(step, lang)
        assert flow.card_for(step, Slots()).type == step


def test_answer_text_in_both_languages():
    slots = Slots()
    for step, value in DEMO_ANSWERS:
        slots = flow.apply_answer(slots, step, value)
    assert flow.answer_text("people", None, slots, "en") == "4 adults"
    assert flow.answer_text("people", None, slots, "ja") == "大人4人"
    assert flow.answer_text("budget", None, slots, "en") == "50,000 JPY per person"
    assert flow.answer_text("budget", None, slots, "ja") == "50,000 JPY（1人あたり）"
    assert flow.answer_text("transport", None, slots, "en") == "car, from Fukuoka"
    assert flow.answer_text("dates", "skip", slots, "ja") == "まだ決めていない"
