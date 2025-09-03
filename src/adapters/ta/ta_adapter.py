from __future__ import annotations


def _none(*a, **k):
    return None


try:
    import ta as _ta

    rsi = getattr(_ta, "rsi", _none)
    sma = getattr(_ta, "sma", _none)
    ema = getattr(_ta, "ema", _none)
    macd = getattr(_ta, "macd", _none)
    bbands = getattr(_ta, "bbands", _none)
except Exception:
    rsi = sma = ema = macd = bbands = _none
try:
    import pandas_ta as _pta

    rsi_pta = getattr(_pta, "rsi", _none)
except Exception:
    rsi_pta = _none
