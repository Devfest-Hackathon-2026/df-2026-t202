"""Plan pipeline with Gemini, Places, Routes and Firestore faked (no network, no cost)."""

import asyncio
from datetime import date

from app import pipeline
from app.agents import planner
from app.models import Cost, Day, DayFix, Leg, Plan, PlanUpdate, Stop
from app.services import firestore as fs
from app.services import places, routes, youtube

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

    async def save_plan(trip_id, plan, reason="initial", slots=None):
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
        log["fix_seen"] = plan
        return new

    async def search_text(query, lang, near=None):
        return PLACES.get(query)

    async def local_name(place_id, country):
        return "黒川温泉" if place_id == "p-onsen" else None

    async def shorts_for(place_id, name_local, region, name="", lang="en"):
        log.setdefault("videos", []).append(place_id)
        return [f"vid-{place_id}"]

    async def cached(place_id):
        return None

    async def leg(a, b, mode, lang):
        log["routes"].append(mode)
        return {"minutes": 10 if mode == "WALK" else 50, "polyline": "abc"}

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
        (youtube, "shorts_for", shorts_for),
        (youtube, "cached", cached),
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
    assert gorge.videoIds == ["vid-p-gorge"]
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

    found, closed = pipeline.add_warnings(plan, run)

    assert plan.days[0].stops[0].warn.startswith("About 6 h 0 min of driving")
    assert "closed" in plan.days[0].stops[1].warn
    assert len(found) == 2 and closed == 1


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


def test_no_videos_for_start_end_transport(monkeypatch):
    log = fake_world(monkeypatch, replace_with="Kurokawa Onsen")
    original = draft_plan

    def with_kinds():
        plan = original()
        plan.days[0].stops[0].kind = "start"
        return plan

    async def draft(slots, messages, lang):
        return with_kinds()

    monkeypatch.setattr(planner, "draft", draft)
    asyncio.run(pipeline.run("t1"))
    assert "p-gorge" not in log["videos"] and "p-food" in log["videos"]


def test_night_view_never_moves_earlier():
    plan = draft_plan()
    night = plan.days[0].stops[-1]
    night.kind, night.time = "night_view", "19:00"
    pipeline.retime(plan)
    assert night.time == "19:00"  # would be 14:50 from the legs alone
    assert plan.days[0].stops[-2].stayMinutes == 60 + 250  # the stop before gets the extra time


def test_city_is_not_a_stop(monkeypatch):
    city = {
        "placeId": "p-city",
        "name": "Nagasaki",
        "lat": 32.75,
        "lng": 129.88,
        "countryCode": "JP",
        "types": ["locality", "political"],
    }
    sight = {
        **city,
        "placeId": "p-sight",
        "name": "Glover Garden",
        "types": ["tourist_attraction", "point_of_interest"],
    }

    async def search_text(query, lang, near=None):
        return city if query == "Nagasaki" else sight

    monkeypatch.setattr(places, "search_text", search_text)
    run = pipeline.Run(lang="en", near=None, country="JP", default_mode="DRIVE")
    assert asyncio.run(pipeline._find(stop("s-1", "09:00", "Nagasaki"), run)) is None
    assert asyncio.run(pipeline._find(stop("s-2", "09:00", "Glover Garden"), run))["placeId"] == "p-sight"


def test_english_trip_keeps_gemini_name_over_a_japanese_only_name(monkeypatch):
    async def search_text(query, lang, near=None):
        return {
            "placeId": "p-car",
            "name": "トヨタレンタカー 福岡空港店",
            "lat": 33.59,
            "lng": 130.45,
            "countryCode": "JP",
        }

    async def local_name(place_id, country):
        return None

    monkeypatch.setattr(places, "search_text", search_text)
    monkeypatch.setattr(places, "local_name", local_name)
    run = pipeline.Run(lang="en", near=None, country="JP", default_mode="DRIVE")
    s = stop("s-1", "09:00", "Toyota Rent a Car Fukuoka Airport")
    assert asyncio.run(pipeline._verify_stop(s, run))
    assert s.name == "Toyota Rent a Car Fukuoka Airport" and s.placeId == "p-car"


