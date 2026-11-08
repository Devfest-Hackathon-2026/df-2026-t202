"""Settings from env vars (PLAN.md section 12). Locally from api/.env, on Cloud Run from env + Secret Manager."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: str = "development"  # "production" on Cloud Run

    google_cloud_project: str | None = None
    google_cloud_location: str = "asia-northeast1"

    # Vertex AI model IDs. Check the exact names in Vertex AI → Model Garden; no "-latest" aliases.
    gemini_model_fast: str | None = None
    gemini_model_planner: str | None = None

    places_api_key: SecretStr | None = None
    routes_api_key: SecretStr | None = None  # may be the same key as Places
    youtube_api_key: SecretStr | None = None

    allowed_origins: str = "http://localhost:4200"
    require_app_check: bool = True  # set false only for local dev

    # Abuse limits (PLAN.md 9.6)
    max_plans_per_user_per_day: int = 20
    max_messages_per_trip: int = 60

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.env == "production" and not s.require_app_check:
        raise RuntimeError("REQUIRE_APP_CHECK must be true in production")
    return s
