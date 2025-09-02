"""
Backtester Service - Adapter for existing backtest engine
"""

import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
import json
import uuid
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class BacktesterService:
    """Backtester adapter for running strategies"""
    
    def __init__(self):
        self.results_dir = Path("backtests")
        self.results_dir.mkdir(exist_ok=True)
        
    def run_backtest(
        self,
        symbol: str,
        timeframe: str,
        start_date: str,
        end_date: str,
        strategy: str,
        params: Dict
    ) -> Dict:
        """
        Run a backtest and return results
        """
        # Generate unique run ID
        run_id = str(uuid.uuid4())[:8]
        
        # Get data from datahub
        from src.services.datahub import datahub
        ohlcv_data = datahub.get_ohlcv(symbol, timeframe, start_date, end_date)
        
        if not ohlcv_data:
            return {
                "error": "Failed to fetch data",
                "run_id": run_id
            }
            
        # Convert to DataFrame
        df = pd.DataFrame(
            ohlcv_data,
            columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
        )
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        
        # Run strategy
        if strategy == "sma_cross":
            results = self._run_sma_cross(df, params)
        elif strategy == "rsi_revert":
            results = self._run_rsi_revert(df, params)
        elif strategy == "grid":
            results = self._run_grid(df, params)
        elif strategy == "mean_revert":
            results = self._run_mean_revert(df, params)
        else:
            results = self._run_buy_hold(df)
            
        # Add metadata
        results["run_id"] = run_id
        results["symbol"] = symbol
        results["timeframe"] = timeframe
        results["start_date"] = start_date
        results["end_date"] = end_date
        results["strategy"] = strategy
        results["params"] = params
        
        # Save results
        self._save_results(run_id, results)
        
        return results
        
    def _run_sma_cross(self, df: pd.DataFrame, params: Dict) -> Dict:
        """SMA Crossover Strategy"""
        fast_period = params.get("fast", 20)
        slow_period = params.get("slow", 50)
        
        # Calculate SMAs
        df['sma_fast'] = df['close'].rolling(window=fast_period).mean()
        df['sma_slow'] = df['close'].rolling(window=slow_period).mean()
        
        # Generate signals
        df['signal'] = 0
        df.loc[df['sma_fast'] > df['sma_slow'], 'signal'] = 1
        df.loc[df['sma_fast'] < df['sma_slow'], 'signal'] = -1
        
        # Calculate returns
        df['returns'] = df['close'].pct_change()
        df['strategy_returns'] = df['signal'].shift(1) * df['returns']
        
        # Calculate equity curve
        initial_capital = 10000
        df['equity'] = initial_capital * (1 + df['strategy_returns']).cumprod()
        df['drawdown'] = (df['equity'] / df['equity'].cummax() - 1) * 100
        
        # Extract trades
        trades = self._extract_trades(df)
        
        # Calculate statistics
        stats = self._calculate_stats(df, initial_capital)
        
        # Prepare output
        equity_curve = [
            [int(idx.timestamp() * 1000), float(row['equity'])]
            for idx, row in df[['equity']].dropna().iterrows()
        ]
        
        drawdown_curve = [
            [int(idx.timestamp() * 1000), float(row['drawdown'])]
            for idx, row in df[['drawdown']].dropna().iterrows()
        ]
        
        return {
            "equity_curve": equity_curve,
            "drawdown": drawdown_curve,
            "trades": trades,
            "stats": stats
        }
        
    def _run_rsi_revert(self, df: pd.DataFrame, params: Dict) -> Dict:
        """RSI Mean Reversion Strategy"""
        period = params.get("period", 14)
        oversold = params.get("oversold", 30)
        overbought = params.get("overbought", 70)
        
        # Calculate RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # Generate signals
        df['signal'] = 0
        df.loc[df['rsi'] < oversold, 'signal'] = 1  # Buy when oversold
        df.loc[df['rsi'] > overbought, 'signal'] = -1  # Sell when overbought
        
        # Calculate returns
        df['returns'] = df['close'].pct_change()
        df['strategy_returns'] = df['signal'].shift(1) * df['returns']
        
        # Calculate equity curve
        initial_capital = 10000
        df['equity'] = initial_capital * (1 + df['strategy_returns']).cumprod()
        df['drawdown'] = (df['equity'] / df['equity'].cummax() - 1) * 100
        
        # Extract trades
        trades = self._extract_trades(df)
        
        # Calculate statistics
        stats = self._calculate_stats(df, initial_capital)
        
        # Prepare output
        equity_curve = [
            [int(idx.timestamp() * 1000), float(row['equity'])]
            for idx, row in df[['equity']].dropna().iterrows()
        ]
        
        drawdown_curve = [
            [int(idx.timestamp() * 1000), float(row['drawdown'])]
            for idx, row in df[['drawdown']].dropna().iterrows()
        ]
        
        return {
            "equity_curve": equity_curve,
            "drawdown": drawdown_curve,
            "trades": trades,
            "stats": stats
        }
        
    def _run_grid(self, df: pd.DataFrame, params: Dict) -> Dict:
        """Grid Trading Strategy (simplified)"""
        grid_levels = params.get("levels", 10)
        grid_spacing = params.get("spacing_pct", 1.0) / 100
        
        # Set up grid levels
        mid_price = df['close'].iloc[0]
        grid_prices = []
        for i in range(-grid_levels//2, grid_levels//2 + 1):
            grid_prices.append(mid_price * (1 + i * grid_spacing))
            
        # Simulate grid trading
        trades = []
        position = 0
        capital = 10000
        equity = []
        
        for idx, row in df.iterrows():
            current_price = row['close']
            
            # Check if price crossed any grid level
            for grid_price in grid_prices:
                if abs(current_price - grid_price) / grid_price < 0.001:  # Within 0.1%
                    # Execute trade at grid level
                    if position == 0:
                        # Open position
                        position = capital * 0.1 / current_price  # Use 10% per grid
                        trades.append({
                            "timestamp": int(idx.timestamp() * 1000),
                            "side": "buy",
                            "price": current_price,
                            "size": position
                        })
                    elif position > 0:
                        # Close position
                        trades.append({
                            "timestamp": int(idx.timestamp() * 1000),
                            "side": "sell",
                            "price": current_price,
                            "size": position
                        })
                        capital += position * (current_price - trades[-2]["price"])
                        position = 0
                        
            # Track equity
            current_equity = capital + position * current_price
            equity.append([int(idx.timestamp() * 1000), current_equity])
            
        # Calculate drawdown
        equity_df = pd.DataFrame(equity, columns=['timestamp', 'equity'])
        equity_df['drawdown'] = (equity_df['equity'] / equity_df['equity'].cummax() - 1) * 100
        
        drawdown_curve = [
            [row['timestamp'], row['drawdown']]
            for _, row in equity_df.iterrows()
        ]
        
        # Calculate stats
        total_return = (equity[-1][1] - 10000) / 10000 * 100 if equity else 0
        max_dd = equity_df['drawdown'].min() if not equity_df.empty else 0
        
        stats = {
            "total_return": total_return,
            "max_drawdown": max_dd,
            "num_trades": len(trades),
            "win_rate": 50.0  # Simplified
        }
        
        return {
            "equity_curve": equity,
            "drawdown": drawdown_curve,
            "trades": trades[:100],  # Limit trades
            "stats": stats
        }
        
    def _run_mean_revert(self, df: pd.DataFrame, params: Dict) -> Dict:
        """Mean Reversion Strategy"""
        lookback = params.get("lookback", 20)
        z_threshold = params.get("z_threshold", 2.0)
        
        # Calculate z-score
        df['ma'] = df['close'].rolling(window=lookback).mean()
        df['std'] = df['close'].rolling(window=lookback).std()
        df['z_score'] = (df['close'] - df['ma']) / df['std']
        
        # Generate signals
        df['signal'] = 0
        df.loc[df['z_score'] < -z_threshold, 'signal'] = 1  # Buy when oversold
        df.loc[df['z_score'] > z_threshold, 'signal'] = -1  # Sell when overbought
        
        # Calculate returns
        df['returns'] = df['close'].pct_change()
        df['strategy_returns'] = df['signal'].shift(1) * df['returns']
        
        # Calculate equity curve
        initial_capital = 10000
        df['equity'] = initial_capital * (1 + df['strategy_returns']).cumprod()
        df['drawdown'] = (df['equity'] / df['equity'].cummax() - 1) * 100
        
        # Extract trades
        trades = self._extract_trades(df)
        
        # Calculate statistics
        stats = self._calculate_stats(df, initial_capital)
        
        # Prepare output
        equity_curve = [
            [int(idx.timestamp() * 1000), float(row['equity'])]
            for idx, row in df[['equity']].dropna().iterrows()
        ]
        
        drawdown_curve = [
            [int(idx.timestamp() * 1000), float(row['drawdown'])]
            for idx, row in df[['drawdown']].dropna().iterrows()
        ]
        
        return {
            "equity_curve": equity_curve,
            "drawdown": drawdown_curve,
            "trades": trades,
            "stats": stats
        }
        
    def _run_buy_hold(self, df: pd.DataFrame) -> Dict:
        """Buy and Hold Strategy (benchmark)"""
        initial_capital = 10000
        initial_price = df['close'].iloc[0]
        shares = initial_capital / initial_price
        
        df['equity'] = shares * df['close']
        df['drawdown'] = (df['equity'] / df['equity'].cummax() - 1) * 100
        
        equity_curve = [
            [int(idx.timestamp() * 1000), float(row['equity'])]
            for idx, row in df[['equity']].iterrows()
        ]
        
        drawdown_curve = [
            [int(idx.timestamp() * 1000), float(row['drawdown'])]
            for idx, row in df[['drawdown']].iterrows()
        ]
        
        trades = [
            {
                "timestamp": int(df.index[0].timestamp() * 1000),
                "side": "buy",
                "price": initial_price,
                "size": shares
            }
        ]
        
        total_return = (df['equity'].iloc[-1] - initial_capital) / initial_capital * 100
        max_dd = df['drawdown'].min()
        
        stats = {
            "total_return": total_return,
            "max_drawdown": max_dd,
            "num_trades": 1,
            "win_rate": 100.0 if total_return > 0 else 0.0
        }
        
        return {
            "equity_curve": equity_curve,
            "drawdown": drawdown_curve,
            "trades": trades,
            "stats": stats
        }
        
    def _extract_trades(self, df: pd.DataFrame) -> List[Dict]:
        """Extract trades from signals"""
        trades = []
        df['position'] = df['signal'].diff()
        
        for idx, row in df[df['position'] != 0].iterrows():
            if not pd.isna(row['position']):
                trades.append({
                    "timestamp": int(idx.timestamp() * 1000),
                    "side": "buy" if row['position'] > 0 else "sell",
                    "price": float(row['close']),
                    "size": abs(row['position'])
                })
                
        return trades[:100]  # Limit to 100 trades
        
    def _calculate_stats(self, df: pd.DataFrame, initial_capital: float) -> Dict:
        """Calculate strategy statistics"""
        if 'equity' not in df or df['equity'].isna().all():
            return {
                "total_return": 0,
                "sharpe_ratio": 0,
                "max_drawdown": 0,
                "win_rate": 0,
                "num_trades": 0
            }
            
        # Total return
        total_return = (df['equity'].iloc[-1] - initial_capital) / initial_capital * 100
        
        # Sharpe ratio (simplified - annualized)
        if 'strategy_returns' in df:
            returns = df['strategy_returns'].dropna()
            if len(returns) > 0:
                sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
            else:
                sharpe = 0
        else:
            sharpe = 0
            
        # Max drawdown
        max_dd = df['drawdown'].min() if 'drawdown' in df else 0
        
        # Win rate
        if 'strategy_returns' in df:
            winning_trades = (df['strategy_returns'] > 0).sum()
            total_trades = (df['strategy_returns'] != 0).sum()
            win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0
        else:
            win_rate = 0
            total_trades = 0
            
        return {
            "total_return": round(total_return, 2),
            "sharpe_ratio": round(sharpe, 2),
            "max_drawdown": round(max_dd, 2),
            "win_rate": round(win_rate, 2),
            "num_trades": int(total_trades)
        }
        
    def _save_results(self, run_id: str, results: Dict):
        """Save backtest results"""
        # Save JSON
        json_file = self.results_dir / f"{run_id}.json"
        with open(json_file, 'w') as f:
            json.dump(results, f, indent=2)
            
        # Save CSV of trades
        if results.get("trades"):
            csv_file = self.results_dir / f"{run_id}.csv"
            trades_df = pd.DataFrame(results["trades"])
            trades_df.to_csv(csv_file, index=False)
            
    def get_results(self, run_id: str) -> Optional[Dict]:
        """Get saved backtest results"""
        json_file = self.results_dir / f"{run_id}.json"
        if json_file.exists():
            with open(json_file, 'r') as f:
                return json.load(f)
        return None
        
    def export_csv(self, run_id: str) -> Optional[Path]:
        """Get CSV export path"""
        csv_file = self.results_dir / f"{run_id}.csv"
        if csv_file.exists():
            return csv_file
        return None

# Global instance
backtester = BacktesterService()