def test_start_and_end_keep_gemini_names(monkeypatch):
    async def search_text(query, lang, near=None):
        return {
            "placeId": "p-car",
            "name": "Toyota Rent A Car Fukuoka Airport Car Return",
            "lat": 33.59,
            "lng": 130.45,
            "countryCode": "JP",
        }

    monkeypatch.setattr(places, "search_text", search_text)
    run = pipeline.Run(lang="en", near=None, country="JP", default_mode="DRIVE")
    s = stop("s-101", "09:00", "Toyota Rent a Car Fukuoka Airport", "トヨタレンタカー")
    s.kind = "start"
    assert asyncio.run(pipeline._verify_stop(s, run))
    assert s.name == "Toyota Rent a Car Fukuoka Airport" and s.placeId == "p-car"


def test_at_most_4_youtube_searches_at_once(monkeypatch):
    running, peak = 0, 0

    async def shorts_for(place_id, name_local, region, name="", lang="en"):
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.01)
        running -= 1
        return ["v"]

    async def cached(place_id):
        return None

    monkeypatch.setattr(youtube, "shorts_for", shorts_for)
    monkeypatch.setattr(youtube, "cached", cached)
    plan = draft_plan()
    plan.days[0].stops = [stop(f"s-1{i:02d}", "09:00", f"Spot {i}") for i in range(12)]
    for s in plan.days[0].stops:
        s.placeId = "p"
    run = pipeline.Run(lang="en", near=None, country="JP", default_mode="DRIVE")
    asyncio.run(pipeline.add_videos(plan, run, max_searches=12))
    assert peak == 4 and all(s.videoIds == ["v"] for s in plan.days[0].stops)


def jp_run(**kw):
    return pipeline.Run(lang="en", near=None, country="JP", default_mode="TRANSIT", **kw)


def test_videos_skip_hotels_and_stations_and_search_sights_first(monkeypatch):
    searched = []

    async def shorts_for(place_id, name_local, region, name="", lang="en"):
        searched.append(place_id)
        return ["new"]

    async def cached(place_id):
        return ["old"] if place_id == "p-cached" else None

    monkeypatch.setattr(youtube, "shorts_for", shorts_for)
    monkeypatch.setattr(youtube, "cached", cached)
    plan = draft_plan()
    kinds = [("p-shop", "shop"), ("p-food", "food"), ("p-cached", "shop"), ("p-sight", "sight"), ("p-hotel", "sight")]
    plan.days[0].stops = [stop(f"s-10{i}", "09:00", pid) for i, (pid, _) in enumerate(kinds)]
    for s, (pid, kind) in zip(plan.days[0].stops, kinds, strict=True):
        s.placeId, s.kind = pid, kind
    run = jp_run()
    run.types = {"s-104": {"lodging"}, "s-103": {"tourist_attraction"}}

    asyncio.run(pipeline.add_videos(plan, run, max_searches=2))

    assert searched == ["p-sight", "p-food"]  # sights first, then food; the shop is over the cap; no hotel search
    assert [s.videoIds for s in plan.days[0].stops] == [[], ["new"], ["old"], ["new"], []]  # cached is free


def test_transit_without_a_route_walks_when_close(monkeypatch):
    asked = []

    async def leg(a, b, mode, lang):
        asked.append(mode)
        return {"minutes": 20, "polyline": "w"} if mode == "WALK" else None  # no transit data in Japan

    monkeypatch.setattr(routes, "leg", leg)
    a, near, far = stop("s-101", "09:00", "A"), stop("s-102", "10:00", "B"), stop("s-103", "11:00", "C")
    a.lat, a.lng, near.lat, near.lng, far.lat, far.lng = 35.0, 135.77, 35.012, 135.77, 35.2, 135.77  # 1.3 / 22 km
    a.leg = near.leg = Leg(mode="TRANSIT", minutes=25)
    plan = Plan(title="t", language="en", days=[Day(day=1, stops=[a, near, far])])

    asyncio.run(pipeline.add_legs(plan, jp_run()))

    assert (a.leg.mode, a.leg.minutes, a.leg.estimate) == ("WALK", 20, False)
    assert (near.leg.mode, near.leg.minutes, near.leg.estimate) == ("TRANSIT", 25, True)  # the Planner's honest guess
    assert asked == ["TRANSIT", "WALK", "TRANSIT"]


