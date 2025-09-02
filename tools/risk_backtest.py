"""
Risk Backtest Suite with Monte Carlo Simulation
Calculates VaR, ETL, Sharpe, Sortino through simulation
"""

import numpy as np
from scipy import stats
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RiskBacktest:
    """Risk assessment through backtesting and Monte Carlo"""
    
    def __init__(self, config: Dict = None):
        if config is None:
            config = self.load_config()
        
        # Simulation parameters
        self.n_simulations = config.get("n_simulations", 10000)
        self.n_days = config.get("n_days", 30)
        self.confidence_levels = config.get("confidence_levels", [0.95, 0.99])
        
        # Risk-free rate (annual)
        self.risk_free_rate = config.get("risk_free_rate", 0.02)
        
        # Position limits
        self.max_position = config.get("max_position", 100000)
        self.initial_capital = config.get("initial_capital", 100000)
    
    def load_config(self) -> Dict:
        """Load risk backtest configuration"""
        config_file = Path("config/risk_backtest.yaml")
        
        if config_file.exists():
            import yaml
            with open(config_file, 'r') as f:
                return yaml.safe_load(f)
        
        # Default config
        return {
            "n_simulations": 10000,
            "n_days": 30,
            "confidence_levels": [0.95, 0.99],
            "risk_free_rate": 0.02,
            "max_position": 100000,
            "initial_capital": 100000
        }
    
    def load_historical_returns(self) -> np.ndarray:
        """Load historical returns from backtest results"""
        
        returns = []
        
        # Try to load from backtest results
        backtest_file = Path("reports/backtest_results.json")
        if backtest_file.exists():
            with open(backtest_file, 'r') as f:
                results = json.load(f)
                if "daily_returns" in results:
                    returns = results["daily_returns"]
        
        # Try to load from daily scores
        if not returns:
            daily_score_file = Path("reports/daily_score.json")
            if daily_score_file.exists():
                with open(daily_score_file, 'r') as f:
                    scores = json.load(f)
                    if "returns" in scores:
                        returns = scores["returns"]
        
        # Generate synthetic returns if no data
        if not returns:
            # Generate realistic crypto returns (higher vol)
            mean_return = 0.002  # 0.2% daily
            volatility = 0.03    # 3% daily vol
            returns = np.random.normal(mean_return, volatility, 100)
        
        return np.array(returns)
    
    def calculate_var(
        self,
        returns: np.ndarray,
        confidence_level: float = 0.95
    ) -> float:
        """Calculate Value at Risk"""
        
        # Sort returns
        sorted_returns = np.sort(returns)
        
        # Find the index for VaR
        index = int((1 - confidence_level) * len(sorted_returns))
        
        # VaR is the loss at this percentile (negative return)
        var = -sorted_returns[index] if index < len(sorted_returns) else -sorted_returns[0]
        
        return var
    
    def calculate_etl(
        self,
        returns: np.ndarray,
        confidence_level: float = 0.95
    ) -> float:
        """Calculate Expected Tail Loss (Conditional VaR)"""
        
        # Get VaR threshold
        var = self.calculate_var(returns, confidence_level)
        
        # Get all returns worse than VaR
        tail_returns = returns[returns <= -var]
        
        if len(tail_returns) == 0:
            return var
        
        # ETL is average of tail returns
        etl = -np.mean(tail_returns)
        
        return etl
    
    def calculate_sharpe_ratio(
        self,
        returns: np.ndarray,
        periods_per_year: int = 252
    ) -> float:
        """Calculate Sharpe Ratio"""
        
        # Annualized return
        mean_return = np.mean(returns) * periods_per_year
        
        # Annualized volatility
        volatility = np.std(returns) * np.sqrt(periods_per_year)
        
        if volatility == 0:
            return 0
        
        # Sharpe ratio
        sharpe = (mean_return - self.risk_free_rate) / volatility
        
        return sharpe
    
    def calculate_sortino_ratio(
        self,
        returns: np.ndarray,
        periods_per_year: int = 252
    ) -> float:
        """Calculate Sortino Ratio (downside deviation)"""
        
        # Annualized return
        mean_return = np.mean(returns) * periods_per_year
        
        # Downside returns only
        downside_returns = returns[returns < 0]
        
        if len(downside_returns) == 0:
            return float('inf')  # No downside risk
        
        # Downside deviation
        downside_dev = np.std(downside_returns) * np.sqrt(periods_per_year)
        
        if downside_dev == 0:
            return float('inf')
        
        # Sortino ratio
        sortino = (mean_return - self.risk_free_rate) / downside_dev
        
        return sortino
    
    def calculate_max_drawdown(self, returns: np.ndarray) -> Tuple[float, int]:
        """Calculate maximum drawdown and duration"""
        
        # Calculate cumulative returns
        cum_returns = np.cumprod(1 + returns)
        
        # Calculate running maximum
        running_max = np.maximum.accumulate(cum_returns)
        
        # Calculate drawdown
        drawdown = (cum_returns - running_max) / running_max
        
        # Find maximum drawdown
        max_dd = np.min(drawdown)
        
        # Find drawdown duration
        if max_dd < 0:
            dd_start = np.argmax(running_max[:np.argmin(drawdown)])
            dd_end = np.argmin(drawdown)
            duration = dd_end - dd_start
        else:
            duration = 0
        
        return abs(max_dd), duration
    
    def monte_carlo_simulation(
        self,
        historical_returns: np.ndarray
    ) -> Dict:
        """Run Monte Carlo simulation"""
        
        # Fit distribution to historical returns
        mean = np.mean(historical_returns)
        std = np.std(historical_returns)
        
        # Also fit a t-distribution for fat tails
        params = stats.t.fit(historical_returns)
        df, loc, scale = params
        
        # Storage for simulation results
        final_values = []
        paths = []
        vars = []
        max_dds = []
        
        logger.info(f"Running {self.n_simulations} Monte Carlo simulations...")
        
        for sim in range(self.n_simulations):
            # Generate returns path
            if sim < self.n_simulations // 2:
                # Half with normal distribution
                sim_returns = np.random.normal(mean, std, self.n_days)
            else:
                # Half with t-distribution (fat tails)
                sim_returns = stats.t.rvs(df, loc=loc, scale=scale, size=self.n_days)
            
            # Calculate cumulative value
            cum_value = self.initial_capital * np.cumprod(1 + sim_returns)
            final_value = cum_value[-1]
            
            # Store results
            final_values.append(final_value)
            
            # Store sample paths
            if sim < 100:  # Store first 100 paths for visualization
                paths.append(cum_value)
            
            # Calculate VaR for this path
            path_var = self.calculate_var(sim_returns, 0.95)
            vars.append(path_var)
            
            # Calculate max drawdown
            max_dd, _ = self.calculate_max_drawdown(sim_returns)
            max_dds.append(max_dd)
        
        # Calculate statistics
        final_values = np.array(final_values)
        vars = np.array(vars)
        max_dds = np.array(max_dds)
        
        results = {
            "n_simulations": self.n_simulations,
            "n_days": self.n_days,
            "initial_capital": self.initial_capital,
            "final_values": {
                "mean": np.mean(final_values),
                "median": np.median(final_values),
                "std": np.std(final_values),
                "min": np.min(final_values),
                "max": np.max(final_values),
                "p5": np.percentile(final_values, 5),
                "p95": np.percentile(final_values, 95)
            },
            "returns": {
                "mean": (np.mean(final_values) / self.initial_capital - 1),
                "median": (np.median(final_values) / self.initial_capital - 1),
                "best": (np.max(final_values) / self.initial_capital - 1),
                "worst": (np.min(final_values) / self.initial_capital - 1)
            },
            "var_distribution": {
                "mean": np.mean(vars),
                "p95": np.percentile(vars, 95),
                "p99": np.percentile(vars, 99)
            },
            "max_dd_distribution": {
                "mean": np.mean(max_dds),
                "p95": np.percentile(max_dds, 95),
                "worst": np.max(max_dds)
            },
            "probability": {
                "profit": np.mean(final_values > self.initial_capital),
                "loss_10pct": np.mean(final_values < self.initial_capital * 0.9),
                "loss_20pct": np.mean(final_values < self.initial_capital * 0.8),
                "gain_20pct": np.mean(final_values > self.initial_capital * 1.2),
                "gain_50pct": np.mean(final_values > self.initial_capital * 1.5)
            }
        }
        
        return results
    
    def run_comprehensive_backtest(self) -> Dict:
        """Run comprehensive risk backtest"""
        
        logger.info("Starting comprehensive risk backtest...")
        
        # Load historical returns
        historical_returns = self.load_historical_returns()
        
        # Calculate risk metrics
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "data_points": len(historical_returns),
            "historical_metrics": {},
            "monte_carlo": {},
            "risk_limits": {}
        }
        
        # Historical metrics
        logger.info("Calculating historical metrics...")
        
        for conf_level in self.confidence_levels:
            var = self.calculate_var(historical_returns, conf_level)
            etl = self.calculate_etl(historical_returns, conf_level)
            
            metrics["historical_metrics"][f"var_{int(conf_level*100)}"] = var
            metrics["historical_metrics"][f"etl_{int(conf_level*100)}"] = etl
        
        metrics["historical_metrics"]["sharpe_ratio"] = self.calculate_sharpe_ratio(historical_returns)
        metrics["historical_metrics"]["sortino_ratio"] = self.calculate_sortino_ratio(historical_returns)
        
        max_dd, dd_duration = self.calculate_max_drawdown(historical_returns)
        metrics["historical_metrics"]["max_drawdown"] = max_dd
        metrics["historical_metrics"]["max_dd_duration"] = dd_duration
        
        # Monte Carlo simulation
        logger.info("Running Monte Carlo simulation...")
        mc_results = self.monte_carlo_simulation(historical_returns)
        metrics["monte_carlo"] = mc_results
        
        # Risk limits recommendations
        metrics["risk_limits"] = self.calculate_risk_limits(metrics)
        
        # Save results
        self.save_results(metrics)
        
        return metrics
    
    def calculate_risk_limits(self, metrics: Dict) -> Dict:
        """Calculate recommended risk limits"""
        
        limits = {}
        
        # Position size limit based on VaR
        var_95 = metrics["historical_metrics"].get("var_95", 0.02)
        max_loss_per_trade = self.initial_capital * var_95
        limits["max_position_size"] = min(max_loss_per_trade * 2, self.max_position)
        
        # Daily loss limit
        etl_95 = metrics["historical_metrics"].get("etl_95", 0.03)
        limits["daily_loss_limit"] = self.initial_capital * etl_95
        
        # Drawdown limit
        max_dd = metrics["historical_metrics"].get("max_drawdown", 0.1)
        limits["max_drawdown_limit"] = min(max_dd * 1.5, 0.2)  # Cap at 20%
        
        # Leverage limit based on Sharpe
        sharpe = metrics["historical_metrics"].get("sharpe_ratio", 0)
        if sharpe > 1.5:
            limits["max_leverage"] = 3.0
        elif sharpe > 1.0:
            limits["max_leverage"] = 2.0
        else:
            limits["max_leverage"] = 1.0
        
        return limits
    
    def save_results(self, metrics: Dict):
        """Save risk backtest results"""
        
        results_file = Path("reports/risk_backtest.json")
        results_file.parent.mkdir(exist_ok=True)
        
        with open(results_file, 'w') as f:
            json.dump(metrics, f, indent=2)
        
        logger.info(f"Risk backtest results saved to {results_file}")
    
    def print_report(self, metrics: Dict):
        """Print formatted risk report"""
        
        print("\n" + "="*60)
        print(" RISK BACKTEST REPORT")
        print("="*60)
        print(f"Generated: {metrics['timestamp']}")
        print(f"Data Points: {metrics['data_points']}")
        print("-"*60)
        
        # Historical Metrics
        hist = metrics["historical_metrics"]
        print("\nHISTORICAL METRICS:")
        print(f"  VaR (95%): {hist.get('var_95', 0)*100:.2f}%")
        print(f"  VaR (99%): {hist.get('var_99', 0)*100:.2f}%")
        print(f"  ETL (95%): {hist.get('etl_95', 0)*100:.2f}%")
        print(f"  ETL (99%): {hist.get('etl_99', 0)*100:.2f}%")
        print(f"  Sharpe Ratio: {hist.get('sharpe_ratio', 0):.2f}")
        print(f"  Sortino Ratio: {hist.get('sortino_ratio', 0):.2f}")
        print(f"  Max Drawdown: {hist.get('max_drawdown', 0)*100:.2f}%")
        print(f"  DD Duration: {hist.get('max_dd_duration', 0)} periods")
        
        # Monte Carlo Results
        mc = metrics["monte_carlo"]
        if mc:
            print(f"\nMONTE CARLO ({mc['n_simulations']} simulations, {mc['n_days']} days):")
            
            print("\n  Final Value Distribution:")
            fv = mc["final_values"]
            print(f"    Mean: ${fv['mean']:,.0f}")
            print(f"    Median: ${fv['median']:,.0f}")
            print(f"    5th percentile: ${fv['p5']:,.0f}")
            print(f"    95th percentile: ${fv['p95']:,.0f}")
            
            print("\n  Return Distribution:")
            ret = mc["returns"]
            print(f"    Mean: {ret['mean']*100:.2f}%")
            print(f"    Best: {ret['best']*100:.2f}%")
            print(f"    Worst: {ret['worst']*100:.2f}%")
            
            print("\n  Probabilities:")
            prob = mc["probability"]
            print(f"    P(Profit): {prob['profit']*100:.1f}%")
            print(f"    P(Loss > 10%): {prob['loss_10pct']*100:.1f}%")
            print(f"    P(Loss > 20%): {prob['loss_20pct']*100:.1f}%")
            print(f"    P(Gain > 20%): {prob['gain_20pct']*100:.1f}%")
            print(f"    P(Gain > 50%): {prob['gain_50pct']*100:.1f}%")
        
        # Risk Limits
        limits = metrics["risk_limits"]
        if limits:
            print("\nRECOMMENDED RISK LIMITS:")
            print(f"  Max Position Size: ${limits['max_position_size']:,.0f}")
            print(f"  Daily Loss Limit: ${limits['daily_loss_limit']:,.0f}")
            print(f"  Max Drawdown: {limits['max_drawdown_limit']*100:.1f}%")
            print(f"  Max Leverage: {limits['max_leverage']:.1f}x")
        
        print("="*60)


def main():
    """Run risk backtest"""
    
    backtest = RiskBacktest()
    metrics = backtest.run_comprehensive_backtest()
    backtest.print_report(metrics)
    
    print("\nRisk assessment complete. Results saved to reports/risk_backtest.json")


if __name__ == "__main__":
    main()