#!/usr/bin/env python3
"""
Generate Morning Summary Report
"""

import asyncio
import json
import os
import sys
from datetime import date, datetime, timedelta
from typing import Any, Dict, List

import numpy as np

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import only if available - graceful degradation
try:
    from src.paper.parallel_runner import ParallelPaperRunner
except ImportError:
    ParallelPaperRunner = None

try:
    from src.optimization.runner import StrategyOptimizer
except ImportError:
    StrategyOptimizer = None

try:
    from src.ai.news_sentiment import NewsSentimentAnalyzer
except ImportError:
    NewsSentimentAnalyzer = None


class MorningReportGenerator:
    """Generate comprehensive morning summary report"""

    def __init__(self):
        self.report_date = date.today()
        self.report_dir = f"reports/nightly/summary_{self.report_date.strftime('%Y%m%d')}"
        os.makedirs(self.report_dir, exist_ok=True)

    async def generate_report(self) -> str:
        """Generate complete morning report"""
        print("Generating Morning Report...")
        print("=" * 60)

        # Collect all data
        paper_data = await self._collect_paper_trading_data()
        optimizer_data = self._collect_optimizer_data()
        news_data = await self._collect_news_sentiment_data()
        system_data = self._collect_system_metrics()

        # Generate report sections
        summary = self._generate_executive_summary(paper_data, optimizer_data, news_data)
        paper_section = self._generate_paper_trading_section(paper_data)
        optimizer_section = self._generate_optimizer_section(optimizer_data)
        news_section = self._generate_news_section(news_data)
        system_section = self._generate_system_section(system_data)
        recommendations = self._generate_recommendations(paper_data, optimizer_data, news_data)

        # Create HTML report
        html_report = self._create_html_report(
            summary, paper_section, optimizer_section, news_section, system_section, recommendations
        )

        # Save reports
        html_file = os.path.join(self.report_dir, "morning_summary.html")
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(html_report)

        # Create JSON data export
        json_data = {
            "date": self.report_date.isoformat(),
            "generated_at": datetime.now().isoformat(),
            "paper_trading": paper_data,
            "optimization": optimizer_data,
            "news_sentiment": news_data,
            "system_metrics": system_data,
            "executive_summary": summary,
        }

        json_file = os.path.join(self.report_dir, "morning_data.json")
        with open(json_file, "w") as f:
            json.dump(json_data, f, indent=2, default=str)

        print(f"\nMorning report generated: {html_file}")
        print(f"Data export saved: {json_file}")

        return html_file

    async def _collect_paper_trading_data(self) -> Dict[str, Any]:
        """Collect paper trading performance data"""
        try:
            # Check if paper runner is active (in production would connect to running instance)
            paper_state = self._get_mock_paper_state()

            # Get divergence reports from overnight
            divergence_reports = self._collect_divergence_reports()

            return {
                "current_state": paper_state,
                "divergence_reports": divergence_reports,
                "overnight_performance": self._calculate_overnight_performance(paper_state),
                "risk_violations": self._check_risk_violations(paper_state),
            }
        except Exception as e:
            print(f"Failed to collect paper trading data: {e}")
            return {"error": str(e)}

    def _collect_optimizer_data(self) -> Dict[str, Any]:
        """Collect optimization results from last run"""
        try:
            # Find latest optimization results
            optimizer_dir = "reports/optimizer"
            if not os.path.exists(optimizer_dir):
                return {"error": "No optimization results found"}

            subdirs = [
                d
                for d in os.listdir(optimizer_dir)
                if os.path.isdir(os.path.join(optimizer_dir, d))
            ]

            if not subdirs:
                return {"error": "No optimization results found"}

            latest_dir = sorted(subdirs)[-1]
            results_file = os.path.join(optimizer_dir, latest_dir, "optimization_results.json")

            if os.path.exists(results_file):
                with open(results_file) as f:
                    results = json.load(f)

                # Analyze results
                analysis = self._analyze_optimization_results(results)

                return {
                    "results": results,
                    "analysis": analysis,
                    "latest_run": latest_dir,
                    "run_date": latest_dir[:8] if len(latest_dir) >= 8 else "unknown",
                }
            else:
                return {"error": "Optimization results file not found"}

        except Exception as e:
            print(f"Failed to collect optimizer data: {e}")
            return {"error": str(e)}

    async def _collect_news_sentiment_data(self) -> Dict[str, Any]:
        """Collect news sentiment analysis data"""
        try:
            if NewsSentimentAnalyzer is None:
                return {"error": "News sentiment analysis not available"}

            analyzer = NewsSentimentAnalyzer()

            if not analyzer.enabled:
                return {"error": "News sentiment analysis disabled"}

            symbols = ["BTC/USDT", "ETH/USDT", "AAPL", "MSFT"]
            sentiment_data = {}

            for symbol in symbols:
                summary = await analyzer.get_sentiment_summary(symbol)
                if summary:
                    sentiment_data[symbol] = summary

            # Analyze sentiment trends
            trends = self._analyze_sentiment_trends(sentiment_data)

            return {
                "symbol_sentiments": sentiment_data,
                "trends": trends,
                "market_overview": self._generate_sentiment_market_overview(sentiment_data),
            }

        except Exception as e:
            print(f"Failed to collect news sentiment data: {e}")
            return {"error": str(e)}

    def _collect_system_metrics(self) -> Dict[str, Any]:
        """Collect system performance metrics"""
        try:
            # Mock system metrics - in production would collect from Prometheus/monitoring
            return {
                "uptime_hours": 24,
                "cpu_usage_avg": 45.2,
                "memory_usage_avg": 68.7,
                "disk_usage_pct": 23.4,
                "api_response_time_ms": 125,
                "websocket_connections": 12,
                "data_feed_status": "healthy",
                "error_rate_pct": 0.02,
                "last_restart": (datetime.now() - timedelta(hours=24)).isoformat(),
            }
        except Exception as e:
            print(f"Failed to collect system metrics: {e}")
            return {"error": str(e)}

    def _get_mock_paper_state(self) -> Dict[str, Any]:
        """Get mock paper trading state"""
        # In production, this would connect to actual paper runner
        return {
            "total_pnl": 156.78,
            "daily_pnl": 23.45,
            "total_trades": 42,
            "win_rate": 67.3,
            "positions_count": 3,
            "strategies_running": 8,
            "total_strategies": 12,
            "k_factor": 0.75,
            "kill_switch_active": False,
            "gate_violations": 1,
            "running": True,
            "strategy_breakdown": {
                "supertrend_BTC/USDT": {"total_pnl": 89.23, "win_rate": 72.1, "trades": 8},
                "bollinger_revert_ETH/USDT": {"total_pnl": 45.67, "win_rate": 63.4, "trades": 11},
                "donchian_breakout_AAPL": {"total_pnl": 21.88, "win_rate": 58.7, "trades": 7},
            },
        }

    def _collect_divergence_reports(self) -> List[Dict[str, Any]]:
        """Collect overnight divergence reports"""
        divergence_dir = "reports/paper/divergence"
        if not os.path.exists(divergence_dir):
            return []

        reports = []
        yesterday = date.today() - timedelta(days=1)

        for filename in os.listdir(divergence_dir):
            if filename.startswith(f"divergence_{yesterday.strftime('%Y%m%d')}"):
                filepath = os.path.join(divergence_dir, filename)
                try:
                    with open(filepath) as f:
                        report = json.load(f)
                        reports.append(report)
                except Exception as e:
                    print(f"Failed to load divergence report {filename}: {e}")

        return sorted(reports, key=lambda x: x.get("timestamp", ""))

    def _calculate_overnight_performance(self, paper_state: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overnight performance metrics"""
        if "error" in paper_state:
            return {"error": "No paper trading data"}

        # Mock calculation - would compare with previous day's close
        return {
            "pnl_change": paper_state.get("daily_pnl", 0),
            "trades_overnight": paper_state.get("total_trades", 0),
            "new_positions": paper_state.get("positions_count", 0),
            "performance_vs_expected": "outperforming",  # Mock
            "risk_adjusted_return": 8.7,  # Mock Sharpe-like metric
        }

    def _check_risk_violations(self, paper_state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check for risk violations"""
        violations = []

        if paper_state.get("gate_violations", 0) > 0:
            violations.append(
                {
                    "type": "gate_violation",
                    "severity": "medium",
                    "message": f"{paper_state['gate_violations']} strategy gate violations detected",
                }
            )

        if paper_state.get("kill_switch_active", False):
            violations.append(
                {"type": "kill_switch", "severity": "high", "message": "Kill switch is active"}
            )

        daily_pnl = paper_state.get("daily_pnl", 0)
        if daily_pnl < -100:  # Mock threshold
            violations.append(
                {
                    "type": "daily_loss",
                    "severity": "high",
                    "message": f"Daily loss exceeds threshold: ${daily_pnl:.2f}",
                }
            )

        return violations

    def _analyze_optimization_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze optimization results"""
        if not results:
            return {"error": "No results to analyze"}

        all_results = []
        for symbol, symbol_results in results.items():
            for result in symbol_results:
                result["symbol"] = symbol
                all_results.append(result)

        if not all_results:
            return {"total_strategies": 0, "profitable_count": 0}

        # Calculate summary statistics
        profitable_count = sum(1 for r in all_results if r.get("profitable", False))

        sharpe_ratios = [r["oos_metrics"].get("sharpe", 0) for r in all_results]
        mar_ratios = [r["oos_metrics"].get("mar", 0) for r in all_results]

        # Top performers
        top_performers = sorted(
            all_results, key=lambda x: x["oos_metrics"].get("sharpe", 0), reverse=True
        )[:5]

        return {
            "total_strategies": len(all_results),
            "profitable_count": profitable_count,
            "success_rate": profitable_count / len(all_results) * 100,
            "avg_sharpe": np.mean(sharpe_ratios),
            "avg_mar": np.mean(mar_ratios),
            "top_performers": [
                {
                    "strategy": r["strategy_name"],
                    "symbol": r["symbol"],
                    "sharpe": r["oos_metrics"].get("sharpe", 0),
                    "mar": r["oos_metrics"].get("mar", 0),
                }
                for r in top_performers
            ],
        }

    def _analyze_sentiment_trends(self, sentiment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze sentiment trends"""
        if not sentiment_data:
            return {"error": "No sentiment data"}

        # Calculate market-wide sentiment
        sentiments_1h = [data["sentiment_1h"] for data in sentiment_data.values()]
        sentiments_24h = [data["sentiment_24h"] for data in sentiment_data.values()]

        market_sentiment_1h = np.mean(sentiments_1h) if sentiments_1h else 0
        market_sentiment_24h = np.mean(sentiments_24h) if sentiments_24h else 0

        sentiment_momentum = market_sentiment_1h - market_sentiment_24h

        # Identify sentiment leaders
        sentiment_leaders = sorted(
            sentiment_data.items(), key=lambda x: abs(x[1]["sentiment_1h"]), reverse=True
        )

        return {
            "market_sentiment_1h": market_sentiment_1h,
            "market_sentiment_24h": market_sentiment_24h,
            "sentiment_momentum": sentiment_momentum,
            "trend_direction": (
                "bullish"
                if sentiment_momentum > 0.1
                else "bearish"
                if sentiment_momentum < -0.1
                else "neutral"
            ),
            "sentiment_leaders": [
                {"symbol": symbol, "sentiment": data["sentiment_1h"]}
                for symbol, data in sentiment_leaders[:3]
            ],
        }

    def _generate_sentiment_market_overview(self, sentiment_data: Dict[str, Any]) -> str:
        """Generate market sentiment overview"""
        if not sentiment_data:
            return "No sentiment data available"

        positive_symbols = [
            symbol for symbol, data in sentiment_data.items() if data["sentiment_1h"] > 0.2
        ]
        negative_symbols = [
            symbol for symbol, data in sentiment_data.items() if data["sentiment_1h"] < -0.2
        ]

        overview = f"Market sentiment overview: {len(positive_symbols)} symbols showing positive sentiment, "
        overview += f"{len(negative_symbols)} showing negative sentiment. "

        if positive_symbols:
            overview += f"Most positive: {positive_symbols[0]}. "
        if negative_symbols:
            overview += f"Most negative: {negative_symbols[0]}."

        return overview

    def _generate_executive_summary(
        self, paper_data: Dict, optimizer_data: Dict, news_data: Dict
    ) -> Dict[str, Any]:
        """Generate executive summary"""
        summary = {
            "date": self.report_date.isoformat(),
            "overall_status": "healthy",
            "key_metrics": {},
            "highlights": [],
            "concerns": [],
        }

        # Paper trading status
        if "error" not in paper_data:
            state = paper_data["current_state"]
            summary["key_metrics"]["paper_pnl"] = state.get("total_pnl", 0)
            summary["key_metrics"]["paper_trades"] = state.get("total_trades", 0)
            summary["key_metrics"]["win_rate"] = state.get("win_rate", 0)

            if state.get("total_pnl", 0) > 0:
                summary["highlights"].append(f"Paper trading profitable: ${state['total_pnl']:.2f}")
            else:
                summary["concerns"].append(f"Paper trading losses: ${state['total_pnl']:.2f}")

        # Optimization results
        if "error" not in optimizer_data:
            analysis = optimizer_data["analysis"]
            summary["key_metrics"]["optimization_success_rate"] = analysis.get("success_rate", 0)
            summary["key_metrics"]["avg_sharpe"] = analysis.get("avg_sharpe", 0)

            if analysis.get("success_rate", 0) > 60:
                summary["highlights"].append(
                    f"Optimization success rate: {analysis['success_rate']:.1f}%"
                )
            else:
                summary["concerns"].append(
                    f"Low optimization success rate: {analysis['success_rate']:.1f}%"
                )

        # News sentiment
        if "error" not in news_data:
            trends = news_data["trends"]
            summary["key_metrics"]["market_sentiment"] = trends.get("market_sentiment_1h", 0)

            if trends.get("trend_direction") == "bullish":
                summary["highlights"].append("Bullish market sentiment detected")
            elif trends.get("trend_direction") == "bearish":
                summary["concerns"].append("Bearish market sentiment detected")

        return summary

    def _generate_paper_trading_section(self, paper_data: Dict) -> str:
        """Generate paper trading section HTML"""
        if "error" in paper_data:
            return f"<p class='error'>Error: {paper_data['error']}</p>"

        state = paper_data["current_state"]
        overnight = paper_data["overnight_performance"]
        violations = paper_data["risk_violations"]

        html = f"""
        <div class="metric-row">
            <div class="metric-card {'positive' if state.get('total_pnl', 0) >= 0 else 'negative'}">
                <h4>Total P&L</h4>
                <div class="metric-value">${state.get('total_pnl', 0):.2f}</div>
            </div>
            <div class="metric-card">
                <h4>Win Rate</h4>
                <div class="metric-value">{state.get('win_rate', 0):.1f}%</div>
            </div>
            <div class="metric-card">
                <h4>Total Trades</h4>
                <div class="metric-value">{state.get('total_trades', 0)}</div>
            </div>
            <div class="metric-card">
                <h4>Active Strategies</h4>
                <div class="metric-value">{state.get('strategies_running', 0)}/{state.get('total_strategies', 0)}</div>
            </div>
        </div>

        <h4>Strategy Breakdown</h4>
        <table>
            <thead>
                <tr><th>Strategy</th><th>P&L</th><th>Win Rate</th><th>Trades</th></tr>
            </thead>
            <tbody>
        """

        for strategy, data in state.get("strategy_breakdown", {}).items():
            pnl_class = "positive" if data.get("total_pnl", 0) >= 0 else "negative"
            html += f"""
                <tr>
                    <td>{strategy}</td>
                    <td class="{pnl_class}">${data.get('total_pnl', 0):.2f}</td>
                    <td>{data.get('win_rate', 0):.1f}%</td>
                    <td>{data.get('trades', 0)}</td>
                </tr>
            """

        html += "</tbody></table>"

        if violations:
            html += "<h4>Risk Violations</h4><ul>"
            for violation in violations:
                severity_class = violation["severity"]
                html += f"<li class='{severity_class}'><strong>{violation['type'].title()}:</strong> {violation['message']}</li>"
            html += "</ul>"

        return html

    def _generate_optimizer_section(self, optimizer_data: Dict) -> str:
        """Generate optimization section HTML"""
        if "error" in optimizer_data:
            return f"<p class='error'>Error: {optimizer_data['error']}</p>"

        analysis = optimizer_data["analysis"]

        html = f"""
        <div class="metric-row">
            <div class="metric-card">
                <h4>Success Rate</h4>
                <div class="metric-value">{analysis.get('success_rate', 0):.1f}%</div>
            </div>
            <div class="metric-card">
                <h4>Avg Sharpe</h4>
                <div class="metric-value">{analysis.get('avg_sharpe', 0):.2f}</div>
            </div>
            <div class="metric-card">
                <h4>Avg MAR</h4>
                <div class="metric-value">{analysis.get('avg_mar', 0):.2f}</div>
            </div>
            <div class="metric-card">
                <h4>Strategies Tested</h4>
                <div class="metric-value">{analysis.get('total_strategies', 0)}</div>
            </div>
        </div>

        <h4>Top Performers</h4>
        <table>
            <thead>
                <tr><th>Strategy</th><th>Symbol</th><th>Sharpe</th><th>MAR</th></tr>
            </thead>
            <tbody>
        """

        for performer in analysis.get("top_performers", []):
            html += f"""
                <tr>
                    <td>{performer['strategy']}</td>
                    <td>{performer['symbol']}</td>
                    <td>{performer['sharpe']:.2f}</td>
                    <td>{performer['mar']:.2f}</td>
                </tr>
            """

        html += "</tbody></table>"
        return html

    def _generate_news_section(self, news_data: Dict) -> str:
        """Generate news sentiment section HTML"""
        if "error" in news_data:
            return f"<p class='error'>Error: {news_data['error']}</p>"

        trends = news_data["trends"]

        html = f"""
        <div class="metric-row">
            <div class="metric-card">
                <h4>Market Sentiment (1H)</h4>
                <div class="metric-value {'positive' if trends.get('market_sentiment_1h', 0) >= 0 else 'negative'}">
                    {trends.get('market_sentiment_1h', 0):.2f}
                </div>
            </div>
            <div class="metric-card">
                <h4>Sentiment Momentum</h4>
                <div class="metric-value {'positive' if trends.get('sentiment_momentum', 0) >= 0 else 'negative'}">
                    {trends.get('sentiment_momentum', 0):.2f}
                </div>
            </div>
            <div class="metric-card">
                <h4>Trend Direction</h4>
                <div class="metric-value">{trends.get('trend_direction', 'neutral').title()}</div>
            </div>
            <div class="metric-card">
                <h4>Symbols Tracked</h4>
                <div class="metric-value">{len(news_data.get('symbol_sentiments', {}))}</div>
            </div>
        </div>

        <h4>Symbol Sentiment Overview</h4>
        <table>
            <thead>
                <tr><th>Symbol</th><th>1H Sentiment</th><th>24H Sentiment</th><th>Volume (24H)</th><th>Strategy Bias</th></tr>
            </thead>
            <tbody>
        """

        for symbol, data in news_data.get("symbol_sentiments", {}).items():
            sentiment_1h_class = "positive" if data["sentiment_1h"] >= 0 else "negative"
            html += f"""
                <tr>
                    <td>{symbol}</td>
                    <td class="{sentiment_1h_class}">{data['sentiment_1h']:.2f}</td>
                    <td>{data['sentiment_24h']:.2f}</td>
                    <td>{data['volume_24h']}</td>
                    <td>{data['strategy_overlay'].get('strategy_bias', 'neutral')}</td>
                </tr>
            """

        html += "</tbody></table>"
        return html

    def _generate_system_section(self, system_data: Dict) -> str:
        """Generate system metrics section HTML"""
        if "error" in system_data:
            return f"<p class='error'>Error: {system_data['error']}</p>"

        html = f"""
        <div class="metric-row">
            <div class="metric-card">
                <h4>Uptime</h4>
                <div class="metric-value">{system_data.get('uptime_hours', 0):.1f}h</div>
            </div>
            <div class="metric-card">
                <h4>CPU Usage</h4>
                <div class="metric-value">{system_data.get('cpu_usage_avg', 0):.1f}%</div>
            </div>
            <div class="metric-card">
                <h4>Memory Usage</h4>
                <div class="metric-value">{system_data.get('memory_usage_avg', 0):.1f}%</div>
            </div>
            <div class="metric-card">
                <h4>Error Rate</h4>
                <div class="metric-value">{system_data.get('error_rate_pct', 0):.3f}%</div>
            </div>
        </div>

        <div class="status-indicators">
            <div class="status-item">
                <span class="status-label">Data Feed:</span>
                <span class="status-value {'healthy' if system_data.get('data_feed_status') == 'healthy' else 'error'}">
                    {system_data.get('data_feed_status', 'unknown').title()}
                </span>
            </div>
            <div class="status-item">
                <span class="status-label">API Response Time:</span>
                <span class="status-value">{system_data.get('api_response_time_ms', 0)}ms</span>
            </div>
        </div>
        """
        return html

    def _generate_recommendations(
        self, paper_data: Dict, optimizer_data: Dict, news_data: Dict
    ) -> str:
        """Generate recommendations section"""
        recommendations = []

        # Paper trading recommendations
        if "error" not in paper_data:
            state = paper_data["current_state"]
            if state.get("total_pnl", 0) < 0:
                recommendations.append(
                    "📉 Consider reducing K-factor or reviewing strategy parameters due to negative P&L"
                )

            if state.get("win_rate", 0) < 50:
                recommendations.append(
                    "📊 Win rate below 50% - review signal quality and entry/exit criteria"
                )

            if paper_data.get("risk_violations"):
                recommendations.append("⚠️ Address risk violations before increasing position sizes")

        # Optimization recommendations
        if "error" not in optimizer_data:
            analysis = optimizer_data["analysis"]
            if analysis.get("success_rate", 0) < 50:
                recommendations.append(
                    "🔄 Low optimization success rate - consider expanding parameter ranges or adding new strategies"
                )

            if analysis.get("avg_sharpe", 0) < 1.0:
                recommendations.append(
                    "📈 Average Sharpe ratio below 1.0 - focus on risk-adjusted performance"
                )

        # News sentiment recommendations
        if "error" not in news_data:
            trends = news_data["trends"]
            if trends.get("trend_direction") == "bearish":
                recommendations.append(
                    "🐻 Bearish sentiment detected - consider defensive positioning or mean-reversion strategies"
                )
            elif trends.get("trend_direction") == "bullish":
                recommendations.append(
                    "🐂 Bullish sentiment detected - consider trend-following strategies"
                )

        if not recommendations:
            recommendations.append(
                "✅ All systems operating normally - continue current strategy allocation"
            )

        html = "<ul>"
        for rec in recommendations:
            html += f"<li>{rec}</li>"
        html += "</ul>"

        return html

    def _create_html_report(
        self,
        summary: Dict,
        paper_section: str,
        optimizer_section: str,
        news_section: str,
        system_section: str,
        recommendations: str,
    ) -> str:
        """Create complete HTML report"""

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Sofia V2 - Morning Report {self.report_date}</title>
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; margin: 0; background: #f5f7fa; color: #333; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 2rem; }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 2rem; }}
        .section {{ background: white; margin: 2rem 0; padding: 2rem; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .metric-row {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin: 1rem 0; }}
        .metric-card {{ background: #f8f9fa; padding: 1rem; border-radius: 6px; text-align: center; }}
        .metric-card h4 {{ margin: 0 0 0.5rem 0; color: #6c757d; font-size: 0.9rem; text-transform: uppercase; }}
        .metric-value {{ font-size: 1.8rem; font-weight: bold; color: #495057; }}
        .positive {{ color: #28a745; }}
        .negative {{ color: #dc3545; }}
        .error {{ color: #dc3545; background: #f8d7da; padding: 1rem; border-radius: 4px; }}
        .healthy {{ color: #28a745; }}
        table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; }}
        th, td {{ padding: 0.75rem; text-align: left; border-bottom: 1px solid #dee2e6; }}
        th {{ background: #e9ecef; font-weight: 600; }}
        .status-indicators {{ margin: 1rem 0; }}
        .status-item {{ margin: 0.5rem 0; }}
        .status-label {{ font-weight: 600; }}
        .status-value {{ margin-left: 0.5rem; }}
        .highlights {{ background: #d4edda; padding: 1rem; border-left: 4px solid #28a745; margin: 1rem 0; }}
        .concerns {{ background: #f8d7da; padding: 1rem; border-left: 4px solid #dc3545; margin: 1rem 0; }}
        ul {{ padding-left: 1.5rem; }}
        .high {{ color: #dc3545; }}
        .medium {{ color: #ffc107; }}
        .footer {{ text-align: center; color: #6c757d; margin-top: 2rem; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🌅 Sofia V2 - Morning Report</h1>
        <p>{self.report_date.strftime('%A, %B %d, %Y')} | Generated at {datetime.now().strftime('%H:%M:%S UTC')}</p>
    </div>

    <div class="container">
        <!-- Executive Summary -->
        <div class="section">
            <h2>📊 Executive Summary</h2>

            <div class="metric-row">
                <div class="metric-card">
                    <h4>Paper P&L</h4>
                    <div class="metric-value {'positive' if summary['key_metrics'].get('paper_pnl', 0) >= 0 else 'negative'}">
                        ${summary['key_metrics'].get('paper_pnl', 0):.2f}
                    </div>
                </div>
                <div class="metric-card">
                    <h4>Win Rate</h4>
                    <div class="metric-value">{summary['key_metrics'].get('win_rate', 0):.1f}%</div>
                </div>
                <div class="metric-card">
                    <h4>Optimization Success</h4>
                    <div class="metric-value">{summary['key_metrics'].get('optimization_success_rate', 0):.1f}%</div>
                </div>
                <div class="metric-card">
                    <h4>Market Sentiment</h4>
                    <div class="metric-value {'positive' if summary['key_metrics'].get('market_sentiment', 0) >= 0 else 'negative'}">
                        {summary['key_metrics'].get('market_sentiment', 0):.2f}
                    </div>
                </div>
            </div>

            {f'<div class="highlights"><h4>✅ Highlights</h4><ul>{"".join(f"<li>{h}</li>" for h in summary["highlights"])}</ul></div>' if summary.get('highlights') else ''}
            {f'<div class="concerns"><h4>⚠️ Concerns</h4><ul>{"".join(f"<li>{c}</li>" for c in summary["concerns"])}</ul></div>' if summary.get('concerns') else ''}
        </div>

        <!-- Paper Trading Performance -->
        <div class="section">
            <h2>📈 Paper Trading Performance</h2>
            {paper_section}
        </div>

        <!-- Optimization Results -->
        <div class="section">
            <h2>🔬 Strategy Optimization</h2>
            {optimizer_section}
        </div>

        <!-- News Sentiment Analysis -->
        <div class="section">
            <h2>📰 News Sentiment Analysis</h2>
            {news_section}
        </div>

        <!-- System Health -->
        <div class="section">
            <h2>⚙️ System Health</h2>
            {system_section}
        </div>

        <!-- Recommendations -->
        <div class="section">
            <h2>💡 Recommendations</h2>
            {recommendations}
        </div>
    </div>

    <div class="footer">
        <p>Generated by Sofia V2 Cloud Overnight Optimizer | {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
    </div>
</body>
</html>
        """

        return html


async def main():
    """Generate morning report"""
    generator = MorningReportGenerator()

    try:
        report_path = await generator.generate_report()
        print("\n🎉 Morning report complete!")
        print(f"📄 View report: {report_path}")

        # Print summary to console
        print("\n" + "=" * 60)
        print("QUICK SUMMARY")
        print("=" * 60)
        # Would print key metrics here

    except Exception as e:
        print(f"Failed to generate morning report: {e}")
        return 1

    return 0


if __name__ == "__main__":
    import asyncio

    exit_code = asyncio.run(main())
    exit(exit_code)
