"""Tripi API (FastAPI on Cloud Run). Endpoints: PLAN.md 9.1."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import plan, trips

logging.basicConfig(level=logging.INFO, format="%(message)s")
# httpx logs every request URL at INFO, and YouTube puts the API key in the query string: keep it out of the logs.
logging.getLogger("httpx").setLevel(logging.WARNING)

settings = get_settings()
app = FastAPI(title="Tripi API", docs_url=None if settings.env == "production" else "/docs")

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
