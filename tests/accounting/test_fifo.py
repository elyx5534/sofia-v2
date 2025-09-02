"""
Test FIFO Accounting System
"""

import pytest
from decimal import Decimal
from datetime import datetime
from src.core.accounting import FIFOAccounting, Fill


class TestFIFOAccounting:
    
    def test_simple_buy_sell_profit(self):
        """Test case: buy@100 → sell@101"""
        accounting = FIFOAccounting(initial_cash=Decimal("1000"))
        
        # Buy 1 BTC at 100
        buy_fill = Fill(
            symbol="BTC/USDT",
            side="buy",
            quantity=Decimal("1"),
            price=Decimal("100"),
            fee_pct=Decimal("0.1"),
            timestamp=datetime.now(),
            fill_id="buy_1"
        )
        result = accounting.update_on_fill(buy_fill)
        
        # Check cash decreased by 100 + 0.1% fee
        assert accounting.cash == Decimal("899.9")  # 1000 - 100 - 0.1
        assert accounting.get_position("BTC/USDT") == Decimal("1")
        
        # Sell 1 BTC at 101
        sell_fill = Fill(
            symbol="BTC/USDT",
            side="sell",
            quantity=Decimal("1"),
            price=Decimal("101"),
            fee_pct=Decimal("0.1"),
            timestamp=datetime.now(),
            fill_id="sell_1"
        )
        result = accounting.update_on_fill(sell_fill)
        
        # Check realized P&L (101 - 100 - fees)
        # Sell proceeds: 101 - 0.101 = 100.899
        # Cost basis: 100 + 0.1 = 100.1
        # P&L = 100.899 - 100.1 = 0.799
        assert accounting.get_realized() == Decimal("0.799")
        assert accounting.get_position("BTC/USDT") == Decimal("0")
        
    def test_multiple_lots_fifo(self):
        """Test case: buy@100, buy@110 → sell@120"""
        accounting = FIFOAccounting(initial_cash=Decimal("10000"))
        
        # Buy 1 BTC at 100
        buy1 = Fill(
            symbol="BTC/USDT",
            side="buy",
            quantity=Decimal("1"),
            price=Decimal("100"),
            fee_pct=Decimal("0.1"),
            timestamp=datetime.now(),
            fill_id="buy_1"
        )
        accounting.update_on_fill(buy1)
        
        # Buy 1 BTC at 110
        buy2 = Fill(
            symbol="BTC/USDT",
            side="buy",
            quantity=Decimal("1"),
            price=Decimal("110"),
            fee_pct=Decimal("0.1"),
            timestamp=datetime.now(),
            fill_id="buy_2"
        )
        accounting.update_on_fill(buy2)
        
        assert accounting.get_position("BTC/USDT") == Decimal("2")
        assert accounting.get_average_entry("BTC/USDT") == Decimal("105")  # (100+110)/2
        
        # Sell 1.5 BTC at 120 (FIFO: 1 from @100, 0.5 from @110)
        sell = Fill(
            symbol="BTC/USDT",
            side="sell",
            quantity=Decimal("1.5"),
            price=Decimal("120"),
            fee_pct=Decimal("0.1"),
            timestamp=datetime.now(),
            fill_id="sell_1"
        )
        accounting.update_on_fill(sell)
        
        # P&L calculation:
        # Lot 1 (1 BTC@100): (120-100)*1 - fees = 20 - 0.1 - 0.12 = 19.78
        # Lot 2 (0.5 BTC@110): (120-110)*0.5 - fees = 5 - 0.055 - 0.06 = 4.885
        # Total: ~24.665
        assert accounting.get_realized() > Decimal("24")
        assert accounting.get_position("BTC/USDT") == Decimal("0.5")
        
    def test_mark_to_market(self):
        """Test m2m with mid price"""
        accounting = FIFOAccounting(initial_cash=Decimal("1000"))
        
        # Buy 1 BTC at 100
        buy = Fill(
            symbol="BTC/USDT",
            side="buy",
            quantity=Decimal("1"),
            price=Decimal("100"),
            fee_pct=Decimal("0.1"),
            timestamp=datetime.now(),
            fill_id="buy_1"
        )
        accounting.update_on_fill(buy)
        
        # Mark to market at 105
        prices = {"BTC/USDT": Decimal("105")}
        unrealized = accounting.get_unrealized(prices, mid_or_bidask="mid")
        
        # Unrealized = (105 - 100) * 1 - fee = 5 - 0.1 = 4.9
        assert unrealized == Decimal("4.9")
        
        # Equity = cash + unrealized
        equity = accounting.get_equity(prices)
        assert equity == accounting.cash + unrealized
        
    def test_partial_fill_consumption(self):
        """Test partial lot consumption"""
        accounting = FIFOAccounting(initial_cash=Decimal("1000"))
        
        # Buy 2 BTC at 100
        buy = Fill(
            symbol="BTC/USDT",
            side="buy",
            quantity=Decimal("2"),
            price=Decimal("100"),
            fee_pct=Decimal("0.1"),
            timestamp=datetime.now(),
            fill_id="buy_1"
        )
        accounting.update_on_fill(buy)
        
        # Sell 0.5 BTC at 110
        sell1 = Fill(
            symbol="BTC/USDT",
            side="sell",
            quantity=Decimal("0.5"),
            price=Decimal("110"),
            fee_pct=Decimal("0.1"),
            timestamp=datetime.now(),
            fill_id="sell_1"
        )
        accounting.update_on_fill(sell1)
        
        assert accounting.get_position("BTC/USDT") == Decimal("1.5")
        
        # Sell another 1 BTC at 115
        sell2 = Fill(
            symbol="BTC/USDT",
            side="sell",
            quantity=Decimal("1"),
            price=Decimal("115"),
            fee_pct=Decimal("0.1"),
            timestamp=datetime.now(),
            fill_id="sell_2"
        )
        accounting.update_on_fill(sell2)
        
        assert accounting.get_position("BTC/USDT") == Decimal("0.5")
        assert accounting.get_realized() > Decimal("0")  # Should have profit
        
    def test_state_export(self):
        """Test state export to dictionary"""
        accounting = FIFOAccounting(initial_cash=Decimal("1000"))
        
        # Buy some BTC
        buy = Fill(
            symbol="BTC/USDT",
            side="buy",
            quantity=Decimal("0.5"),
            price=Decimal("100"),
            fee_pct=Decimal("0.1"),
            timestamp=datetime.now(),
            fill_id="buy_1"
        )
        accounting.update_on_fill(buy)
        
        state = accounting.to_dict()
        
        assert "cash" in state
        assert "realized_pnl" in state
        assert "total_fees_paid" in state
        assert "positions" in state
        assert "BTC/USDT" in state["positions"]
        assert state["positions"]["BTC/USDT"]["quantity"] == 0.5
        assert state["positions"]["BTC/USDT"]["avg_entry"] == 100.0