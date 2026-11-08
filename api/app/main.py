"""Planner API (FastAPI on Cloud Run). Routes: PLAN.md section 9.1.

Add routes here (or in routers included here). Every route except /healthz takes `uid: Uid`.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(message)s")

settings = get_settings()
app = FastAPI(title="AI Trip Planner API", docs_url=None if settings.env == "production" else "/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-Firebase-AppCheck"],
    max_age=600,
)


@app.get("/healthz")
def healthz() -> dict[str, bool]:
    return {"ok": True}


# TODO (M1+): POST /trips, POST /trips/{id}/messages, POST /trips/{id}/plan, POST /trips/{id}/share
