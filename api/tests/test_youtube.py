"""YouTube Shorts service with faked HTTP and cache (no network, no quota)."""

import asyncio
from datetime import timedelta
from types import SimpleNamespace

import httpx
import pytest
from pydantic import SecretStr

from app.services import firestore, places, youtube

SEARCH = {
    "items": [
        {"id": {"videoId": "v1"}, "snippet": {"title": "Kyushu trip vlog: Takachiho"}},
        {"id": {"videoId": "v2"}, "snippet": {"title": "高千穂峡 ボート #shorts"}},
        {"id": {"videoId": "v3"}, "snippet": {"title": "Kids song at Takachiho"}},
        {"id": {"videoId": "v4"}, "snippet": {"title": "Japan in 60 s"}},
        {"id": {"videoId": "v5"}, "snippet": {"title": "宮崎の絶景 高千穂峡"}},
    ]
}
# videos.list answers (title, description, tags, views, Made for Kids). Ids not listed come back with no details.
DETAILS = {
    "v1": {"snippet": {"title": "Kyushu trip vlog: Takachiho"}, "statistics": {"viewCount": "500"}},
    "v2": {"snippet": {"title": "高千穂峡 ボート #shorts"}, "statistics": {"viewCount": "90000"}},
    "v3": {"status": {"madeForKids": True}},
    "v5": {"snippet": {"title": "高千穂峡", "description": "#宮崎旅行"}, "statistics": {"viewCount": "2000"}},
}


