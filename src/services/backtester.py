"""
Backtest Engine v2 - Portfolio, Fees, Slippage, WFO, GA/Grid
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import json
import uuid
import itertools
import random
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)

@dataclass
class Position:
    symbol: str
    size: float
    entry_price: float
    entry_time: datetime
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    pnl: float = 0.0
    fees: float = 0.0

@dataclass
class BacktestConfig:
    initial_capital: float = 10000
    commission_bps: float = 10  # basis points
    slippage_bps: float = 5
    funding_rate: float = 0.0001  # daily funding for perps
    max_positions: int = 10
    position_size_pct: float = 10  # % of capital per position

class Portfolio:
    """Portfolio manager with multi-asset support"""
    
    def __init__(self, config: BacktestConfig):
        self.config = config
        self.cash = config.initial_capital
        self.positions: Dict[str, Position] = {}
        self.closed_positions: List[Position] = []
        self.equity_curve = []
        self.trades = []
        
    def calculate_commission(self, notional: float) -> float:
        """Calculate trading commission"""
        return notional * self.config.commission_bps / 10000
        
    def calculate_slippage(self, price: float, is_buy: bool) -> float:
        """Calculate slippage-adjusted price"""
        slippage = price * self.config.slippage_bps / 10000
        return price + slippage if is_buy else price - slippage
        
    def calculate_funding(self, notional: float, days: float) -> float:
        """Calculate funding cost for perpetuals"""
        return notional * self.config.funding_rate * days
        
    def open_position(self, symbol: str, size: float, price: float, timestamp: datetime) -> bool:
        """Open a new position"""
        if symbol in self.positions:
            return False
            
        if len(self.positions) >= self.config.max_positions:
            return False
            
        # Apply slippage
        exec_price = self.calculate_slippage(price, is_buy=True)
        notional = abs(size) * exec_price
        
        # Calculate fees
        commission = self.calculate_commission(notional)
        
        # Check capital
        if self.cash < notional + commission:
            return False
            
        # Create position
        position = Position(
            symbol=symbol,
            size=size,
            entry_price=exec_price,
            entry_time=timestamp,
            fees=commission
        )
        
        self.positions[symbol] = position
        self.cash -= notional + commission
        
        # Log trade
        self.trades.append({
            "timestamp": int(timestamp.timestamp() * 1000),
            "symbol": symbol,
            "side": "buy" if size > 0 else "sell",
            "price": exec_price,
            "size": abs(size),
            "fee": commission,
            "type": "open"
        })
        
        return True
        
    def close_position(self, symbol: str, price: float, timestamp: datetime) -> bool:
        """Close an existing position"""
        if symbol not in self.positions:
            return False
            
        position = self.positions[symbol]
        
        # Apply slippage
        exec_price = self.calculate_slippage(price, is_buy=False)
        notional = abs(position.size) * exec_price
        
        # Calculate fees
        commission = self.calculate_commission(notional)
        
        # Calculate funding (if held overnight)
        days_held = (timestamp - position.entry_time).days
        funding = self.calculate_funding(abs(position.size) * position.entry_price, days_held)
        
        # Calculate PnL
        gross_pnl = position.size * (exec_price - position.entry_price)
        net_pnl = gross_pnl - position.fees - commission - funding
        
        # Update position
        position.exit_price = exec_price
        position.exit_time = timestamp
        position.pnl = net_pnl
        position.fees += commission + funding
        
        # Update cash
        self.cash += notional - commission - funding
        
        # Move to closed
        self.closed_positions.append(position)
        del self.positions[symbol]
        
        # Log trade
        self.trades.append({
            "timestamp": int(timestamp.timestamp() * 1000),
            "symbol": symbol,
            "side": "sell" if position.size > 0 else "buy",
            "price": exec_price,
            "size": abs(position.size),
            "fee": commission + funding,
            "pnl": net_pnl,
            "type": "close"
        })
        
        return True
        
    def get_equity(self, prices: Dict[str, float]) -> float:
        """Calculate current equity"""
        equity = self.cash
        for symbol, position in self.positions.items():
            if symbol in prices:
                current_value = position.size * prices[symbol]
                equity += current_value
        return equity
        
    def get_statistics(self) -> Dict:
        """Calculate portfolio statistics"""
        if not self.closed_positions:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0,
                "avg_win": 0,
                "avg_loss": 0,
                "profit_factor": 0,
                "total_pnl": 0,
                "total_fees": 0
            }
            
        wins = [p.pnl for p in self.closed_positions if p.pnl > 0]
        losses = [p.pnl for p in self.closed_positions if p.pnl < 0]
        
        return {
            "total_trades": len(self.closed_positions),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": len(wins) / len(self.closed_positions) * 100 if self.closed_positions else 0,
            "avg_win": np.mean(wins) if wins else 0,
            "avg_loss": np.mean(losses) if losses else 0,
            "profit_factor": abs(sum(wins) / sum(losses)) if losses and sum(losses) != 0 else 0,
            "total_pnl": sum(p.pnl for p in self.closed_positions),
            "total_fees": sum(p.fees for p in self.closed_positions)
        }

class Strategy:
    """Base strategy class"""
    
    def __init__(self, params: Dict):
        self.params = params
        
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        """Generate trading signals"""
        raise NotImplementedError

class SMAStrategy(Strategy):
    """SMA Crossover Strategy"""
    
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        fast = self.params.get("fast", 20)
        slow = self.params.get("slow", 50)
        
        sma_fast = df['close'].rolling(window=fast).mean()
        sma_slow = df['close'].rolling(window=slow).mean()
        
        signals = pd.Series(0, index=df.index)
        signals[sma_fast > sma_slow] = 1
        signals[sma_fast < sma_slow] = -1
        
        return signals

class RSIStrategy(Strategy):
    """RSI Mean Reversion Strategy"""
    
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        period = self.params.get("period", 14)
        oversold = self.params.get("oversold", 30)
        overbought = self.params.get("overbought", 70)
        
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        signals = pd.Series(0, index=df.index)
        signals[rsi < oversold] = 1
        signals[rsi > overbought] = -1
        
        return signals

class BreakoutStrategy(Strategy):
    """Channel Breakout Strategy"""
    
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        period = self.params.get("period", 20)
        
        upper = df['high'].rolling(window=period).max()
        lower = df['low'].rolling(window=period).min()
        
        signals = pd.Series(0, index=df.index)
        signals[df['close'] > upper.shift(1)] = 1
        signals[df['close'] < lower.shift(1)] = -1
        
        return signals

class MeanRevSpreadStrategy(Strategy):
    """Mean Reversion Spread Strategy (Pairs Trading)"""
    
    def generate_signals(self, df1: pd.DataFrame, df2: pd.DataFrame) -> pd.Series:
        lookback = self.params.get("lookback", 20)
        z_entry = self.params.get("z_entry", 2.0)
        z_exit = self.params.get("z_exit", 0.5)
        
        # Calculate spread
        spread = df1['close'] / df2['close']
        
        # Calculate z-score
        ma = spread.rolling(window=lookback).mean()
        std = spread.rolling(window=lookback).std()
        z_score = (spread - ma) / std
        
        signals = pd.Series(0, index=df1.index)
        signals[z_score < -z_entry] = 1  # Long spread
        signals[z_score > z_entry] = -1  # Short spread
        signals[abs(z_score) < z_exit] = 0  # Exit
        
        return signals

class BacktesterV2:
    """Enhanced Backtester with Portfolio, WFO, GA/Grid"""
    
    def __init__(self):
        self.results_dir = Path("backtests")
        self.results_dir.mkdir(exist_ok=True)
        self.strategies = {
            "sma_cross": SMAStrategy,
            "rsi_revert": RSIStrategy,
            "breakout": BreakoutStrategy,
            "mean_rev_spread": MeanRevSpreadStrategy
        }
        
    def run_backtest(
        self,
        symbol: str,
        timeframe: str,
        start_date: str,
        end_date: str,
        strategy: str,
        params: Dict,
        config: Optional[BacktestConfig] = None
    ) -> Dict:
        """Run single backtest"""
        
        # Generate run ID
        run_id = str(uuid.uuid4())[:8]
        
        # Get data
        from src.services.datahub import datahub
        ohlcv_data = datahub.get_ohlcv(symbol, timeframe, start_date, end_date)
        
        if not ohlcv_data:
            return {"error": "Failed to fetch data", "run_id": run_id}
            
        # Convert to DataFrame
        df = pd.DataFrame(
            ohlcv_data,
            columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
        )
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        
        # Initialize portfolio
        if config is None:
            config = BacktestConfig()
        portfolio = Portfolio(config)
        
        # Initialize strategy
        if strategy not in self.strategies:
            return {"error": f"Unknown strategy: {strategy}", "run_id": run_id}
            
        strat = self.strategies[strategy](params)
        
        # Generate signals
        if strategy == "mean_rev_spread":
            # For pairs trading, need second symbol
            symbol2 = params.get("symbol2", "ETH/USDT")
            ohlcv_data2 = datahub.get_ohlcv(symbol2, timeframe, start_date, end_date)
            df2 = pd.DataFrame(
                ohlcv_data2,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df2['timestamp'] = pd.to_datetime(df2['timestamp'], unit='ms')
            df2.set_index('timestamp', inplace=True)
            signals = strat.generate_signals(df, df2)
        else:
            signals = strat.generate_signals(df)
            
        # Execute trades
        position_open = False
        equity_curve = []
        drawdown_curve = []
        max_equity = config.initial_capital
        
        for idx, (timestamp, row) in enumerate(df.iterrows()):
            signal = signals.iloc[idx] if idx < len(signals) else 0
            
            # Position management
            if signal != 0 and not position_open:
                # Open position
                position_size = config.position_size_pct / 100 * portfolio.cash / row['close']
                if signal > 0:
                    portfolio.open_position(symbol, position_size, row['close'], timestamp)
                else:
                    portfolio.open_position(symbol, -position_size, row['close'], timestamp)
                position_open = True
                
            elif signal == 0 and position_open:
                # Close position
                portfolio.close_position(symbol, row['close'], timestamp)
                position_open = False
                
            # Track equity
            current_equity = portfolio.get_equity({symbol: row['close']})
            equity_curve.append([int(timestamp.timestamp() * 1000), current_equity])
            
            # Track drawdown
            max_equity = max(max_equity, current_equity)
            drawdown = (current_equity / max_equity - 1) * 100
            drawdown_curve.append([int(timestamp.timestamp() * 1000), drawdown])
            
        # Close any remaining positions
        if position_open:
            portfolio.close_position(symbol, df['close'].iloc[-1], df.index[-1])
            
        # Calculate statistics
        stats = portfolio.get_statistics()
        
        # Calculate performance metrics
        final_equity = equity_curve[-1][1] if equity_curve else config.initial_capital
        total_return = (final_equity - config.initial_capital) / config.initial_capital * 100
        
        # Calculate Sharpe ratio
        equity_series = pd.Series([e[1] for e in equity_curve])
        returns = equity_series.pct_change().dropna()
        sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
        
        # Max drawdown
        max_dd = min([d[1] for d in drawdown_curve]) if drawdown_curve else 0
        
        # Prepare results
        results = {
            "run_id": run_id,
            "symbol": symbol,
            "timeframe": timeframe,
            "start_date": start_date,
            "end_date": end_date,
            "strategy": strategy,
            "params": params,
            "equity_curve": equity_curve,
            "drawdown": drawdown_curve,
            "trades": portfolio.trades[:100],  # Limit trades
            "stats": {
                **stats,
                "total_return": round(total_return, 2),
                "sharpe_ratio": round(sharpe, 2),
                "max_drawdown": round(max_dd, 2),
                "final_equity": round(final_equity, 2)
            }
        }
        
        # Save results
        self._save_results(run_id, results)
        
        return results
        
    def run_grid_search(
        self,
        symbol: str,
        timeframe: str,
        start_date: str,
        end_date: str,
        strategy: str,
        param_grid: Dict[str, List]
    ) -> Dict:
        """Run grid search optimization"""
        
        # Generate parameter combinations
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        param_combinations = list(itertools.product(*param_values))
        
        results = []
        best_result = None
        best_sharpe = -float('inf')
        
        for combination in param_combinations:
            params = dict(zip(param_names, combination))
            
            # Run backtest
            result = self.run_backtest(
                symbol, timeframe, start_date, end_date,
                strategy, params
            )
            
            if "error" not in result:
                sharpe = result["stats"]["sharpe_ratio"]
                results.append({
                    "params": params,
                    "sharpe": sharpe,
                    "return": result["stats"]["total_return"],
                    "max_dd": result["stats"]["max_drawdown"]
                })
                
                if sharpe > best_sharpe:
                    best_sharpe = sharpe
                    best_result = result
                    
        return {
            "grid_results": results,
            "best_params": best_result["params"] if best_result else None,
            "best_sharpe": best_sharpe,
            "best_result": best_result
        }
        
    def run_genetic_algorithm(
        self,
        symbol: str,
        timeframe: str,
        start_date: str,
        end_date: str,
        strategy: str,
        param_ranges: Dict[str, Tuple[float, float]],
        population_size: int = 30,
        generations: int = 15,
        elite_size: int = 2
    ) -> Dict:
        """Run genetic algorithm optimization"""
        
        def create_individual():
            """Create random individual"""
            return {
                param: random.uniform(range_min, range_max)
                if isinstance(range_min, float)
                else random.randint(int(range_min), int(range_max))
                for param, (range_min, range_max) in param_ranges.items()
            }
            
        def fitness(individual):
            """Calculate fitness (Sharpe ratio)"""
            result = self.run_backtest(
                symbol, timeframe, start_date, end_date,
                strategy, individual
            )
            return result["stats"]["sharpe_ratio"] if "error" not in result else -float('inf')
            
        def crossover(parent1, parent2):
            """Crossover two parents"""
            child = {}
            for param in param_ranges:
                if random.random() < 0.5:
                    child[param] = parent1[param]
                else:
                    child[param] = parent2[param]
            return child
            
        def mutate(individual, mutation_rate=0.1):
            """Mutate individual"""
            for param, (range_min, range_max) in param_ranges.items():
                if random.random() < mutation_rate:
                    if isinstance(range_min, float):
                        individual[param] = random.uniform(range_min, range_max)
                    else:
                        individual[param] = random.randint(int(range_min), int(range_max))
            return individual
            
        # Initialize population
        population = [create_individual() for _ in range(population_size)]
        
        best_individual = None
        best_fitness = -float('inf')
        generation_history = []
        
        for generation in range(generations):
            # Evaluate fitness
            fitness_scores = [(ind, fitness(ind)) for ind in population]
            fitness_scores.sort(key=lambda x: x[1], reverse=True)
            
            # Track best
            if fitness_scores[0][1] > best_fitness:
                best_fitness = fitness_scores[0][1]
                best_individual = fitness_scores[0][0]
                
            generation_history.append({
                "generation": generation,
                "best_fitness": best_fitness,
                "avg_fitness": np.mean([f for _, f in fitness_scores])
            })
            
            # Select elite
            elite = [ind for ind, _ in fitness_scores[:elite_size]]
            
            # Create new population
            new_population = elite.copy()
            
            while len(new_population) < population_size:
                # Tournament selection
                parent1 = random.choice(fitness_scores[:population_size//2])[0]
                parent2 = random.choice(fitness_scores[:population_size//2])[0]
                
                # Crossover
                child = crossover(parent1, parent2)
                
                # Mutation
                child = mutate(child)
                
                new_population.append(child)
                
            population = new_population
            
        # Run final backtest with best params
        best_result = self.run_backtest(
            symbol, timeframe, start_date, end_date,
            strategy, best_individual
        )
        
        return {
            "best_params": best_individual,
            "best_fitness": best_fitness,
            "generation_history": generation_history,
            "best_result": best_result
        }
        
    def run_walk_forward_optimization(
        self,
        symbol: str,
        timeframe: str,
        start_date: str,
        end_date: str,
        strategy: str,
        param_grid: Dict[str, List],
        n_splits: int = 3,
        train_ratio: float = 0.7
    ) -> Dict:
        """Run walk-forward optimization"""
        
        # Parse dates
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        total_days = (end_dt - start_dt).days
        
        # Calculate split size
        split_days = total_days // n_splits
        
        wfo_results = []
        
        for split in range(n_splits):
            # Calculate train/test periods
            split_start = start_dt + timedelta(days=split * split_days)
            split_end = split_start + timedelta(days=split_days)
            
            train_end = split_start + timedelta(days=int(split_days * train_ratio))
            
            train_start_str = split_start.strftime("%Y-%m-%d")
            train_end_str = train_end.strftime("%Y-%m-%d")
            test_start_str = train_end_str
            test_end_str = split_end.strftime("%Y-%m-%d")
            
            # Optimize on training data
            grid_result = self.run_grid_search(
                symbol, timeframe,
                train_start_str, train_end_str,
                strategy, param_grid
            )
            
            if grid_result["best_params"]:
                # Test on out-of-sample data
                test_result = self.run_backtest(
                    symbol, timeframe,
                    test_start_str, test_end_str,
                    strategy, grid_result["best_params"]
                )
                
                wfo_results.append({
                    "split": split,
                    "train_period": f"{train_start_str} to {train_end_str}",
                    "test_period": f"{test_start_str} to {test_end_str}",
                    "best_params": grid_result["best_params"],
                    "in_sample_sharpe": grid_result["best_sharpe"],
                    "oos_sharpe": test_result["stats"]["sharpe_ratio"] if "error" not in test_result else 0,
                    "oos_return": test_result["stats"]["total_return"] if "error" not in test_result else 0
                })
                
        # Calculate average out-of-sample performance
        avg_oos_sharpe = np.mean([r["oos_sharpe"] for r in wfo_results])
        avg_oos_return = np.mean([r["oos_return"] for r in wfo_results])
        
        return {
            "wfo_results": wfo_results,
            "avg_oos_sharpe": round(avg_oos_sharpe, 2),
            "avg_oos_return": round(avg_oos_return, 2),
            "n_splits": n_splits
        }
        
    def _save_results(self, run_id: str, results: Dict):
        """Save backtest results"""
        # Save JSON
        json_file = self.results_dir / f"{run_id}.json"
        with open(json_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
            
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
backtester = BacktesterV2()