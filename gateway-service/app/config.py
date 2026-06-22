from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Emotional Support Gateway"
    safety_service_url: str = "http://127.0.0.1:8001"
    chat_service_url: str = "http://127.0.0.1:8002"
    save_service_url: str = "http://127.0.0.1:8003"
    request_timeout_seconds: float = 30.0
    auth_token_secret: str = "replace-this-development-auth-secret"
    auth_token_minutes: int = 60 * 24 * 7
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
