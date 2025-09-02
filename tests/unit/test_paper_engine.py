"""Tests for Paper Trading Engine."""

import pytest
from unittest.mock import MagicMock, patch, Mock
import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta


class TestPaperEngine:
    """Test paper trading engine state management."""
    
    def test_paper_engine_state_persist(self):
        """Test paper engine state persistence."""
        from src.services.paper_engine import PaperEngine
        
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "paper_state.json"
            
            engine = PaperEngine(state_file=state_file, initial_balance=10000)
            
            # Execute some trades
            engine.execute_trade("BTC/USDT", "buy", 0.1, 50000)
            engine.execute_trade("BTC/USDT", "sell", 0.05, 51000)
            
            # Save state
            engine.save_state()
            
            # Verify state file exists
            assert state_file.exists()
            
            # Load state
            with open(state_file) as f:
                state = json.load(f)
            
            assert state["balance"] < 10000  # Some balance used
            assert len(state["positions"]) > 0
            assert len(state["trade_history"]) == 2
    
    def test_paper_engine_state_resume(self):
        """Test paper engine state resume."""
        from src.services.paper_engine import PaperEngine
        
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "paper_state.json"
            
            # Create initial state
            initial_state = {
                "balance": 9500,
                "positions": {"BTC/USDT": {"quantity": 0.05, "avg_price": 50000}},
                "trade_history": [
                    {"symbol": "BTC/USDT", "side": "buy", "quantity": 0.05, "price": 50000}
                ],
                "equity_series": [[1, 10000], [2, 9800], [3, 9500]]
            }
            
            with open(state_file, 'w') as f:
                json.dump(initial_state, f)
            
            # Resume engine
            engine = PaperEngine(state_file=state_file)
            engine.load_state()
            
            assert engine.balance == 9500
            assert engine.positions["BTC/USDT"]["quantity"] == 0.05
            assert len(engine.trade_history) == 1
            assert len(engine.equity_series) == 3
    
    def test_equity_series_tail_length(self):
        """Test equity series tail maintains correct length."""
        from src.services.paper_engine import PaperEngine
        
        engine = PaperEngine(initial_balance=10000, max_equity_points=100)
        
        # Add 150 equity points
        for i in range(150):
            engine.update_equity(10000 + i * 10)
        
        # Should only keep last 100 points
        assert len(engine.equity_series) <= 100
        
        # Last point should be the most recent
        assert engine.equity_series[-1][1] == 10000 + 149 * 10
    
    def test_reset_day_behavior(self):
        """Test daily reset behavior."""
        from src.services.paper_engine import PaperEngine
        
        engine = PaperEngine(initial_balance=10000, reset_daily=True)
        
        # Simulate trades
        engine.execute_trade("BTC/USDT", "buy", 0.1, 50000)
        engine.execute_trade("BTC/USDT", "sell", 0.1, 51000)
        
        # Record state before reset
        trades_before = len(engine.trade_history)
        
        # Simulate day change
        with patch('src.services.paper_engine.datetime') as mock_dt:
            mock_dt.now.return_value = datetime.now() + timedelta(days=1)
            engine.check_daily_reset()
        
        # After reset
        assert engine.balance == 10000  # Reset to initial
        assert len(engine.positions) == 0  # Positions cleared
        assert len(engine.daily_trades) == 0  # Daily trades cleared
        assert engine.daily_pnl == 0  # Daily P&L reset
    
    def test_idempotent_orders(self):
        """Test idempotent order processing."""
        from src.services.paper_engine import PaperEngine
        
        engine = PaperEngine(initial_balance=10000)
        
        # Submit same order twice with same ID
        order_id = "order-123"
        
        result1 = engine.execute_order({
            "id": order_id,
            "symbol": "BTC/USDT",
            "side": "buy",
            "quantity": 0.1,
            "price": 50000
        })
        
        result2 = engine.execute_order({
            "id": order_id,
            "symbol": "BTC/USDT",
            "side": "buy",
            "quantity": 0.1,
            "price": 50000
        })
        
        # Second order should be rejected (idempotent)
        assert result1["status"] == "filled"
        assert result2["status"] == "rejected"
        assert result2["reason"] == "duplicate_order"
        
        # Only one trade should be recorded
        assert len(engine.trade_history) == 1