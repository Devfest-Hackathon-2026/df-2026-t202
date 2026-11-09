"""Endpoint + Firestore helper tests against the Firestore emulator.

Run:  firebase emulators:exec --only firestore --project demo-trip-planner ".venv/bin/pytest -q"
(from api/; skipped when FIRESTORE_EMULATOR_HOST is not set). Gemini and Places are mocked.
"""

import os

import httpx
import pytest

from app import flow
from app.agents import concierge
from app.auth import require_user
from app.main import app
from app.models import ConciergeOutput, Day, PlaceRef, Plan, Stop
from app.services import firestore as fs
from app.services.llm import LLMError
from tests.test_flow import DEMO_ANSWERS

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.skipif(not os.getenv("FIRESTORE_EMULATOR_HOST"), reason="needs the Firestore emulator"),
]

OWNER, FRIEND = "owner-uid", "friend-uid"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
async def clean_db():
    fs.db.cache_clear()  # the async client is bound to the event loop of each test
    yield
    async with httpx.AsyncClient() as http:
        host = os.environ["FIRESTORE_EMULATOR_HOST"]
        await http.delete(f"http://{host}/emulator/v1/projects/demo-trip-planner/databases/(default)/documents")
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def no_places(monkeypatch):
    """Card answers look up the destination with Places. Tests never call Google; some tests set their own."""

    async def not_found(query, lang):
        return None

    monkeypatch.setattr(flow, "search_place", not_found)


def as_user(uid: str) -> None:
    app.dependency_overrides[require_user] = lambda: uid


@pytest.fixture
async def api():
    as_user(OWNER)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def new_trip(api, lang="en") -> str:
    resp = await api.post("/trips", json={"language": lang})
    assert resp.status_code == 200, resp.text
    return resp.json()["tripId"]


async def answer(api, trip_id, step, value):
    return await api.post(f"/trips/{trip_id}/messages", json={"type": "answer", "step": step, "value": value})


# ---------- trips + card answers ----------


async def test_create_trip_writes_trip_and_first_question(api):
    trip_id = await new_trip(api, "ja")
    trip = await fs.get_trip(trip_id)
    assert trip["members"] == {OWNER: "owner"} and trip["asking"] == "dest" and trip["status"] == "chatting"
    msgs = await fs.list_messages(trip_id)
    assert len(msgs) == 1 and msgs[0]["text"] == "どこに行きたいですか？" and msgs[0]["ui"]["type"] == "dest"


async def test_card_answers_reach_ready_with_demo_slots(api):
    trip_id = await new_trip(api)
    for step, value in DEMO_ANSWERS:
        resp = await answer(api, trip_id, step, value)
        assert resp.status_code == 200, resp.text
    assert resp.json() == {"asking": "ready"}
    trip = await fs.get_trip(trip_id)
    assert trip["slots"]["budget"] == {"basis": "person", "amount": 50000, "currency": "JPY"}
    msgs = await fs.list_messages(trip_id)
    assert [m["role"] for m in msgs[:3]] == ["ai", "user", "ai"]  # ordered by createdAt
    assert msgs[-1]["ui"]["type"] == "ready"


async def test_future_step_is_rejected_and_repeat_tap_is_ignored(api):
    trip_id = await new_trip(api)
    assert (await answer(api, trip_id, "budget", {"amount": 1})).status_code == 409
    await answer(api, trip_id, "dest", {"label": "Kyushu", "countryCode": "JP"})
    count = len(await fs.list_messages(trip_id))
    resp = await answer(api, trip_id, "dest", {"label": "Kyushu", "countryCode": "JP"})  # double tap
    assert resp.json() == {"asking": "dates"}
    assert len(await fs.list_messages(trip_id)) == count


async def test_bad_answer_is_400(api):
    trip_id = await new_trip(api)
    resp = await answer(api, trip_id, "dest", {"countryCode": "JP"})
    assert resp.status_code == 400 and resp.json() == {"detail": "invalid_answer"}  # no input echoed


async def test_answer_is_stored_normalized_and_counted(api):
    trip_id = await new_trip(api)
    assert (await fs.get_trip(trip_id))["messageCount"] == 1
    await answer(api, trip_id, "dest", {"label": "  " + "K" * 300, "countryCode": "JP", "extra": "x"})
    await answer(api, trip_id, "dates", "skip")
    msgs = await fs.list_messages(trip_id)
    assert msgs[1]["answer"] == {"step": "dest", "value": {**KYUSHU_NONE, "label": "K" * flow.MAX_ITEM_LENGTH}}
    assert msgs[3]["answer"] == {"step": "dates", "value": "skip"}
    assert (await fs.get_trip(trip_id))["messageCount"] == 5 == len(msgs)


