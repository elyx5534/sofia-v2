class _Dummy:
    def __init__(self, *a, **k):
        pass

    def fetch_ticker(self, symbol):
        return {"last": 100.0}

    def fetch_ohlcv(self, symbol, timeframe="1h", since=None, limit=100):
        import time

        t = int(time.time() * 1000)
        return [[t, 1, 2, 0.5, 1.5, 123]]


binance = _Dummy
bybit = _Dummy
okx = _Dummy
