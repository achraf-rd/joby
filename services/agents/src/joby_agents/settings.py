from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # SQLAlchemy async URL, e.g. postgresql+asyncpg://joby:joby@localhost:5432/joby
    database_url: str
    # Shared with Nest; verifies inbound calls and signs outbound callbacks (ARCHITECTURE §5.2).
    internal_hmac_secret: str
    # Base URL of the Nest API, used to deliver run events to /internal/runs/{id}/events.
    api_internal_url: str = "http://localhost:3000"
    # Maximum allowed clock skew for signed requests.
    signature_max_skew_seconds: int = 300

    worker_concurrency: int = Field(default=4, ge=1)
    worker_per_tenant_concurrency: int = Field(default=2, ge=1)
    worker_poll_interval_seconds: float = 1.0
    worker_heartbeat_interval_seconds: float = 15.0
    # A claimed run whose heartbeat is older than this becomes reclaimable.
    worker_stale_after_seconds: float = 120.0

    @property
    def psycopg_url(self) -> str:
        """Plain libpq URL for psycopg (used by the LangGraph checkpointer)."""
        return self.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


@lru_cache
def get_settings() -> Settings:
    return Settings()
