"""
Technical indicators for cryptocurrency analysis
"""

from typing import Tuple

import numpy as np
import pandas as pd
from loguru import logger


def rsi(df: pd.DataFrame, period: int = 14, column: str = "close") -> pd.Series:
    """Calculate Relative Strength Index (RSI)"""
    try:
        if len(df) < period:
            return pd.Series(index=df.index, dtype=float)
        delta = df[column].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        rs = avg_gain / avg_loss
        rsi_values = 100 - 100 / (1 + rs)
        return rsi_values
    except Exception as e:
        logger.error(f"Error calculating RSI: {e}")
        return pd.Series(index=df.index, dtype=float)


def sma(df: pd.DataFrame, period: int, column: str = "close") -> pd.Series:
    """Calculate Simple Moving Average (SMA)"""
    try:
        return df[column].rolling(window=period).mean()
    except Exception as e:
        logger.error(f"Error calculating SMA: {e}")
        return pd.Series(index=df.index, dtype=float)


def ema(df: pd.DataFrame, period: int, column: str = "close") -> pd.Series:
    """Calculate Exponential Moving Average (EMA)"""
    try:
        return df[column].ewm(span=period).mean()
    except Exception as e:
        logger.error(f"Error calculating EMA: {e}")
        return pd.Series(index=df.index, dtype=float)


def bbands(
    df: pd.DataFrame, period: int = 20, std_dev: float = 2, column: str = "close"
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Calculate Bollinger Bands (Upper, Middle, Lower)"""
    try:
        if len(df) < period:
            empty_series = pd.Series(index=df.index, dtype=float)
            return (empty_series, empty_series, empty_series)
        middle = sma(df, period, column)
        std = df[column].rolling(window=period).std()
        upper = middle + std * std_dev
        lower = middle - std * std_dev
        return (upper, middle, lower)
    except Exception as e:
        logger.error(f"Error calculating Bollinger Bands: {e}")
        empty_series = pd.Series(index=df.index, dtype=float)
        return (empty_series, empty_series, empty_series)


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average True Range (ATR)"""
    try:
        high_low = df["high"] - df["low"]
        high_close = np.abs(df["high"] - df["close"].shift())
        low_close = np.abs(df["low"] - df["close"].shift())
        true_range = np.maximum(high_low, np.maximum(high_close, low_close))
        atr_values = pd.Series(true_range).rolling(window=period).mean()
        return atr_values
    except Exception as e:
        logger.error(f"Error calculating ATR: {e}")
        return pd.Series(index=df.index, dtype=float)


def macd(
    df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9, column: str = "close"
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Calculate MACD (MACD line, Signal line, Histogram)"""
    try:
        ema_fast = ema(df, fast, column)
        ema_slow = ema(df, slow, column)
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal).mean()
        histogram = macd_line - signal_line
        return (macd_line, signal_line, histogram)
    except Exception as e:
        logger.error(f"Error calculating MACD: {e}")
        empty_series = pd.Series(index=df.index, dtype=float)
        return (empty_series, empty_series, empty_series)


def stochastic(
    df: pd.DataFrame, k_period: int = 14, d_period: int = 3
) -> Tuple[pd.Series, pd.Series]:
    """Calculate Stochastic Oscillator (%K, %D)"""
    try:
        if len(df) < k_period:
            empty_series = pd.Series(index=df.index, dtype=float)
            return (empty_series, empty_series)
        lowest_low = df["low"].rolling(window=k_period).min()
        highest_high = df["high"].rolling(window=k_period).max()
        k_percent = 100 * ((df["close"] - lowest_low) / (highest_high - lowest_low))
        d_percent = k_percent.rolling(window=d_period).mean()
        return (k_percent, d_percent)
    except Exception as e:
        logger.error(f"Error calculating Stochastic: {e}")
        empty_series = pd.Series(index=df.index, dtype=float)
        return (empty_series, empty_series)


def volume_sma(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Calculate Volume Simple Moving Average"""
    try:
        return df["volume"].rolling(window=period).mean()
    except Exception as e:
        logger.error(f"Error calculating Volume SMA: {e}")
        return pd.Series(index=df.index, dtype=float)


def price_change_percent(df: pd.DataFrame, periods: int = 1, column: str = "close") -> pd.Series:
    """Calculate percentage price change over n periods"""
    try:
        return df[column].pct_change(periods=periods) * 100
    except Exception as e:
        logger.error(f"Error calculating price change: {e}")
        return pd.Series(index=df.index, dtype=float)


def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add all technical indicators to a DataFrame"""
    try:
        if df.empty or len(df) < 26:
            return df
        df_with_indicators = df.copy()
        df_with_indicators["rsi"] = rsi(df)
        df_with_indicators["sma_20"] = sma(df, 20)
        df_with_indicators["sma_50"] = sma(df, 50)
        df_with_indicators["ema_12"] = ema(df, 12)
        df_with_indicators["ema_26"] = ema(df, 26)
        bb_upper, bb_middle, bb_lower = bbands(df)
        df_with_indicators["bb_upper"] = bb_upper
        df_with_indicators["bb_middle"] = bb_middle
        df_with_indicators["bb_lower"] = bb_lower
        df_with_indicators["atr"] = atr(df)
        macd_line, signal_line, histogram = macd(df)
        df_with_indicators["macd"] = macd_line
        df_with_indicators["macd_signal"] = signal_line
        df_with_indicators["macd_histogram"] = histogram
        stoch_k, stoch_d = stochastic(df)
        df_with_indicators["stoch_k"] = stoch_k
        df_with_indicators["stoch_d"] = stoch_d
        df_with_indicators["volume_sma"] = volume_sma(df)
        df_with_indicators["price_change_1h"] = price_change_percent(df, 1)
        df_with_indicators["price_change_24h"] = price_change_percent(df, 24)
        return df_with_indicators
    except Exception as e:
        logger.error(f"Error adding indicators: {e}")
        return df


def get_latest_indicators(df: pd.DataFrame) -> dict:
    """Get latest indicator values as a dictionary"""
    try:
        if df.empty:
            return {}
        df_with_indicators = add_all_indicators(df)
        if df_with_indicators.empty:
            return {}
        latest = df_with_indicators.iloc[-1]
        return {
            "timestamp": latest.name,
            "open": float(latest.get("open", 0)),
            "high": float(latest.get("high", 0)),
            "low": float(latest.get("low", 0)),
            "close": float(latest.get("close", 0)),
            "volume": float(latest.get("volume", 0)),
            "rsi": float(latest.get("rsi", 50)),
            "sma_20": float(latest.get("sma_20", latest.get("close", 0))),
            "sma_50": float(latest.get("sma_50", latest.get("close", 0))),
            "bb_upper": float(latest.get("bb_upper", latest.get("close", 0))),
            "bb_middle": float(latest.get("bb_middle", latest.get("close", 0))),
            "bb_lower": float(latest.get("bb_lower", latest.get("close", 0))),
            "atr": float(latest.get("atr", 0)),
            "macd": float(latest.get("macd", 0)),
            "macd_signal": float(latest.get("macd_signal", 0)),
            "stoch_k": float(latest.get("stoch_k", 50)),
            "stoch_d": float(latest.get("stoch_d", 50)),
            "price_change_1h": float(latest.get("price_change_1h", 0)),
            "price_change_24h": float(latest.get("price_change_24h", 0)),
        }
    except Exception as e:
        logger.error(f"Error getting latest indicators: {e}")
        return {}
