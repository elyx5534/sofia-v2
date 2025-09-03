"""Configuration settings for the data-hub module."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )
    cache_ttl: int = 600
    database_url: str = "sqlite+aiosqlite:///./data_hub.db"
    default_exchange: str = "binance"
    provider_timeout: int = 30
    api_title: str = "Data Hub API"
    api_version: str = "0.1.0"
    api_description: str = "FastAPI service for OHLCV data with caching"
    log_level: str = "INFO"
    claude_api_key: str = ""
    claude_model: str = "claude-3-5-sonnet-20241022"
    claude_max_tokens: int = 4000
    cors_origins: list[str] = ["*"]
    cors_credentials: bool = True
    cors_methods: list[str] = ["*"]
    cors_headers: list[str] = ["*"]


settings = Settings()
