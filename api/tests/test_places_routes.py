"""Places and Routes services with faked HTTP and cache (no network)."""

import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest
from pydantic import SecretStr

from app.models import PlaceRef
from app.services import firestore, places, routes

FAKE_SETTINGS = SimpleNamespace(places_api_key=SecretStr("test-key"), routes_api_key=SecretStr("test-key"))

TAKACHIHO = {
    "id": "ChIJ-takachiho",
    "displayName": {"text": "Takachiho Gorge", "languageCode": "en"},
    "location": {"latitude": 32.7027, "longitude": 131.3007},
    "addressComponents": [
        {"longText": "Miyazaki", "shortText": "Miyazaki", "types": ["administrative_area_level_1", "political"]},
        {"longText": "Japan", "shortText": "JP", "types": ["country", "political"]},
    ],
}


@pytest.fixture
def cache(monkeypatch):
    """In-memory stand-in for Person A's firestore.cache_get / cache_set."""
    store: dict = {}

    async def cache_get(name, key):
        return store.get((name, key))

    async def cache_set(name, key, data):
        store[(name, key)] = data

    monkeypatch.setattr(firestore, "cache_get", cache_get, raising=False)
    monkeypatch.setattr(firestore, "cache_set", cache_set, raising=False)
    return store


def fake_http(monkeypatch, module, handler):
    """Route the module's httpx client to `handler` and record each request."""
    calls: list[httpx.Request] = []

    def record(request):
        calls.append(request)
        return handler(request)

    monkeypatch.setattr(module, "_client", httpx.AsyncClient(transport=httpx.MockTransport(record)))
    monkeypatch.setattr(module, "get_settings", lambda: FAKE_SETTINGS)
    return calls


def places_api(request: httpx.Request) -> httpx.Response:
    """Fake Places: POST = Text Search, GET = Place Details."""
    if request.method == "POST":
        return httpx.Response(200, json={"places": [TAKACHIHO]})
    return httpx.Response(200, json=TAKACHIHO)


def test_search_text_parses_result(monkeypatch, cache):
    calls = fake_http(monkeypatch, places, places_api)

    out = asyncio.run(places.search_text("Takachiho Gorge", "en", near=(32.59, 130.8)))

    assert out["placeId"] == "ChIJ-takachiho"
    assert out["name"] == out["label"] == "Takachiho Gorge"
    assert out["countryCode"] == "JP"
    assert (out["lat"], out["lng"]) == (32.7027, 131.3007)
    req = calls[0]
    assert req.headers["X-Goog-FieldMask"] == (
        "places.id,places.displayName,places.location,places.regularOpeningHours,places.addressComponents"
    )
    body = json.loads(req.content)
    assert body["languageCode"] == "en"
    assert body["locationBias"]["circle"]["radius"] <= 50_000


def test_result_fits_person_a_placeref(monkeypatch, cache):
    fake_http(monkeypatch, places, places_api)
    ref = PlaceRef.model_validate(asyncio.run(places.search_text("Kyushu", "en")))
    assert ref.label == "Takachiho Gorge" and ref.countryCode == "JP"


def test_cache_keeps_only_place_id(monkeypatch, cache):
    calls = fake_http(monkeypatch, places, places_api)

    first = asyncio.run(places.search_text("Takachiho Gorge", "en"))
    second = asyncio.run(places.search_text("Takachiho Gorge", "en"))

    assert first == second
    assert list(cache.values()) == [{"query": "Takachiho Gorge", "placeId": "ChIJ-takachiho"}]  # no names or coords
    assert [c.method for c in calls] == ["POST", "GET"]  # second run: fresh details by ID, no new search
    assert calls[1].url.path == "/v1/places/ChIJ-takachiho"


def test_cached_place_gone_falls_back_to_search(monkeypatch, cache):
    calls = fake_http(
        monkeypatch,
        places,
        lambda r: httpx.Response(404) if r.method == "GET" else httpx.Response(200, json={"places": [TAKACHIHO]}),
    )
    asyncio.run(places.search_text("Takachiho Gorge", "en"))
    assert asyncio.run(places.search_text("Takachiho Gorge", "en"))["placeId"] == "ChIJ-takachiho"
    assert [c.method for c in calls] == ["POST", "GET", "POST"]


def test_broken_cache_is_skipped(monkeypatch):
    async def broken(*args):
        raise RuntimeError("firestore down")

    monkeypatch.setattr(firestore, "cache_get", broken)
    monkeypatch.setattr(firestore, "cache_set", broken)
    fake_http(monkeypatch, places, places_api)

    assert asyncio.run(places.search_text("Takachiho Gorge", "en"))["placeId"] == "ChIJ-takachiho"


def test_long_query_is_cut(monkeypatch, cache):
    calls = fake_http(monkeypatch, places, places_api)
    asyncio.run(places.search_text("x" * 1000, "en"))
    assert len(json.loads(calls[0].content)["textQuery"]) == 200


