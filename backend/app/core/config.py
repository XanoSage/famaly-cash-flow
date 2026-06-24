from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    app_name: str = "Family Cash Flow"
    api_v1_prefix: str = "/api/v1"
    cors_allowed_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    database_url: str = "postgresql+psycopg://family_cash_flow:family_cash_flow_dev@localhost:5433/family_cash_flow"
    jwt_secret_key: str = "change-me-in-local-env"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 30
    telegram_bot_token: str | None = None
    telegram_webhook_secret_token: str | None = None
    telegram_default_family_id: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

