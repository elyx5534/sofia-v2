from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)

def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200

def test_metrics_ok():
    r = client.get("/metrics")
    assert r.status_code == 200
    assert len(r.text) > 0

def test_quotes_ohlcv_mock(monkeypatch):
    import src.services.datahub as dh
    def fake_get_ohlcv(asset, tf, start, end):
        return [[1700000000, 1.0, 2.0, 0.5, 1.5, 123.0]]
    monkeypatch.setattr(dh.datahub, "get_ohlcv", fake_get_ohlcv, raising=True)
    r = client.get("/api/quotes/ohlcv", params={
        "symbol":"BTC/USDT","tf":"1h","start":"2024-01-01","end":"2024-01-02"})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list) and len(data) >= 1 and len(data[0]) == 6

def test_backtest_run_mock(monkeypatch):
    import src.services.backtester as bt
    def fake_run(symbol, timeframe, start_date, end_date, strategy, params, config=None):
        return {
            "run_id": "test-123",
            "equity_curve": [[1,100.0],[2,101.0]],
            "drawdown": [[1,0.0],[2,-0.01]],
            "trades": [{"ts":1,"side":"buy","price":100.0}],
            "stats": {"total_return":0.01,"sharpe":1.0,"max_dd":-0.01,"winrate":1.0}
        }
    monkeypatch.setattr(bt.backtester, "run_backtest", fake_run, raising=False)
    payload = {
        "symbol":"BTC/USDT","timeframe":"1h",
        "start":"2023-01-01","end":"2023-02-01",
        "strategy":"sma_cross","params":{"fast":10,"slow":20}
    }
    r = client.post("/api/backtest/run", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert "run_id" in data
    assert "equity_curve" in data
    assert "stats" in data
    assert "total_return" in data["stats"]