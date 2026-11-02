from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_SECRET = "change-me-in-env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Spendzer API"
    environment: str = "development"

    database_url: str = "postgresql+asyncpg://spendzer:spendzer@localhost:5433/spendzer"
    database_null_pool: bool = False

    jwt_secret: str = _DEFAULT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7

    refresh_cookie_name: str = "spendzer_refresh"
    cookie_secure: bool = True

    cors_origins: list[str] = ["http://localhost:5173"]

    rate_limit_enabled: bool = True
    login_rate_limit: str = "5/minute"
    upload_rate_limit: str = "20/hour"

    max_upload_bytes: int = 10 * 1024 * 1024
    upload_tmp_dir: str = ""  # empty = system temp dir
    pending_upload_ttl_minutes: int = 60

    # The shared demo account (README / "Try the demo"). It can't be deleted.
    demo_email: str = "demo@spendzer.app"

    @field_validator("database_url")
    @classmethod
    def _async_driver(cls, value: str) -> str:
        """Hosts hand out postgres:// URLs; SQLAlchemy's async engine needs +asyncpg."""
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+asyncpg://" + value[len(prefix) :]
        return value

    @model_validator(mode="after")
    def _production_guards(self) -> "Settings":
        if self.environment == "production":
            if self.jwt_secret == _DEFAULT_SECRET or len(self.jwt_secret) < 32:
                raise ValueError("Set JWT_SECRET to a long random value in production.")
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE must be true in production (HTTPS only).")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
