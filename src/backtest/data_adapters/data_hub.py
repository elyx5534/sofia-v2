"""Data Hub adapter for fetching OHLCV data."""

from datetime import datetime
from typing import Optional

import httpx
import pandas as pd

from src.data_hub.models import AssetType


class DataHubAdapter:
    """Adapter for fetching data from Data Hub API."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        """
        Initialize Data Hub adapter.

        Args:
            base_url: Base URL of Data Hub API
        """
        self.base_url = base_url
        self.client = httpx.Client(timeout=30.0)

    def fetch_ohlcv(
        self,
        symbol: str,
        asset_type: AssetType,
        timeframe: str = "1d",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 500,
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data from Data Hub.

        Args:
            symbol: Trading symbol
            asset_type: Type of asset (crypto, stock, etc.)
            timeframe: Data timeframe (1m, 5m, 1h, 1d, etc.)
            start_date: Start date for data
            end_date: End date for data
            limit: Maximum number of records

        Returns:
            DataFrame with OHLCV data
        """
        params = {
            "symbol": symbol,
            "asset_type": asset_type.value,
            "timeframe": timeframe,
            "limit": limit,
        }
        if start_date:
            params["start_date"] = start_date.isoformat()
        if end_date:
            params["end_date"] = end_date.isoformat()
        try:
            response = self.client.get(f"{self.base_url}/ohlcv", params=params)
            response.raise_for_status()
            data = response.json()
            if not data or "data" not in data:
                return pd.DataFrame()
            df = pd.DataFrame(data["data"])
            if df.empty:
                return df
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df.set_index("timestamp", inplace=True)
            numeric_cols = ["open", "high", "low", "close", "volume"]
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            return df
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ValueError(f"Symbol {symbol} not found")
            raise RuntimeError(f"HTTP error: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to fetch data: {e}")

    def __del__(self):
        """Cleanup HTTP client."""
        if hasattr(self, "client"):
            self.client.close()
