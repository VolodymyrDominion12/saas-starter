from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, read from environment variables or a `.env` file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "SaaS Starter"
    app_url: str = "http://localhost:8000"
    environment: Literal["development", "test", "production"] = "development"

    database_url: str = "sqlite+aiosqlite:///./dev.db"
    database_echo: bool = False

    session_cookie_name: str = "session"
    session_ttl_days: int = 30
    cookie_secure: bool = False

    email_from: str = "no-reply@example.com"

    login_max_failures: int = 10
    login_window_seconds: int = 900

    verify_email_ttl_minutes: int = 24 * 60
    password_reset_ttl_minutes: int = 60
    magic_link_ttl_minutes: int = 15

    @model_validator(mode="after")
    def _production_guards(self) -> "Settings":
        if self.environment == "production":
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE must be true in production")
            if self.database_url.startswith("sqlite"):
                raise ValueError("Use PostgreSQL in production")
        return self

    @property
    def base_url(self) -> str:
        return self.app_url.rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()
