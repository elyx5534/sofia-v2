# thirdparty_stubs/talib/__init__.py
import numpy as np


def RSI(close, timeperiod=14):
    return np.array([50.0] * len(close))


def SMA(close, timeperiod=20):
    return np.array([100.0] * len(close))


def EMA(close, timeperiod=20):
    return np.array([100.0] * len(close))


def MACD(close, fastperiod=12, slowperiod=26, signalperiod=9):
    length = len(close)
    return (np.array([0.0] * length), np.array([0.0] * length), np.array([0.0] * length))


def BBANDS(close, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0):
    length = len(close)
    return (np.array([100.0] * length), np.array([100.0] * length), np.array([100.0] * length))


def STOCH(
    high, low, close, fastk_period=5, slowk_period=3, slowk_matype=0, slowd_period=3, slowd_matype=0
):
    length = len(close)
    return (np.array([50.0] * length), np.array([50.0] * length))


def ATR(high, low, close, timeperiod=14):
    return np.array([1.0] * len(close))


def ADX(high, low, close, timeperiod=14):
    return np.array([25.0] * len(close))


__all__ = ["RSI", "SMA", "EMA", "MACD", "BBANDS", "STOCH", "ATR", "ADX"]
