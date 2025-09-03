"""Data models for the data-hub module."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from src.adapters.db.sqlmodel_adapter import Field as SQLField
from src.adapters.db.sqlmodel_adapter import SQLModel


class AssetType(str, Enum):
    """Enumeration of supported asset types."""

    EQUITY = "equity"
    CRYPTO = "crypto"


class Timeframe(str, Enum):
    """Enumeration of supported timeframes."""

    ONE_MIN = "1m"
    FIVE_MIN = "5m"
    FIFTEEN_MIN = "15m"
    THIRTY_MIN = "30m"
    ONE_HOUR = "1h"
    FOUR_HOUR = "4h"
    ONE_DAY = "1d"
    ONE_WEEK = "1w"
    ONE_MONTH = "1M"


class SymbolInfo(BaseModel):
    """Symbol information model for API responses."""

    symbol: str = Field(..., description="Symbol ticker (e.g., AAPL, BTC/USDT)")
    name: str | None = Field(None, description="Full name of the asset")
    asset_type: AssetType = Field(..., description="Type of asset")
    exchange: str | None = Field(None, description="Exchange name for crypto")
    currency: str | None = Field(None, description="Quote currency")
    active: bool = Field(True, description="Whether the symbol is actively traded")


class OHLCVData(BaseModel):
    """OHLCV data model for API responses."""

    timestamp: datetime = Field(..., description="Candle timestamp")
    open: float = Field(..., description="Opening price")
    high: float = Field(..., description="Highest price")
    low: float = Field(..., description="Lowest price")
    close: float = Field(..., description="Closing price")
    volume: float = Field(..., description="Trading volume")


class OHLCVResponse(BaseModel):
    """Response model for OHLCV data requests."""

    symbol: str = Field(..., description="Symbol ticker")
    asset_type: AssetType = Field(..., description="Type of asset")
    timeframe: str = Field(..., description="Data timeframe")
    data: list[OHLCVData] = Field(..., description="OHLCV data points")
    cached: bool = Field(False, description="Whether data was served from cache")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")


class SymbolSearchResponse(BaseModel):
    """Response model for symbol search."""

    query: str = Field(..., description="Search query")
    asset_type: AssetType = Field(..., description="Asset type searched")
    results: list[SymbolInfo] = Field(..., description="Search results")
    count: int = Field(..., description="Number of results")


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str = Field("healthy", description="Service status")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Current timestamp")
    version: str = Field(..., description="API version")


class ErrorResponse(BaseModel):
    """Error response model."""

    error: str = Field(..., description="Error message")
    detail: str | None = Field(None, description="Detailed error information")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")


class CandleCache(SQLModel, table=True):
    """SQLModel for caching OHLCV data."""

    __tablename__ = "candle_cache"
    id: int | None = SQLField(default=None, primary_key=True)
    symbol: str = SQLField(index=True, nullable=False)
    asset_type: str = SQLField(nullable=False)
    timeframe: str = SQLField(nullable=False)
    exchange: str | None = SQLField(default=None)
    timestamp: datetime = SQLField(nullable=False)
    open: float = SQLField(nullable=False)
    high: float = SQLField(nullable=False)
    low: float = SQLField(nullable=False)
    close: float = SQLField(nullable=False)
    volume: float = SQLField(nullable=False)
    created_at: datetime = SQLField(default_factory=datetime.utcnow, nullable=False)
    cache_key: str = SQLField(index=True, nullable=False)

    class Config:
        """Pydantic config."""

        json_encoders = {datetime: lambda v: v.isoformat()}


class SymbolCache(SQLModel, table=True):
    """SQLModel for caching symbol information."""

    __tablename__ = "symbol_cache"
    id: int | None = SQLField(default=None, primary_key=True)
    symbol: str = SQLField(index=True, unique=True, nullable=False)
    name: str | None = SQLField(default=None)
    asset_type: str = SQLField(nullable=False)
    exchange: str | None = SQLField(default=None)
    currency: str | None = SQLField(default=None)
    active: bool = SQLField(default=True)
    created_at: datetime = SQLField(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = SQLField(default_factory=datetime.utcnow, nullable=False)