async def test_message_limit_is_429(api, monkeypatch):
    called = []

    async def fake_run(*args):
        called.append(1)
        return ConciergeOutput.model_validate({"updates": {}})

    monkeypatch.setattr(concierge, "run", fake_run)
    trip_id = await new_trip(api)
    await fs.db().collection("trips").document(trip_id).update({"messageCount": 59})
    resp = await api.post(f"/trips/{trip_id}/messages", json={"type": "text", "text": "hi"})
    assert resp.status_code == 429 and not called  # rejected before Gemini
    assert (await answer(api, trip_id, "dest", {"label": "Kyushu"})).status_code == 429


async def test_edit_after_plan_offers_rebuild(api):
    trip_id = await new_trip(api)
    for step, value in DEMO_ANSWERS:
        await answer(api, trip_id, step, value)
    await fs.save_plan(trip_id, tiny_plan())
    resp = await answer(api, trip_id, "people", {"adult": 2})
    assert resp.json() == {"asking": "ready"}
    msgs = await fs.list_messages(trip_id)
    assert msgs[-1]["text"] == "Updated. Build the plan again?"
    assert (await fs.get_trip(trip_id))["currentPlanId"]


async def test_non_member_gets_403(api):
    trip_id = await new_trip(api)
    as_user(FRIEND)
    assert (await answer(api, trip_id, "dest", {"label": "x"})).status_code == 403
    assert (await api.post("/trips/missing/messages", json={"type": "text", "text": "hi"})).status_code == 404


# ---------- free text (Concierge mocked) ----------


async def test_free_text_fills_several_steps(api, monkeypatch):
    async def fake_run(slots, step, text, lang):
        return ConciergeOutput.model_validate(
            {
                "updates": {"dest": "Kyushu", "people": {"adult": 4}, "budget": {"basis": "person", "amount": 50000}},
                "comment": "Great! March is a good season for onsen.",
            }
        )

    async def fake_search(query, lang):
        return PlaceRef.model_validate(KYUSHU_REF)

    monkeypatch.setattr(concierge, "run", fake_run)
    monkeypatch.setattr(flow, "search_place", fake_search)
    trip_id = await new_trip(api)
    resp = await api.post(f"/trips/{trip_id}/messages", json={"type": "text", "text": "Kyushu, 4 people, 50k yen"})
    assert resp.json() == {"asking": "dates"}
    slots = (await fs.get_trip(trip_id))["slots"]
    assert slots["people"]["adult"] == 4 and slots["budget"]["currency"] == "JPY"
    msgs = await fs.list_messages(trip_id)
    assert msgs[-1]["text"].startswith("Great!") and msgs[-1]["ui"]["type"] == "dates"


async def test_place_not_found_asks_back(api, monkeypatch):
    async def fake_run(slots, step, text, lang):
        return ConciergeOutput.model_validate({"updates": {"dest": "Atlantis"}, "comment": "Nice!"})

    async def no_place(query, lang):
        return None

    monkeypatch.setattr(concierge, "run", fake_run)
    monkeypatch.setattr(flow, "search_place", no_place)
    trip_id = await new_trip(api)
    resp = await api.post(f"/trips/{trip_id}/messages", json={"type": "text", "text": "Atlantis"})
    assert resp.json() == {"asking": "dest"}
    last = (await fs.list_messages(trip_id))[-1]
    assert "couldn't find" in last["text"] and last["ui"]["type"] == "dest"


async def test_unresolved_dest_change_drops_the_claiming_comment(api, monkeypatch):
    async def fake_run(slots, step, text, lang):
        return ConciergeOutput.model_validate(
            {"updates": {"dest": "Hokaido"}, "comment": "Changing to Hokkaido!", "clarify": "Which part?"}
        )

    async def no_place(query, lang):
        return None

    trip_id = await new_trip(api)
    await answer(api, trip_id, "dest", KYUSHU_REF)
    monkeypatch.setattr(concierge, "run", fake_run)
    monkeypatch.setattr(flow, "search_place", no_place)
    resp = await api.post(f"/trips/{trip_id}/messages", json={"type": "text", "text": "go to hokaido instead"})
    assert resp.json() == {"asking": "dates"}
    last = (await fs.list_messages(trip_id))[-1]
    assert last["text"] == flow.text_for("place_not_found", "en")  # no "Changing to Hokkaido!"
    assert (await fs.get_trip(trip_id))["slots"]["dest"]["label"] == KYUSHU_REF["label"]


