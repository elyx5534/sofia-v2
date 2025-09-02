"""
Smoke Tests - Quick validation of critical functionality
"""

import asyncio
from pathlib import Path

import pytest


def test_critical_imports():
    """Test that all critical modules can be imported"""
    imports_to_test = [
        ("src.core.accounting", "FIFOAccounting"),
        ("src.core.watchdog", "Watchdog"),
        ("src.core.profit_guard", "ProfitGuard"),
        ("src.paper_trading.fill_engine", "RealisticFillEngine"),
        ("src.trading.turkish_arbitrage", "TurkishArbitrage"),
        ("src.trading.arbitrage_rules", "ArbitrageMicroRules"),
        ("src.trading.live_pilot", "LiveTradingPilot"),
        ("src.reporting.daily_report", "DailyReportGenerator"),
        ("src.strategies.grid_auto_tuner", "GridAutoTuner"),
    ]

    failed_imports = []

    for module_path, class_name in imports_to_test:
        try:
            module = __import__(module_path, fromlist=[class_name])
            cls = getattr(module, class_name)
            assert cls is not None
            print(f"✅ {module_path}.{class_name}")
        except Exception as e:
            failed_imports.append(f"{module_path}.{class_name}: {e!s}")
            print(f"❌ {module_path}.{class_name}: {e!s}")

    assert len(failed_imports) == 0, f"Failed imports: {failed_imports}"


def test_config_files_exist():
    """Test that required config files exist or can be created"""
    config_files = [
        "config/risk.yaml",
        "config/pilot.json",
    ]

    for config_file in config_files:
        path = Path(config_file)
        if not path.exists():
            # Create parent directory if needed
            path.parent.mkdir(exist_ok=True, parents=True)
            print(f"⚠️  {config_file} does not exist (will be created at runtime)")
        else:
            print(f"✅ {config_file} exists")


def test_log_directories():
    """Test that log directories can be created"""
    log_dirs = [
        "logs",
        "reports",
        "artifacts",
    ]

    for log_dir in log_dirs:
        path = Path(log_dir)
        path.mkdir(exist_ok=True)
        assert path.exists()
        print(f"✅ {log_dir}/ directory ready")


@pytest.mark.asyncio
async def test_watchdog_initialization():
    """Test watchdog can be initialized"""
    from src.core.watchdog import Watchdog

    watchdog = Watchdog()
    assert watchdog.state.status == "NORMAL"
    print("✅ Watchdog initialized")


@pytest.mark.asyncio
async def test_profit_guard_initialization():
    """Test profit guard can be initialized"""
    from src.core.profit_guard import ProfitGuard

    guard = ProfitGuard()
    assert guard.state.current_scale_factor == 1.0
    print("✅ Profit guard initialized")


@pytest.mark.asyncio
async def test_fill_engine_initialization():
    """Test fill engine can be initialized"""
    from src.paper_trading.fill_engine import RealisticFillEngine

    engine = RealisticFillEngine()
    assert engine.metrics is not None
    print("✅ Fill engine initialized")


def test_accounting_basic_operation():
    """Test basic FIFO accounting operation"""
    from decimal import Decimal

    from src.core.accounting import FIFOAccounting

    accounting = FIFOAccounting()

    # Test basic buy
    buy_fill = type(
        "Fill",
        (),
        {
            "symbol": "BTC/USDT",
            "side": "buy",
            "price": Decimal("50000"),
            "quantity": Decimal("0.1"),
            "fee_pct": Decimal("0.1"),  # 0.1% fee
            "fill_id": "test-fill-1",
            "timestamp": "2024-01-01T00:00:00",
        },
    )()

    result = accounting.update_on_fill(buy_fill)
    assert "realized_pnl" in result
    print("✅ FIFO accounting works")


def test_grid_tuner_basic():
    """Test grid auto-tuner basic functionality"""
    from src.strategies.grid_auto_tuner import GridAutoTuner

    tuner = GridAutoTuner()

    # Test with dummy candle data
    candles = [
        {"high": 51000, "low": 49000, "close": 50000, "volume": 100},
        {"high": 51500, "low": 49500, "close": 51000, "volume": 120},
    ]

    conditions = tuner.analyze_market(candles, 50000)
    assert conditions.volatility_regime in ["low", "normal", "high", "extreme"]
    print("✅ Grid auto-tuner works")


def test_live_pilot_modes():
    """Test live pilot trading modes"""
    from src.trading.live_pilot import LiveTradingPilot, TradingMode

    pilot = LiveTradingPilot()
    assert pilot.state.mode == TradingMode.PAPER

    # Test trade permission in paper mode
    can_trade, reason = pilot.can_execute_trade({"symbol": "BTC/USDT", "size_usd": 100})
    assert can_trade is True
    print("✅ Live pilot system works")


def test_report_generator():
    """Test daily report generator initialization"""
    from src.reporting.daily_report import DailyReportGenerator

    generator = DailyReportGenerator()
    assert generator.report_time == "16:00"
    print("✅ Report generator initialized")


if __name__ == "__main__":
    # Run smoke tests
    print("=" * 60)
    print("RUNNING SMOKE TESTS")
    print("=" * 60)

    test_critical_imports()
    test_config_files_exist()
    test_log_directories()

    # Run async tests
    asyncio.run(test_watchdog_initialization())
    asyncio.run(test_profit_guard_initialization())
    asyncio.run(test_fill_engine_initialization())

    test_accounting_basic_operation()
    test_grid_tuner_basic()
    test_live_pilot_modes()
    test_report_generator()

    print("=" * 60)
    print("✅ ALL SMOKE TESTS PASSED")
    print("=" * 60)
