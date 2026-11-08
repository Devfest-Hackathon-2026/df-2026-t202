"""Verify the Firebase ID token and App Check token on every API request (PLAN.md 9.1)."""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from firebase_admin import app_check, auth

from app.config import get_settings
from app.services.firestore import firebase_app


def require_uid(
    authorization: Annotated[str | None, Header()] = None,
    x_firebase_appcheck: Annotated[str | None, Header()] = None,
) -> str:
    """FastAPI dependency: returns the caller's uid or raises 401.

    Sync on purpose: FastAPI runs it in a thread pool, because the Admin SDK calls block.
    """
    app = firebase_app()

    if get_settings().require_app_check:
        if not x_firebase_appcheck:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "app_check_required")
        try:
            app_check.verify_token(x_firebase_appcheck, app=app)
        except Exception:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "app_check_invalid") from None

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unauthenticated")
    try:
        decoded = auth.verify_id_token(authorization.removeprefix("Bearer "), app=app)
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_token") from None
    return decoded["uid"]


Uid = Annotated[str, Depends(require_uid)]
