"""Plan pipeline with Gemini, Places, Routes and Firestore faked (no network, no cost)."""

import asyncio
from datetime import date

from app import pipeline
from app.agents import planner
from app.models import Day, Leg, Plan, Stop
from app.services import firestore as fs
from app.services import places, routes

KYUSHU = {"label": "Kyushu", "countryCode": "JP", "lat": 32.59, "lng": 130.8}
SLOTS = {"dest": KYUSHU, "transport": ["car"], "dates": {"start": "2027-03-10", "end": "2027-03-10"}}
# Wednesday 2027-03-10; Google counts days from Sunday = 0, so Wednesday = 3.
OPEN_10_TO_17 = {
    "periods": [{"open": {"day": 3, "hour": 10, "minute": 0}, "close": {"day": 3, "hour": 17, "minute": 0}}]
}
PLACES = {
    "高千穂峡": {"placeId": "p-gorge", "name": "Takachiho Gorge", "lat": 32.70, "lng": 131.30, "countryCode": "JP"},
    "千穂の家": {
        "placeId": "p-food",
        "name": "Chiho no Ie",
        "lat": 32.701,
        "lng": 131.302,
        "countryCode": "JP",
        "openingHours": OPEN_10_TO_17,
    },
    "Kurokawa Onsen": {
        "placeId": "p-onsen",
        "name": "Kurokawa Onsen",
        "lat": 33.08,
        "lng": 131.14,
        "countryCode": "JP",
    },
    "Fake Cafe": {"placeId": "p-us", "name": "Fake Cafe", "lat": 40.7, "lng": -74.0, "countryCode": "US"},
}


def stop(sid, time, name, local=None, leg=None):
    return Stop(id=sid, time=time, name=name, nameLocal=local, stayMinutes=60, leg=leg)


def draft_plan():
    return Plan(
        title="Test",
        language="en",
        days=[
            Day(
                day=1,
                date="2027-03-10",
                stops=[
                    stop("s-101", "09:00", "Takachiho Gorge", "高千穂峡", Leg(mode="DRIVE", minutes=10)),
                    stop("s-102", "10:00", "Chiho no Ie", "千穂の家", Leg(mode="DRIVE", minutes=99)),
                    stop("s-103", "12:00", "Fake Cafe", None, Leg(mode="DRIVE", minutes=60)),
                    stop("s-104", "15:00", "Kurokawa Onsen"),
                ],
            )
        ],
    )


def fake_world(monkeypatch, replace_with=None):
    log = {"progress": [], "fix": [], "routes": [], "saved": None, "status": []}

    async def get_trip(trip_id):
        return {"language": "en", "slots": SLOTS}

    async def list_messages(trip_id):
        return []

    async def update_trip(trip_id, data):
        if "progress" in data:
            log["progress"].append(data["progress"])
        if "status" in data:
            log["status"].append(data["status"])

    async def save_plan(trip_id, plan, reason="initial"):
        log["saved"] = plan
        return "plan-1"

    async def draft(slots, messages, lang):
        return draft_plan()

    async def fix(plan, warnings, lang):
        log["fix"].append(warnings)
        new = plan.model_copy(deep=True)
        for day in new.days:
            day.stops = [s for s in day.stops if s.name != "Fake Cafe"]
            if replace_with:
                day.stops.insert(2, stop("s-103", "12:00", replace_with, None, Leg(mode="DRIVE", minutes=60)))
        return new

    async def search_text(query, lang, near=None):
        return PLACES.get(query)

    async def local_name(place_id, country):
        return "黒川温泉" if place_id == "p-onsen" else None

    async def leg(a, b, mode, lang):
        log["routes"].append(mode)
        return {"minutes": 50, "polyline": "abc"}

    for target, name, fn in [
        (fs, "get_trip", get_trip),
        (fs, "list_messages", list_messages),
        (fs, "update_trip", update_trip),
        (fs, "save_plan", save_plan),
        (planner, "draft", draft),
        (planner, "fix", fix),
        (places, "search_text", search_text),
        (places, "local_name", local_name),
        (routes, "leg", leg),
    ]:
        monkeypatch.setattr(target, name, fn)
    return log


