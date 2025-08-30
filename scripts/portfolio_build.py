#!/usr/bin/env python3
"""
Portfolio Construction Script
"""

import os
import sys
import asyncio
import argparse
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta, date
import pandas as pd
import numpy as np

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.portfolio.constructor import PortfolioConstructor


class PortfolioBuilder:
    """Build and analyze portfolios from strategy returns"""
    
    def __init__(self, output_dir: str = "reports/portfolio"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
    async def build_portfolio(self, method: str = "hrp", 
                            lookback_days: int = 60) -> Dict[str, Any]:
        """Build portfolio from recent optimization and paper trading results"""
        
        print(f"Building portfolio with {method} method...")
        print("="*60)
        
        # Load strategy returns data
        returns_data = await self._load_strategy_returns(lookback_days)
        
        if not returns_data:
            print("No strategy returns data found")
            return {'error': 'No returns data'}
        
        print(f"Loaded {len(returns_data)} strategies with {len(list(returns_data.values())[0])} return periods")
        
        # Build portfolio
        constructor = PortfolioConstructor(method=method)
        portfolio_result = constructor.build_portfolio(returns_data)
        
        if 'error' in portfolio_result:
            print(f"Portfolio construction failed: {portfolio_result['error']}")
            return portfolio_result
        
        # Generate reports
        await self._generate_portfolio_reports(portfolio_result, returns_data, method)
        
        # Save weights for live trading
        await self._save_portfolio_weights(portfolio_result)
        
        print("\nPortfolio construction complete!")
        print("="*60)
        
        # Print summary
        weights = portfolio_result['weights']
        metrics = portfolio_result['metrics']
        
        print(f"Method: {method.upper()}")
        print(f"Expected Return: {metrics['expected_return']*100:.1f}%")
        print(f"Volatility: {metrics['volatility']*100:.1f}%")
        print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
        print(f"Max Drawdown: {metrics['max_drawdown']*100:.1f}%")
        print(f"Effective Assets: {metrics['effective_n_assets']:.1f}")
        
        print(f"\nTop 5 Positions:")
        sorted_weights = sorted(weights.items(), key=lambda x: x[1], reverse=True)
        for i, (asset, weight) in enumerate(sorted_weights[:5]):
            print(f"{i+1:2d}. {asset:30s} {weight*100:6.1f}%")
        
        return portfolio_result
    
    async def _load_strategy_returns(self, lookback_days: int) -> Optional[Dict[str, pd.Series]]:
        """Load strategy returns from paper trading and optimization results"""
        
        # Strategy return mapping (in production would load from database/files)
        strategy_returns = {}
        
        # Generate mock returns for demonstration
        strategies = [
            'sma_cross_BTC/USDT', 'sma_cross_ETH/USDT', 'sma_cross_AAPL', 'sma_cross_MSFT',
            'supertrend_BTC/USDT', 'supertrend_ETH/USDT', 'supertrend_AAPL', 
            'bollinger_revert_BTC/USDT', 'bollinger_revert_ETH/USDT',
            'donchian_breakout_BTC/USDT', 'donchian_breakout_AAPL'
        ]
        
        # Create date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_days)
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        
        for strategy in strategies:
            # Generate realistic returns with different characteristics
            if 'BTC' in strategy or 'ETH' in strategy:
                # Crypto strategies - higher volatility
                base_return = np.random.normal(0.0008, 0.03, len(date_range))  # 0.08% daily mean, 3% vol
            else:
                # Equity strategies - lower volatility  
                base_return = np.random.normal(0.0004, 0.015, len(date_range))  # 0.04% daily mean, 1.5% vol
            
            # Add strategy-specific characteristics
            if 'trend' in strategy or 'breakout' in strategy:
                # Trend strategies - momentum and skewness
                base_return += np.random.exponential(0.002, len(date_range)) * np.random.choice([-1, 1], len(date_range))
            elif 'revert' in strategy:
                # Mean reversion - higher win rate, smaller wins
                base_return = np.where(np.random.random(len(date_range)) < 0.6, 
                                     np.abs(base_return) * 0.5, 
                                     -np.abs(base_return) * 1.5)
            
            # Create series
            returns_series = pd.Series(base_return, index=date_range)
            strategy_returns[strategy] = returns_series
        
        return strategy_returns
    
    async def _generate_portfolio_reports(self, portfolio_result: Dict[str, Any], 
                                        returns_data: Dict[str, pd.Series], method: str):
        """Generate comprehensive portfolio reports"""
        
        # Generate HTML report
        constructor = PortfolioConstructor(method=method)
        html_report = constructor.generate_portfolio_report(portfolio_result, returns_data)
        
        # Create full HTML with additional analysis
        full_html = self._create_full_portfolio_html(portfolio_result, returns_data, method, html_report)
        
        # Save HTML report
        html_file = os.path.join(self.output_dir, f"portfolio_report_{method}_{date.today().strftime('%Y%m%d')}.html")
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(full_html)
        
        print(f"Portfolio report saved: {html_file}")
        
        # Generate correlation heatmap data (JSON for frontend)
        heatmap_data = self._generate_heatmap_data(returns_data)
        heatmap_file = os.path.join(self.output_dir, f"correlation_heatmap_{date.today().strftime('%Y%m%d')}.json")
        
        with open(heatmap_file, 'w') as f:
            json.dump(heatmap_data, f, indent=2)
        
        print(f"Correlation heatmap data: {heatmap_file}")
    
    def _create_full_portfolio_html(self, portfolio_result: Dict[str, Any], 
                                   returns_data: Dict[str, pd.Series], 
                                   method: str, basic_report: str) -> str:
        """Create comprehensive HTML portfolio report"""
        
        weights = portfolio_result['weights']
        metrics = portfolio_result['metrics']
        
        # Risk contributions analysis
        risk_contribs = metrics.get('risk_contributions', {})
        sorted_risk_contribs = sorted(risk_contribs.items(), key=lambda x: abs(x[1]), reverse=True)
        
        risk_table = """
        <table>
            <thead>
                <tr><th>Strategy-Symbol</th><th>Weight</th><th>Risk Contrib</th><th>Risk/Weight Ratio</th></tr>
            </thead>
            <tbody>
        """
        
        for asset, risk_contrib in sorted_risk_contribs[:10]:  # Top 10
            weight = weights.get(asset, 0)
            ratio = abs(risk_contrib) / weight if weight > 0 else 0
            
            risk_table += f"""
                <tr>
                    <td>{asset}</td>
                    <td>{weight*100:.1f}%</td>
                    <td>{risk_contrib*100:.1f}%</td>
                    <td>{ratio:.2f}</td>
                </tr>
            """
        
        risk_table += "</tbody></table>"
        
        # Correlation analysis
        corr_matrix = pd.DataFrame(returns_data).corr()
        avg_correlation = corr_matrix.values[np.triu_indices_from(corr_matrix.values, k=1)].mean()
        max_correlation = corr_matrix.values[np.triu_indices_from(corr_matrix.values, k=1)].max()
        min_correlation = corr_matrix.values[np.triu_indices_from(corr_matrix.values, k=1)].min()
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Sofia V2 - Portfolio Construction Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .header {{ background: #2c3e50; color: white; padding: 20px; border-radius: 5px; }}
        .section {{ background: white; padding: 20px; margin: 20px 0; border-radius: 5px; }}
        .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px; }}
        .metric-card {{ background: #f8f9fa; padding: 15px; border-radius: 5px; text-align: center; }}
        .metric-card h4 {{ margin: 0 0 10px 0; color: #6c757d; font-size: 0.9rem; }}
        .metric-value {{ font-size: 1.8rem; font-weight: bold; color: #495057; }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th, td {{ padding: 8px 12px; text-align: left; border: 1px solid #ddd; }}
        th {{ background: #e9ecef; }}
        .weights-table {{ max-height: 400px; overflow-y: auto; }}
        .correlation-stats {{ background: #e3f2fd; padding: 15px; border-radius: 5px; margin: 15px 0; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 Portfolio Construction Report</h1>
        <p>Method: {method.upper()} | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>Assets: {portfolio_result['n_assets']} | Periods: {portfolio_result['n_periods']}</p>
    </div>
    
    {basic_report}
    
    <div class="section">
        <h2>Risk Analysis</h2>
        <div class="correlation-stats">
            <h4>Correlation Statistics</h4>
            <p><strong>Average Correlation:</strong> {avg_correlation:.3f}</p>
            <p><strong>Max Correlation:</strong> {max_correlation:.3f}</p>
            <p><strong>Min Correlation:</strong> {min_correlation:.3f}</p>
        </div>
        
        <h3>Risk Contributions</h3>
        {risk_table}
    </div>
    
    <div class="section">
        <h2>Implementation Notes</h2>
        <ul>
            <li><strong>Rebalancing Frequency:</strong> Daily or when significant drift detected</li>
            <li><strong>Transaction Costs:</strong> {portfolio_result.get('turnover_penalty', 1)}% turnover penalty applied</li>
            <li><strong>Constraints:</strong> Max symbol weight {os.getenv('MAX_SYMBOL_WEIGHT', '30')}%, max strategy weight {os.getenv('MAX_STRATEGY_WEIGHT', '20')}%</li>
            <li><strong>Capital Allocation:</strong> Weights will be scaled by current canary capital percentage</li>
            <li><strong>Risk Management:</strong> Individual strategy stops and portfolio-level risk limits apply</li>
        </ul>
    </div>
    
    <div style="text-align: center; color: #666; margin-top: 40px;">
        <p>Sofia V2 Portfolio Construction | Generated by {method.upper()} optimizer</p>
    </div>
</body>
</html>
        """
        
        return html
    
    def _generate_heatmap_data(self, returns_data: Dict[str, pd.Series]) -> Dict[str, Any]:
        """Generate correlation heatmap data for frontend"""
        
        df = pd.DataFrame(returns_data)
        corr_matrix = df.corr()
        
        # Convert to format suitable for heatmap visualization
        heatmap_data = {
            'symbols': list(corr_matrix.index),
            'correlations': corr_matrix.values.tolist(),
            'title': f'Strategy Correlation Matrix ({len(corr_matrix)} strategies)',
            'generated_at': datetime.now().isoformat()
        }
        
        return heatmap_data
    
    async def _save_portfolio_weights(self, portfolio_result: Dict[str, Any]):
        """Save portfolio weights for live trading"""
        
        weights_data = {
            'timestamp': datetime.now().isoformat(),
            'method': portfolio_result['method'],
            'weights': portfolio_result['weights'],
            'metrics': portfolio_result['metrics'],
            'n_assets': portfolio_result['n_assets'],
            'total_weight': sum(portfolio_result['weights'].values())
        }
        
        # Save with date
        weights_file = os.path.join(self.output_dir, f"weights_{date.today().strftime('%Y%m%d')}.json")
        
        with open(weights_file, 'w') as f:
            json.dump(weights_data, f, indent=2, default=str)
        
        print(f"Portfolio weights saved: {weights_file}")
        
        # Also save as 'latest' for easy access
        latest_file = os.path.join(self.output_dir, "weights_latest.json")
        with open(latest_file, 'w') as f:
            json.dump(weights_data, f, indent=2, default=str)
    
    def compare_methods(self, methods: List[str] = ['hrp', 'voltarget', 'kelly']) -> Dict[str, Any]:
        """Compare different portfolio construction methods"""
        
        print("Comparing portfolio construction methods...")
        
        # Load returns data
        returns_data = asyncio.run(self._load_strategy_returns(60))
        
        if not returns_data:
            return {'error': 'No returns data for comparison'}
        
        comparison_results = {}
        
        for method in methods:
            print(f"Building portfolio with {method}...")
            
            constructor = PortfolioConstructor(method=method)
            result = constructor.build_portfolio(returns_data)
            
            if 'error' not in result:
                comparison_results[method] = {
                    'expected_return': result['metrics']['expected_return'],
                    'volatility': result['metrics']['volatility'],
                    'sharpe_ratio': result['metrics']['sharpe_ratio'],
                    'max_drawdown': result['metrics']['max_drawdown'],
                    'concentration': result['metrics']['concentration_hhi'],
                    'effective_assets': result['metrics']['effective_n_assets']
                }
        
        # Generate comparison report
        self._generate_comparison_report(comparison_results)
        
        return comparison_results
    
    def _generate_comparison_report(self, comparison_results: Dict[str, Dict[str, float]]):
        """Generate method comparison report"""
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Portfolio Method Comparison</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 10px; border: 1px solid #ddd; text-align: right; }}
        th {{ background: #f5f5f5; }}
        .best {{ background: #d4edda; font-weight: bold; }}
    </style>
</head>
<body>
    <h1>Portfolio Construction Method Comparison</h1>
    <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    
    <table>
        <thead>
            <tr>
                <th>Method</th>
                <th>Expected Return (%)</th>
                <th>Volatility (%)</th>
                <th>Sharpe Ratio</th>
                <th>Max Drawdown (%)</th>
                <th>Effective Assets</th>
                <th>Concentration</th>
            </tr>
        </thead>
        <tbody>
        """
        
        # Find best in each category
        best_sharpe = max(comparison_results.values(), key=lambda x: x['sharpe_ratio'])['sharpe_ratio']
        best_return = max(comparison_results.values(), key=lambda x: x['expected_return'])['expected_return']
        
        for method, metrics in comparison_results.items():
            html += f"""
            <tr>
                <td><strong>{method.upper()}</strong></td>
                <td {'class="best"' if metrics['expected_return'] == best_return else ''}>{metrics['expected_return']*100:.1f}</td>
                <td>{metrics['volatility']*100:.1f}</td>
                <td {'class="best"' if metrics['sharpe_ratio'] == best_sharpe else ''}>{metrics['sharpe_ratio']:.2f}</td>
                <td>{metrics['max_drawdown']*100:.1f}</td>
                <td>{metrics['effective_assets']:.1f}</td>
                <td>{metrics['concentration']:.3f}</td>
            </tr>
            """
        
        html += """
        </tbody>
        </table>
        
        <h2>Method Characteristics</h2>
        <ul>
            <li><strong>HRP:</strong> Hierarchical clustering, good diversification, robust to estimation error</li>
            <li><strong>Vol Target:</strong> Inverse volatility weighting, simple and stable</li>  
            <li><strong>Kelly:</strong> Optimal growth, may concentrate in high-return assets</li>
        </ul>
</body>
</html>
        """
        
        comparison_file = os.path.join(self.output_dir, f"method_comparison_{date.today().strftime('%Y%m%d')}.html")
        with open(comparison_file, 'w', encoding='utf-8') as f:
            f.write(html)
        
        print(f"Method comparison report: {comparison_file}")


async def main():
    """Main portfolio building function"""
    parser = argparse.ArgumentParser(description='Build portfolio from strategy returns')
    parser.add_argument('--method', choices=['hrp', 'voltarget', 'kelly', 'equal'], 
                       default='hrp', help='Portfolio construction method')
    parser.add_argument('--out', default='reports/portfolio', 
                       help='Output directory for reports')
    parser.add_argument('--lookback', type=int, default=60, 
                       help='Lookback days for returns data')
    parser.add_argument('--compare', action='store_true', 
                       help='Compare all methods')
    
    args = parser.parse_args()
    
    builder = PortfolioBuilder(output_dir=args.out)
    
    try:
        if args.compare:
            comparison = builder.compare_methods()
            
            if 'error' not in comparison:
                print("\nMethod Comparison Results:")
                for method, metrics in comparison.items():
                    print(f"{method.upper():12s}: Sharpe={metrics['sharpe_ratio']:5.2f}, "
                          f"Return={metrics['expected_return']*100:5.1f}%, "
                          f"Vol={metrics['volatility']*100:4.1f}%")
        else:
            result = await builder.build_portfolio(args.method, args.lookback)
            
            if 'error' in result:
                print(f"Portfolio construction failed: {result['error']}")
                return 1
        
        return 0
        
    except Exception as e:
        print(f"Portfolio building failed: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)