from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    app_name: str = "Family Cash Flow"
    api_v1_prefix: str = "/api/v1"
    cors_allowed_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    database_url: str = (
        "postgresql+psycopg://family_cash_flow:family_cash_flow_dev@localhost:5433/family_cash_flow"
    )
    jwt_secret_key: str = "local-development-only-change-me-not-production"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 30
    auth_cookie_secure: bool | None = None
    auth_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    auth_cookie_domain: str | None = None
    demo_user_email: str | None = None
    demo_user_password: str | None = None
    telegram_bot_token: str | None = None
    telegram_webhook_secret_token: str | None = None
    telegram_default_family_id: str | None = None
    telegram_default_account_id: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def validate_auth_settings(self) -> "Settings":
        if self.app_env.lower() in {"prod", "production"}:
            if (
                self.jwt_secret_key == "local-development-only-change-me-not-production"
                or len(self.jwt_secret_key.encode("utf-8")) < 32
            ):
                raise ValueError("Production requires JWT_SECRET_KEY with at least 32 characters.")
            if not self.effective_auth_cookie_secure:
                raise ValueError("Production requires AUTH_COOKIE_SECURE=true.")
        if self.auth_cookie_samesite == "none" and not self.effective_auth_cookie_secure:
            raise ValueError("AUTH_COOKIE_SECURE must be true when AUTH_COOKIE_SAMESITE is none.")
        return self

    @property
    def effective_auth_cookie_secure(self) -> bool:
        if self.auth_cookie_secure is not None:
            return self.auth_cookie_secure
        return self.app_env.lower() not in {"local", "development", "test"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
