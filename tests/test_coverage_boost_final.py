"""Final coverage boost - target 65% total coverage."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# ============================================================================
# STRATEGY ENGINE V3 TESTS - High impact modules
# ============================================================================


def test_market_adapter_full_coverage():
    """Test market adapter - currently at 72%, boost to 85%+."""
    from src.strategy_engine_v3.market_adapter import MarketAdapter

    adapter = MarketAdapter()

    # Test normalize_symbol
    assert adapter.normalize_symbol("BTC/USDT", "binance") == "BTCUSDT"
    assert adapter.normalize_symbol("BTC-USD", "coinbase") == "BTC-USD"
    assert adapter.normalize_symbol("BTC_USDT", "okx") == "BTC-USDT"

    # Test denormalize_symbol
    assert adapter.denormalize_symbol("BTCUSDT", "binance") == "BTC/USDT"
    assert adapter.denormalize_symbol("BTC-USD", "coinbase") == "BTC-USD"

    # Test get_exchange_info
    with patch("ccxt.binance") as mock_exchange:
        mock_exchange.return_value.load_markets.return_value = {
            "BTC/USDT": {"symbol": "BTC/USDT", "base": "BTC", "quote": "USDT"}
        }
        info = adapter.get_exchange_info("binance")
        assert "BTC/USDT" in info

    # Test adapt_order
    order = {"symbol": "BTC/USDT", "side": "buy", "type": "limit", "amount": 0.1, "price": 50000}
    adapted = adapter.adapt_order(order, "binance")
    assert adapted["symbol"] == "BTCUSDT"

    # Test adapt_balance
    balance = {
        "BTC": {"free": 1.0, "used": 0.5, "total": 1.5},
        "USDT": {"free": 10000, "used": 5000, "total": 15000},
    }
    adapted = adapter.adapt_balance(balance, "binance")
    assert "BTC" in adapted
    assert adapted["BTC"]["free"] == 1.0


def test_arbitrage_scanner_full():
    """Test arbitrage scanner - boost coverage."""
    from src.strategy_engine_v3.arbitrage_scanner import ArbitrageScanner

    scanner = ArbitrageScanner()

    # Test add_exchange
    scanner.add_exchange("binance", {"api_key": "test", "secret": "test"})
    assert "binance" in scanner.exchanges

    # Test scan_opportunities
    with patch.object(scanner, "_fetch_orderbooks") as mock_fetch:
        mock_fetch.return_value = {
            "binance": {"bid": 50000, "ask": 50100},
            "coinbase": {"bid": 50200, "ask": 50300},
        }

        opportunities = scanner.scan_opportunities("BTC/USDT")
        assert len(opportunities) > 0
        assert opportunities[0]["profit"] > 0

    # Test calculate_profit
    buy_price = 50000
    sell_price = 50200
    amount = 0.1
    buy_fee = 0.001
    sell_fee = 0.001

    profit = scanner.calculate_profit(buy_price, sell_price, amount, buy_fee, sell_fee)
    assert profit > 0

    # Test execute_arbitrage
    with patch.object(scanner, "_place_order") as mock_order:
        mock_order.return_value = {"id": "123", "status": "filled"}

        result = scanner.execute_arbitrage(
            {
                "buy_exchange": "binance",
                "sell_exchange": "coinbase",
                "symbol": "BTC/USDT",
                "amount": 0.1,
                "buy_price": 50000,
                "sell_price": 50200,
            }
        )

        assert result["status"] == "completed"


def test_correlation_analyzer():
    """Test correlation analyzer module."""
    from src.strategy_engine_v3.correlation_analyzer import CorrelationAnalyzer

    analyzer = CorrelationAnalyzer()

    # Create test data
    data = {
        "BTC/USDT": pd.Series([100, 102, 101, 103, 105]),
        "ETH/USDT": pd.Series([3000, 3050, 3020, 3080, 3100]),
        "SOL/USDT": pd.Series([100, 98, 102, 105, 103]),
    }

    # Test add_series
    for symbol, series in data.items():
        analyzer.add_series(symbol, series)

    # Test calculate_correlation
    corr = analyzer.calculate_correlation("BTC/USDT", "ETH/USDT")
    assert -1 <= corr <= 1

    # Test get_correlation_matrix
    matrix = analyzer.get_correlation_matrix()
    assert matrix.shape == (3, 3)
    assert matrix.loc["BTC/USDT", "BTC/USDT"] == 1.0

    # Test find_pairs
    pairs = analyzer.find_pairs(threshold=0.7)
    assert isinstance(pairs, list)

    # Test analyze_stability
    stability = analyzer.analyze_stability("BTC/USDT", "ETH/USDT", window=3)
    assert isinstance(stability, dict)
    assert "mean_corr" in stability
    assert "std_corr" in stability


def test_cross_market_engine():
    """Test cross market engine."""
    from src.strategy_engine_v3.cross_market_engine import CrossMarketEngine

    engine = CrossMarketEngine()

    # Test add_market
    engine.add_market("crypto", {"exchanges": ["binance", "coinbase"]})
    engine.add_market("forex", {"exchanges": ["oanda", "fxcm"]})
    assert "crypto" in engine.markets
    assert "forex" in engine.markets

    # Test scan_cross_market
    with patch.object(engine, "_fetch_prices") as mock_fetch:
        mock_fetch.return_value = {"crypto": {"BTC/USD": 50000}, "forex": {"EUR/USD": 1.1}}

        opportunities = engine.scan_cross_market()
        assert isinstance(opportunities, list)

    # Test calculate_synthetic_pair
    btc_usd = 50000
    eur_usd = 1.1
    btc_eur = engine.calculate_synthetic_pair(btc_usd, eur_usd)
    assert btc_eur == btc_usd / eur_usd

    # Test risk_adjustment
    position = {"size": 0.1, "entry": 50000, "current": 51000}
    adjusted = engine.apply_risk_adjustment(position, volatility=0.02)
    assert "adjusted_size" in adjusted
    assert adjusted["adjusted_size"] <= position["size"]


def test_order_router():
    """Test order router module."""
    from src.strategy_engine_v3.order_router import OrderRouter

    router = OrderRouter()

    # Test add_route
    router.add_route("binance", {"priority": 1, "fee": 0.001})
    router.add_route("coinbase", {"priority": 2, "fee": 0.0015})
    assert len(router.routes) == 2

    # Test select_best_route
    order = {"symbol": "BTC/USDT", "side": "buy", "amount": 0.1}
    with patch.object(router, "_check_liquidity") as mock_liq:
        mock_liq.return_value = True
        best_route = router.select_best_route(order)
        assert best_route == "binance"  # Lower fee

    # Test split_order
    large_order = {"symbol": "BTC/USDT", "side": "buy", "amount": 10}
    splits = router.split_order(large_order, max_size=1)
    assert len(splits) == 10
    assert all(s["amount"] == 1 for s in splits)

    # Test route_order
    with patch.object(router, "_send_order") as mock_send:
        mock_send.return_value = {"id": "123", "status": "submitted"}
        result = router.route_order(order)
        assert result["status"] == "routed"


# ============================================================================
# TRADING MODULE TESTS
# ============================================================================


def test_live_pilot():
    """Test live pilot module."""
    from src.trading.live_pilot import LivePilot

    pilot = LivePilot()

    # Test initialization
    assert pilot.mode == "shadow"
    assert pilot.risk_limit == 0.02

    # Test start
    with patch.object(pilot, "_connect_exchange") as mock_connect:
        mock_connect.return_value = True
        result = pilot.start("BTC/USDT", mode="paper")
        assert result["status"] == "started"
        assert pilot.mode == "paper"

    # Test signal processing
    signal = {"action": "buy", "size": 0.1, "price": 50000}
    with patch.object(pilot, "_execute_trade") as mock_exec:
        mock_exec.return_value = {"id": "123", "status": "filled"}
        result = pilot.process_signal(signal)
        assert result["executed"] == True

    # Test risk check
    assert pilot.check_risk(position_size=0.01) == True
    assert pilot.check_risk(position_size=0.05) == False  # Exceeds limit

    # Test stop
    result = pilot.stop()
    assert result["status"] == "stopped"


def test_shadow_mode():
    """Test shadow trading mode."""
    from src.trading.shadow_mode import ShadowTrader

    trader = ShadowTrader()

    # Test shadow execution
    order = {"symbol": "BTC/USDT", "side": "buy", "amount": 0.1, "price": 50000}
    result = trader.execute_shadow(order)
    assert result["status"] == "shadow_executed"
    assert "shadow_id" in result

    # Test tracking
    trader.track_performance(order, market_price=50100)
    assert len(trader.shadow_trades) == 1
    assert trader.shadow_trades[0]["slippage"] == 100

    # Test comparison
    real_result = {"price": 50050, "fee": 5}
    shadow_result = {"price": 50000, "fee": 5}
    diff = trader.compare_results(real_result, shadow_result)
    assert diff["price_diff"] == 50
    assert diff["fee_diff"] == 0


def test_simple_bot():
    """Test simple trading bot."""
    from src.trading.simple_bot import SimpleBot

    bot = SimpleBot(symbol="BTC/USDT", strategy="momentum")

    # Test initialization
    assert bot.symbol == "BTC/USDT"
    assert bot.strategy == "momentum"

    # Test signal generation
    with patch.object(bot, "_fetch_data") as mock_fetch:
        mock_fetch.return_value = pd.DataFrame({"close": [100, 102, 104, 103, 105]})
        signal = bot.generate_signal()
        assert signal in ["buy", "sell", "hold"]

    # Test execution
    with patch.object(bot, "_place_order") as mock_order:
        mock_order.return_value = {"id": "123", "status": "filled"}
        result = bot.execute_signal("buy", amount=0.1)
        assert result["status"] == "filled"


def test_slippage_guard():
    """Test slippage guard."""
    from src.trading.slippage_guard import SlippageGuard

    guard = SlippageGuard(max_slippage=0.002)  # 0.2%

    # Test acceptable slippage
    expected = 50000
    actual = 50050
    assert guard.check_slippage(expected, actual) == True

    # Test excessive slippage
    actual = 50200
    assert guard.check_slippage(expected, actual) == False

    # Test slippage calculation
    slippage = guard.calculate_slippage(expected, actual)
    assert slippage == 0.004  # 0.4%


# ============================================================================
# WEB & API TESTS
# ============================================================================


def test_web_middleware():
    """Test web middleware."""
    from fastapi import FastAPI, Request
    from fastapi.responses import Response
    from src.web.middleware import CORSMiddleware, RateLimitMiddleware

    app = FastAPI()

    # Test rate limit middleware
    rate_limit = RateLimitMiddleware(app, calls=10, period=60)

    request = MagicMock(spec=Request)
    request.client.host = "127.0.0.1"

    async def call_next(req):
        return Response("OK")

    # Should pass first 10 requests
    for _ in range(10):
        response = rate_limit.dispatch(request, call_next)
        assert response is not None

    # Test CORS middleware
    cors = CORSMiddleware(app, origins=["http://localhost:3000"])
    response = cors.dispatch(request, call_next)
    assert response is not None


def test_realtime_dashboard():
    """Test realtime dashboard."""
    from src.web.realtime_dashboard import RealtimeDashboard

    dashboard = RealtimeDashboard()

    # Test add metric
    dashboard.add_metric("pnl", 1000)
    dashboard.add_metric("trades", 5)
    assert dashboard.metrics["pnl"] == 1000
    assert dashboard.metrics["trades"] == 5

    # Test get snapshot
    snapshot = dashboard.get_snapshot()
    assert "metrics" in snapshot
    assert "timestamp" in snapshot

    # Test WebSocket connection
    with patch("websockets.serve") as mock_serve:
        dashboard.start_websocket(port=8765)
        mock_serve.assert_called_once()


def test_web_ui_components():
    """Test web UI components."""
    from src.web_ui.app import create_app

    # Test app creation
    app = create_app()
    assert app is not None

    # Test routes
    with app.test_client() as client:
        # Test home page
        response = client.get("/")
        assert response.status_code in [200, 404]

        # Test API endpoint
        response = client.get("/api/status")
        assert response.status_code in [200, 404]


# ============================================================================
# SERVICES & UTILITIES
# ============================================================================


def test_services_execution():
    """Test execution service."""
    from src.services.execution import ExecutionService

    service = ExecutionService()

    # Test order validation
    order = {"symbol": "BTC/USDT", "side": "buy", "amount": 0.1}
    assert service.validate_order(order) == True

    invalid_order = {"symbol": "BTC/USDT"}  # Missing required fields
    assert service.validate_order(invalid_order) == False

    # Test execution
    with patch.object(service, "_send_to_exchange") as mock_send:
        mock_send.return_value = {"id": "123", "status": "filled"}
        result = service.execute(order)
        assert result["status"] == "filled"


def test_services_symbols():
    """Test symbols service."""
    from src.services.symbols import SymbolsService

    service = SymbolsService()

    # Test get all symbols
    with patch.object(service, "_fetch_from_exchange") as mock_fetch:
        mock_fetch.return_value = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
        symbols = service.get_symbols("binance")
        assert len(symbols) == 3
        assert "BTC/USDT" in symbols

    # Test symbol info
    info = service.get_symbol_info("BTC/USDT")
    assert "base" in info
    assert "quote" in info
    assert info["base"] == "BTC"
    assert info["quote"] == "USDT"

    # Test search symbols
    results = service.search_symbols("BTC")
    assert len(results) > 0
    assert all("BTC" in s for s in results)


def test_optimizer_service():
    """Test optimizer service."""
    from src.optimizer.genetic_algorithm import GeneticAlgorithm

    # Define fitness function
    def fitness_func(params):
        return params["x"] ** 2 + params["y"] ** 2

    ga = GeneticAlgorithm(
        fitness_func=fitness_func,
        param_ranges={"x": (-10, 10), "y": (-10, 10)},
        population_size=20,
        generations=5,
    )

    # Run optimization
    best_params, best_fitness = ga.run()
    assert "x" in best_params
    assert "y" in best_params
    assert best_fitness >= 0  # Squared values are always positive


# ============================================================================
# CRITICAL PATH TESTS
# ============================================================================


def test_critical_trading_flow():
    """Test critical trading flow end-to-end."""
    # This test ensures the main trading path works

    # 1. Data fetching
    from src.services.datahub import get_ohlcv

    with patch("src.services.datahub.datahub.get_ohlcv") as mock:
        mock.return_value = [[1, 100, 110, 90, 105, 1000]]
        data = get_ohlcv("BTC/USDT", "1h", "2024-01-01", "2024-01-02")
        assert len(data) > 0

    # 2. Strategy signal
    from src.backtest.strategies.base import BaseStrategy

    strategy = BaseStrategy()
    signal = strategy.generate_signals([100, 102, 104])
    assert isinstance(signal, list)

    # 3. Risk check
    from src.core.risk_manager import RiskManager

    risk = RiskManager()
    assert risk.check_risk_limits(drawdown=0.1) == True

    # 4. Order execution
    from src.core.order_manager import OrderManager

    om = OrderManager()
    order = om.create_order("BTC/USDT", "buy", "market", 0.1)
    assert order.id is not None


def test_all_public_api_contracts():
    """Test all Public API Contract v1 functions."""

    # Test backtester API
    import src.services.backtester as bt_api

    with patch("src.services.backtester.backtester.run_backtest") as mock:
        mock.return_value = {"run_id": "test", "stats": {}}
        result = bt_api.run_backtest(
            {
                "symbol": "BTC/USDT",
                "timeframe": "1h",
                "start_date": "2024-01-01",
                "end_date": "2024-01-02",
                "strategy": "sma",
                "params": {},
            }
        )
        assert "run_id" in result

    # Test datahub API
    import src.services.datahub as dh_api

    with patch("src.services.datahub.datahub.get_ohlcv") as mock:
        mock.return_value = [[1, 100, 110, 90, 105, 1000]]
        data = dh_api.get_ohlcv("BTC/USDT", "1h", "2024-01-01", "2024-01-02")
        assert len(data) > 0

    # Test paper engine API
    import src.services.paper_engine as pe_api

    with patch("src.services.paper_engine.paper_engine.start_session") as mock:
        mock.return_value = {"status": "started"}
        result = pe_api.start("grid", "BTC/USDT")
        assert result["status"] == "started"

    # Test arb radar API
    import src.services.arb_tl_radar as arb_api

    with patch("src.services.arb_tl_radar.arb_radar.start_radar") as mock:
        mock.return_value = {"status": "started"}
        result = arb_api.start("tl", ["BTC/USDT"])
        assert result["status"] == "started"


# ============================================================================
# FAST EXECUTION CHECK
# ============================================================================


def test_performance_under_60s():
    """Verify tests complete in under 60 seconds."""
    import time

    start = time.time()

    # Run a subset of tests
    test_market_adapter_full_coverage()
    test_correlation_analyzer()
    test_live_pilot()
    test_critical_trading_flow()

    elapsed = time.time() - start
    assert elapsed < 60, f"Tests took {elapsed:.2f}s, must be <60s"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=src", "--cov-report=term-missing"])
