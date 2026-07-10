"""Application settings — single source of runtime configuration.

All values come from environment variables / .env. Nothing candidate- or
profession-specific lives here (see CLAUDE.md §4): per-user config is stored
in the database, not in app settings.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_name: str = "AJH — AI Job Hunter"
    environment: str = "development"  # development | production | test
    api_v1_prefix: str = "/api/v1"
    debug: bool = False

    # Security
    secret_key: str = "CHANGE_ME"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14
    jwt_algorithm: str = "HS256"

    # Database
    database_url: str = "postgresql+asyncpg://ajh:ajh@localhost:5432/ajh"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Encryption key for stored provider credentials (Fernet)
    credentials_encryption_key: str = "CHANGE_ME"


@lru_cache
def get_settings() -> Settings:
    return Settings()
