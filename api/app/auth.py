"""Request authentication.

Every endpoint except /health and /healthz needs:
  Authorization: Bearer <Firebase ID token>    (who the user is)
  X-Firebase-AppCheck: <App Check token>       (that the request comes from our app, not a script)
"""

import asyncio
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from firebase_admin import app_check, auth

from app.config import get_settings
from app.services.firestore import firebase_app, get_trip


@dataclass(frozen=True)
class Account:
    uid: str
    guest: bool  # anonymous sign-in: lower daily limits (PLAN.md 9.6)


async def _verify(request: Request) -> Account:
    """Check the App Check token and the ID token. HTTP 401 if either is missing or invalid."""
    app = firebase_app()

    if not get_settings().skip_appcheck:
        token = request.headers.get("X-Firebase-AppCheck")
        if not token:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "app_check_required")
        try:
            # The Admin SDK calls block, so run them in a worker thread.
            await asyncio.to_thread(app_check.verify_token, token, app)
        except Exception:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "app_check_invalid") from None

    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unauthenticated")
    try:
        decoded = await asyncio.to_thread(auth.verify_id_token, header.removeprefix("Bearer "), app)
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_token") from None
    provider = (decoded.get("firebase") or {}).get("sign_in_provider")
    return Account(uid=decoded["uid"], guest=provider == "anonymous")


async def require_account(request: Request) -> Account:
    """FastAPI dependency: the caller's uid and whether it is a guest, else HTTP 401."""
    return await _verify(request)


async def require_user(request: Request) -> str:
    """FastAPI dependency: returns the caller's uid, else HTTP 401."""
    return (await _verify(request)).uid


async def require_member(trip_id: str, uid: str) -> dict:
    """Returns the trip if `uid` is a member (owner or viewer). 404 if missing, 403 if not a member."""
    trip = await get_trip(trip_id)
    if trip is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "trip_not_found")
    if (trip.get("members") or {}).get(uid) not in ("owner", "viewer"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not_a_member")
    return trip


async def require_owner(trip_id: str, uid: str) -> dict:
    trip = await require_member(trip_id, uid)
    if trip["members"][uid] != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "owner_only")
    return trip


# Use in a route: `async def handler(uid: User): ...` (or `account: CurrentAccount` when limits depend on guest)
User = Annotated[str, Depends(require_user)]
CurrentAccount = Annotated[Account, Depends(require_account)]

# Firestore document ids we create: auto ids (20 chars) and share ids (22 chars). Anything else is a 422, not a 500.
ID_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"