def test_a_long_walk_becomes_a_ride(monkeypatch):
    async def leg(a, b, mode, lang):
        return {"WALK": {"minutes": 177, "polyline": "w"}, "DRIVE": {"minutes": 20, "polyline": "d"}}.get(mode)

    monkeypatch.setattr(routes, "leg", leg)
    shrine, beef = stop("s-101", "10:40", "Shrine"), stop("s-102", "14:25", "Beef")
    park = stop("s-103", "18:00", "Park")
    shrine.lat, shrine.lng, beef.lat, beef.lng, park.lat, park.lng = 33.19, 130.02, 33.25, 130.02, 33.31, 130.02
    shrine.leg = beef.leg = Leg(mode="WALK", minutes=30)
    plan = Plan(title="t", language="en", days=[Day(day=1, stops=[shrine, beef, park])])

    asyncio.run(pipeline.add_legs(plan, jp_run()))  # a train trip in Japan: no transit data

    leg = shrine.leg
    assert (leg.mode, leg.minutes, leg.estimate, leg.polyline) == ("TRANSIT", 30, True, None)  # car time + 10
    car = pipeline.Run(lang="en", near=None, country="JP", default_mode="DRIVE")
    shrine.leg = Leg(mode="WALK", minutes=30)
    asyncio.run(pipeline.add_legs(plan, car))
    assert (shrine.leg.mode, shrine.leg.minutes, shrine.leg.estimate) == ("DRIVE", 20, False)


def test_transit_keeps_the_planners_line_when_routes_has_none(monkeypatch):
    async def leg(a, b, mode, lang):
        return None

    monkeypatch.setattr(routes, "leg", leg)
    a, b = stop("s-101", "09:00", "Hakata"), stop("s-102", "11:00", "Nagasaki")
    a.lat, a.lng, b.lat, b.lng = 33.59, 130.42, 32.75, 129.87
    a.leg = Leg(mode="TRANSIT", minutes=90, line="Kamome Shinkansen")
    plan = Plan(title="t", language="en", days=[Day(day=1, stops=[a, b])])

    asyncio.run(pipeline.add_legs(plan, jp_run()))

    assert (a.leg.line, a.leg.minutes, a.leg.estimate) == ("Kamome Shinkansen", 90, True)


def test_a_long_walk_instead_of_a_planned_train_keeps_the_planners_train_time(monkeypatch):
    async def leg(a, b, mode, lang):
        return {"WALK": {"minutes": 45, "polyline": "w"}, "DRIVE": {"minutes": 8, "polyline": "d"}}.get(mode)

    monkeypatch.setattr(routes, "leg", leg)
    a, b = stop("s-101", "09:00", "Osaka Castle"), stop("s-102", "12:00", "Kuromon Market")
    a.lat, a.lng, b.lat, b.lng = 34.687, 135.526, 34.672, 135.517  # 1.8 km, but a 45-minute walk
    a.leg = Leg(mode="TRANSIT", minutes=20, line="Osaka Metro Chuo Line")
    plan = Plan(title="t", language="en", days=[Day(day=1, stops=[a, b])])

    asyncio.run(pipeline.add_legs(plan, jp_run()))

    assert (a.leg.mode, a.leg.minutes, a.leg.estimate, a.leg.line) == ("TRANSIT", 20, True, "Osaka Metro Chuo Line")


def test_retime_rounds_every_time_to_five_minutes():
    a, b, c = stop("s-101", "09:02", "A"), stop("s-102", "10:00", "B"), stop("s-103", "18:27", "C")
    a.leg, b.leg = Leg(mode="WALK", minutes=7), Leg(mode="WALK", minutes=3)
    c.kind = "food"  # a meal keeps the Planner's (later) time
    plan = Plan(title="t", language="en", days=[Day(day=1, stops=[a, b, c])])

    pipeline.retime(plan)

    assert [s.time for s in plan.days[0].stops] == ["09:05", "10:15", "18:30"]