def test_search_text_not_found(monkeypatch, cache):
    fake_http(monkeypatch, places, lambda r: httpx.Response(200, json={}))
    assert asyncio.run(places.search_text("Nowhere at all", "en")) is None


def test_search_text_bad_key_fails_without_retry(monkeypatch, cache):
    calls = fake_http(monkeypatch, places, lambda r: httpx.Response(403, json={"error": {}}))
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(places.search_text("Takachiho Gorge", "en"))
    assert len(calls) == 1  # retrying can't fix a bad key


def test_search_text_retries_once_on_temporary_error(monkeypatch, cache):
    monkeypatch.setattr(places, "RETRY_DELAY_S", 0)
    replies = iter([httpx.Response(503), httpx.Response(200, json={"places": [TAKACHIHO]})])
    calls = fake_http(monkeypatch, places, lambda r: next(replies))

    assert asyncio.run(places.search_text("Takachiho Gorge", "en"))["placeId"] == "ChIJ-takachiho"
    assert len(calls) == 2


def test_search_text_fails_after_second_temporary_error(monkeypatch, cache):
    monkeypatch.setattr(places, "RETRY_DELAY_S", 0)
    calls = fake_http(monkeypatch, places, lambda r: httpx.Response(503))
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(places.search_text("Takachiho Gorge", "en"))
    assert len(calls) == 2


def test_local_name_uses_destination_language(monkeypatch, cache):
    calls = fake_http(monkeypatch, places, lambda r: httpx.Response(200, json={"displayName": {"text": "高千穂峡"}}))

    assert asyncio.run(places.local_name("ChIJ-takachiho", "JP")) == "高千穂峡"
    assert calls[0].url.params["languageCode"] == "ja"
    assert calls[0].headers["X-Goog-FieldMask"] == "displayName"
    assert cache == {}  # names are never cached


def test_local_name_defaults_to_english(monkeypatch, cache):
    calls = fake_http(monkeypatch, places, lambda r: httpx.Response(200, json={"displayName": {"text": "X"}}))
    asyncio.run(places.local_name("id", "BR"))
    assert calls[0].url.params["languageCode"] == "en"


def test_empty_key_is_reported_as_missing(monkeypatch, cache):
    empty = SimpleNamespace(places_api_key=SecretStr(""), routes_api_key=SecretStr("  "))
    calls = fake_http(monkeypatch, places, places_api)
    fake_http(monkeypatch, routes, lambda r: httpx.Response(200))
    monkeypatch.setattr(places, "get_settings", lambda: empty)
    monkeypatch.setattr(routes, "get_settings", lambda: empty)

    with pytest.raises(RuntimeError, match="places_api_key_missing"):
        asyncio.run(places.search_text("Takachiho Gorge", "en"))
    with pytest.raises(RuntimeError, match="routes_api_key_missing"):
        asyncio.run(routes.leg((0, 0), (1, 1), "DRIVE", "en"))
    assert calls == []  # nothing is sent to Google without a key


def test_duration_minutes():
    assert routes.duration_minutes("7260s") == 121
    assert routes.duration_minutes("61s") == 2
    assert routes.duration_minutes("0s") == 1


def test_leg_drive(monkeypatch):
    route = {"routes": [{"duration": "7260s", "polyline": {"encodedPolyline": "abc"}}]}
    calls = fake_http(monkeypatch, routes, lambda r: httpx.Response(200, json=route))

    out = asyncio.run(routes.leg((32.70, 131.30), (33.06, 131.11), "DRIVE", "en"))

    assert out == {"minutes": 121, "polyline": "abc"}
    body = json.loads(calls[0].content)
    assert body["travelMode"] == "DRIVE"
    assert body["routingPreference"] == "TRAFFIC_UNAWARE"


def test_leg_transit_has_no_routing_preference(monkeypatch):
    calls = fake_http(monkeypatch, routes, lambda r: httpx.Response(200, json={"routes": [{"duration": "600s"}]}))
    out = asyncio.run(routes.leg((0, 0), (1, 1), "TRANSIT", "ja"))
    assert out == {"minutes": 10, "polyline": None}
    assert "routingPreference" not in json.loads(calls[0].content)


def test_leg_no_route_or_error_returns_none(monkeypatch):
    fake_http(monkeypatch, routes, lambda r: httpx.Response(200, json={}))
    assert asyncio.run(routes.leg((0, 0), (1, 1), "TRANSIT", "en")) is None

    fake_http(monkeypatch, routes, lambda r: httpx.Response(400, json={"error": {}}))
    assert asyncio.run(routes.leg((0, 0), (1, 1), "DRIVE", "en")) is None


def test_leg_skips_flight_and_ferry(monkeypatch):
    calls = fake_http(monkeypatch, routes, lambda r: httpx.Response(500))
    assert asyncio.run(routes.leg((0, 0), (1, 1), "FLIGHT", "en")) is None
    assert asyncio.run(routes.leg((0, 0), (1, 1), "FERRY", "en")) is None
    assert calls == []
