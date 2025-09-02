"""
Turkish Arbitrage Session Runner
Run Binance-BTCTurk arbitrage for specified duration with detailed metrics
"""

import sys
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from decimal import Decimal
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.trading.turkish_arbitrage import TurkishArbitrage
from src.trading.arbitrage_rules import ArbitrageMicroRules

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/tr_arb_audit.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class TurkishArbitrageSession:
    """Managed Turkish arbitrage session with metrics"""
    
    def __init__(self, duration_minutes: int = 30):
        self.duration_minutes = duration_minutes
        self.arbitrage = TurkishArbitrage(paper_mode=True)
        self.micro_rules = ArbitrageMicroRules()
        
        # Session metrics
        self.session_start = None
        self.session_end = None
        self.opportunities_analyzed = 0
        self.trades_executed = 0
        self.trades_rejected = 0
        self.total_profit_tl = Decimal("0")
        self.total_profit_usd = Decimal("0")
        self.latencies = []
        
        # TL gateway settings
        self.min_profit_tl = Decimal("100")  # Minimum 100 TL profit after fees
        self.gateway_fee_pct = Decimal("0.1")  # 0.1% TL gateway fee
        
    async def run(self):
        """Run arbitrage session"""
        print("=" * 60)
        print(f"TURKISH ARBITRAGE SESSION - {self.duration_minutes} MINUTES")
        print("=" * 60)
        print(f"Start: {datetime.now()}")
        print(f"Min Profit: {self.min_profit_tl} TL")
        print(f"Gateway Fee: {self.gateway_fee_pct}%")
        print("-" * 60)
        
        self.session_start = datetime.now()
        self.session_end = self.session_start + timedelta(minutes=self.duration_minutes)
        
        try:
            # Initialize systems
            await self.arbitrage.initialize()
            
            # Custom monitoring loop
            await self._monitor_and_trade()
            
        except KeyboardInterrupt:
            logger.info("Session interrupted by user")
        except Exception as e:
            logger.error(f"Session error: {e}")
        finally:
            # Stop and report
            await self.arbitrage.stop()
            self._print_report()
            
    async def _monitor_and_trade(self):
        """Monitor and execute arbitrage opportunities"""
        
        while datetime.now() < self.session_end:
            try:
                # Measure latency to both exchanges
                binance_latency = await self.micro_rules.measure_latency("binance", self.arbitrage.binance)
                btcturk_latency = await self.micro_rules.measure_latency("btcturk", self.arbitrage.btcturk)
                self.latencies.append((binance_latency, btcturk_latency))
                
                # Find opportunities
                opportunities = await self._find_profitable_opportunities()
                self.opportunities_analyzed += len(opportunities)
                
                # Execute best opportunities
                for opp in opportunities[:3]:  # Top 3 opportunities
                    if await self._should_execute(opp):
                        await self._execute_trade(opp)
                    else:
                        self.trades_rejected += 1
                        
                # Status update every minute
                elapsed = (datetime.now() - self.session_start).seconds
                if elapsed > 0 and elapsed % 60 == 0:
                    self._print_status()
                    
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                await asyncio.sleep(10)
                
    async def _find_profitable_opportunities(self) -> list:
        """Find opportunities that meet minimum profit threshold"""
        opportunities = []
        
        symbols = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT']
        
        for symbol in symbols:
            try:
                # Get prices from both exchanges
                binance_ticker = await self.arbitrage.binance.fetch_ticker(symbol)
                
                base = symbol.split('/')[0]
                btcturk_symbol = f"{base}/TRY"
                
                if btcturk_symbol not in self.arbitrage.btcturk.markets:
                    continue
                    
                btcturk_ticker = await self.arbitrage.btcturk.fetch_ticker(btcturk_symbol)
                usdt_try = await self._get_usdt_try_rate()
                
                # Calculate opportunity
                opp = self._calculate_net_opportunity(
                    symbol, binance_ticker, btcturk_ticker, usdt_try
                )
                
                if opp and opp['net_profit_tl'] >= self.min_profit_tl:
                    opportunities.append(opp)
                    logger.info(f"Opportunity found: {symbol} - Net: {opp['net_profit_tl']:.2f} TL")
                    
            except Exception as e:
                logger.warning(f"Error checking {symbol}: {e}")
                
        return sorted(opportunities, key=lambda x: x['net_profit_tl'], reverse=True)
        
    def _calculate_net_opportunity(self, symbol: str, binance_ticker: dict, 
                                  btcturk_ticker: dict, usdt_try: float) -> dict:
        """Calculate net profit after all fees"""
        try:
            # Prices
            binance_bid = binance_ticker['bid']
            binance_ask = binance_ticker['ask']
            btcturk_bid = btcturk_ticker['bid']
            btcturk_ask = btcturk_ticker['ask']
            
            # Convert to common currency (TRY)
            binance_bid_try = binance_bid * usdt_try
            binance_ask_try = binance_ask * usdt_try
            
            # Calculate both directions
            # Direction 1: Buy on Binance, Sell on BTCTurk
            gross_profit1_try = btcturk_bid - binance_ask_try
            
            # Deduct fees
            exchange_fee = 0.001  # 0.1% each exchange
            gateway_fee = float(self.gateway_fee_pct) / 100
            total_fee_pct = exchange_fee * 2 + gateway_fee
            
            net_profit1_try = gross_profit1_try * (1 - total_fee_pct)
            
            # Direction 2: Buy on BTCTurk, Sell on Binance
            gross_profit2_try = binance_bid_try - btcturk_ask
            net_profit2_try = gross_profit2_try * (1 - total_fee_pct)
            
            # Choose best direction
            if net_profit1_try > net_profit2_try and net_profit1_try > 0:
                return {
                    'symbol': symbol,
                    'direction': 'binance_to_btcturk',
                    'gross_profit_tl': Decimal(str(gross_profit1_try)),
                    'net_profit_tl': Decimal(str(net_profit1_try)),
                    'net_profit_pct': float(net_profit1_try / binance_ask_try * 100),
                    'usdt_try_rate': usdt_try,
                    'timestamp': datetime.now().isoformat()
                }
            elif net_profit2_try > 0:
                return {
                    'symbol': symbol,
                    'direction': 'btcturk_to_binance',
                    'gross_profit_tl': Decimal(str(gross_profit2_try)),
                    'net_profit_tl': Decimal(str(net_profit2_try)),
                    'net_profit_pct': float(net_profit2_try / btcturk_ask * 100),
                    'usdt_try_rate': usdt_try,
                    'timestamp': datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Calculation error: {e}")
            
        return None
        
    async def _get_usdt_try_rate(self) -> float:
        """Get USDT/TRY rate"""
        try:
            ticker = await self.arbitrage.binance.fetch_ticker('USDT/TRY')
            return ticker['last']
        except:
            return 34.5  # Fallback rate
            
    async def _should_execute(self, opportunity: dict) -> bool:
        """Check if opportunity should be executed"""
        # Check micro-rules
        can_execute, violations = self.micro_rules.check_execution_rules(opportunity)
        
        if not can_execute:
            logger.warning(f"Trade rejected: {violations}")
            return False
            
        # Check minimum profit
        if opportunity['net_profit_tl'] < self.min_profit_tl:
            return False
            
        return True
        
    async def _execute_trade(self, opportunity: dict):
        """Execute arbitrage trade (paper mode)"""
        trade_size_usd = 1000  # $1000 per trade
        
        # Record trade
        self.trades_executed += 1
        self.total_profit_tl += opportunity['net_profit_tl']
        self.total_profit_usd += opportunity['net_profit_tl'] / Decimal(str(opportunity['usdt_try_rate']))
        
        logger.info(
            f"EXECUTED: {opportunity['symbol']} {opportunity['direction']} "
            f"Net Profit: {opportunity['net_profit_tl']:.2f} TL "
            f"({opportunity['net_profit_pct']:.3f}%)"
        )
        
    def _print_status(self):
        """Print current status"""
        elapsed = (datetime.now() - self.session_start).total_seconds() / 60
        
        print(f"\n[{elapsed:.0f} min] Status:")
        print(f"  Opportunities: {self.opportunities_analyzed}")
        print(f"  Executed: {self.trades_executed}")
        print(f"  Rejected: {self.trades_rejected}")
        print(f"  Total Profit: {self.total_profit_tl:.2f} TL (${self.total_profit_usd:.2f})")
        
        if self.latencies:
            avg_binance = sum(l[0] for l in self.latencies) / len(self.latencies)
            avg_btcturk = sum(l[1] for l in self.latencies) / len(self.latencies)
            print(f"  Avg Latency: Binance={avg_binance:.0f}ms, BTCTurk={avg_btcturk:.0f}ms")
            
    def _print_report(self):
        """Print final report"""
        duration = (datetime.now() - self.session_start).total_seconds() / 60
        
        print("\n" + "=" * 60)
        print("TURKISH ARBITRAGE SESSION REPORT")
        print("=" * 60)
        print(f"Duration: {duration:.1f} minutes")
        print(f"Opportunities Analyzed: {self.opportunities_analyzed}")
        print(f"Trades Executed: {self.trades_executed}")
        print(f"Trades Rejected: {self.trades_rejected}")
        
        if self.trades_executed > 0:
            success_rate = (self.trades_executed / (self.trades_executed + self.trades_rejected)) * 100
            print(f"Success Rate: {success_rate:.1f}%")
        else:
            print("Success Rate: N/A")
            
        print(f"\nP&L Summary:")
        print(f"  Total Profit (TL): {self.total_profit_tl:.2f} TL")
        print(f"  Total Profit (USD): ${self.total_profit_usd:.2f}")
        
        if self.trades_executed > 0:
            print(f"  Avg Profit per Trade: {self.total_profit_tl/self.trades_executed:.2f} TL")
            
        if self.latencies:
            avg_binance = sum(l[0] for l in self.latencies) / len(self.latencies)
            avg_btcturk = sum(l[1] for l in self.latencies) / len(self.latencies)
            print(f"\nLatency Metrics:")
            print(f"  Binance Avg: {avg_binance:.0f}ms")
            print(f"  BTCTurk Avg: {avg_btcturk:.0f}ms")
            
        print("=" * 60)
        
        # Save detailed report
        report = {
            'session': {
                'start': self.session_start.isoformat(),
                'end': datetime.now().isoformat(),
                'duration_minutes': duration
            },
            'metrics': {
                'opportunities_analyzed': self.opportunities_analyzed,
                'trades_executed': self.trades_executed,
                'trades_rejected': self.trades_rejected,
                'success_rate': (self.trades_executed / max(1, self.trades_executed + self.trades_rejected)) * 100,
                'total_profit_tl': float(self.total_profit_tl),
                'total_profit_usd': float(self.total_profit_usd)
            },
            'latency': {
                'binance_avg_ms': sum(l[0] for l in self.latencies) / len(self.latencies) if self.latencies else 0,
                'btcturk_avg_ms': sum(l[1] for l in self.latencies) / len(self.latencies) if self.latencies else 0
            }
        }
        
        report_file = Path("logs/tr_arb_session_report.json")
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
            
        print(f"\nDetailed report saved to: {report_file}")


async def main():
    # Get duration from command line
    duration = 30  # Default 30 minutes
    if len(sys.argv) > 1:
        try:
            duration = int(sys.argv[1])
        except ValueError:
            print(f"Invalid duration: {sys.argv[1]}, using default 30 minutes")
            
    # Run session
    session = TurkishArbitrageSession(duration)
    await session.run()


if __name__ == "__main__":
    asyncio.run(main())