def test_full_run_replaces_a_wrong_country_match(monkeypatch):
    log = fake_world(monkeypatch, replace_with="Kurokawa Onsen")
    assert asyncio.run(pipeline.run("t1")) == "plan-1"

    plan = log["saved"]
    assert "Fake Cafe" in log["fix"][0][0]  # the US match was treated as not found and sent for replacement
    names = [s.name for s in plan.days[0].stops]
    assert "Fake Cafe" not in names
    gorge = plan.days[0].stops[0]
    assert (gorge.placeId, gorge.lat) == ("p-gorge", 32.70)
    assert plan.days[0].stops[-1].nameLocal == "黒川温泉"
    assert gorge.leg.mode == "WALK"  # under 1 km to the restaurant
    assert plan.days[0].stops[-1].leg is None
    assert log["progress"] == ["routes", "videos"]
    assert plan.checks == []


def test_still_missing_after_replacement_is_dropped_with_a_note(monkeypatch):
    log = fake_world(monkeypatch, replace_with="Another Fake")
    asyncio.run(pipeline.run("t1"))
    plan = log["saved"]
    assert [s.name for s in plan.days[0].stops] == ["Takachiho Gorge", "Chiho no Ie", "Kurokawa Onsen"]
    assert plan.checks == ["Another Fake: couldn't be found on Google Maps, so it was removed. Please check."]


def test_failure_sets_status_error(monkeypatch):
    log = fake_world(monkeypatch)

    async def broken(*args):
        raise RuntimeError("boom")

    monkeypatch.setattr(planner, "draft", broken)
    try:
        asyncio.run(pipeline.run("t1"))
        raise AssertionError("should raise")
    except RuntimeError:
        pass
    assert log["status"] == ["error"]


def test_retime_rounds_up_to_5_minutes():
    plan = draft_plan()
    plan.days[0].stops[0].leg.minutes = 12
    pipeline.retime(plan)
    assert [s.time for s in plan.days[0].stops] == ["09:00", "10:15", "12:55", "14:55"]


def test_is_open():
    wed = date(2027, 3, 10)
    assert pipeline.is_open(OPEN_10_TO_17, wed, "11:00") is True
    assert pipeline.is_open(OPEN_10_TO_17, wed, "09:30") is False
    assert pipeline.is_open(OPEN_10_TO_17, date(2027, 3, 11), "11:00") is False  # closed on Thursday
    assert pipeline.is_open(None, wed, "11:00") is None
    assert pipeline.is_open({"periods": [{"open": {"day": 0, "hour": 0, "minute": 0}}]}, wed, "03:00") is True
    late = {"periods": [{"open": {"day": 3, "hour": 18}, "close": {"day": 4, "hour": 2}}]}
    assert pipeline.is_open(late, date(2027, 3, 11), "01:00") is True  # still open after midnight


def test_warnings_long_drive_and_closed(monkeypatch):
    plan = draft_plan()
    for s in plan.days[0].stops[:-1]:
        s.leg.minutes = 120  # 360 min of driving
    run = pipeline.Run(lang="en", near=None, country="JP", default_mode="DRIVE")
    run.hours["s-102"] = OPEN_10_TO_17
    plan.days[0].stops[1].time = "09:30"

    found = pipeline.add_warnings(plan, run)

    assert plan.days[0].stops[0].warn.startswith("About 6 h 0 min of driving")
    assert "closed" in plan.days[0].stops[1].warn
    assert len(found) == 2


def test_match_far_from_the_rough_location_is_rejected(monkeypatch):
    calls = []

    async def search_text(query, lang, near=None):
        calls.append(near)
        return PLACES["千穂の家"]  # at 32.70, 131.30

    monkeypatch.setattr(places, "search_text", search_text)
    run = pipeline.Run(lang="en", near=(32.59, 130.8), country="JP", default_mode="DRIVE")
    far = stop("s-1", "09:00", "Kajiya", "かじ屋")
    far.lat, far.lng = 33.19, 130.02  # Planner says: near Takeo, about 125 km away
    near = stop("s-2", "09:00", "Chiho no Ie")
    near.lat, near.lng = 32.71, 131.29

    assert asyncio.run(pipeline._find(far, run)) is None
    assert asyncio.run(pipeline._find(near, run))["placeId"] == "p-food"
    assert calls[0] == (33.19, 130.02)  # searched near the Planner's guess, not the middle of Kyushu
