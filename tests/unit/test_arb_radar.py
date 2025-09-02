"""Tests for Turkish Arbitrage Radar."""

import pytest
from unittest.mock import MagicMock, patch, Mock
import json
import tempfile
from pathlib import Path
from decimal import Decimal


class TestArbRadar:
    """Test arbitrage radar functionality."""
    
    def test_arb_pnl_json_creation(self):
        """Test arb_pnl.json file creation with snapshots."""
        from src.services.arb_tl_radar import ArbRadar
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "arb_pnl.json"
            
            radar = ArbRadar(output_file=output_file)
            
            # Create 3 snapshots
            snapshots = [
                {
                    "timestamp": "2024-01-01T10:00:00",
                    "binance_tr": {"bid": 1850000, "ask": 1851000},
                    "btcturk": {"bid": 1852000, "ask": 1853000},
                    "paribu": {"bid": 1854000, "ask": 1855000},
                    "arb_opportunity": 0.002,  # 0.2%
                    "best_path": "buy_binance_sell_paribu"
                },
                {
                    "timestamp": "2024-01-01T10:01:00",
                    "binance_tr": {"bid": 1851000, "ask": 1852000},
                    "btcturk": {"bid": 1850000, "ask": 1851000},
                    "paribu": {"bid": 1853000, "ask": 1854000},
                    "arb_opportunity": 0.001,  # 0.1%
                    "best_path": "buy_btcturk_sell_paribu"
                },
                {
                    "timestamp": "2024-01-01T10:02:00",
                    "binance_tr": {"bid": 1852000, "ask": 1853000},
                    "btcturk": {"bid": 1852500, "ask": 1853500},
                    "paribu": {"bid": 1852000, "ask": 1853000},
                    "arb_opportunity": 0.0,  # No opportunity
                    "best_path": "none"
                }
            ]
            
            for snapshot in snapshots:
                radar.add_snapshot(snapshot)
            
            # Save to file
            radar.save_results()
            
            # Verify file exists and contains data
            assert output_file.exists()
            
            with open(output_file) as f:
                data = json.load(f)
            
            assert len(data["snapshots"]) == 3
            assert data["summary"]["total_snapshots"] == 3
            assert data["summary"]["opportunities_found"] == 2
    
    def test_threshold_bps_dynamic_logic(self):
        """Test dynamic threshold adjustment based on volatility."""
        from src.services.arb_tl_radar import ArbRadar
        
        radar = ArbRadar(base_threshold_bps=30)  # 0.3% base threshold
        
        # Low volatility - threshold should decrease
        low_vol_prices = [1850000, 1850100, 1850050, 1850080]
        threshold_low = radar.calculate_dynamic_threshold(low_vol_prices)
        assert threshold_low < 30  # Should be lower than base
        
        # High volatility - threshold should increase
        high_vol_prices = [1850000, 1860000, 1840000, 1870000]
        threshold_high = radar.calculate_dynamic_threshold(high_vol_prices)
        assert threshold_high > 30  # Should be higher than base
        
        # Extreme volatility - threshold should be capped
        extreme_vol_prices = [1850000, 1900000, 1800000, 1950000]
        threshold_extreme = radar.calculate_dynamic_threshold(extreme_vol_prices)
        assert threshold_extreme <= 100  # Should be capped at max
    
    def test_slip_fee_net_impact(self):
        """Test slippage and fee impact on arbitrage calculation."""
        from src.services.arb_tl_radar import ArbRadar
        
        radar = ArbRadar(
            fee_rate=0.001,  # 0.1% fee
            slippage=0.0005  # 0.05% slippage
        )
        
        # Example 1: Profitable after fees
        gross_profit = radar.calculate_arbitrage(
            buy_price=1850000,
            sell_price=1855000
        )
        net_profit = radar.calculate_net_profit(
            gross_profit=gross_profit,
            buy_price=1850000,
            sell_price=1855000,
            volume=0.1
        )
        
        # Gross profit: (1855000 - 1850000) / 1850000 = 0.27%
        # Fees: 0.1% * 2 = 0.2%
        # Slippage: 0.05% * 2 = 0.1%
        # Net should be positive but less than gross
        assert net_profit > 0
        assert net_profit < gross_profit
        
        # Example 2: Not profitable after fees
        gross_profit = radar.calculate_arbitrage(
            buy_price=1850000,
            sell_price=1852000
        )
        net_profit = radar.calculate_net_profit(
            gross_profit=gross_profit,
            buy_price=1850000,
            sell_price=1852000,
            volume=0.1
        )
        
        # Gross profit: (1852000 - 1850000) / 1850000 = 0.108%
        # Total costs: 0.3%
        # Net should be negative
        assert net_profit < 0
    
    def test_multi_exchange_arbitrage_scan(self):
        """Test multi-exchange arbitrage scanning."""
        from src.services.arb_tl_radar import ArbRadar
        
        radar = ArbRadar()
        
        # Mock exchange prices
        prices = {
            "binance_tr": {"bid": 1850000, "ask": 1851000},
            "btcturk": {"bid": 1853000, "ask": 1854000},
            "paribu": {"bid": 1855000, "ask": 1856000},
            "bitexen": {"bid": 1852000, "ask": 1853000}
        }
        
        opportunities = radar.scan_arbitrage_opportunities(prices)
        
        # Should find best opportunity
        assert len(opportunities) > 0
        
        best = opportunities[0]
        assert best["buy_exchange"] == "binance_tr"
        assert best["sell_exchange"] == "paribu"
        assert best["profit_bps"] > 0
        
        # Verify all combinations checked
        total_combinations = 4 * 3  # 4 exchanges, each can trade with 3 others
        assert radar.last_scan_stats["combinations_checked"] == total_combinations
    
    def test_arb_execution_simulation(self):
        """Test arbitrage execution simulation."""
        from src.services.arb_tl_radar import ArbRadar
        
        radar = ArbRadar(initial_capital=100000)  # 100k TRY
        
        # Simulate successful arbitrage
        result = radar.simulate_execution(
            buy_exchange="binance_tr",
            sell_exchange="paribu",
            buy_price=1850000,
            sell_price=1855000,
            max_volume=0.05  # 0.05 BTC
        )
        
        assert result["status"] == "success"
        assert result["gross_profit"] > 0
        assert result["net_profit"] > 0
        assert result["net_profit"] < result["gross_profit"]  # Fees reduce profit
        
        # Update capital after trade
        radar.update_capital(result["net_profit"])
        assert radar.current_capital > 100000
    
    def test_arb_alert_generation(self):
        """Test arbitrage alert generation."""
        from src.services.arb_tl_radar import ArbRadar
        
        radar = ArbRadar(alert_threshold_bps=50)  # Alert if > 0.5%
        
        # Mock high arbitrage opportunity
        opportunity = {
            "buy_exchange": "binance_tr",
            "sell_exchange": "paribu",
            "profit_bps": 75,  # 0.75%
            "net_profit_estimate": 750
        }
        
        alert = radar.should_alert(opportunity)
        assert alert
        
        alert_message = radar.generate_alert_message(opportunity)
        assert "binance_tr" in alert_message
        assert "paribu" in alert_message
        assert "0.75%" in alert_message or "75 bps" in alert_message