def test_one_closed_stop_triggers_a_repair_with_its_opening_hours(monkeypatch):
    log = fake_world(monkeypatch)
    hours = {**OPEN_10_TO_17, "weekdayDescriptions": [f"Day{i}: 10:00 AM - 5:00 PM" for i in range(7)]}
    monkeypatch.setitem(PLACES, "千穂の家", {**PLACES["千穂の家"], "openingHours": hours})

    async def leg(a, b, mode, lang):
        return {"minutes": 5, "polyline": "abc"}  # 09:00 + 60 + 5 -> the restaurant at 10:05 is open...

    monkeypatch.setattr(routes, "leg", leg)
    original = draft_plan

    async def draft(slots, messages, lang):
        plan = original()
        plan.days[0].stops[1].kind = "food"
        plan.days[0].stops[1].time = "17:30"  # ...but a meal keeps the Planner's (closed) time
        return plan

    monkeypatch.setattr(planner, "draft", draft)
    asyncio.run(pipeline.run("t1"))

    closed = [w for w in log["fix"][-1] if "closed" in w]
    assert closed and "Opening hours: Day2: 10:00 AM - 5:00 PM" in closed[0]  # Wednesday, Monday-first list


def test_missing_place_and_closed_stop_share_one_repair_call(monkeypatch):
    log = fake_world(monkeypatch, replace_with="Kurokawa Onsen")
    hours = {**OPEN_10_TO_17, "weekdayDescriptions": [f"Day{i}: 10:00 AM - 5:00 PM" for i in range(7)]}
    monkeypatch.setitem(PLACES, "千穂の家", {**PLACES["千穂の家"], "openingHours": hours})
    original = draft_plan

    async def draft(slots, messages, lang):
        plan = original()
        plan.days[0].stops[1].kind, plan.days[0].stops[1].time = "food", "17:30"  # closed at 17:30
        return plan

    monkeypatch.setattr(planner, "draft", draft)
    asyncio.run(pipeline.run("t1"))

    assert len(log["fix"]) == 1  # one Gemini repair, not one per problem (D6)
    asks = log["fix"][0]
    assert any("Fake Cafe" in a for a in asks) and any("closed" in a for a in asks)
    seen = [s.name for s in log["fix_seen"].days[0].stops]
    assert "Fake Cafe" in seen  # the Planner sees where the missing stop was, to replace it in place
    assert log["fix_seen"].days[0].stops[0].leg.polyline == "abc"  # ...and the real travel times
    assert log["progress"] == ["routes", "videos"]


def test_no_repair_round_late_in_the_request(monkeypatch):
    log = fake_world(monkeypatch)
    monkeypatch.setattr(pipeline, "FIX_BEFORE_S", -1)
    asyncio.run(pipeline.run("t1"))
    assert log["fix"] == []  # Fake Cafe is dropped at once instead
    assert log["saved"].checks == ["Fake Cafe: couldn't be found on Google Maps, so it was removed. Please check."]


def test_cancelled_request_resets_the_status(monkeypatch):
    log = fake_world(monkeypatch)

    async def cancelled(*args):
        raise asyncio.CancelledError

    monkeypatch.setattr(planner, "draft", cancelled)
    try:
        asyncio.run(pipeline.run("t1"))
        raise AssertionError("should raise")
    except asyncio.CancelledError:
        pass
    assert log["status"] == ["error"]


def test_meal_never_moves_earlier_and_late_day_is_flagged():
    plan = draft_plan()
    dinner = plan.days[0].stops[-1]
    dinner.kind, dinner.time = "food", "18:30"
    pipeline.retime(plan)
    assert dinner.time == "18:30"

    plan.days[0].stops[0].stayMinutes = 20 * 60  # way too long: the day would end after midnight
    pipeline.retime(plan)
    found, _ = pipeline.add_warnings(plan, jp_run())
    assert plan.days[0].stops[1].time == "23:55" and "past midnight" in plan.days[0].stops[1].warn
    assert len(found) == 1


