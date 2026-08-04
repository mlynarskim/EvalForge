from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "EvalForge"
    app_env: Literal["development", "test", "production"] = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8080
    database_url: str = "sqlite:///./evalforge.db"
    redis_url: str = "redis://localhost:6379/0"
    session_secret: str = "local-development-session-secret-change-me"
    encryption_key: str | None = None
    demo_mode: bool = True
    demo_admin_email: str = "demo@evalforge.dev"
    demo_admin_password: str = "ChangeMe123!"
    default_language: Literal["en", "pl"] = "en"
    default_currency: Literal["PLN", "USD", "EUR"] = "PLN"
    usd_to_pln: float = Field(default=4.0, gt=0)
    eur_to_pln: float = Field(default=4.35, gt=0)
    max_upload_mb: int = Field(default=10, ge=1, le=100)
    max_prompt_length: int = Field(default=100_000, ge=1_000, le=1_000_000)
    report_directory: Path = Path("reports")

    @field_validator("session_secret")
    @classmethod
    def validate_session_secret(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError("SESSION_SECRET must contain at least 32 characters")
        return value

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
