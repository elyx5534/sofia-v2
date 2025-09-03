"""Technical indicators calculation module."""

from typing import Tuple, Union

import numpy as np
import pandas as pd


class TechnicalIndicators:
    """Calculate various technical indicators for trading analysis."""

    @staticmethod
    def sma(data: pd.Series, window: int) -> pd.Series:
        """
        Simple Moving Average.

        Args:
            data: Price series
            window: Period for moving average

        Returns:
            SMA series
        """
        return data.rolling(window=window).mean()

    @staticmethod
    def ema(data: pd.Series, window: int) -> pd.Series:
        """
        Exponential Moving Average.

        Args:
            data: Price series
            window: Period for moving average

        Returns:
            EMA series
        """
        return data.ewm(span=window, adjust=False).mean()

    @staticmethod
    def rsi(data: pd.Series, period: int = 14) -> pd.Series:
        """
        Relative Strength Index.

        Args:
            data: Price series
            period: RSI period (default 14)

        Returns:
            RSI series (0-100)
        """
        delta = data.diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - 100 / (1 + rs)
        return rsi

    @staticmethod
    def macd(
        data: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        MACD (Moving Average Convergence Divergence).

        Args:
            data: Price series
            fast: Fast EMA period (default 12)
            slow: Slow EMA period (default 26)
            signal: Signal line EMA period (default 9)

        Returns:
            Tuple of (MACD line, Signal line, Histogram)
        """
        ema_fast = data.ewm(span=fast, adjust=False).mean()
        ema_slow = data.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return (macd_line, signal_line, histogram)

    @staticmethod
    def bollinger_bands(
        data: pd.Series, window: int = 20, num_std: float = 2
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Bollinger Bands.

        Args:
            data: Price series
            window: Period for moving average (default 20)
            num_std: Number of standard deviations (default 2)

        Returns:
            Tuple of (Upper band, Middle band (SMA), Lower band)
        """
        middle = data.rolling(window=window).mean()
        std = data.rolling(window=window).std()
        upper = middle + std * num_std
        lower = middle - std * num_std
        return (upper, middle, lower)

    @staticmethod
    def stochastic(
        high: pd.Series, low: pd.Series, close: pd.Series, k_period: int = 14, d_period: int = 3
    ) -> Tuple[pd.Series, pd.Series]:
        """
        Stochastic Oscillator.

        Args:
            high: High price series
            low: Low price series
            close: Close price series
            k_period: Period for %K (default 14)
            d_period: Period for %D (default 3)

        Returns:
            Tuple of (%K, %D)
        """
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()
        k_percent = 100 * ((close - lowest_low) / (highest_high - lowest_low))
        d_percent = k_percent.rolling(window=d_period).mean()
        return (k_percent, d_percent)

    @staticmethod
    def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """
        Average True Range.

        Args:
            high: High price series
            low: Low price series
            close: Close price series
            period: ATR period (default 14)

        Returns:
            ATR series
        """
        high_low = high - low
        high_close = np.abs(high - close.shift())
        low_close = np.abs(low - close.shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        return true_range.rolling(window=period).mean()

    @staticmethod
    def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
        """
        On-Balance Volume.

        Args:
            close: Close price series
            volume: Volume series

        Returns:
            OBV series
        """
        obv = (np.sign(close.diff()) * volume).fillna(0).cumsum()
        return obv

    @staticmethod
    def vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
        """
        Volume Weighted Average Price.

        Args:
            high: High price series
            low: Low price series
            close: Close price series
            volume: Volume series

        Returns:
            VWAP series
        """
        typical_price = (high + low + close) / 3
        return (typical_price * volume).cumsum() / volume.cumsum()

    @staticmethod
    def calculate_all(df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate all indicators for a DataFrame with OHLCV data.

        Args:
            df: DataFrame with columns: open, high, low, close, volume

        Returns:
            DataFrame with all indicators added as new columns
        """
        result = df.copy()
        result["sma_20"] = TechnicalIndicators.sma(df["close"], 20)
        result["sma_50"] = TechnicalIndicators.sma(df["close"], 50)
        result["ema_12"] = TechnicalIndicators.ema(df["close"], 12)
        result["ema_26"] = TechnicalIndicators.ema(df["close"], 26)
        result["rsi"] = TechnicalIndicators.rsi(df["close"])
        macd, signal, histogram = TechnicalIndicators.macd(df["close"])
        result["macd"] = macd
        result["macd_signal"] = signal
        result["macd_histogram"] = histogram
        upper, middle, lower = TechnicalIndicators.bollinger_bands(df["close"])
        result["bb_upper"] = upper
        result["bb_middle"] = middle
        result["bb_lower"] = lower
        k, d = TechnicalIndicators.stochastic(df["high"], df["low"], df["close"])
        result["stoch_k"] = k
        result["stoch_d"] = d
        result["atr"] = TechnicalIndicators.atr(df["high"], df["low"], df["close"])
        if "volume" in df.columns:
            result["obv"] = TechnicalIndicators.obv(df["close"], df["volume"])
            result["vwap"] = TechnicalIndicators.vwap(
                df["high"], df["low"], df["close"], df["volume"]
            )
        return result


def calculate_rsi(prices: Union[pd.Series, list, np.ndarray], period: int = 14) -> float:
    """Calculate current RSI value."""
    if isinstance(prices, (list, np.ndarray)):
        prices = pd.Series(prices)
    indicators = TechnicalIndicators()
    rsi_series = indicators.rsi(prices, period)
    return rsi_series.iloc[-1] if not rsi_series.empty else 50.0


def calculate_sma(prices: Union[pd.Series, list, np.ndarray], window: int) -> float:
    """Calculate current SMA value."""
    if isinstance(prices, (list, np.ndarray)):
        prices = pd.Series(prices)
    indicators = TechnicalIndicators()
    sma_series = indicators.sma(prices, window)
    return sma_series.iloc[-1] if not sma_series.empty else prices.iloc[-1]