def test_hotel_as_a_meal_goes_to_the_replacement_round(monkeypatch):
    ryokan = {
        "placeId": "p-ryokan",
        "name": "Ryokan Sanga",
        "lat": 33.08,
        "lng": 131.14,
        "countryCode": "JP",
        "primaryType": "japanese_inn",
        "types": ["japanese_inn", "lodging", "restaurant"],
    }

    async def search_text(query, lang, near=None):
        return ryokan

    monkeypatch.setattr(places, "search_text", search_text)
    run = jp_run()
    lunch, bath = stop("s-1", "12:00", "Ryokan Sanga"), stop("s-2", "15:00", "Ryokan Sanga")
    lunch.kind, bath.kind = "food", "onsen"
    assert asyncio.run(pipeline._find(lunch, run)) is None
    assert pipeline._ask(1, lunch, run).startswith('Day 1: "Ryokan Sanga" is a hotel or ryokan')
    assert asyncio.run(pipeline._find(bath, run))["placeId"] == "p-ryokan"  # a ryokan's bath is a fine onsen stop


def test_seo_padded_google_name_keeps_gemini_name(monkeypatch):
    found = {"placeId": "p-1", "lat": 43.0, "lng": 141.3, "countryCode": "JP"}
    names = iter(["Sapporo's Secret Onsen Sanctuary Marukoma Onsen Ryokan", "Fushimi Inari Taisha"])

    async def search_text(query, lang, near=None):
        return {**found, "name": next(names)}

    async def local_name(place_id, country):
        return None

    monkeypatch.setattr(places, "search_text", search_text)
    monkeypatch.setattr(places, "local_name", local_name)
    spa, shrine = stop("s-1", "09:00", "Marukoma Onsen Ryokan"), stop("s-2", "09:00", "Fushimi Inari Shrine")
    spa.kind = "onsen"
    asyncio.run(pipeline._verify_stop(spa, jp_run()))
    asyncio.run(pipeline._verify_stop(shrine, jp_run()))
    assert spa.name == "Marukoma Onsen Ryokan"  # Google's name is SEO padding
    assert shrine.name == "Fushimi Inari Taisha"  # same place, official name


def test_budget_check_when_the_estimate_may_exceed_it():
    from app.models import Cost, Slots

    run = jp_run()
    slots = Slots.model_validate({"budget": {"basis": "person", "amount": 30000, "currency": "JPY"}})
    plan = draft_plan()
    plan.cost = Cost(basis="person", min=25000, max=35000)
    pipeline.check_cost(plan, slots, run)
    assert plan.checks == ["The estimate (35,000 JPY) may exceed your budget (30,000 JPY). Please check."]
    pipeline.check_cost(plan, slots, run)
    assert len(plan.checks) == 1  # already mentioned

    plan.checks, plan.cost.basis = [], "total"
    pipeline.check_cost(plan, slots, run)
    assert plan.checks == []  # different basis: can't compare
    plan.cost.basis, plan.cost.max = "person", 30000
    pipeline.check_cost(plan, slots, run)
    assert plan.checks == []  # within budget

    ja = pipeline.Run(lang="ja", near=None, country="JP", default_mode="TRANSIT")
    plan.cost.max = 40000
    pipeline.check_cost(plan, slots, ja)
    assert plan.checks[0].startswith("見積もり（最大40,000 JPY）がご予算（30,000 JPY）を超える")


# ---------- Plan updates (D27) ----------

UPDATE_SLOTS = {
    "dest": {**KYUSHU, "placeId": "p-kyushu"},
    "transport": ["car"],
    "dates": {"start": "2027-03-10", "end": "2027-03-11"},
    "budget": {"basis": "person", "amount": 50000, "currency": "JPY"},
}
ASO = {"placeId": "p-aso", "name": "Aso Shrine", "lat": 32.94, "lng": 131.12, "countryCode": "JP"}
BY_ID = {p["placeId"]: p for p in [*PLACES.values(), ASO]}


