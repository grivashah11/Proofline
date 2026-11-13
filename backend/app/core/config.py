from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import (
    AliasChoices,
    Field,
    SecretStr,
    field_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    app_env: Literal["development", "test", "production"] = "development"
    app_name: str = "Proofline API"
    app_version: str = "0.1.0"

    api_v1_prefix: str = "/api/v1"

    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    supabase_url: str | None = None
    supabase_publishable_key: SecretStr | None = None

    # The existing internal names are retained to avoid breaking
    # current endpoint code and tests. These fields now accept
    # OpenRouter environment variables.
    openai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "OPENROUTER_API_KEY",
            "OPENAI_API_KEY",
        ),
    )

    openai_model: str = Field(
        default="openrouter/free",
        validation_alias=AliasChoices(
            "OPENROUTER_MODEL",
            "OPENAI_MODEL",
        ),
    )

    @field_validator("api_v1_prefix")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        value = value.strip()

        if not value.startswith("/") or value == "/" or value.endswith("/"):
            raise ValueError(
                "API_V1_PREFIX must start with '/' and must not end with '/'."
            )

        return value

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, origins: list[str]) -> list[str]:
        validated: list[str] = []

        for origin in origins:
            origin = origin.strip().rstrip("/")
            parsed = urlsplit(origin)

            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.path
                or parsed.query
                or parsed.fragment
                or origin == "*"
            ):
                raise ValueError(f"Invalid CORS origin: {origin}")

            if origin not in validated:
                validated.append(origin)

        return validated

    @field_validator("supabase_url", mode="before")
    @classmethod
    def empty_supabase_url_to_none(cls, value):
        if value is None or not str(value).strip():
            return None

        return str(value).strip().rstrip("/")

    @field_validator("supabase_url")
    @classmethod
    def validate_supabase_url(cls, value: str | None):
        if value is None:
            return None

        parsed = urlsplit(value)

        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("SUPABASE_URL must be a valid HTTP or HTTPS URL.")

        return value

    @field_validator("supabase_publishable_key", mode="before")
    @classmethod
    def empty_publishable_key_to_none(cls, value):
        if value is None or not str(value).strip():
            return None

        return value

    @field_validator("openai_api_key", mode="before")
    @classmethod
    def empty_ai_key_to_none(cls, value):
        if value is None or not str(value).strip():
            return None

        return value

    @field_validator("openai_model")
    @classmethod
    def validate_ai_model(cls, value: str) -> str:
        value = value.strip()

        if not value or len(value) > 100:
            raise ValueError("Invalid OPENROUTER_MODEL.")

        return value

    @property
    def supabase_is_configured(self) -> bool:
        return (
            self.supabase_url is not None and self.supabase_publishable_key is not None
        )

    @property
    def openai_is_configured(self) -> bool:
        """Compatibility property used by existing backend code."""
        return self.openai_api_key is not None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
