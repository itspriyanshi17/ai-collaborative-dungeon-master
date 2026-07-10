from functools import lru_cache
import json
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
]


class Settings(BaseSettings):
    app_name: str = "AI Collaborative Dungeon Master"
    environment: str = "local"
    database_url: str = Field(default="")
    jwt_secret_key: str = Field(default="")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30
    auth_cookie_secure: bool = False
    gemini_api_key: str = ""
    allowed_origins: list[str] = Field(default_factory=lambda: DEFAULT_ALLOWED_ORIGINS.copy())

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: Any) -> list[str]:
        if value is None or value == "":
            return DEFAULT_ALLOWED_ORIGINS.copy()

        if isinstance(value, str):
            parsed = json.loads(value) if value.strip().startswith("[") else value.split(",")
        else:
            parsed = value

        if not isinstance(parsed, list):
            raise ValueError("ALLOWED_ORIGINS must be a JSON array or comma-separated list")

        return [str(origin).strip() for origin in parsed if str(origin).strip()]

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