def verified(sid, time, name, place, leg=None):
    return Stop(
        id=sid,
        time=time,
        name=name,
        nameLocal=name,
        placeId=place["placeId"],
        lat=place["lat"],
        lng=place["lng"],
        videoIds=[f"vid-{place['placeId']}"],
        leg=leg,
    )


def saved_plan():
    """A 2-day plan as the pipeline saved it: real places and legs."""
    real = Leg(mode="DRIVE", minutes=50, polyline="abc")
    walk = Leg(mode="WALK", minutes=10, polyline="abc")  # gorge -> restaurant is under 1 km
    return Plan(
        title="Test",
        language="en",
        days=[
            Day(
                day=1,
                date="2027-03-10",
                stops=[
                    verified("s-101", "09:00", "Takachiho Gorge", PLACES["高千穂峡"], walk),
                    verified("s-102", "10:00", "Chiho no Ie", PLACES["千穂の家"]),
                ],
            ),
            Day(
                day=2,
                date="2027-03-11",
                stops=[
                    verified("s-201", "09:00", "Kurokawa Onsen", PLACES["Kurokawa Onsen"], real),
                    verified("s-202", "11:00", "Takachiho Gorge", PLACES["高千穂峡"]),
                ],
            ),
        ],
    )


def update_world(monkeypatch, slots, snapshot=UPDATE_SLOTS, out=None, pending=None):
    log = {"search": [], "by_id": [], "routes": [], "videos": [], "revise": [], "run": [], "saved": None}
    old = saved_plan()

    async def get_trip(trip_id):
        return {"language": "en", "slots": slots, "currentPlanId": "plan-0", "pendingEdits": pending or []}

    async def get_plan(trip_id, plan_id):
        doc = {"plan": old.model_dump(mode="json"), "version": 1}
        return {**doc, "slots": snapshot} if snapshot else doc

    async def update_trip(trip_id, data):
        pass

    async def save_plan(trip_id, plan, reason="initial", slots=None):
        log["saved"], log["reason"], log["snapshot"] = plan, reason, slots
        return "plan-2"

    async def revise(plan, changes, requests, slots, lang):
        log["revise"].append((changes, requests))
        return out or PlanUpdate(days=[])

    async def search_text(query, lang, near=None):
        log["search"].append(query)
        return {**PLACES, "Aso Shrine": ASO}.get(query)

    async def by_id(place_id, lang):
        log["by_id"].append(place_id)
        return BY_ID.get(place_id)

    async def leg(a, b, mode, lang):
        log["routes"].append((a, b))
        return {"minutes": 40, "polyline": "new"}

    async def cached(place_id):
        return None if place_id == "p-aso" else [f"vid-{place_id}"]

    async def shorts_for(place_id, *args, **kw):
        log["videos"].append(place_id)
        return [f"vid-{place_id}"]

    async def local_name(place_id, country):
        return None

    async def fix(plan, warnings, lang):
        log.setdefault("fix", []).append(warnings)
        return plan.model_copy(deep=True)

    async def full_run(trip_id, reason="initial"):
        log["run"].append(reason)
        return "plan-full"

    for target, name, fn in [
        (fs, "get_trip", get_trip),
        (fs, "get_plan", get_plan),
        (fs, "update_trip", update_trip),
        (fs, "save_plan", save_plan),
        (planner, "revise", revise),
        (planner, "fix", fix),
        (places, "search_text", search_text),
        (places, "by_id", by_id),
        (places, "local_name", local_name),
        (routes, "leg", leg),
        (youtube, "cached", cached),
        (youtube, "shorts_for", shorts_for),
        (pipeline, "run", full_run),
    ]:
        monkeypatch.setattr(target, name, fn)
    return log, old


