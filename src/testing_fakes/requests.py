"""Fake requests module for offline testing."""


class Response:
    def __init__(self, json_data=None, status_code=200, text=""):
        self._json_data = json_data or {}
        self.status_code = status_code
        self.text = text

    def json(self):
        return self._json_data


def get(url, **kwargs):
    """Mock GET request - return fake data based on URL patterns."""
    if "binance.com" in url:
        if "klines" in url:
            return Response(
                [
                    [1704067200000, "50000", "50500", "49500", "50200", "1000"],
                    [1704070800000, "50200", "50700", "50100", "50500", "1100"],
                ]
            )
        elif "ticker/price" in url:
            return Response({"price": "52000.50"})
    elif "coinbase.com" in url:
        return Response([[1704067200, 49500, 50200, 50800, 50000, 1000]])
    elif "stooq.com" in url:
        csv_data = "Date,Open,High,Low,Close,Volume\n2024-01-01,100,101,99,100.5,1000\n2024-01-02,100.5,102,100,101.5,1100"
        return Response(text=csv_data)
    return Response({"status": "ok"})


def post(url, **kwargs):
    """Mock POST request."""
    return Response({"status": "success", "id": "mock-123"})
