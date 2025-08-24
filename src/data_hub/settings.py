"""Configuration settings for the data-hub module."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Cache settings
    cache_ttl: int = 600  # 10 minutes in seconds
    database_url: str = "sqlite+aiosqlite:///./data_hub.db"

    # Provider settings
    default_exchange: str = "binance"
    provider_timeout: int = 30  # seconds

    # API settings
    api_title: str = "Data Hub API"
    api_version: str = "0.1.0"
    api_description: str = "FastAPI service for OHLCV data with caching"

    # Logging
    log_level: str = "INFO"

    # Claude AI settings
    claude_api_key: str = ""
    claude_model: str = "claude-3-5-sonnet-20241022"
    claude_max_tokens: int = 4000

    # CORS settings
    cors_origins: list[str] = ["*"]
    cors_credentials: bool = True
    cors_methods: list[str] = ["*"]
    cors_headers: list[str] = ["*"]


settings = Settings()
