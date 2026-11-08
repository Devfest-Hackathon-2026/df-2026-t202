"""Routes API computeRoutes over httpx (Person B). BACKEND_PERSON_B.md T1, PLAN.md 9.3 step 4.

One call per leg (TRANSIT can't use intermediate waypoints anyway). FLIGHT / FERRY are never sent to the API:
we return None and the pipeline keeps the Planner's minutes with estimate=True.
"""

from __future__ import annotations

import json
import logging
import math

import httpx

from app.config import get_settings

URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
FIELD_MASK = "routes.duration,routes.polyline.encodedPolyline"
ROUTABLE = {"DRIVE", "TRANSIT", "WALK"}

_client = httpx.AsyncClient(timeout=10.0)
log = logging.getLogger(__name__)


def duration_minutes(duration: str) -> int:
    """'7260s' -> 121. Rounds up so a 61-second hop is 2 minutes, never 0."""
    return max(1, math.ceil(float(duration.rstrip("s")) / 60))


def _waypoint(p: tuple[float, float]) -> dict:
    return {"location": {"latLng": {"latitude": p[0], "longitude": p[1]}}}


async def leg(a: tuple[float, float], b: tuple[float, float], mode: str, lang: str) -> dict | None:
    """Return {"minutes": int, "polyline": str}, or None if there is no route."""
    if mode not in ROUTABLE:
        return None
    key = get_settings().routes_api_key
    secret = key.get_secret_value().strip() if key else ""
    if not secret:  # unset or "ROUTES_API_KEY=" left empty in .env
        raise RuntimeError("routes_api_key_missing")

    body: dict = {"origin": _waypoint(a), "destination": _waypoint(b), "travelMode": mode, "languageCode": lang}
    if mode == "DRIVE":
        body["routingPreference"] = "TRAFFIC_UNAWARE"  # cheapest tier; only allowed for DRIVE
    headers = {"X-Goog-Api-Key": secret, "X-Goog-FieldMask": FIELD_MASK}

    try:
        resp = await _client.post(URL, json=body, headers=headers)
    except httpx.HTTPError as e:
        log.warning(json.dumps({"event": "routes_error", "mode": mode, "error": type(e).__name__}))
        return None
    if resp.status_code != 200:
        # No route (e.g. no transit data in that country) or an upstream error: the pipeline falls back to an estimate.
        log.warning(json.dumps({"event": "routes_error", "mode": mode, "status": resp.status_code}))
        return None

    routes = resp.json().get("routes", [])
    if not routes or "duration" not in routes[0]:
        return None
    r = routes[0]
    return {"minutes": duration_minutes(r["duration"]), "polyline": r.get("polyline", {}).get("encodedPolyline")}
