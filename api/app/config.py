"""Settings from env vars.

Locally from api/.env; on Cloud Run from env vars and Secret Manager.
"""

import os
from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: str = "development"  # "production" on Cloud Run (set in the Dockerfile)

    google_cloud_project: str | None = None
    google_cloud_location: str = "asia-northeast1"

    # Exact Vertex AI model IDs (Model Garden). No "-latest" aliases.
    gemini_model_fast: str = ""
    gemini_model_planner: str = ""

    places_api_key: SecretStr | None = None
    routes_api_key: SecretStr | None = None
    youtube_api_key: SecretStr | None = None

    allowed_origins: str = "http://localhost:4200"
    skip_appcheck: bool = False  # SKIP_APPCHECK=1 for local development only

    # Abuse limits (PLAN.md 9.6)
    max_plans_per_user_per_day: int = 10
    max_plans_per_guest_per_day: int = 3
    max_trips_per_user_per_day: int = 10
    max_trips_per_guest_per_day: int = 3
    max_plans_per_day: int = 200  # whole app: protects the credit and the YouTube quota
    max_messages_per_trip: int = 40
    min_seconds_between_texts: float = 2.0  # per trip, free-text messages only (cards are cheap)
    max_members_per_trip: int = 50  # owner + viewers who opened the share link

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.env == "production" and s.skip_appcheck:
        raise RuntimeError("SKIP_APPCHECK must not be set in production")
    if s.env == "production":
        # The Admin SDK trusts unsigned emulator tokens when these are set: that would bypass auth.
        for name in ("FIRESTORE_EMULATOR_HOST", "FIREBASE_AUTH_EMULATOR_HOST"):
            if os.environ.get(name):
                raise RuntimeError(f"{name} must not be set in production")
    return s
