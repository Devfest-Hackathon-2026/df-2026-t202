"""Tripi API (FastAPI on Cloud Run). Endpoints: PLAN.md 9.1."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import get_settings
from app.routers import plan, trips

logging.basicConfig(level=logging.INFO, format="%(message)s")
# httpx logs every request URL at INFO, and YouTube puts the API key in the query string: keep it out of the logs.
logging.getLogger("httpx").setLevel(logging.WARNING)

MAX_BODY_BYTES = 16 * 1024  # the largest real request (a card answer or a 1000-character message) is ~4 KB


class BodyLimit:
    """413 for request bodies over MAX_BODY_BYTES, before anything parses them (Content-Length or streamed)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        length = dict(scope.get("headers") or []).get(b"content-length")
        if length is not None and (not length.isdigit() or int(length) > MAX_BODY_BYTES):
            return await JSONResponse({"detail": "body_too_large"}, status_code=413)(scope, receive, send)

        seen = 0

        async def limited() -> Message:
            nonlocal seen
            message = await receive()
            seen += len(message.get("body", b""))
            if seen > MAX_BODY_BYTES:
                raise _TooLarge
            return message

        try:
            await self.app(scope, limited, send)
        except _TooLarge:
            await JSONResponse({"detail": "body_too_large"}, status_code=413)(scope, receive, send)


class _TooLarge(Exception):
    pass


settings = get_settings()
app = FastAPI(title="Tripi API", docs_url=None if settings.env == "production" else "/docs")

app.add_middleware(BodyLimit)  # inside CORS (the last one added runs first), so a 413 still has CORS headers
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-Firebase-AppCheck"],
    max_age=600,
)


@app.get("/health")  # Cloud Run reserves paths ending in "z" (/healthz never reaches the app)
@app.get("/healthz")
async def healthz() -> dict[str, bool]:
    return {"ok": True}


app.include_router(trips.router)
app.include_router(plan.router)  # Person B
