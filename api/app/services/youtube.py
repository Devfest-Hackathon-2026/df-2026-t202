"""YouTube Data API v3 search.list (Person B). BACKEND_PERSON_B.md T5, PLAN.md 9.4.

type=video, videoDuration=short, maxResults=5, regionCode=region, q="<name_local> shorts", no relevanceLanguage.
Cache by placeId in cache_videos for 7 days (about 100 searches/day quota).
"""

from __future__ import annotations


async def shorts_for(place_id: str, name_local: str, region: str) -> list[str]:
    """Return up to 3 Shorts video ids for a stop (titles with the spot name first). Empty list is OK."""
    raise NotImplementedError("TODO(B): T5 shorts_for")
