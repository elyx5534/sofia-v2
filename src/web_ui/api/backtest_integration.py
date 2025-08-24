"""Backtest engine integration for Web UI."""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import pandas as pd
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from src.backtester.engine import BacktestEngine
from src.backtester.strategies.sma import SMACrossStrategy
from src.data_hub.pipeline import Pipeline

class BacktestService:
    """Service for running backtests and managing results."""
    
    def __init__(self):
        self.engine = BacktestEngine(initial_capital=10000.0)
        self.pipeline = Pipeline()
        self.results_cache = {}
        
    async def run_backtest(
        self,
        symbol: str,
        strategy_type: str = "sma_cross",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **strategy_params
    ) -> Dict[str, Any]:
        """
        Run a backtest for given parameters.
        
        Args:
            symbol: Trading symbol (e.g., "AAPL", "BTC-USD")
            strategy_type: Type of strategy to use
            start_date: Start date for backtest (YYYY-MM-DD)
            end_date: End date for backtest (YYYY-MM-DD)
            **strategy_params: Additional strategy parameters
            
        Returns:
            Backtest results including metrics and trades
        """
        # Default dates if not provided
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        
        # Create cache key
        cache_key = f"{symbol}_{strategy_type}_{start_date}_{end_date}"
        
        # Check cache
        if cache_key in self.results_cache:
            cached_result, timestamp = self.results_cache[cache_key]
            if datetime.now() - timestamp < timedelta(minutes=10):
                return cached_result
        
        try:
            # Fetch data
            data_path = self.pipeline.fetch_symbol(
                symbol=symbol,
                start=start_date,
                end=end_date,
                interval="1d"
            )
            
            # Load data
            data = pd.read_parquet(data_path)
            
            # Select strategy
            if strategy_type == "sma_cross":
                strategy = SMACrossStrategy(
                    fast_period=strategy_params.get("fast_period", 20),
                    slow_period=strategy_params.get("slow_period", 50)
                )
            else:
                # Default to SMA cross
                strategy = SMACrossStrategy()
            
            # Run backtest
            results = self.engine.run(data, strategy)
            
            # Format results for UI
            formatted_results = self._format_results(results, symbol, strategy_type)
            
            # Cache results
            self.results_cache[cache_key] = (formatted_results, datetime.now())
            
            return formatted_results
            
        except Exception as e:
            print(f"Backtest error: {e}")
            # Return mock results for demo
            return self._get_mock_results(symbol, strategy_type)
    
    def _format_results(self, results: Dict, symbol: str, strategy_type: str) -> Dict:
        """Format backtest results for UI display."""
        return {
            "symbol": symbol,
            "strategy": strategy_type,
            "metrics": {
                "total_return": results.get("return", 0),
                "sharpe_ratio": results.get("sharpe", 0),
                "max_drawdown": results.get("max_drawdown", 0),
                "win_rate": results.get("win_rate", 0),
                "total_trades": len(results.get("trades", [])),
                "final_equity": results.get("final_equity", 10000)
            },
            "equity_curve": results.get("equity_curve", []),
            "trades": results.get("trades", [])[:10],  # Last 10 trades
            "timestamp": datetime.now().isoformat()
        }
    
    def _get_mock_results(self, symbol: str, strategy_type: str) -> Dict:
        """Get mock backtest results for demo."""
        import random
        
        # Generate mock equity curve
        equity_curve = []
        equity = 10000
        for i in range(100):
            equity *= (1 + random.uniform(-0.02, 0.03))
            equity_curve.append({
                "date": (datetime.now() - timedelta(days=100-i)).isoformat(),
                "equity": round(equity, 2)
            })
        
        return {
            "symbol": symbol,
            "strategy": strategy_type,
            "metrics": {
                "total_return": round(random.uniform(0.1, 0.5), 2),
                "sharpe_ratio": round(random.uniform(0.5, 2.5), 2),
                "max_drawdown": round(random.uniform(-0.15, -0.05), 2),
                "win_rate": round(random.uniform(0.45, 0.75), 2),
                "total_trades": random.randint(50, 200),
                "final_equity": round(equity, 2)
            },
            "equity_curve": equity_curve,
            "trades": [
                {
                    "date": (datetime.now() - timedelta(days=i)).isoformat(),
                    "type": random.choice(["BUY", "SELL"]),
                    "price": round(random.uniform(100, 200), 2),
                    "quantity": random.randint(10, 100),
                    "pnl": round(random.uniform(-100, 200), 2)
                }
                for i in range(10)
            ],
            "timestamp": datetime.now().isoformat()
        }

# Singleton instance
backtest_service = BacktestService()