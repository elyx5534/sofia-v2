"""
Run Paper Trading Session for N minutes
Usage: python run_paper_session.py [minutes]
"""

import sys
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from src.paper_trading.fill_engine import RealisticFillEngine, Order
from src.core.watchdog import Watchdog
from src.core.profit_guard import ProfitGuard
from src.core.accounting import FIFOAccounting
from src.strategies.grid_auto_tuner import GridAutoTuner
from decimal import Decimal
import random
import json

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PaperTradingSession:
    """Complete paper trading session with all features"""
    
    def __init__(self, duration_minutes: int = 60):
        self.duration_minutes = duration_minutes
        self.fill_engine = RealisticFillEngine()
        self.watchdog = Watchdog()
        self.profit_guard = ProfitGuard()
        self.accounting = FIFOAccounting()
        self.grid_tuner = GridAutoTuner()
        
        self.trades_executed = 0
        self.total_pnl = Decimal("0")
        self.start_time = None
        self.end_time = None
        
    async def run_session(self):
        """Run complete paper trading session"""
        print("=" * 60)
        print(f"PAPER TRADING SESSION - {self.duration_minutes} MINUTES")
        print("=" * 60)
        print(f"Start Time: {datetime.now()}")
        print("Features Enabled:")
        print("  [OK] Realistic Fill Engine with Maker-Only Orders")
        print("  [OK] FIFO Accounting with Fees")
        print("  [OK] Watchdog System with Kill-Switch")
        print("  [OK] Profit Guard with Daily Targets")
        print("  [OK] Grid Auto-Tuner with ATR")
        print("-" * 60)
        
        self.start_time = datetime.now()
        self.end_time = self.start_time + timedelta(minutes=self.duration_minutes)
        
        try:
            # Start all systems
            await self.fill_engine.start()
            await self.watchdog.start()
            await self.profit_guard.start_monitoring()
            
            logger.info("All systems started successfully")
            
            # Run trading loop
            await self._trading_loop()
            
        except KeyboardInterrupt:
            logger.info("Session interrupted by user")
        finally:
            # Stop all systems
            await self.fill_engine.stop()
            await self.watchdog.stop()
            await self.profit_guard.stop_monitoring()
            
            # Print final report
            self._print_final_report()
            
    async def _trading_loop(self):
        """Main trading loop"""
        symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
        
        while datetime.now() < self.end_time:
            # Check watchdog status
            if self.watchdog.state.status == "PAUSED":
                logger.warning(f"System paused: {self.watchdog.state.pause_reason}")
                await asyncio.sleep(10)
                continue
                
            # Check profit guard
            can_trade = not self.profit_guard.state.positions_blocked
            if not can_trade:
                logger.warning(f"Trading blocked: {self.profit_guard.state.block_reason}")
                await asyncio.sleep(10)
                continue
                
            # Generate and submit orders
            for symbol in symbols:
                if random.random() < 0.3:  # 30% chance to trade each symbol
                    await self._execute_trade(symbol)
                    
            # Update metrics
            self._update_metrics()
            
            # Status update every 30 seconds
            if self.trades_executed % 10 == 0 and self.trades_executed > 0:
                self._print_status()
                
            # Sleep before next iteration
            await asyncio.sleep(5)
            
    async def _execute_trade(self, symbol: str):
        """Execute a single trade"""
        # Get current price (simulated)
        base_prices = {
            "BTC/USDT": 108000,
            "ETH/USDT": 3800,
            "SOL/USDT": 180
        }
        current_price = base_prices.get(symbol, 100000)
        current_price *= (1 + random.uniform(-0.02, 0.02))  # ±2% variation
        
        # Generate candle data for grid tuner
        candles = self._generate_candles(current_price)
        
        # Tune grid parameters
        grid_params = self.grid_tuner.tune_parameters(
            symbol, current_price, candles, base_capital=1000
        )
        
        # Get position size from profit guard
        base_size = 100  # $100 base
        position_size = self.profit_guard.get_scaled_position_size(base_size)
        
        # Create order
        side = "buy" if random.random() < 0.5 else "sell"
        order_type = "limit"
        
        # Adjust price for limit order
        if side == "buy":
            order_price = current_price * 0.999  # Buy slightly below
        else:
            order_price = current_price * 1.001  # Sell slightly above
            
        order = Order(
            order_id=f"paper_{self.trades_executed}",
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=Decimal(str(position_size / order_price)),
            price=Decimal(str(order_price)),
            maker_only=random.random() < 0.7,  # 70% maker orders
            cancel_unfilled_sec=30
        )
        
        # Submit order
        self.fill_engine.submit_order(order)
        self.trades_executed += 1
        
        logger.info(
            f"Order submitted: {symbol} {side} "
            f"{order.quantity:.4f} @ ${order_price:.2f} "
            f"(maker_only={order.maker_only})"
        )
        
        # Wait for potential fill
        await asyncio.sleep(2)
        
        # Process fills through accounting
        if order.fills:
            for fill_data in order.fills:
                fill = type('Fill', (), {
                    'symbol': symbol,
                    'side': side,
                    'price': Decimal(str(fill_data['price'])),
                    'quantity': Decimal(str(fill_data['quantity'])),
                    'fee': Decimal(str(fill_data.get('fee', 0.001))),
                    'fee_currency': 'USDT',
                    'timestamp': fill_data['timestamp']
                })()
                
                result = self.accounting.update_on_fill(fill)
                self.total_pnl += result['realized_pnl']
                
                # Update profit guard
                self.profit_guard.update_pnl(float(self.total_pnl))
                
                # Report to watchdog (success)
                self.watchdog.state.error_count = max(0, self.watchdog.state.error_count - 1)
                
    def _generate_candles(self, current_price: float) -> list:
        """Generate dummy candle data for grid tuner"""
        candles = []
        for i in range(50):
            variation = random.uniform(0.98, 1.02)
            high = current_price * variation * 1.01
            low = current_price * variation * 0.99
            close = random.uniform(low, high)
            candles.append({
                'high': high,
                'low': low,
                'close': close,
                'volume': random.uniform(100, 1000)
            })
        return candles
        
    def _update_metrics(self):
        """Update system metrics"""
        # Update watchdog daily P&L
        self.watchdog.state.daily_pnl = self.total_pnl
        
        # Check for errors (simulated)
        if random.random() < 0.01:  # 1% error rate
            self.watchdog.report_error()
            
        # Check for rate limits (simulated)
        if random.random() < 0.005:  # 0.5% rate limit
            self.watchdog.report_rate_limit()
            
    def _print_status(self):
        """Print current status"""
        elapsed = (datetime.now() - self.start_time).total_seconds() / 60
        remaining = self.duration_minutes - elapsed
        
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] STATUS UPDATE")
        print(f"  Elapsed: {elapsed:.1f} min | Remaining: {remaining:.1f} min")
        print(f"  Trades: {self.trades_executed} | P&L: ${float(self.total_pnl):.2f}")
        print(f"  Fill Metrics: {self.fill_engine.get_metrics()}")
        print(f"  Watchdog: {self.watchdog.state.status}")
        print(f"  Profit Guard: Scale={float(self.profit_guard.state.current_scale_factor)*100:.0f}%")
        
    def _print_final_report(self):
        """Print final session report"""
        duration = (datetime.now() - self.start_time).total_seconds() / 60
        
        print("\n" + "=" * 60)
        print("PAPER TRADING SESSION COMPLETE")
        print("=" * 60)
        print(f"Duration: {duration:.1f} minutes")
        print(f"Total Trades: {self.trades_executed}")
        print(f"Total P&L: ${float(self.total_pnl):.2f}")
        
        # Fill engine metrics
        fill_metrics = self.fill_engine.get_metrics()
        print("\nFill Engine Metrics:")
        print(f"  Maker Fill Rate: {fill_metrics['maker_fill_rate']:.1f}%")
        print(f"  Avg Fill Time: {fill_metrics['avg_time_to_fill_ms']:.0f}ms")
        print(f"  Partial Fills: {fill_metrics['partial_fill_count']}")
        print(f"  Cancelled Orders: {fill_metrics['cancelled_orders']}")
        
        # Accounting summary
        positions = self.accounting.positions
        print(f"\nOpen Positions: {len(positions)}")
        for symbol, lots in positions.items():
            total_qty = sum(lot['quantity'] for lot in lots)
            avg_price = sum(lot['price'] * lot['quantity'] for lot in lots) / total_qty if total_qty > 0 else 0
            print(f"  {symbol}: {float(total_qty):.4f} @ ${float(avg_price):.2f}")
            
        # Risk metrics
        print(f"\nRisk Status:")
        print(f"  Watchdog: {self.watchdog.state.status}")
        print(f"  Errors: {self.watchdog.state.error_count}")
        print(f"  Rate Limits: {self.watchdog.state.rate_limit_hits}")
        print(f"  Profit Guard Scale: {float(self.profit_guard.state.current_scale_factor)*100:.0f}%")
        
        # Save report
        self._save_report(duration, fill_metrics)
        
        print("\n[OK] Report saved to logs/paper_session_report.json")
        print("=" * 60)
        
    def _save_report(self, duration: float, fill_metrics: dict):
        """Save session report to file"""
        report = {
            'session': {
                'start_time': self.start_time.isoformat(),
                'end_time': datetime.now().isoformat(),
                'duration_minutes': duration,
                'trades_executed': self.trades_executed,
                'total_pnl': float(self.total_pnl)
            },
            'fill_metrics': fill_metrics,
            'watchdog': self.watchdog.get_status(),
            'profit_guard': self.profit_guard.get_risk_status(),
            'grid_tuner': self.grid_tuner.get_status(),
            'positions': {
                symbol: [
                    {
                        'quantity': float(lot['quantity']),
                        'price': float(lot['price']),
                        'timestamp': lot['timestamp']
                    }
                    for lot in lots
                ]
                for symbol, lots in self.accounting.get_all_positions().items()
            }
        }
        
        report_path = Path("logs/paper_session_report.json")
        report_path.parent.mkdir(exist_ok=True)
        
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)


async def main():
    # Get duration from command line or use default
    duration = 60  # Default 60 minutes
    if len(sys.argv) > 1:
        try:
            duration = int(sys.argv[1])
        except ValueError:
            print(f"Invalid duration: {sys.argv[1]}, using default 60 minutes")
            
    # Run session
    session = PaperTradingSession(duration)
    await session.run_session()


if __name__ == "__main__":
    asyncio.run(main())