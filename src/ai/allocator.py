"""
Capital Allocator with Alpha Scoring
Allocates paper capital based on strategy performance
"""

import json
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


class AlphaAllocator:
    """Allocate capital based on alpha scores"""
    
    def __init__(self):
        # Weights for alpha calculation
        self.weights = {
            'sharpe': 0.3,
            'win_rate': 0.25,
            'fill_quality': 0.2,
            'latency': -0.15,
            'drawdown': -0.1
        }
        
        # Allocation constraints
        self.constraints = {
            'grid': {'min': 0.2, 'max': 0.4},
            'arbitrage': {'min': 0.6, 'max': 0.8}
        }
        
    def calculate_sharpe(self, returns: List[float]) -> float:
        """Calculate Sharpe ratio"""
        if not returns or len(returns) < 2:
            return 0
        
        returns_array = np.array(returns)
        mean_return = np.mean(returns_array)
        std_return = np.std(returns_array)
        
        if std_return == 0:
            return 0
        
        # Annualized Sharpe (assuming daily returns)
        return (mean_return / std_return) * np.sqrt(252)
    
    def calculate_alpha_score(self, metrics: Dict) -> float:
        """Calculate alpha score for a strategy"""
        score = 0
        
        # Sharpe ratio component
        if 'returns' in metrics:
            sharpe = self.calculate_sharpe(metrics['returns'])
            score += self.weights['sharpe'] * min(sharpe, 3)  # Cap at 3
        
        # Win rate component
        if 'win_rate' in metrics:
            win_rate = metrics['win_rate'] / 100  # Convert to 0-1
            score += self.weights['win_rate'] * win_rate
        
        # Fill quality component
        if 'maker_fill_rate' in metrics:
            fill_quality = metrics['maker_fill_rate'] / 100
            score += self.weights['fill_quality'] * fill_quality
        
        # Latency penalty
        if 'avg_latency_ms' in metrics:
            latency_normalized = min(metrics['avg_latency_ms'] / 1000, 1)  # Normalize to 0-1
            score += self.weights['latency'] * latency_normalized
        
        # Drawdown penalty
        if 'max_dd_pct' in metrics:
            dd_normalized = abs(metrics['max_dd_pct']) / 10  # Normalize (10% = 1.0)
            score += self.weights['drawdown'] * min(dd_normalized, 1)
        
        return max(0, score)  # Ensure non-negative
    
    def softmax(self, scores: Dict[str, float]) -> Dict[str, float]:
        """Apply softmax to convert scores to probabilities"""
        if not scores:
            return {}
        
        # Convert to numpy array
        names = list(scores.keys())
        values = np.array(list(scores.values()))
        
        # Apply softmax
        exp_values = np.exp(values - np.max(values))  # Subtract max for numerical stability
        softmax_values = exp_values / exp_values.sum()
        
        return dict(zip(names, softmax_values))
    
    def apply_constraints(self, weights: Dict[str, float]) -> Dict[str, float]:
        """Apply min/max constraints to allocations"""
        constrained = {}
        
        for strategy, weight in weights.items():
            if strategy in self.constraints:
                min_weight = self.constraints[strategy]['min']
                max_weight = self.constraints[strategy]['max']
                constrained[strategy] = np.clip(weight, min_weight, max_weight)
            else:
                constrained[strategy] = weight
        
        # Renormalize to sum to 1
        total = sum(constrained.values())
        if total > 0:
            for strategy in constrained:
                constrained[strategy] /= total
        
        return constrained
    
    def load_metrics(self) -> Dict:
        """Load metrics from various sources"""
        metrics = {}
        
        # Load daily scores
        daily_score_file = Path("reports/daily_score.json")
        if daily_score_file.exists():
            with open(daily_score_file, 'r') as f:
                daily_score = json.load(f)
                
                # Extract grid metrics
                if 'grid' in daily_score:
                    metrics['grid'] = {
                        'win_rate': daily_score['grid'].get('win_rate', 50),
                        'maker_fill_rate': daily_score['grid'].get('maker_fill_rate', 0),
                        'returns': [daily_score['grid'].get('pnl_pct', 0)]
                    }
                
                # Extract arbitrage metrics
                if 'arb' in daily_score:
                    metrics['arbitrage'] = {
                        'win_rate': daily_score['arb'].get('success_rate', 0),
                        'avg_latency_ms': daily_score['arb'].get('avg_latency_ms', 1000),
                        'returns': [daily_score['arb'].get('pnl_tl', 0) / 1000]  # Normalize TL to %
                    }
                
                # Extract risk metrics
                if 'risk' in daily_score:
                    for strategy in ['grid', 'arbitrage']:
                        if strategy in metrics:
                            metrics[strategy]['max_dd_pct'] = daily_score['risk'].get('max_dd_pct', 0)
        
        # Load strategy lab results
        for strategy in ['grid', 'turkish_arbitrage', 'grid_monster']:
            result_file = Path(f"logs/{strategy}_last_run.json")
            if result_file.exists():
                with open(result_file, 'r') as f:
                    result = json.load(f)
                    
                    strategy_key = 'arbitrage' if strategy == 'turkish_arbitrage' else strategy
                    if strategy_key not in metrics:
                        metrics[strategy_key] = {}
                    
                    metrics[strategy_key].update(result.get('metrics', {}))
        
        return metrics
    
    def calculate_allocations(self) -> Dict:
        """Calculate capital allocations"""
        # Load metrics
        metrics = self.load_metrics()
        
        if not metrics:
            # Default allocations
            return {
                'grid': 0.4,
                'arbitrage': 0.6
            }
        
        # Calculate alpha scores
        alpha_scores = {}
        for strategy, strategy_metrics in metrics.items():
            alpha_scores[strategy] = self.calculate_alpha_score(strategy_metrics)
        
        # Apply softmax
        raw_weights = self.softmax(alpha_scores)
        
        # Apply constraints
        final_weights = self.apply_constraints(raw_weights)
        
        # Prepare output
        output = {
            'timestamp': datetime.now().isoformat(),
            'alpha_scores': alpha_scores,
            'raw_weights': raw_weights,
            'final_weights': final_weights,
            'metrics_used': metrics
        }
        
        # Save to file
        output_file = Path("logs/allocator_weights.json")
        output_file.parent.mkdir(exist_ok=True)
        
        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2)
        
        logger.info(f"Allocator weights saved: {final_weights}")
        
        return output


def main():
    """Run allocator"""
    allocator = AlphaAllocator()
    result = allocator.calculate_allocations()
    
    print("=" * 60)
    print("ALPHA ALLOCATOR RESULTS")
    print("=" * 60)
    
    print("\nAlpha Scores:")
    for strategy, score in result['alpha_scores'].items():
        print(f"  {strategy}: {score:.3f}")
    
    print("\nFinal Weights:")
    for strategy, weight in result['final_weights'].items():
        print(f"  {strategy}: {weight:.1%}")
    
    print("\nSaved to: logs/allocator_weights.json")
    print("=" * 60)


if __name__ == "__main__":
    main()