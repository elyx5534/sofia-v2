# thirdparty_stubs/ta/__init__.py
def rsi(*args, **kwargs):
    return [50.0] * 10


def sma(*args, **kwargs):
    return [100.0] * 10


def ema(*args, **kwargs):
    return [100.0] * 10


def macd(*args, **kwargs):
    return ([0.0] * 10, [0.0] * 10, [0.0] * 10)


def bbands(*args, **kwargs):
    return ([100.0] * 10, [100.0] * 10, [100.0] * 10)


def stoch(*args, **kwargs):
    return ([50.0] * 10, [50.0] * 10)


def atr(*args, **kwargs):
    return [1.0] * 10


def adx(*args, **kwargs):
    return [25.0] * 10


__all__ = ["rsi", "sma", "ema", "macd", "bbands", "stoch", "atr", "adx"]
