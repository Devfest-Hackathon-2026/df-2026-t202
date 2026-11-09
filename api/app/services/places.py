"""Places API (New) over httpx. PLAN.md 9.5.

Headers: X-Goog-Api-Key (PLACES_API_KEY) and X-Goog-FieldMask with only the fields we use (the mask sets the price).

Caching follows Google's Places policy (docs/decisions.md P9): cache_places stores only query -> placeId,
which may be kept forever. Names, coordinates and opening hours are never stored; a cache hit looks the place up
fresh by its ID (Place Details), so repeat runs also get exactly the same place.
The cache is optional: if Firestore fails, we log it and call Google directly (decision 10).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import unicodedata

import httpx

from app.config import get_settings
from app.services import firestore

BASE = "https://places.googleapis.com/v1"
# regularOpeningHours is an Enterprise SKU field (D35), so every search is billed as Text Search Enterprise; the other
# fields (types, primaryType) are Pro fields and cost nothing extra on top of that.
PLACE_FIELDS = "id,displayName,location,regularOpeningHours,addressComponents,types,primaryType"
SEARCH_FIELDS = ",".join(f"places.{f}" for f in PLACE_FIELDS.split(","))
BIAS_RADIUS_M = 50_000.0  # the API maximum
MAX_QUERY_CHARS = 200  # queries can be user text: keep them short

log = logging.getLogger(__name__)

# Destination country -> language for nameLocal (used for the YouTube search). Default: English.
COUNTRY_LANG = {
    "JP": "ja",
    "KR": "ko",
    "TW": "zh-TW",
    "CN": "zh-CN",
    "TH": "th",
    "FR": "fr",
    "DE": "de",
    "ES": "es",
    "IT": "it",
}

# Retry once on temporary failures, then fail loudly (docs/decisions.md P5).
RETRY_STATUS = {429, 500, 502, 503, 504}
RETRY_DELAY_S = 0.5

_client = httpx.AsyncClient(timeout=10.0)


async def _send(method: str, url: str, **kwargs) -> httpx.Response:
    """Send a request. On a network error or a temporary status, wait briefly and try one more time."""
    try:
        resp = await _client.request(method, url, **kwargs)
        if resp.status_code not in RETRY_STATUS:
            return resp
    except httpx.TransportError:
        pass
    await asyncio.sleep(RETRY_DELAY_S)
    return await _client.request(method, url, **kwargs)  # a second network error is raised to the caller


def _headers(field_mask: str) -> dict[str, str]:
    key = get_settings().places_api_key
    secret = key.get_secret_value().strip() if key else ""
    if not secret:  # unset or "PLACES_API_KEY=" left empty in .env
        raise RuntimeError("places_api_key_missing")
    return {"X-Goog-Api-Key": secret, "X-Goog-FieldMask": field_mask}


def _cache_key(*parts: object) -> str:
    return hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()


def _country_code(place: dict) -> str | None:
    for comp in place.get("addressComponents", []):
        if "country" in comp.get("types", []):
            return comp.get("shortText")
    return None


def parse_place(place: dict) -> dict:
    """Turn one Places API `place` object into our small result dict.

    "label" is the same as "name": it lets Person A's chat code read the result as a PlaceRef.
    """
    loc = place.get("location", {})
    name = place.get("displayName", {}).get("text", "")
    return {
        "placeId": place["id"],
        "name": name,
        "label": name,
        "lat": loc.get("latitude"),
        "lng": loc.get("longitude"),
        "countryCode": _country_code(place),
        "openingHours": place.get("regularOpeningHours"),
        "types": place.get("types", []),
        "primaryType": place.get("primaryType"),
    }


async def _details(place_id: str, lang: str, fields: str) -> dict | None:
    """Place Details by ID. None if the place no longer exists."""
    resp = await _send("GET", f"{BASE}/places/{place_id}", params={"languageCode": lang}, headers=_headers(fields))
    if resp.status_code == 404:
        return None
    resp.raise_for_status()  # a bad key or quota error should be loud, not look like "not found"
    return resp.json()


async def _search(query: str, lang: str, near: tuple[float, float] | None) -> dict | None:
    body: dict = {"textQuery": query, "languageCode": lang, "pageSize": 1}
    if near:
        body["locationBias"] = {
            "circle": {"center": {"latitude": near[0], "longitude": near[1]}, "radius": BIAS_RADIUS_M}
        }
    resp = await _send("POST", f"{BASE}/places:searchText", json=body, headers=_headers(SEARCH_FIELDS))
    resp.raise_for_status()
    places = resp.json().get("places", [])
    return places[0] if places else None


async def search_text(query: str, lang: str, near: tuple[float, float] | None = None) -> dict | None:
    """Find a place by text. Returns {"placeId", "name", "label", "lat", "lng", "countryCode", "openingHours"} or None.

    Raises httpx.HTTPError if Google fails twice (decision 5); callers decide how to show that.
    """
    query = query.strip()[:MAX_QUERY_CHARS]
    key = _cache_key(query, lang, near)
    cached = await _cache_get(key)
    place = await _details(cached["placeId"], lang, PLACE_FIELDS) if cached else None
    if place is None:
        place = await _search(query, lang, near)
        if place is None:
            return None
        await _cache_set(key, {"query": query, "placeId": place["id"]})
    return parse_place(place)


async def _cache_get(key: str) -> dict | None:
    try:
        return await firestore.cache_get("places", key)
    except Exception as e:  # the cache only saves calls; any Firestore failure is skipped
        log.warning(json.dumps({"event": "places_cache_error", "op": "get", "error": type(e).__name__}))
        return None


async def _cache_set(key: str, data: dict) -> None:
    try:
        await firestore.cache_set("places", key, data)
    except Exception as e:
        log.warning(json.dumps({"event": "places_cache_error", "op": "set", "error": type(e).__name__}))


async def local_name(place_id: str, country_code: str) -> str | None:
    """Place Details in the destination's language. Returns the local display name (not cached: decision 9)."""
    lang = COUNTRY_LANG.get((country_code or "").upper(), "en")
    place = await _details(place_id, lang, "displayName")
    return place.get("displayName", {}).get("text") if place else None


