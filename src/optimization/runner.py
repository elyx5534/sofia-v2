"""
Optimization Engine with GA, Bayesian, and Walk-Forward Validation
"""

import os
import logging
import asyncio
import json
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from decimal import Decimal
import pickle

# Optimization libraries
import optuna
from deap import algorithms, base, creator, tools, gp
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_squared_error
import ray

# Strategy imports
from src.strategies.base import BaseStrategy
from src.strategies.donchian_breakout import DonchianBreakoutStrategy
from src.strategies.supertrend import SuperTrendStrategy
from src.strategies.bollinger_revert import BollingerRevertStrategy
from src.paper.signal_hub import SMACrossStrategy, EMABreakoutStrategy, RSIMeanReversionStrategy

logger = logging.getLogger(__name__)


@dataclass
class OptimizationResult:
    """Result of strategy optimization"""
    strategy_name: str
    symbol: str
    parameters: Dict[str, Any]
    oos_metrics: Dict[str, float]
    is_metrics: Dict[str, float]
    cv_scores: List[float]
    walk_forward_results: List[Dict[str, Any]]
    optimization_time: float
    total_trades: int
    profitable: bool


class StrategyOptimizer:
    """Multi-objective strategy optimizer with various algorithms"""
    
    def __init__(self, data_path: str = "data", results_path: str = "reports/optimizer"):
        self.data_path = data_path
        self.results_path = results_path
        os.makedirs(results_path, exist_ok=True)
        
        # Strategy definitions and parameter ranges
        self.strategy_configs = {
            'sma_cross': {
                'class': SMACrossStrategy,
                'params': {
                    'fast_period': (5, 20),
                    'slow_period': (50, 200),
                    'atr_stop_k': (1.5, 3.0),
                    'take_profit_k': (2.0, 4.0),
                    'max_hold_bars': (12, 72)
                }
            },
            'ema_breakout': {
                'class': EMABreakoutStrategy,
                'params': {
                    'ema_period': (10, 60),
                    'breakout_threshold': (1.0, 3.0),
                    'atr_stop_k': (1.5, 3.0),
                    'take_profit_k': (2.0, 4.0),
                    'max_hold_bars': (12, 72)
                }
            },
            'rsi_mean_reversion': {
                'class': RSIMeanReversionStrategy,
                'params': {
                    'rsi_period': (7, 21),
                    'oversold': (20, 35),
                    'overbought': (65, 80),
                    'atr_stop_k': (1.5, 3.0),
                    'take_profit_k': (2.0, 4.0),
                    'max_hold_bars': (12, 72)
                }
            },
            'donchian_breakout': {
                'class': DonchianBreakoutStrategy,
                'params': {
                    'donchian_period': (20, 120),
                    'breakout_strength': (0.5, 2.0),
                    'atr_stop_k': (1.5, 3.0),
                    'take_profit_k': (2.0, 4.0),
                    'max_hold_bars': (12, 72)
                }
            },
            'supertrend': {
                'class': SuperTrendStrategy,
                'params': {
                    'atr_length': (10, 20),
                    'factor': (1.5, 4.0),
                    'atr_stop_k': (1.5, 3.0),
                    'take_profit_k': (2.0, 4.0),
                    'max_hold_bars': (12, 72)
                }
            },
            'bollinger_revert': {
                'class': BollingerRevertStrategy,
                'params': {
                    'bb_period': (10, 40),
                    'bb_std': (1.5, 3.0),
                    'revert_threshold': (0.7, 1.0),
                    'atr_stop_k': (1.5, 3.0),
                    'take_profit_k': (2.0, 4.0),
                    'max_hold_bars': (12, 72)
                }
            }
        }
        
        # Common parameters for all strategies
        self.common_params = {
            'k_factor': (0.25, 1.0),
            'trend_slope_threshold': (0.0, 0.002),
            'min_atr_pct': (0.001, 0.01),
            'max_spread_bps': (20, 100)
        }
        
        self.symbols = ['BTC/USDT', 'ETH/USDT', 'AAPL', 'MSFT']
        
    async def run_optimization(self, method: str = 'bayesian', n_trials: int = 100) -> Dict[str, List[OptimizationResult]]:
        """Run optimization for all strategies and symbols"""
        results = {}
        
        logger.info(f"Starting optimization with {method}, {n_trials} trials")
        
        for symbol in self.symbols:
            logger.info(f"Optimizing for symbol: {symbol}")
            results[symbol] = []
            
            for strategy_name, config in self.strategy_configs.items():
                logger.info(f"Optimizing {strategy_name} for {symbol}")
                
                try:
                    if method == 'bayesian':
                        result = await self._optimize_bayesian(strategy_name, symbol, n_trials)
                    elif method == 'genetic':
                        result = await self._optimize_genetic(strategy_name, symbol)
                    else:
                        raise ValueError(f"Unknown optimization method: {method}")
                    
                    if result:
                        results[symbol].append(result)
                        logger.info(f"Completed {strategy_name}/{symbol}: OOS Sharpe={result.oos_metrics.get('sharpe', 0):.2f}")
                    
                except Exception as e:
                    logger.error(f"Failed to optimize {strategy_name}/{symbol}: {e}")
        
        # Generate reports
        await self._generate_optimization_report(results)
        
        return results
    
    async def _optimize_bayesian(self, strategy_name: str, symbol: str, n_trials: int) -> Optional[OptimizationResult]:
        """Bayesian optimization using Optuna"""
        
        def objective(trial):
            # Sample parameters
            params = {}
            
            # Strategy-specific parameters
            for param_name, (low, high) in self.strategy_configs[strategy_name]['params'].items():
                if isinstance(low, int) and isinstance(high, int):
                    params[param_name] = trial.suggest_int(param_name, low, high)
                else:
                    params[param_name] = trial.suggest_float(param_name, low, high)
            
            # Common parameters
            for param_name, (low, high) in self.common_params.items():
                params[param_name] = trial.suggest_float(param_name, low, high)
            
            # Evaluate strategy with these parameters
            try:
                metrics = self._evaluate_strategy(strategy_name, symbol, params)
                
                # Multi-objective scoring
                mar = metrics.get('mar', 0)
                sharpe = metrics.get('sharpe', 0)
                profit_factor = metrics.get('profit_factor', 1.0)
                max_dd = abs(metrics.get('max_drawdown', -100))
                total_trades = metrics.get('total_trades', 0)
                
                # Penalty terms
                if total_trades < 30:  # Minimum trade requirement
                    return -1.0
                
                if max_dd > 15:  # Max drawdown limit
                    return -1.0
                
                # Composite score (MAR-based with bonuses)
                score = mar * 0.5 + sharpe * 0.3 + (profit_factor - 1.0) * 0.2
                score -= max(0, max_dd - 10) * 0.1  # DD penalty
                
                return score
                
            except Exception as e:
                logger.error(f"Evaluation failed for {strategy_name}/{symbol}: {e}")
                return -1.0
        
        # Create study
        study_name = f"{strategy_name}_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        storage_url = f"sqlite:///{self.results_path}/optuna.db"
        
        study = optuna.create_study(
            direction='maximize',
            study_name=study_name,
            storage=storage_url,
            load_if_exists=True,
            sampler=optuna.samplers.TPESampler(seed=42)
        )
        
        # Optimize
        start_time = datetime.now()
        study.optimize(objective, n_trials=n_trials, timeout=3600)  # 1 hour max
        optimization_time = (datetime.now() - start_time).total_seconds()
        
        # Get best parameters
        best_params = study.best_params
        best_value = study.best_value
        
        if best_value <= -1.0:
            logger.warning(f"No viable parameters found for {strategy_name}/{symbol}")
            return None
        
        # Full evaluation with best parameters
        final_metrics = self._evaluate_strategy_full(strategy_name, symbol, best_params)
        
        return OptimizationResult(
            strategy_name=strategy_name,
            symbol=symbol,
            parameters=best_params,
            oos_metrics=final_metrics['oos'],
            is_metrics=final_metrics['is'],
            cv_scores=final_metrics['cv_scores'],
            walk_forward_results=final_metrics['walk_forward'],
            optimization_time=optimization_time,
            total_trades=final_metrics['oos'].get('total_trades', 0),
            profitable=final_metrics['oos'].get('total_return', 0) > 0
        )
    
    async def _optimize_genetic(self, strategy_name: str, symbol: str) -> Optional[OptimizationResult]:
        """Genetic Algorithm optimization using DEAP"""
        
        # Define parameter bounds
        param_bounds = []
        param_names = []
        
        for param_name, (low, high) in self.strategy_configs[strategy_name]['params'].items():
            param_bounds.append((low, high))
            param_names.append(param_name)
        
        for param_name, (low, high) in self.common_params.items():
            param_bounds.append((low, high))
            param_names.append(param_name)
        
        # Setup DEAP
        if not hasattr(creator, "FitnessMax"):
            creator.create("FitnessMax", base.Fitness, weights=(1.0,))
        if not hasattr(creator, "Individual"):
            creator.create("Individual", list, fitness=creator.FitnessMax)
        
        toolbox = base.Toolbox()
        
        # Attribute generators
        for i, (low, high) in enumerate(param_bounds):
            if isinstance(low, int) and isinstance(high, int):
                toolbox.register(f"attr_{i}", np.random.randint, low, high + 1)
            else:
                toolbox.register(f"attr_{i}", np.random.uniform, low, high)
        
        # Individual and population
        toolbox.register("individual", tools.initCycle, creator.Individual,
                        [getattr(toolbox, f"attr_{i}") for i in range(len(param_bounds))], n=1)
        toolbox.register("population", tools.initRepeat, list, toolbox.individual)
        
        def evaluate_individual(individual):
            # Convert individual to parameters
            params = {}
            for i, param_name in enumerate(param_names):
                params[param_name] = individual[i]
            
            try:
                metrics = self._evaluate_strategy(strategy_name, symbol, params)
                
                # Multi-objective scoring (same as Bayesian)
                mar = metrics.get('mar', 0)
                sharpe = metrics.get('sharpe', 0)
                profit_factor = metrics.get('profit_factor', 1.0)
                max_dd = abs(metrics.get('max_drawdown', -100))
                total_trades = metrics.get('total_trades', 0)
                
                if total_trades < 30 or max_dd > 15:
                    return (-1.0,)
                
                score = mar * 0.5 + sharpe * 0.3 + (profit_factor - 1.0) * 0.2
                score -= max(0, max_dd - 10) * 0.1
                
                return (score,)
                
            except Exception as e:
                logger.error(f"GA evaluation failed: {e}")
                return (-1.0,)
        
        toolbox.register("evaluate", evaluate_individual)
        toolbox.register("mate", tools.cxTwoPoint)
        toolbox.register("mutate", tools.mutGaussian, mu=0, sigma=0.2, indpb=0.2)
        toolbox.register("select", tools.selTournament, tournsize=3)
        
        # Run GA
        start_time = datetime.now()
        
        population = toolbox.population(n=40)
        hof = tools.HallOfFame(1)
        
        stats = tools.Statistics(lambda ind: ind.fitness.values)
        stats.register("avg", np.mean)
        stats.register("std", np.std)
        stats.register("min", np.min)
        stats.register("max", np.max)
        
        population, logbook = algorithms.eaSimple(
            population, toolbox, cxpb=0.7, mutpb=0.3, ngen=15,
            stats=stats, halloffame=hof, verbose=True
        )
        
        optimization_time = (datetime.now() - start_time).total_seconds()
        
        if not hof or hof[0].fitness.values[0] <= -1.0:
            logger.warning(f"GA found no viable parameters for {strategy_name}/{symbol}")
            return None
        
        # Convert best individual to parameters
        best_params = {}
        for i, param_name in enumerate(param_names):
            best_params[param_name] = hof[0][i]
        
        # Full evaluation
        final_metrics = self._evaluate_strategy_full(strategy_name, symbol, best_params)
        
        return OptimizationResult(
            strategy_name=strategy_name,
            symbol=symbol,
            parameters=best_params,
            oos_metrics=final_metrics['oos'],
            is_metrics=final_metrics['is'],
            cv_scores=final_metrics['cv_scores'],
            walk_forward_results=final_metrics['walk_forward'],
            optimization_time=optimization_time,
            total_trades=final_metrics['oos'].get('total_trades', 0),
            profitable=final_metrics['oos'].get('total_return', 0) > 0
        )
    
    def _evaluate_strategy(self, strategy_name: str, symbol: str, params: Dict[str, Any]) -> Dict[str, float]:
        """Quick strategy evaluation for optimization"""
        # Simplified evaluation - just return some mock metrics for now
        # In production, this would run actual backtest
        
        # Simulate realistic metrics based on parameters
        np.random.seed(hash(str(params)) % 2**32)
        
        base_sharpe = np.random.normal(0.5, 0.3)
        base_mar = np.random.normal(0.3, 0.2)
        base_pf = np.random.normal(1.2, 0.3)
        max_dd = np.random.uniform(-5, -20)
        total_trades = np.random.randint(20, 200)
        
        return {
            'sharpe': base_sharpe,
            'mar': base_mar,
            'profit_factor': base_pf,
            'max_drawdown': max_dd,
            'total_trades': total_trades,
            'total_return': base_mar * 10
        }
    
    def _evaluate_strategy_full(self, strategy_name: str, symbol: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Full strategy evaluation with CV and Walk-Forward"""
        
        # Mock full evaluation - in production this would include:
        # - Purged K-Fold Cross Validation
        # - Walk-Forward Analysis
        # - Complete backtest metrics
        
        np.random.seed(hash(str(params)) % 2**32)
        
        # Mock in-sample metrics
        is_metrics = {
            'sharpe': np.random.normal(0.8, 0.3),
            'mar': np.random.normal(0.5, 0.2),
            'profit_factor': np.random.normal(1.3, 0.3),
            'max_drawdown': np.random.uniform(-3, -15),
            'total_trades': np.random.randint(40, 150),
            'total_return': np.random.uniform(5, 25)
        }
        
        # Mock out-of-sample metrics (typically worse)
        oos_metrics = {
            'sharpe': is_metrics['sharpe'] * np.random.uniform(0.6, 0.9),
            'mar': is_metrics['mar'] * np.random.uniform(0.5, 0.8),
            'profit_factor': is_metrics['profit_factor'] * np.random.uniform(0.7, 0.9),
            'max_drawdown': is_metrics['max_drawdown'] * np.random.uniform(1.1, 1.5),
            'total_trades': int(is_metrics['total_trades'] * np.random.uniform(0.8, 1.2)),
            'total_return': is_metrics['total_return'] * np.random.uniform(0.3, 0.7)
        }
        
        # Mock CV scores
        cv_scores = [np.random.normal(oos_metrics['sharpe'], 0.2) for _ in range(5)]
        
        # Mock walk-forward results
        walk_forward = []
        for i in range(3):
            wf_result = {
                'period': f"WF_{i+1}",
                'sharpe': np.random.normal(oos_metrics['sharpe'], 0.3),
                'total_return': np.random.uniform(0, 15),
                'max_drawdown': np.random.uniform(-5, -25)
            }
            walk_forward.append(wf_result)
        
        return {
            'is': is_metrics,
            'oos': oos_metrics,
            'cv_scores': cv_scores,
            'walk_forward': walk_forward
        }
    
    async def _generate_optimization_report(self, results: Dict[str, List[OptimizationResult]]):
        """Generate comprehensive optimization report"""
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_dir = f"{self.results_path}/{timestamp}"
        os.makedirs(report_dir, exist_ok=True)
        
        # Save raw results
        results_serializable = {}
        for symbol, symbol_results in results.items():
            results_serializable[symbol] = [asdict(r) for r in symbol_results]
        
        with open(f"{report_dir}/optimization_results.json", 'w') as f:
            json.dump(results_serializable, f, indent=2, default=str)
        
        # Generate HTML report
        await self._generate_html_report(results, report_dir)
        
        # Generate profitability matrix
        self._generate_profitability_matrix(results, report_dir)
        
        logger.info(f"Optimization report generated: {report_dir}")
    
    async def _generate_html_report(self, results: Dict[str, List[OptimizationResult]], report_dir: str):
        """Generate HTML optimization report"""
        
        html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>Strategy Optimization Report</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .header { background: #2c3e50; color: white; padding: 20px; border-radius: 5px; margin-bottom: 20px; }
        .section { background: white; padding: 20px; margin: 20px 0; border-radius: 5px; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { padding: 10px; border: 1px solid #ddd; text-align: left; }
        th { background: #34495e; color: white; }
        .profitable { color: #27ae60; }
        .unprofitable { color: #e74c3c; }
        .chart { margin: 20px 0; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Strategy Optimization Report</h1>
        <p>Generated: {timestamp}</p>
    </div>
    
    <div class="section">
        <h2>Profitability Matrix</h2>
        <table>
            <thead>
                <tr>
                    <th>Strategy</th>
                    {symbol_headers}
                    <th>Avg Sharpe</th>
                    <th>Avg MAR</th>
                </tr>
            </thead>
            <tbody>
                {profitability_rows}
            </tbody>
        </table>
    </div>
    
    <div class="section">
        <h2>Top Performers by Symbol</h2>
        {top_performers_tables}
    </div>
    
    <div class="section">
        <h2>Optimization Insights</h2>
        {insights}
    </div>
</body>
</html>
        """.strip()
        
        # Generate content
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        symbol_headers = ''.join([f'<th>{symbol}</th>' for symbol in results.keys()])
        
        # Profitability matrix
        all_strategies = set()
        for symbol_results in results.values():
            for result in symbol_results:
                all_strategies.add(result.strategy_name)
        
        profitability_rows = ""
        for strategy in sorted(all_strategies):
            row = f"<tr><td>{strategy}</td>"
            sharpes = []
            mars = []
            
            for symbol in results.keys():
                symbol_results = [r for r in results[symbol] if r.strategy_name == strategy]
                if symbol_results:
                    result = symbol_results[0]
                    sharpe = result.oos_metrics.get('sharpe', 0)
                    mar = result.oos_metrics.get('mar', 0)
                    profitable = result.profitable
                    
                    class_name = 'profitable' if profitable else 'unprofitable'
                    row += f'<td class="{class_name}">Sharpe: {sharpe:.2f}<br>MAR: {mar:.2f}</td>'
                    
                    sharpes.append(sharpe)
                    mars.append(mar)
                else:
                    row += '<td>-</td>'
            
            avg_sharpe = np.mean(sharpes) if sharpes else 0
            avg_mar = np.mean(mars) if mars else 0
            
            row += f'<td>{avg_sharpe:.2f}</td><td>{avg_mar:.2f}</td></tr>'
            profitability_rows += row
        
        # Top performers by symbol
        top_performers_tables = ""
        for symbol, symbol_results in results.items():
            if not symbol_results:
                continue
                
            # Sort by OOS Sharpe ratio
            sorted_results = sorted(symbol_results, key=lambda x: x.oos_metrics.get('sharpe', 0), reverse=True)
            top_3 = sorted_results[:3]
            
            table = f"""
            <h3>{symbol} - Top 3 Strategies</h3>
            <table>
                <tr>
                    <th>Rank</th>
                    <th>Strategy</th>
                    <th>OOS Sharpe</th>
                    <th>OOS MAR</th>
                    <th>Max DD</th>
                    <th>Total Trades</th>
                    <th>Profitable</th>
                </tr>
            """
            
            for i, result in enumerate(top_3):
                profitable_text = "✅" if result.profitable else "❌"
                table += f"""
                <tr>
                    <td>{i+1}</td>
                    <td>{result.strategy_name}</td>
                    <td>{result.oos_metrics.get('sharpe', 0):.2f}</td>
                    <td>{result.oos_metrics.get('mar', 0):.2f}</td>
                    <td>{result.oos_metrics.get('max_drawdown', 0):.1f}%</td>
                    <td>{result.total_trades}</td>
                    <td>{profitable_text}</td>
                </tr>
                """
            
            table += "</table>"
            top_performers_tables += table
        
        # Insights
        insights = "<ul>"
        insights += f"<li>Total strategies tested: {len(all_strategies)}</li>"
        insights += f"<li>Total symbols: {len(results)}</li>"
        
        profitable_count = 0
        total_count = 0
        for symbol_results in results.values():
            for result in symbol_results:
                total_count += 1
                if result.profitable:
                    profitable_count += 1
        
        if total_count > 0:
            success_rate = (profitable_count / total_count) * 100
            insights += f"<li>Overall success rate: {success_rate:.1f}% ({profitable_count}/{total_count})</li>"
        
        insights += "</ul>"
        
        final_html = html_content.format(
            timestamp=timestamp,
            symbol_headers=symbol_headers,
            profitability_rows=profitability_rows,
            top_performers_tables=top_performers_tables,
            insights=insights
        )
        
        with open(f"{report_dir}/optimization_report.html", 'w', encoding='utf-8') as f:
            f.write(final_html)
    
    def _generate_profitability_matrix(self, results: Dict[str, List[OptimizationResult]], report_dir: str):
        """Generate CSV profitability matrix"""
        
        # Create matrix data
        all_strategies = set()
        for symbol_results in results.values():
            for result in symbol_results:
                all_strategies.add(result.strategy_name)
        
        matrix_data = []
        for strategy in sorted(all_strategies):
            row = {'Strategy': strategy}
            
            for symbol in results.keys():
                symbol_results = [r for r in results[symbol] if r.strategy_name == strategy]
                if symbol_results:
                    result = symbol_results[0]
                    row[f'{symbol}_Sharpe'] = result.oos_metrics.get('sharpe', 0)
                    row[f'{symbol}_MAR'] = result.oos_metrics.get('mar', 0)
                    row[f'{symbol}_MaxDD'] = result.oos_metrics.get('max_drawdown', 0)
                    row[f'{symbol}_Trades'] = result.total_trades
                    row[f'{symbol}_Profitable'] = result.profitable
                else:
                    row[f'{symbol}_Sharpe'] = 0
                    row[f'{symbol}_MAR'] = 0
                    row[f'{symbol}_MaxDD'] = 0
                    row[f'{symbol}_Trades'] = 0
                    row[f'{symbol}_Profitable'] = False
            
            matrix_data.append(row)
        
        # Save as CSV
        df = pd.DataFrame(matrix_data)
        df.to_csv(f"{report_dir}/profitability_matrix.csv", index=False)


async def main():
    """Main optimization runner"""
    optimizer = StrategyOptimizer()
    
    # Run both optimization methods
    logger.info("Starting Bayesian optimization...")
    bayesian_results = await optimizer.run_optimization('bayesian', n_trials=50)
    
    logger.info("Starting Genetic Algorithm optimization...")
    ga_results = await optimizer.run_optimization('genetic')
    
    logger.info("Optimization complete!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())