def test_budget_only_update_checks_nothing_again(monkeypatch):
    slots = {**UPDATE_SLOTS, "budget": {"basis": "person", "amount": 80000, "currency": "JPY"}}
    log, old = update_world(monkeypatch, slots, out=PlanUpdate(days=[], cost=Cost(min=60000, max=70000)))

    assert asyncio.run(pipeline.update("t1")) == "plan-2"

    assert log["revise"][0][0][0].startswith("Budget: ")
    assert log["search"] == log["by_id"] == log["routes"] == log["videos"] == [] and log["run"] == []
    assert log["saved"].days == old.days and log["saved"].cost.max == 70000
    assert log["reason"] == "update" and log["snapshot"]["budget"]["amount"] == 80000


def test_one_day_update_checks_only_that_day(monkeypatch):
    kept = saved_plan().days[1].stops[0].model_copy(update={"placeId": None, "videoIds": []})
    aso = Stop(id="x", time="11:00", name="Aso Shrine", lat=32.94, lng=131.12)
    out = PlanUpdate(days=[DayFix(day=2, stops=[kept, aso])])
    log, old = update_world(monkeypatch, UPDATE_SLOTS, out=out, pending=["make day 2 calmer"])

    asyncio.run(pipeline.update("t1"))

    assert log["revise"] == [([], ["make day 2 calmer"])]
    assert log["search"] == ["Aso Shrine"]  # only the new stop is searched
    assert log["by_id"] == ["p-onsen"]  # the kept stop is looked up by id, day 1 not at all
    assert len(log["routes"]) == 1  # onsen -> shrine; day 1's leg is never asked again
    assert log["videos"] == ["p-aso"]
    plan = log["saved"]
    assert plan.days[0] == old.days[0]
    assert [(s.name, s.placeId) for s in plan.days[1].stops] == [("Kurokawa Onsen", "p-onsen"), ("Aso Shrine", "p-aso")]
    assert plan.days[1].stops[0].leg.polyline == "new" and plan.days[1].stops[1].leg is None


def test_date_shift_reuses_every_route(monkeypatch):
    slots = {**UPDATE_SLOTS, "dates": {"start": "2027-03-17", "end": "2027-03-18"}}  # a week later, same weekdays
    log, _ = update_world(monkeypatch, slots)
    asyncio.run(pipeline.update("t1"))
    assert [d.date for d in log["saved"].days] == ["2027-03-17", "2027-03-18"]
    assert sorted(log["by_id"]) == ["p-food", "p-gorge", "p-onsen"]  # opening hours for the new dates
    assert log["routes"] == [] and log["search"] == [] and "fix" not in log  # routes come from the old plan


def test_date_shift_onto_a_closed_day_repairs_it(monkeypatch):
    slots = {**UPDATE_SLOTS, "dates": {"start": "2027-03-12", "end": "2027-03-13"}}  # Friday: the restaurant is shut
    log, _ = update_world(monkeypatch, slots)
    asyncio.run(pipeline.update("t1"))
    assert "Chiho no Ie" in log["fix"][0][0] and "May be closed" in log["fix"][0][0]


def test_destination_change_rebuilds_the_whole_plan(monkeypatch):
    slots = {**UPDATE_SLOTS, "dest": {"label": "Hokkaido", "placeId": "p-hokkaido", "countryCode": "JP"}}
    log, _ = update_world(monkeypatch, slots)
    assert asyncio.run(pipeline.update("t1")) == "plan-full"
    assert log["run"] == ["update"] and log["revise"] == []


def test_plan_without_a_snapshot_rebuilds_the_whole_plan(monkeypatch):
    log, _ = update_world(monkeypatch, UPDATE_SLOTS, snapshot=None)
    assert asyncio.run(pipeline.update("t1")) == "plan-full"
    assert log["run"] == ["update"] and log["revise"] == []


def test_update_with_a_missing_day_rebuilds_the_whole_plan(monkeypatch):
    slots = {**UPDATE_SLOTS, "dates": {"start": "2027-03-10", "end": "2027-03-12"}}  # 3 days, no day 3 returned
    log, _ = update_world(monkeypatch, slots)
    assert asyncio.run(pipeline.update("t1")) == "plan-full"
    assert log["saved"] is None
