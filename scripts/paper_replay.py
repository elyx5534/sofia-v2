"""
Paper Trading Replay - Quick Profitability Check
"""

import os
import sys
import asyncio
import logging
from typing import Dict, Any, List
from decimal import Decimal
from datetime import datetime, timedelta
import json
import pandas as pd
import ccxt
import yfinance as yf

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.paper.signal_hub import SignalHub
from src.reports.paper_report import PaperTradingReport

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PaperReplay:
    """Accelerated paper trading simulation for quick profitability check"""
    
    def __init__(self, hours: int = 24):
        self.hours = hours
        self.signal_hub = SignalHub()
        
        # Replay state
        self.balance = Decimal('10000')
        self.positions = {}
        self.trades = []
        self.pnl = Decimal('0')
        
        # Symbols to test
        self.crypto_symbols = ['BTC/USDT', 'ETH/USDT']
        self.equity_symbols = ['AAPL', 'MSFT']
        
    async def run_replay(self) -> Dict[str, Any]:
        """Run accelerated replay simulation"""
        logger.info(f"Starting {self.hours}h replay simulation...")
        
        start_time = datetime.now() - timedelta(hours=self.hours)
        end_time = datetime.now()
        
        # Initialize components
        await self.signal_hub.initialize()
        
        # Fetch historical data
        historical_data = await self._fetch_historical_data(start_time, end_time)
        
        if not historical_data:
            logger.error("No historical data available")
            return None
        
        # Run simulation
        results = await self._simulate_trading(historical_data)
        
        # Generate report
        report = self._generate_replay_report(results)
        
        return report
    
    async def _fetch_historical_data(self, start_time: datetime, end_time: datetime) -> Dict[str, pd.DataFrame]:
        """Fetch historical OHLCV data"""
        data = {}
        
        # Fetch crypto data
        try:
            exchange = ccxt.binance({'enableRateLimit': True})
            
            for symbol in self.crypto_symbols:
                since = int(start_time.timestamp() * 1000)
                ohlcv = exchange.fetch_ohlcv(symbol, '5m', since=since, limit=1000)
                
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('timestamp', inplace=True)
                
                data[symbol] = df
                logger.info(f"Fetched {len(df)} bars for {symbol}")
                
            # Exchange doesn't need explicit close in ccxt
            
        except Exception as e:
            logger.error(f"Failed to fetch crypto data: {e}")
        
        # Fetch equity data
        for symbol in self.equity_symbols:
            try:
                ticker = yf.Ticker(symbol)
                df = ticker.history(period='1d', interval='5m')
                
                if not df.empty:
                    # Rename columns to match
                    df.columns = df.columns.str.lower()
                    data[symbol] = df
                    logger.info(f"Fetched {len(df)} bars for {symbol}")
                    
            except Exception as e:
                logger.error(f"Failed to fetch {symbol} data: {e}")
        
        return data
    
    async def _simulate_trading(self, historical_data: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """Simulate trading on historical data"""
        all_timestamps = set()
        for df in historical_data.values():
            # Convert to timezone-naive for comparison
            if hasattr(df.index, 'tz_localize'):
                df.index = df.index.tz_localize(None)
            all_timestamps.update(df.index.tolist())
        
        all_timestamps = sorted(all_timestamps)
        
        trades_executed = 0
        winning_trades = 0
        total_fees = Decimal('0')
        
        # Process each timestamp
        for timestamp in all_timestamps:
            current_prices = {}
            
            # Get prices at this timestamp
            for symbol, df in historical_data.items():
                if timestamp in df.index:
                    current_prices[symbol] = Decimal(str(df.loc[timestamp, 'close']))
                    
                    # Update signal hub with data up to this point
                    historical_slice = df[:timestamp]
                    if len(historical_slice) > 20:  # Need enough data for indicators
                        # Convert to OHLCV format expected by signal hub
                        ohlcv_data = []
                        for idx, row in historical_slice.iterrows():
                            ohlcv_data.append([
                                int(idx.timestamp() * 1000) if hasattr(idx, 'timestamp') else 0,
                                row['open'],
                                row['high'],
                                row['low'],
                                row['close'],
                                row['volume']
                            ])
                        self.signal_hub.update_ohlcv(symbol, ohlcv_data)
            
            # Get signals and execute trades
            for symbol, price in current_prices.items():
                signal = self.signal_hub.get_signal(symbol, price)
                
                if signal and signal['strength'] != 0:
                    # Simple position sizing
                    position_size = (self.balance * Decimal('0.1')) / price  # 10% per trade
                    
                    if signal['strength'] > 0:  # Buy signal
                        if symbol not in self.positions:
                            # Open position
                            fee = position_size * price * Decimal('0.001')
                            self.positions[symbol] = {
                                'quantity': position_size,
                                'entry_price': price,
                                'entry_time': timestamp
                            }
                            self.balance -= (position_size * price + fee)
                            total_fees += fee
                            trades_executed += 1
                            
                    elif signal['strength'] < 0:  # Sell signal
                        if symbol in self.positions:
                            # Close position
                            pos = self.positions[symbol]
                            pnl = (price - pos['entry_price']) * pos['quantity']
                            fee = pos['quantity'] * price * Decimal('0.001')
                            
                            self.pnl += pnl - fee
                            self.balance += (pos['quantity'] * price - fee)
                            total_fees += fee
                            
                            if pnl > 0:
                                winning_trades += 1
                            
                            trades_executed += 1
                            del self.positions[symbol]
        
        # Close remaining positions at last price
        for symbol, pos in self.positions.items():
            if symbol in historical_data:
                last_price = Decimal(str(historical_data[symbol]['close'].iloc[-1]))
                pnl = (last_price - pos['entry_price']) * pos['quantity']
                self.pnl += pnl
                
                if pnl > 0:
                    winning_trades += 1
        
        return {
            'trades_executed': trades_executed,
            'winning_trades': winning_trades,
            'win_rate': (winning_trades / trades_executed * 100) if trades_executed > 0 else 0,
            'total_pnl': float(self.pnl),
            'total_fees': float(total_fees),
            'final_balance': float(self.balance),
            'return_pct': float((self.pnl / Decimal('10000')) * 100),
            'open_positions': len(self.positions)
        }
    
    def _generate_replay_report(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate replay simulation report"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'simulation': {
                'type': 'replay',
                'hours': self.hours,
                'start_time': (datetime.now() - timedelta(hours=self.hours)).isoformat(),
                'end_time': datetime.now().isoformat()
            },
            'results': results,
            'profitability': {
                'is_profitable': results['total_pnl'] > 0,
                'expected_daily_pnl': results['total_pnl'] / (self.hours / 24),
                'expected_monthly_return': results['return_pct'] * (30 * 24 / self.hours),
                'break_even_trades': int(abs(results['total_fees'] / max(0.01, results['total_pnl'] / max(1, results['trades_executed']))))
            },
            'risk_metrics': {
                'win_rate': results['win_rate'],
                'avg_trade_pnl': results['total_pnl'] / max(1, results['trades_executed']),
                'fee_impact_pct': (results['total_fees'] / 10000) * 100
            }
        }
        
        # Save report
        os.makedirs('reports/paper', exist_ok=True)
        report_file = 'reports/paper/replay_report.json'
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Replay report saved: {report_file}")
        
        # Generate HTML quick check report
        self._generate_quickcheck_html(report)
        
        return report
    
    def _generate_quickcheck_html(self, report: Dict[str, Any]):
        """Generate HTML quick check report"""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Paper Trading Quick Check</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
        .header {{ background: #3498db; color: white; padding: 20px; border-radius: 5px; }}
        .result-box {{ background: white; padding: 20px; margin: 20px 0; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .profitable {{ color: #27ae60; font-size: 24px; font-weight: bold; }}
        .unprofitable {{ color: #e74c3c; font-size: 24px; font-weight: bold; }}
        .metric {{ margin: 10px 0; padding: 10px; background: #ecf0f1; border-radius: 3px; }}
        .metric-label {{ font-weight: bold; color: #34495e; }}
        .metric-value {{ float: right; color: #2c3e50; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Paper Trading Quick Profitability Check</h1>
        <p>Simulation Period: {report['simulation']['hours']}h | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
    
    <div class="result-box">
        <h2>Quick Answer: Is it Profitable?</h2>
        <p class="{'profitable' if report['profitability']['is_profitable'] else 'unprofitable'}">
            {'YES ✓' if report['profitability']['is_profitable'] else 'NO ✗'}
        </p>
        <p>Total P&L: ${report['results']['total_pnl']:.2f} ({report['results']['return_pct']:.2f}%)</p>
    </div>
    
    <div class="result-box">
        <h3>Key Metrics</h3>
        <div class="metric">
            <span class="metric-label">Trades Executed:</span>
            <span class="metric-value">{report['results']['trades_executed']}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Win Rate:</span>
            <span class="metric-value">{report['results']['win_rate']:.1f}%</span>
        </div>
        <div class="metric">
            <span class="metric-label">Expected Daily P&L:</span>
            <span class="metric-value">${report['profitability']['expected_daily_pnl']:.2f}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Expected Monthly Return:</span>
            <span class="metric-value">{report['profitability']['expected_monthly_return']:.2f}%</span>
        </div>
        <div class="metric">
            <span class="metric-label">Total Fees:</span>
            <span class="metric-value">${report['results']['total_fees']:.2f}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Fee Impact:</span>
            <span class="metric-value">{report['risk_metrics']['fee_impact_pct']:.2f}%</span>
        </div>
    </div>
    
    <div class="result-box">
        <h3>Recommendation</h3>
        <p>{'✅ Strategy shows promise. Consider running live paper trading for validation.' if report['profitability']['is_profitable'] else '⚠️ Strategy needs optimization. Review signal generation and risk parameters.'}</p>
    </div>
</body>
</html>
        """
        
        with open('reports/paper/quickcheck.html', 'w', encoding='utf-8') as f:
            f.write(html)
        
        logger.info("Quick check report saved: reports/paper/quickcheck.html")


async def compare_with_live(replay_report: Dict[str, Any], live_metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Compare replay simulation with live paper trading"""
    comparison = {
        'timestamp': datetime.now().isoformat(),
        'replay': {
            'total_pnl': replay_report['results']['total_pnl'],
            'win_rate': replay_report['results']['win_rate'],
            'trades': replay_report['results']['trades_executed']
        },
        'live': {
            'total_pnl': float(live_metrics.get('cumulative_pnl', 0)),
            'win_rate': live_metrics.get('win_rate', 0),
            'trades': live_metrics.get('trade_count', 0)
        },
        'divergence': {
            'pnl_diff': abs(replay_report['results']['total_pnl'] - float(live_metrics.get('cumulative_pnl', 0))),
            'win_rate_diff': abs(replay_report['results']['win_rate'] - live_metrics.get('win_rate', 0)),
            'explanation': 'Differences due to: slippage variation, real-time order book depth, network latency'
        }
    }
    
    return comparison


async def main():
    """Main execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Paper Trading Replay')
    parser.add_argument('--hours', type=int, default=24, help='Hours to replay')
    parser.add_argument('--compare', action='store_true', help='Compare with live')
    
    args = parser.parse_args()
    
    # Run replay
    replay = PaperReplay(hours=args.hours)
    report = await replay.run_replay()
    
    if report:
        print("\n" + "="*60)
        print("PAPER TRADING QUICK CHECK")
        print("="*60)
        print(f"Simulation Period: {args.hours} hours")
        print(f"Is Profitable? {'YES' if report['profitability']['is_profitable'] else 'NO'}")
        print(f"Total P&L: ${report['results']['total_pnl']:.2f}")
        print(f"Return: {report['results']['return_pct']:.2f}%")
        print(f"Win Rate: {report['results']['win_rate']:.1f}%")
        print(f"Trades: {report['results']['trades_executed']}")
        print(f"\nExpected Daily P&L: ${report['profitability']['expected_daily_pnl']:.2f}")
        print(f"Expected Monthly Return: {report['profitability']['expected_monthly_return']:.2f}%")
        
        if args.compare:
            # Compare with live if running
            try:
                from src.reports.paper_report import PaperTradingReport
                live_report = PaperTradingReport()
                live_metrics = live_report.get_live_metrics()
                
                comparison = await compare_with_live(report, live_metrics)
                
                print("\n" + "="*60)
                print("REPLAY vs LIVE COMPARISON")
                print("="*60)
                print(f"Replay P&L: ${comparison['replay']['total_pnl']:.2f}")
                print(f"Live P&L: ${comparison['live']['total_pnl']:.2f}")
                print(f"Divergence: ${comparison['divergence']['pnl_diff']:.2f}")
                print(f"Explanation: {comparison['divergence']['explanation']}")
                
            except Exception as e:
                print(f"Could not compare with live: {e}")
        
        print(f"\nReports saved:")
        print(f"  - reports/paper/replay_report.json")
        print(f"  - reports/paper/quickcheck.html")


if __name__ == "__main__":
    asyncio.run(main())