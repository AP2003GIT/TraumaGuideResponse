from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Emotional Support Save Service"
    database_url: str = (
        "postgresql://support_app:support_app_dev_password"
        "@127.0.0.1:5432/emotional_support"
    )
    chat_retention_days: int = Field(default=10, ge=1, le=365)
    chat_max_saved_chats: int = Field(default=10, ge=1, le=1000)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
