"""YouTube Shorts per stop (Person B). BACKEND_PERSON_B.md T5, PLAN.md 9.4.

search.list: type=video, videoDuration=short, maxResults=5, q="<name> shorts", no relevanceLanguage (videos in any
language are fine). Two names, two audiences: the trip-language name first (an English trip wants English Shorts), then
the other name when that found fewer than 3; the local name searches with regionCode=destination. Both sets are kept.
Only videos whose title names the spot are kept (a search for
a ramen shop can return an unrelated clip). At most 4 searches run at once (pipeline). Once the daily quota is used up
(quotaExceeded), we stop searching until it resets; a short burst limit (rateLimitExceeded) only skips that stop.
videos.list then drops "Made for Kids" videos (YouTube policy III.E.4.j; person_b_WHY.md decision 27).

Videos are optional: on any failure (quota used up, no key) we return [] and the front end shows its fallback.
Cache: cache_videos/{placeId} for 7 days, "no videos" for 1 day (YouTube allows API data for at most 30 days;
quota is ~100 searches a day).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from app.config import get_settings
from app.services import firestore
from app.services.places import mentions

SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
CACHE_FOR = timedelta(days=7)
CACHE_EMPTY_FOR = timedelta(days=1)  # "no videos" may change soon (new uploads, a better name next run)
MAX_VIDEOS = 3
QUOTA_REASONS = {"quotaExceeded", "dailyLimitExceeded"}  # the daily quota; rateLimitExceeded is a short burst limit
QUOTA_RESETS_IN = ZoneInfo("America/Los_Angeles")  # YouTube's daily quota resets at midnight Pacific time

_quota_out_until: datetime | None = None  # set when YouTube says the daily quota is used up (D57)

_client = httpx.AsyncClient(timeout=5.0)  # videos are optional: don't let a slow call hold up the plan
log = logging.getLogger(__name__)


def _key() -> str | None:
    key = get_settings().youtube_api_key
    return key.get_secret_value().strip() if key else None


async def cached(place_id: str) -> list[str] | None:
    """The cached video ids, or None when there is no fresh cache entry (then a search is needed)."""
    try:
        doc = await firestore.cache_get("videos", place_id)
    except Exception as e:  # the cache only saves quota; skip it if Firestore fails
        log.warning(json.dumps({"event": "videos_cache_error", "op": "get", "error": type(e).__name__}))
        return None
    if not doc or not doc.get("fetchedAt"):
        return None
    ids = doc.get("videoIds", [])
    return ids if firestore.now() - doc["fetchedAt"] < (CACHE_FOR if ids else CACHE_EMPTY_FOR) else None


async def _save(place_id: str, query: str, ids: list[str]) -> None:
    try:
        await firestore.cache_set("videos", place_id, {"query": query, "videoIds": ids})
    except Exception as e:
        log.warning(json.dumps({"event": "videos_cache_error", "op": "set", "error": type(e).__name__}))


def relevant(items: list[dict], *names: str) -> list[str]:
    """Ids of the videos whose title names the spot (a distinctive part of one of its names), in search order."""
    return [i["id"]["videoId"] for i in items if mentions(i.get("snippet", {}).get("title", ""), *names)]


async def _get(url: str, params: dict) -> httpx.Response:
    resp = await _client.get(url, params=params)
    resp.raise_for_status()
    return resp


def _quota_used_up(resp: httpx.Response) -> bool:
    if resp.status_code not in (403, 429):
        return False
    try:
        errors = resp.json().get("error", {}).get("errors", [])
    except ValueError:
        return False
    return any(e.get("reason") in QUOTA_REASONS for e in errors)


def _next_reset(now: datetime) -> datetime:
    """The next midnight in Pacific time."""
    pacific = now.astimezone(QUOTA_RESETS_IN)
    return (pacific + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)


async def _search(query: str, region: str | None, key: str) -> list[dict]:
    params = {
        "part": "snippet",
        "type": "video",
        "videoDuration": "short",
        "maxResults": 5,
        "q": query,
        "fields": "items(id/videoId,snippet/title)",
        "key": key,
    }
    if region:
        params["regionCode"] = region
    resp = await _get(SEARCH_URL, params)
    return [i for i in resp.json().get("items", []) if i.get("id", {}).get("videoId")]


async def _made_for_kids(ids: list[str], key: str) -> set[str]:
    params = {"part": "status", "id": ",".join(ids), "fields": "items(id,status/madeForKids)", "key": key}
    resp = await _get(VIDEOS_URL, params)
    return {i["id"] for i in resp.json().get("items", []) if i.get("status", {}).get("madeForKids")}


def _queries(name_local: str, name: str, region: str, lang: str) -> list[tuple[str, str | None]]:
    """(query, regionCode) pairs in search order: the trip-language name first, then the other one."""
    local = (f"{name_local} shorts", region or None)
    if not name or name.strip().casefold() == name_local.strip().casefold():
        return [local]
    translated = (f"{name} shorts", None)  # no region: English Shorts of a Japanese spot come from everywhere
    return [local, translated] if lang == "ja" else [translated, local]


async def shorts_for(place_id: str, name_local: str, region: str, name: str = "", lang: str = "en") -> list[str]:
    """Return up to 3 Shorts video ids for a stop whose titles name it (`name_local`, or `name` in the trip language).
    Empty list is OK."""
    global _quota_out_until
    if not place_id or not name_local:
        return []
    hit = await cached(place_id)
    if hit is not None:
        return hit
    if _quota_out_until and firestore.now() < _quota_out_until:
        return []  # quota used up today: don't spend time on calls YouTube will refuse
    key = _key()
    if not key:
        log.warning(json.dumps({"event": "youtube_key_missing"}))
        return []

    ids: list[str] = []
    queries = _queries(name_local, name, region, lang)
    query = queries[0][0]
    try:
        for q, region_code in queries:
            if len(ids) >= MAX_VIDEOS:
                break  # the first search found enough: save the quota
            ids += [i for i in relevant(await _search(q, region_code, key), name_local, name) if i not in ids]
        if ids:
            kids = await _made_for_kids(ids, key)
            ids = [i for i in ids if i not in kids]
    except httpx.HTTPError as e:  # quota used up, network: no videos this time, and don't cache the failure
        status = e.response.status_code if isinstance(e, httpx.HTTPStatusError) else None
        if isinstance(e, httpx.HTTPStatusError) and _quota_used_up(e.response):
            _quota_out_until = _next_reset(firestore.now())
            log.warning(json.dumps({"event": "youtube_quota_out", "until": _quota_out_until.isoformat()}))
        else:
            log.warning(json.dumps({"event": "youtube_error", "status": status, "error": type(e).__name__}))
            # includes 429 rateLimitExceeded: a burst limit, so only this stop goes without videos
        return []

    ids = ids[:MAX_VIDEOS]
    await _save(place_id, query, ids)  # "no videos" is cached too, but only for a day (CACHE_EMPTY_FOR)
    return ids
