"""Places API (New) over httpx (Person B). BACKEND_PERSON_B.md T1, PLAN.md 9.5.

Headers: X-Goog-Api-Key (PLACES_API_KEY) and X-Goog-FieldMask with only the fields we use.
Cache results in cache_places (key = sha1 of f"{query}|{lang}|{near}").
"""

from __future__ import annotations


async def search_text(query: str, lang: str, near: tuple[float, float] | None = None) -> dict | None:
    """Text Search. Returns {"placeId", "name", "lat", "lng", "countryCode", "openingHours"} or None."""
    raise NotImplementedError("TODO(B): T1 search_text")


async def local_name(place_id: str, country_code: str) -> str | None:
    """Place Details in the destination's language. Returns the local display name."""
    raise NotImplementedError("TODO(B): T1 local_name")
