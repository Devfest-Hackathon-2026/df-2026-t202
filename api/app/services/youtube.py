"""YouTube Shorts per stop (Person B). BACKEND_PERSON_B.md T5, PLAN.md 9.4.

search.list: type=video, videoDuration=short, maxResults=5, regionCode=destination, q="<local name> shorts",
no relevanceLanguage (videos in any language are fine). Titles that contain the spot name come first.
At most 4 searches run at once (pipeline). Once the daily quota is used up, we stop searching until it resets.
videos.list then drops "Made for Kids" videos (YouTube policy III.E.4.j; person_b_WHY.md decision 27).

Videos are optional: on any failure (quota used up, no key) we return [] and the front end shows its fallback.
Cache: cache_videos/{placeId} for 7 days (YouTube allows API data for at most 30 days; quota is ~100 searches a day).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from app.config import get_settings
from app.services import firestore

SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
CACHE_FOR = timedelta(days=7)
MAX_VIDEOS = 3
QUOTA_REASONS = {"quotaExceeded", "rateLimitExceeded", "dailyLimitExceeded"}
QUOTA_RESETS_IN = ZoneInfo("America/Los_Angeles")  # YouTube's daily quota resets at midnight Pacific time

_quota_out_until: datetime | None = None  # set when YouTube says the daily quota is used up (D57)

_client = httpx.AsyncClient(timeout=10.0)
log = logging.getLogger(__name__)


def _key() -> str | None:
    key = get_settings().youtube_api_key
    return key.get_secret_value().strip() if key else None


async def _cached(place_id: str) -> list[str] | None:
    try:
        doc = await firestore.cache_get("videos", place_id)
    except Exception as e:  # the cache only saves quota; skip it if Firestore fails
        log.warning(json.dumps({"event": "videos_cache_error", "op": "get", "error": type(e).__name__}))
        return None
    if doc and doc.get("fetchedAt") and firestore.now() - doc["fetchedAt"] < CACHE_FOR:
        return doc.get("videoIds", [])
    return None


async def _save(place_id: str, query: str, ids: list[str]) -> None:
    try:
        await firestore.cache_set("videos", place_id, {"query": query, "videoIds": ids})
    except Exception as e:
        log.warning(json.dumps({"event": "videos_cache_error", "op": "set", "error": type(e).__name__}))


def rank(items: list[dict], name: str) -> list[str]:
    """Video ids, the ones whose title contains the spot name first (stable order otherwise)."""
    name = name.lower()
    with_name = [i["id"]["videoId"] for i in items if name in i.get("snippet", {}).get("title", "").lower()]
    others = [i["id"]["videoId"] for i in items if i["id"]["videoId"] not in with_name]
    return with_name + others


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


async def shorts_for(place_id: str, name_local: str, region: str) -> list[str]:
    """Return up to 3 Shorts video ids for a stop (titles with the spot name first). Empty list is OK."""
    global _quota_out_until
    if not place_id or not name_local:
        return []
    cached = await _cached(place_id)
    if cached is not None:
        return cached
    if _quota_out_until and firestore.now() < _quota_out_until:
        return []  # quota used up today: don't spend time on calls YouTube will refuse
    key = _key()
    if not key:
        log.warning(json.dumps({"event": "youtube_key_missing"}))
        return []

    query = f"{name_local} shorts"
    try:
        ids = rank(await _search(query, region or None, key), name_local)
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
        return []

    ids = ids[:MAX_VIDEOS]
    await _save(place_id, query, ids)  # also cache "no videos", so we don't spend quota on it again
    return ids
