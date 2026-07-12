from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration with production safety checks."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "sqlite:///./unbound_bible.db"
    jwt_secret_key: str = "development-only-secret-change-before-production"
    public_base_url: str = "http://localhost:5001"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5001"])
    ai_chat_provider: str = "demo"
    ai_embedding_provider: str = "demo"
    ai_transcription_provider: str = "demo"
    ai_api_key: str | None = None
    ai_chat_model: str = "gpt-4o-mini"
    ai_embedding_model: str = "text-embedding-3-small"
    ai_transcription_model: str = "whisper-1"
    openai_compatible_base_url: str = "https://api.openai.com/v1"
    ollama_base_url: str = "http://localhost:11434"
    access_token_minutes: int = 15
    refresh_token_days: int = 30

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        if self.environment != "production":
            return self

        errors: list[str] = []
        if len(self.jwt_secret_key) < 32 or "development" in self.jwt_secret_key.lower():
            errors.append("JWT secret must be at least 32 characters and production-specific")
        if "*" in self.cors_origins:
            errors.append("Wildcard CORS is not allowed in production")
        if not self.database_url.startswith(("postgresql://", "postgresql+psycopg2://")):
            errors.append("Production database must use PostgreSQL")
        if not self.public_base_url.startswith("https://"):
            errors.append("Production public URL must use HTTPS")
        if errors:
            raise ValueError("; ".join(errors))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
