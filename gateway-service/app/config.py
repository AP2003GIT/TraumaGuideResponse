from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SAFETY_SERVICE_URL = "http://127.0.0.1:8001"
DEFAULT_CHAT_SERVICE_URL = "http://127.0.0.1:8002"
DEFAULT_SAVE_SERVICE_URL = "http://127.0.0.1:8003"


class Settings(BaseSettings):
    app_name: str = "Emotional Support Gateway"
    safety_service_url: str = DEFAULT_SAFETY_SERVICE_URL
    chat_service_url: str = DEFAULT_CHAT_SERVICE_URL
    save_service_url: str = DEFAULT_SAVE_SERVICE_URL
    safety_service_host: str | None = None
    chat_service_host: str | None = None
    save_service_host: str | None = None
    safety_service_port: int = 8001
    chat_service_port: int = 8002
    save_service_port: int = 8003
    request_timeout_seconds: float = 30.0
    auth_token_secret: str = "replace-this-development-auth-secret"
    auth_token_minutes: int = 60 * 24 * 7
    auth_rate_limit_per_minute: int = 12
    chat_rate_limit_per_minute: int = 20
    admin_rate_limit_per_minute: int = 30
    single_service_fallback: bool = True
    chat_retention_days: int = 10
    chat_max_saved_chats: int = 10
    admin_emails: list[str] = []
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

    @model_validator(mode="after")
    def build_private_service_urls(self) -> "Settings":
        if (
            self.safety_service_host
            and (
                not self.safety_service_url
                or self.safety_service_url == DEFAULT_SAFETY_SERVICE_URL
            )
        ):
            self.safety_service_url = self._private_url(
                self.safety_service_host,
                self.safety_service_port,
            )

        if (
            self.chat_service_host
            and (
                not self.chat_service_url
                or self.chat_service_url == DEFAULT_CHAT_SERVICE_URL
            )
        ):
            self.chat_service_url = self._private_url(
                self.chat_service_host,
                self.chat_service_port,
            )

        if (
            self.save_service_host
            and (
                not self.save_service_url
                or self.save_service_url == DEFAULT_SAVE_SERVICE_URL
            )
        ):
            self.save_service_url = self._private_url(
                self.save_service_host,
                self.save_service_port,
            )

        return self

    @staticmethod
    def _private_url(host: str, port: int) -> str:
        clean_host = host.removeprefix("http://").removeprefix("https://")
        clean_host = clean_host.rstrip("/")
        if ":" in clean_host:
            return f"http://{clean_host}"
        return f"http://{clean_host}:{port}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
