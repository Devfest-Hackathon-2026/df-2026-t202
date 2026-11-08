"""Routes API computeRoutes over httpx (Person B). BACKEND_PERSON_B.md T1, PLAN.md 9.3 step 4.

Field mask: routes.duration,routes.polyline.encodedPolyline. One call per leg (TRANSIT has no waypoints).
FLIGHT / FERRY are never sent to the API (return None; the pipeline keeps the estimate).
"""

from __future__ import annotations


async def leg(a: tuple[float, float], b: tuple[float, float], mode: str, lang: str) -> dict | None:
    """Return {"minutes": int, "polyline": str}, or None if there is no route."""
    raise NotImplementedError("TODO(B): T1 leg")
