"""YouTube Shorts service with faked HTTP and cache (no network, no quota)."""

import asyncio
from datetime import timedelta
from types import SimpleNamespace

import httpx
import pytest
from pydantic import SecretStr

from app.services import firestore, youtube

SEARCH = {
    "items": [
        {"id": {"videoId": "v1"}, "snippet": {"title": "Kyushu trip vlog"}},
        {"id": {"videoId": "v2"}, "snippet": {"title": "高千穂峡 ボート #shorts"}},
        {"id": {"videoId": "v3"}, "snippet": {"title": "Kids song"}},
        {"id": {"videoId": "v4"}, "snippet": {"title": "Japan in 60 s"}},
    ]
}
STATUS = {"items": [{"id": "v3", "status": {"madeForKids": True}}, {"id": "v1", "status": {"madeForKids": False}}]}


@pytest.fixture
def world(monkeypatch):
    state = {"cache": {}, "calls": [], "search": lambda: httpx.Response(200, json=SEARCH)}

    async def cache_get(name, key):
        return state["cache"].get((name, key))

    async def cache_set(name, key, data):
        state["cache"][(name, key)] = {**data, "fetchedAt": firestore.now()}

    def handler(request):
        state["calls"].append(request)
        return state["search"]() if request.url.path.endswith("/search") else httpx.Response(200, json=STATUS)

    monkeypatch.setattr(firestore, "cache_get", cache_get)
    monkeypatch.setattr(firestore, "cache_set", cache_set)
    monkeypatch.setattr(youtube, "_client", httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(youtube, "get_settings", lambda: SimpleNamespace(youtube_api_key=SecretStr("test-key")))
    return state


def test_ranks_by_name_drops_kids_videos_and_caches(world):
    ids = asyncio.run(youtube.shorts_for("p1", "高千穂峡", "JP"))

    assert ids == ["v2", "v1", "v4"]  # title with the name first; v3 is Made for Kids
    search = world["calls"][0].url.params
    assert search["q"] == "高千穂峡 shorts" and search["regionCode"] == "JP" and search["videoDuration"] == "short"
    assert "relevanceLanguage" not in search
    assert world["cache"][("videos", "p1")]["videoIds"] == ["v2", "v1", "v4"]

    assert asyncio.run(youtube.shorts_for("p1", "高千穂峡", "JP")) == ids
    assert len(world["calls"]) == 2  # the second call came from the cache: no new search


def test_stale_cache_searches_again(world):
    world["cache"][("videos", "p1")] = {"videoIds": ["old"], "fetchedAt": firestore.now() - timedelta(days=8)}
    assert asyncio.run(youtube.shorts_for("p1", "高千穂峡", "JP")) == ["v2", "v1", "v4"]


def test_quota_error_returns_empty_and_is_not_cached(world):
    world["search"] = lambda: httpx.Response(403, json={"error": {"errors": [{"reason": "quotaExceeded"}]}})
    assert asyncio.run(youtube.shorts_for("p1", "高千穂峡", "JP")) == []
    assert world["cache"] == {}


def test_no_results_are_cached_too(world):
    world["search"] = lambda: httpx.Response(200, json={"items": []})
    assert asyncio.run(youtube.shorts_for("p1", "Tiny shrine", "JP")) == []
    assert world["cache"][("videos", "p1")]["videoIds"] == []
    assert len(world["calls"]) == 1  # no status call for an empty result


def test_missing_key_or_place_returns_empty(world, monkeypatch):
    assert asyncio.run(youtube.shorts_for("", "高千穂峡", "JP")) == []
    monkeypatch.setattr(youtube, "get_settings", lambda: SimpleNamespace(youtube_api_key=SecretStr(" ")))
    assert asyncio.run(youtube.shorts_for("p1", "高千穂峡", "JP")) == []
    assert world["calls"] == []