@pytest.fixture
def world(monkeypatch):
    state = {"cache": {}, "calls": [], "search": lambda: httpx.Response(200, json=SEARCH), "gone": set()}

    async def cache_get(name, key):
        return state["cache"].get((name, key))

    async def cache_set(name, key, data):
        state["cache"][(name, key)] = {**data, "fetchedAt": firestore.now()}

    def handler(request):
        state["calls"].append(request)
        if request.url.path.endswith("/search"):
            return state["search"]()
        ids = [i for i in request.url.params["id"].split(",") if i not in state["gone"]]
        return httpx.Response(200, json={"items": [{"id": i, **DETAILS.get(i, {})} for i in ids]})

    monkeypatch.setattr(firestore, "cache_get", cache_get)
    monkeypatch.setattr(firestore, "cache_set", cache_set)
    monkeypatch.setattr(youtube, "_client", httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(youtube, "get_settings", lambda: SimpleNamespace(youtube_api_key=SecretStr("test-key")))
    monkeypatch.setattr(youtube, "_quota_out_until", None)
    return state


def test_keeps_videos_naming_the_spot_drops_kids_videos_and_caches(world):
    ids = asyncio.run(youtube.shorts_for("p1", "高千穂峡", "JP", name="Takachiho Gorge", lang="ja"))

    # v3 is Made for Kids; v4 doesn't name the spot. Travel videos first (v5 #旅行, v1 trip), most views first;
    # v2 has the most views but no travel sign, so it comes last.
    assert ids == ["v5", "v1", "v2"]
    search = world["calls"][0].url.params
    assert search["q"] == "高千穂峡 観光 shorts" and search["regionCode"] == "JP" and search["videoDuration"] == "short"
    assert search["maxResults"] == "10" and "relevanceLanguage" not in search
    details = world["calls"][1].url.params
    assert details["part"] == "snippet,statistics,status" and details["id"] == "v1,v2,v3,v5"
    assert world["cache"][("videos", "p1")]["videoIds"] == ["v5", "v1", "v2"]

    assert asyncio.run(youtube.shorts_for("p1", "高千穂峡", "JP")) == ids
    assert len(world["calls"]) == 2  # the second call came from the cache: no new search


def test_english_trip_searches_the_english_name_first_then_the_local_one(world):
    english = {"items": [{"id": {"videoId": "en1"}, "snippet": {"title": "Takachiho Gorge boat ride #shorts"}}]}
    local = {"items": [{"id": {"videoId": f"ja{i}"}, "snippet": {"title": f"高千穂峡 {i}"}} for i in (1, 2, 3)]}
    answers = iter([english, local])
    world["search"] = lambda: httpx.Response(200, json=next(answers))

    ids = asyncio.run(youtube.shorts_for("p1", "高千穂峡", "JP", name="Takachiho Gorge", lang="en"))

    searches = [c.url.params for c in world["calls"] if c.url.path.endswith("/search")]
    assert [s["q"] for s in searches] == ["Takachiho Gorge travel shorts", "高千穂峡 観光 shorts"]
    assert "regionCode" not in searches[0] and searches[1]["regionCode"] == "JP"
    assert ids == ["en1", "ja1", "ja2"]  # English first, topped up with local Shorts


def test_one_search_is_enough_when_it_finds_three(world):
    asyncio.run(youtube.shorts_for("p1", "高千穂峡", "JP", name="Takachiho Gorge", lang="ja"))
    assert len([c for c in world["calls"] if c.url.path.endswith("/search")]) == 1


def test_stale_cache_searches_again(world):
    old = firestore.now() - timedelta(days=8)
    world["cache"][("videos", "p1")] = {"videoIds": ["old"], "fetchedAt": old, "v": youtube.CACHE_VERSION}
    assert asyncio.run(youtube.shorts_for("p1", "高千穂峡", "JP")) == ["v5", "v2"]


def test_cache_from_the_old_way_of_picking_searches_again(world):
    world["cache"][("videos", "p1")] = {"videoIds": ["old"], "fetchedAt": firestore.now()}  # no version: before D12
    assert asyncio.run(youtube.cached("p1")) is None
    assert asyncio.run(youtube.shorts_for("p1", "高千穂峡", "JP")) == ["v5", "v2"]
    assert world["cache"][("videos", "p1")]["v"] == youtube.CACHE_VERSION


def test_travel_videos_come_first_then_the_trip_language_then_views(world, monkeypatch):
    english = {"items": [{"id": {"videoId": "en1"}, "snippet": {"title": "Takachiho Gorge boat ride"}}]}
    local = {"items": [{"id": {"videoId": i}, "snippet": {"title": f"高千穂峡 {i}"}} for i in ("ja1", "ja2")]}
    answers = iter([english, local])
    world["search"] = lambda: httpx.Response(200, json=next(answers))
    monkeypatch.setitem(DETAILS, "en1", {"snippet": {"title": "Takachiho Gorge"}, "statistics": {"viewCount": "9999"}})
    monkeypatch.setitem(DETAILS, "ja1", {"snippet": {"title": "高千穂峡", "tags": ["#JapanTravel"]}})
    monkeypatch.setitem(DETAILS, "ja2", {"snippet": {"title": "高千穂峡"}, "statistics": {"viewCount": "5"}})

    ids = asyncio.run(youtube.shorts_for("p1", "高千穂峡", "JP", name="Takachiho Gorge", lang="en"))

    assert ids == ["ja1", "en1", "ja2"]  # a travel hashtag beats the trip language and the views


def test_removed_or_private_videos_are_dropped(world):
    world["gone"] = {"v5"}
    assert asyncio.run(youtube.shorts_for("p1", "高千穂峡", "JP")) == ["v2"]


@pytest.mark.parametrize(
    ("snippet", "expected"),
    [
        ({"title": "Osaka Castle at night", "tags": ["#osakatravel"]}, True),
        ({"title": "大阪城", "description": "大阪旅行の思い出"}, True),
        ({"title": "大阪城公園 観光スポット"}, True),
        ({"title": "Osaka Castle prank gone wrong"}, False),
        ({}, False),
    ],
)
def test_travel_signs(snippet, expected):
    assert youtube.is_travel({"snippet": snippet}) is expected


def test_quota_error_returns_empty_and_is_not_cached(world):
    world["search"] = lambda: httpx.Response(403, json={"error": {"errors": [{"reason": "quotaExceeded"}]}})
    assert asyncio.run(youtube.shorts_for("p1", "高千穂峡", "JP")) == []
    assert world["cache"] == {}


def test_no_results_are_cached_for_one_day(world):
    world["search"] = lambda: httpx.Response(200, json={"items": []})
    assert asyncio.run(youtube.shorts_for("p1", "Tiny shrine", "JP")) == []
    assert world["cache"][("videos", "p1")]["videoIds"] == []
    assert len(world["calls"]) == 1  # no status call for an empty result
    assert asyncio.run(youtube.cached("p1")) == []  # fresh: no new search today

    world["cache"][("videos", "p1")]["fetchedAt"] = firestore.now() - timedelta(days=2)
    assert asyncio.run(youtube.cached("p1")) is None  # "no videos" is retried after a day
    two_days = firestore.now() - timedelta(days=2)
    world["cache"][("videos", "p2")] = {"videoIds": ["v"], "fetchedAt": two_days, "v": youtube.CACHE_VERSION}
    assert asyncio.run(youtube.cached("p2")) == ["v"]  # real videos are kept for 7 days


def test_unrelated_videos_are_dropped(world):
    clip = {"items": [{"id": {"videoId": "x"}, "snippet": {"title": "落語 寿限無 #shorts"}}]}
    world["search"] = lambda: httpx.Response(200, json=clip)
    assert asyncio.run(youtube.shorts_for("p1", "一蘭 本店", "JP", name="Ichiran Main Store")) == []


def test_missing_key_or_place_returns_empty(world, monkeypatch):
    assert asyncio.run(youtube.shorts_for("", "高千穂峡", "JP")) == []
    monkeypatch.setattr(youtube, "get_settings", lambda: SimpleNamespace(youtube_api_key=SecretStr(" ")))
    assert asyncio.run(youtube.shorts_for("p1", "高千穂峡", "JP")) == []
    assert world["calls"] == []


def test_quota_used_up_stops_searching_until_reset(world, monkeypatch):
    quota = {"error": {"errors": [{"reason": "quotaExceeded"}]}}
    world["search"] = lambda: httpx.Response(403, json=quota)

    assert asyncio.run(youtube.shorts_for("p1", "高千穂峡", "JP")) == []
    assert asyncio.run(youtube.shorts_for("p2", "Glover Garden", "JP")) == []
    assert len(world["calls"]) == 1  # the second stop didn't call YouTube at all
    assert world["cache"] == {}  # failures aren't cached

    monkeypatch.setattr(youtube, "_quota_out_until", firestore.now() - timedelta(seconds=1))  # quota reset
    world["search"] = lambda: httpx.Response(200, json=SEARCH)
    assert asyncio.run(youtube.shorts_for("p2", "高千穂峡", "JP")) != []


def test_other_errors_dont_stop_searching(world):
    world["search"] = lambda: httpx.Response(500)
    asyncio.run(youtube.shorts_for("p1", "高千穂峡", "JP"))
    asyncio.run(youtube.shorts_for("p2", "Glover Garden", "JP"))
    assert len(world["calls"]) == 2


def test_burst_rate_limit_skips_only_that_stop(world):
    burst = {"error": {"errors": [{"reason": "rateLimitExceeded"}]}}
    world["search"] = lambda: httpx.Response(429, json=burst)
    assert asyncio.run(youtube.shorts_for("p1", "高千穂峡", "JP")) == []
    assert youtube._quota_out_until is None and world["cache"] == {}  # not the daily quota, nothing cached
    world["search"] = lambda: httpx.Response(200, json=SEARCH)
    assert asyncio.run(youtube.shorts_for("p2", "高千穂峡", "JP")) == ["v5", "v2"]


def test_next_reset_is_midnight_pacific():
    from datetime import UTC, datetime

    reset = youtube._next_reset(datetime(2026, 11, 9, 5, 0, tzinfo=UTC))  # 14:00 JST = 21:00 Pacific on Nov 8
    assert reset.isoformat() == "2026-11-09T00:00:00-08:00"  # 17:00 JST


@pytest.mark.parametrize(
    ("name", "title", "expected"),
    [
        ("稲佐山山頂展望台", "稲佐山の夜景がすごい #shorts", True),  # stacked endings stripped
        ("熊本ラーメン 黒亭 本店", "桃黒亭一門 落語タイピング", False),  # 2-char piece alone doesn't count
        ("熊本ラーメン 黒亭 本店", "熊本ラーメン黒亭のにんにく #shorts", True),
        ("Mt. Inasa night view", "Japan night view in Tokyo", False),  # generic English words don't count
        ("Mt. Inasa night view", "Inasa mountain night view Nagasaki", True),
        ("伏見稲荷大社", "伏見稲荷の千本鳥居", True),
        ("清水寺", "京都の夜景", False),
    ],
)
def test_video_title_must_name_the_spot(name, title, expected):
    assert places.mentions(title, name) is expected
