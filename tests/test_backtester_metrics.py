"""Tests for backtester metrics calculations."""

import pytest
from src.backtester.metrics import calculate_metrics


class TestMetrics:
    """Test suite for metrics calculations."""

    def test_empty_data_returns_zeros(self):
        """Test that empty data returns zero metrics."""
        metrics = calculate_metrics([], [])

        assert metrics["sharpe_ratio"] == 0.0
        assert metrics["max_drawdown"] == 0.0
        assert metrics["win_rate"] == 0.0
        assert metrics["cagr"] == 0.0
        assert metrics["total_trades"] == 0
        assert metrics["profit_factor"] == 0.0

    def test_sharpe_ratio_calculation(self):
        """Test Sharpe ratio calculation."""
        # Create steadily growing equity curve
        equity_curve = [
            {"timestamp": f"2024-01-{i:02d}", "equity": 10000 + i * 100} for i in range(1, 31)
        ]

        metrics = calculate_metrics(equity_curve, [], initial_capital=10000.0)

        # Should have positive Sharpe ratio for upward trend
        assert metrics["sharpe_ratio"] > 0

    def test_max_drawdown_calculation(self):
        """Test maximum drawdown calculation."""
        # Create equity curve with drawdown
        equity_curve = [
            {"timestamp": "2024-01-01", "equity": 10000},
            {"timestamp": "2024-01-02", "equity": 11000},
            {"timestamp": "2024-01-03", "equity": 12000},  # Peak
            {"timestamp": "2024-01-04", "equity": 10800},  # 10% drawdown
            {"timestamp": "2024-01-05", "equity": 11500},
        ]

        metrics = calculate_metrics(equity_curve, [], initial_capital=10000.0)

        # Should detect 10% drawdown
        assert metrics["max_drawdown"] == pytest.approx(10.0, rel=0.1)

    def test_win_rate_calculation(self):
        """Test win rate calculation."""
        trades = [
            {
                "timestamp": "2024-01-01",
                "type": "buy",
                "price": 100,
                "quantity": 10,
                "value": 1000,
                "commission": 1,
            },
            {
                "timestamp": "2024-01-02",
                "type": "sell",
                "price": 110,
                "quantity": 10,
                "value": 1100,
                "commission": 1,
            },  # Win
            {
                "timestamp": "2024-01-03",
                "type": "buy",
                "price": 110,
                "quantity": 10,
                "value": 1100,
                "commission": 1,
            },
            {
                "timestamp": "2024-01-04",
                "type": "sell",
                "price": 105,
                "quantity": 10,
                "value": 1050,
                "commission": 1,
            },  # Loss
            {
                "timestamp": "2024-01-05",
                "type": "buy",
                "price": 105,
                "quantity": 10,
                "value": 1050,
                "commission": 1,
            },
            {
                "timestamp": "2024-01-06",
                "type": "sell",
                "price": 115,
                "quantity": 10,
                "value": 1150,
                "commission": 1,
            },  # Win
        ]

        equity_curve = [
            {"timestamp": f"2024-01-{i:02d}", "equity": 10000 + i * 10} for i in range(1, 7)
        ]

        metrics = calculate_metrics(equity_curve, trades, initial_capital=10000.0)

        # 2 wins out of 3 trades = 66.67% win rate
        assert metrics["win_rate"] == pytest.approx(66.67, rel=0.1)
        assert metrics["total_trades"] == 3

    def test_profit_factor_calculation(self):
        """Test profit factor calculation."""
        trades = [
            {
                "timestamp": "2024-01-01",
                "type": "buy",
                "price": 100,
                "quantity": 10,
                "value": 1000,
                "commission": 1,
            },
            {
                "timestamp": "2024-01-02",
                "type": "sell",
                "price": 120,
                "quantity": 10,
                "value": 1200,
                "commission": 1,
            },  # +198
            {
                "timestamp": "2024-01-03",
                "type": "buy",
                "price": 120,
                "quantity": 10,
                "value": 1200,
                "commission": 1,
            },
            {
                "timestamp": "2024-01-04",
                "type": "sell",
                "price": 110,
                "quantity": 10,
                "value": 1100,
                "commission": 1,
            },  # -102
        ]

        equity_curve = [
            {"timestamp": f"2024-01-{i:02d}", "equity": 10000 + i * 10} for i in range(1, 5)
        ]

        metrics = calculate_metrics(equity_curve, trades, initial_capital=10000.0)

        # Profit factor = gross profit / gross loss = 198 / 102 ≈ 1.94
        assert metrics["profit_factor"] == pytest.approx(1.94, rel=0.1)

    def test_cagr_calculation(self):
        """Test CAGR calculation."""
        # Create 1-year equity curve with 20% total return
        equity_curve = []
        for i in range(252):  # Trading days in a year
            equity = 10000 * (1 + 0.2 * i / 251)  # Linear growth to 20%
            equity_curve.append(
                {"timestamp": f"2024-{(i//21)+1:02d}-{(i%21)+1:02d}", "equity": equity}
            )

        metrics = calculate_metrics(equity_curve, [], initial_capital=10000.0, periods_per_year=252)

        # CAGR should be approximately 20%
        assert metrics["cagr"] == pytest.approx(20.0, rel=0.1)

    def test_short_trades_calculation(self):
        """Test metrics with short trades."""
        trades = [
            {
                "timestamp": "2024-01-01",
                "type": "short",
                "price": 100,
                "quantity": 10,
                "value": 1000,
                "commission": 1,
            },
            {
                "timestamp": "2024-01-02",
                "type": "cover",
                "price": 90,
                "quantity": 10,
                "value": 900,
                "commission": 1,
            },  # Win (short)
            {
                "timestamp": "2024-01-03",
                "type": "short",
                "price": 90,
                "quantity": 10,
                "value": 900,
                "commission": 1,
            },
            {
                "timestamp": "2024-01-04",
                "type": "cover",
                "price": 95,
                "quantity": 10,
                "value": 950,
                "commission": 1,
            },  # Loss (short)
        ]

        equity_curve = [
            {"timestamp": f"2024-01-{i:02d}", "equity": 10000 + i * 20} for i in range(1, 5)
        ]

        metrics = calculate_metrics(equity_curve, trades, initial_capital=10000.0)

        assert metrics["total_trades"] == 2  # 2 short positions opened
        assert metrics["win_rate"] == 50.0  # 1 win, 1 loss

    def test_no_trades_metrics(self):
        """Test metrics when no trades are executed."""
        # Flat equity curve (no trading)
        equity_curve = [{"timestamp": f"2024-01-{i:02d}", "equity": 10000} for i in range(1, 31)]

        metrics = calculate_metrics(equity_curve, [], initial_capital=10000.0)

        assert metrics["sharpe_ratio"] == 0.0
        assert metrics["max_drawdown"] == 0.0
        assert metrics["win_rate"] == 0.0
        assert metrics["cagr"] == 0.0
        assert metrics["total_trades"] == 0
        assert metrics["profit_factor"] == 0.0

    def test_all_winning_trades(self):
        """Test profit factor when all trades are winners."""
        trades = [
            {
                "timestamp": "2024-01-01",
                "type": "buy",
                "price": 100,
                "quantity": 10,
                "value": 1000,
                "commission": 1,
            },
            {
                "timestamp": "2024-01-02",
                "type": "sell",
                "price": 110,
                "quantity": 10,
                "value": 1100,
                "commission": 1,
            },
            {
                "timestamp": "2024-01-03",
                "type": "buy",
                "price": 110,
                "quantity": 10,
                "value": 1100,
                "commission": 1,
            },
            {
                "timestamp": "2024-01-04",
                "type": "sell",
                "price": 120,
                "quantity": 10,
                "value": 1200,
                "commission": 1,
            },
        ]

        equity_curve = [
            {"timestamp": f"2024-01-{i:02d}", "equity": 10000 + i * 50} for i in range(1, 5)
        ]

        metrics = calculate_metrics(equity_curve, trades, initial_capital=10000.0)

        assert metrics["win_rate"] == 100.0
        assert metrics["profit_factor"] is None  # Infinity case
