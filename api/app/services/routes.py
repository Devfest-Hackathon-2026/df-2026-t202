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
# TRANSIT also asks which lines to ride, so the UI can say "Central line → Bus 25" instead of "train or bus".
TRANSIT_FIELD_MASK = FIELD_MASK + ",routes.legs.steps.transitDetails.transitLine"
MAX_LINES = 2
ROUTABLE = {"DRIVE", "TRANSIT", "WALK"}

_client = httpx.AsyncClient(timeout=10.0)
log = logging.getLogger(__name__)


def duration_minutes(duration: str) -> int:
    """'7260s' -> 121. Rounds up so a 61-second hop is 2 minutes, never 0."""
    return max(1, math.ceil(float(duration.rstrip("s")) / 60))


def transit_line(route: dict) -> str | None:
    """The lines a TRANSIT route rides, in order ("Ginza Line → Bus 25"), or None when it rides nothing."""
    names: list[str] = []
    for leg in route.get("legs", []):
        for step in leg.get("steps", []):
            line = (step.get("transitDetails") or {}).get("transitLine") or {}
            short, full = line.get("nameShort"), line.get("name")
            vehicle = ((line.get("vehicle") or {}).get("name") or {}).get("text")
            if full:
                name = full
            elif short and vehicle:
                name = f"{vehicle} {short}"  # "Bus 25": a bare number means nothing on its own
            else:
                name = short or vehicle
            if name and name not in names:
                names.append(name)
    return " → ".join(names[:MAX_LINES]) or None


def _waypoint(p: tuple[float, float]) -> dict:
    return {"location": {"latLng": {"latitude": p[0], "longitude": p[1]}}}


async def leg(a: tuple[float, float], b: tuple[float, float], mode: str, lang: str) -> dict | None:
    """Return {"minutes": int, "polyline": str, "line": str | None}, or None if there is no route."""
    if mode not in ROUTABLE:
        return None
    key = get_settings().routes_api_key
    secret = key.get_secret_value().strip() if key else ""
    if not secret:  # unset or "ROUTES_API_KEY=" left empty in .env
        raise RuntimeError("routes_api_key_missing")

    body: dict = {"origin": _waypoint(a), "destination": _waypoint(b), "travelMode": mode, "languageCode": lang}
    if mode == "DRIVE":
        body["routingPreference"] = "TRAFFIC_UNAWARE"  # cheapest tier; only allowed for DRIVE
    mask = TRANSIT_FIELD_MASK if mode == "TRANSIT" else FIELD_MASK
    headers = {"X-Goog-Api-Key": secret, "X-Goog-FieldMask": mask}

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
    return {
        "minutes": duration_minutes(r["duration"]),
        "polyline": r.get("polyline", {}).get("encodedPolyline"),
        "line": transit_line(r) if mode == "TRANSIT" else None,
    }