# ---------- Name matching (used to keep good names and to drop unrelated YouTube videos) ----------

SPLIT = re.compile(r"[\s・･()（）「」『』【】\[\]〈〉<>|/,、。.:：!！?？#＃\-–—~〜'’\"]+")
JA_SUFFIXES = (  # common endings; stripped (repeatedly) to get the distinctive part: 稲佐山山頂展望台 -> 稲佐山
    "展望台", "展望所", "美術館", "博物館", "水族館", "商店街", "本店", "支店", "大社", "神社", "神宮", "山頂", "庭園",
    "公園", "温泉", "市場", "通り", "店", "寺", "駅", "城", "峡", "滝", "湖", "橋", "港",
)  # fmt: skip
JA_GENERIC = set(JA_SUFFIXES) | {"ラーメン", "レストラン", "カフェ", "ホテル", "旅館", "観光", "夜景", "日本"}
EN_COMMON = {
    "the", "and", "shrine", "temple", "castle", "park", "garden", "gardens", "station", "onsen", "ramen", "restaurant",
    "cafe", "market", "museum", "street", "tower", "japan", "hotel", "ryokan", "main", "store", "shop", "branch",
    "night", "view", "views", "viewpoint", "observatory", "observation", "deck", "lake", "river", "beach", "island",
    "mount", "mountain", "falls", "gorge", "bridge", "city", "town", "village", "house", "center", "centre", "hall",
    "food", "sushi", "spring", "springs", "best", "famous", "sunset", "sunrise", "area", "national", "old", "new",
    "great", "kitchen", "honten", "jinja", "dera", "tera",
}  # fmt: skip


def compact(text: str) -> str:
    """Lower case, full-width -> half-width (NFKC), no spaces or punctuation."""
    return SPLIT.sub("", unicodedata.normalize("NFKC", text).lower())


def _strip_ja(word: str) -> str:
    """Remove common endings while at least 3 characters stay: 稲佐山山頂展望台 -> 稲佐山."""
    changed = True
    while changed:
        changed = False
        for suffix in JA_SUFFIXES:
            if word.endswith(suffix) and len(word) - len(suffix) >= 3:
                word, changed = word[: -len(suffix)], True
    return word


def name_keys(name: str) -> set[str]:
    """Distinctive pieces of a place name. Latin words need 4+ letters and must not be generic ("temple", "night").
    Japanese words count whole and without common endings; generic ones ("本店", "ラーメン") never count, and
    2-character pieces only when the name has nothing longer (so "黒亭" doesn't match "桃黒亭一門")."""
    keys, short = set(), set()
    for word in SPLIT.split(unicodedata.normalize("NFKC", name).lower()):
        if not word:
            continue
        if word.isascii():
            if len(word) >= 4 and word not in EN_COMMON:
                keys.add(word)
            continue
        for piece in {word, _strip_ja(word)}:
            if piece in JA_GENERIC:
                continue
            (keys if len(piece) >= 3 else short).add(piece)
    return keys or short


def mentions(text: str, *names: str) -> bool:
    """Does `text` (a video title, another name) contain a distinctive piece of one of the names?"""
    flat = compact(text)
    return any(key in flat for name in names if name for key in name_keys(name))