async def test_places_failure_asks_again_no_500(api, monkeypatch):
    async def fake_run(slots, step, text, lang):
        return ConciergeOutput.model_validate({"updates": {"dest": "Kyushu", "people": {"adult": 4}}})

    async def broken_places(query, lang):
        raise flow.PlaceLookupError

    monkeypatch.setattr(concierge, "run", fake_run)
    monkeypatch.setattr(flow, "search_place", broken_places)
    trip_id = await new_trip(api, "ja")
    resp = await api.post(f"/trips/{trip_id}/messages", json={"type": "text", "text": "九州に4人で"})
    assert resp.status_code == 200 and resp.json() == {"asking": "dest"}
    last = (await fs.list_messages(trip_id))[-1]
    assert "もう一度" in last["text"] and last["ui"]["type"] == "dest"
    assert (await fs.get_trip(trip_id))["slots"]["people"]["adult"] == 4  # other updates kept


async def test_gemini_failure_gives_friendly_fallback(api, monkeypatch):
    async def broken(*args):
        raise LLMError("quota")

    monkeypatch.setattr(concierge, "run", broken)
    trip_id = await new_trip(api, "ja")
    resp = await api.post(f"/trips/{trip_id}/messages", json={"type": "text", "text": "九州"})
    assert resp.status_code == 200 and resp.json() == {"asking": "dest"}
    last = (await fs.list_messages(trip_id))[-1]
    assert last["text"] == flow.text_for("fallback", "ja") and last["ui"]["type"] == "dest"


# ---------- share + join ----------


async def test_share_and_join_as_viewer(api):
    trip_id = await new_trip(api)
    share_id = (await api.post(f"/trips/{trip_id}/share")).json()["shareId"]
    assert len(share_id) >= 22
    assert (await api.post(f"/trips/{trip_id}/share")).json()["shareId"] == share_id  # same link again

    as_user(FRIEND)
    assert (await api.post(f"/trips/{trip_id}/share")).status_code == 403
    assert (await api.post(f"/shares/{share_id}/join")).json() == {"tripId": trip_id}
    assert (await fs.get_trip(trip_id))["members"] == {OWNER: "owner", FRIEND: "viewer"}
    assert (await answer(api, trip_id, "dest", {"label": "x"})).status_code == 403  # viewers can't chat

    as_user(OWNER)
    await api.post(f"/shares/{share_id}/join")
    assert (await fs.get_trip(trip_id))["members"][OWNER] == "owner"  # never downgraded
    assert (await api.post("/shares/nope/join")).status_code == 404


# ---------- helpers Person B uses ----------


def tiny_plan() -> Plan:
    stop = Stop(id="s-101", time="09:00", name="Hakata Station")
    return Plan(title="Test", language="en", days=[Day(day=1, stops=[stop])])


async def test_save_plan_versions(api):
    trip_id = await new_trip(api)
    first = await fs.save_plan(trip_id, tiny_plan())
    second = await fs.save_plan(trip_id, tiny_plan(), reason="edit")
    trip = await fs.get_trip(trip_id)
    assert trip["currentPlanId"] == second != first
    assert trip["status"] == "ready" and trip["progress"] == "done"
    plans = fs.db().collection("trips").document(trip_id).collection("plans")
    versions = sorted([(await plans.document(pid).get()).get("version") for pid in (first, second)])
    assert versions == [1, 2]


async def test_cache_round_trip():
    assert await fs.cache_get("places", "k") is None
    await fs.cache_set("places", "k", {"placeId": "p1"})
    cached = await fs.cache_get("places", "k")
    assert cached["placeId"] == "p1" and "fetchedAt" in cached
    with pytest.raises(ValueError):
        await fs.cache_get("other", "k")


async def test_limits(monkeypatch):
    from app.services import limits

    monkeypatch.setattr(limits.get_settings(), "max_plans_per_user_per_day", 2)
    await limits.check_plan_limit(OWNER)
    await limits.check_plan_limit(OWNER)
    with pytest.raises(Exception) as exc:
        await limits.check_plan_limit(OWNER)
    assert exc.value.status_code == 429


KYUSHU_NONE = {"placeId": None, "countryCode": "JP", "lat": None, "lng": None}
KYUSHU_REF = {"label": "Kyushu, Japan", "placeId": "test-place", "countryCode": "JP", "lat": 32.59, "lng": 130.8}
