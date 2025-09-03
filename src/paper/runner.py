"""
Paper Trading Run Loop with Risk Management and Position Sizing
"""

import asyncio
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_DOWN, Decimal
from typing import Any, Dict, List, Optional

import ccxt
import yfinance as yf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.paper.signal_hub import SignalHub
from src.risk.engine import RiskEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class PaperOrder:
    """Paper trading order"""

    order_id: str
    symbol: str
    side: str
    order_type: str
    quantity: Decimal
    price: Decimal
    timestamp: datetime
    status: str
    filled_price: Optional[Decimal] = None
    filled_quantity: Optional[Decimal] = None
    fees: Optional[Decimal] = None
    slippage: Optional[Decimal] = None


@dataclass
class PaperPosition:
    """Paper trading position"""

    symbol: str
    quantity: Decimal
    entry_price: Decimal
    current_price: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal
    total_fees: Decimal
    position_value: Decimal


class PaperTradingRunner:
    """Main paper trading execution loop"""

    def __init__(self):
        self.mode = os.getenv("MODE", "paper")
        self.base_currency = os.getenv("BASE_CURRENCY", "USD")
        self.heartbeat_sec = int(os.getenv("HEARTBEAT_SEC", "15"))
        self.k_factor = Decimal(os.getenv("K_FACTOR", "0.25"))
        self.fee_rate = Decimal(os.getenv("PAPER_FEE_RATE", "0.001"))
        self.max_daily_loss = Decimal(os.getenv("MAX_DAILY_LOSS", "200"))
        self.max_position_usd = Decimal(os.getenv("MAX_POSITION_USD", "1000"))
        self.max_symbol_exposure = Decimal(os.getenv("MAX_SYMBOL_EXPOSURE_USD", "500"))
        self.single_order_max = Decimal(os.getenv("SINGLE_ORDER_MAX_USD", "100"))
        self.signal_hub = SignalHub()
        self.risk_engine = RiskEngine()
        self.balance = Decimal(os.getenv("PAPER_INITIAL_BALANCE", "10000"))
        self.positions: Dict[str, PaperPosition] = {}
        self.orders: List[PaperOrder] = []
        self.daily_pnl = Decimal("0")
        self.total_pnl = Decimal("0")
        self.trade_count = 0
        self.win_count = 0
        self.exchange = None
        self.current_prices: Dict[str, Decimal] = {}
        self.running = False
        self.error_count = 0
        self.max_errors = 10
        self.crypto_symbols = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "ADA/USDT"]
        self.equity_symbols = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN"]

    async def initialize(self):
        """Initialize paper trading components"""
        logger.info("Initializing paper trading runner...")
        try:
            self.exchange = ccxt.binance(
                {"enableRateLimit": True, "options": {"defaultType": "spot"}}
            )
            await self.exchange.load_markets()
            await self._warmup_indicators()
            await self.signal_hub.initialize()
            logger.info(f"Paper trading initialized with balance: {self.balance}")
            return True
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            return False

    async def _warmup_indicators(self):
        """Warm up technical indicators with historical data"""
        logger.info("Warming up indicators...")
        for symbol in self.crypto_symbols:
            try:
                ohlcv = await self.exchange.fetch_ohlcv(symbol, "1h", limit=500)
                self.signal_hub.update_ohlcv(symbol, ohlcv)
            except Exception as e:
                logger.warning(f"Failed to warm up {symbol}: {e}")
        logger.info("Indicator warmup complete")

    async def run(self):
        """Main paper trading loop"""
        if not await self.initialize():
            logger.error("Failed to initialize, exiting")
            return
        self.running = True
        logger.info("Starting paper trading run loop...")
        while self.running:
            try:
                await self._update_prices()
                signals = await self._get_signals()
                for signal in signals:
                    await self._process_signal(signal)
                self._update_positions()
                await self._check_risk_limits()
                self._log_state()
                self.error_count = 0
                await asyncio.sleep(self.heartbeat_sec)
            except Exception as e:
                logger.error(f"Error in run loop: {e}")
                self.error_count += 1
                if self.error_count >= self.max_errors:
                    logger.critical("Max errors reached, stopping")
                    self.running = False
                else:
                    await asyncio.sleep(self.heartbeat_sec * 2**self.error_count)

    async def _update_prices(self):
        """Update current market prices"""
        for symbol in self.crypto_symbols:
            try:
                ticker = await self.exchange.fetch_ticker(symbol)
                self.current_prices[symbol] = Decimal(str(ticker["last"]))
            except Exception as e:
                logger.warning(f"Failed to fetch {symbol} price: {e}")
                self._update_price_fallback(symbol)
        if self._is_market_hours():
            for symbol in self.equity_symbols:
                self._update_equity_price(symbol)

    def _update_price_fallback(self, symbol: str):
        """Fallback price update using yfinance"""
        try:
            yf_symbol = symbol.replace("/", "-")
            ticker = yf.Ticker(yf_symbol)
            hist = ticker.history(period="1d", interval="1m")
            if not hist.empty:
                self.current_prices[symbol] = Decimal(str(hist["Close"].iloc[-1]))
        except:
            pass

    def _update_equity_price(self, symbol: str):
        """Update equity price"""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            if "regularMarketPrice" in info:
                self.current_prices[symbol] = Decimal(str(info["regularMarketPrice"]))
        except:
            pass

    def _is_market_hours(self) -> bool:
        """Check if US market is open"""
        now = datetime.now()
        if now.weekday() >= 5:
            return False
        hour = now.hour
        return 9 <= hour <= 16

    async def _get_signals(self) -> List[Dict[str, Any]]:
        """Get trading signals from signal hub"""
        signals = []
        all_symbols = self.crypto_symbols + (self.equity_symbols if self._is_market_hours() else [])
        for symbol in all_symbols:
            if symbol not in self.current_prices:
                continue
            signal = self.signal_hub.get_signal(symbol, self.current_prices[symbol])
            if signal and signal["strength"] != 0:
                signals.append(
                    {
                        "symbol": symbol,
                        "side": "buy" if signal["strength"] > 0 else "sell",
                        "strength": abs(signal["strength"]),
                        "source": signal.get("source", "fusion"),
                        "price": self.current_prices[symbol],
                    }
                )
        return signals

    async def _process_signal(self, signal: Dict[str, Any]):
        """Process trading signal and create paper order"""
        symbol = signal["symbol"]
        side = signal["side"]
        price = signal["price"]
        position_size = self._calculate_position_size(symbol, signal["strength"])
        if position_size == 0:
            return
        risk_check = await self.risk_engine.pre_trade_check(
            symbol=symbol,
            side=side,
            order_type="market",
            quantity=position_size,
            current_price=price,
        )
        if risk_check.action.value == "BLOCK":
            logger.warning(f"Order blocked by risk engine: {risk_check.reason}")
            return
        await self._create_paper_order(symbol, side, position_size, price)

    def _calculate_position_size(self, symbol: str, signal_strength: float) -> Decimal:
        """Calculate position size using Kelly Criterion with K-factor"""
        available_balance = self.balance - self._get_total_exposure()
        if available_balance <= 0:
            return Decimal("0")
        base_size = available_balance * self.k_factor * Decimal(str(signal_strength))
        position_value = min(base_size, self.single_order_max)
        current_exposure = self._get_symbol_exposure(symbol)
        remaining_exposure = self.max_symbol_exposure - current_exposure
        position_value = min(position_value, remaining_exposure)
        if symbol in self.current_prices:
            quantity = (position_value / self.current_prices[symbol]).quantize(
                Decimal("0.00001"), rounding=ROUND_DOWN
            )
            return quantity
        return Decimal("0")

    def _get_total_exposure(self) -> Decimal:
        """Get total position exposure"""
        total = Decimal("0")
        for position in self.positions.values():
            total += position.position_value
        return total

    def _get_symbol_exposure(self, symbol: str) -> Decimal:
        """Get exposure for specific symbol"""
        if symbol in self.positions:
            return self.positions[symbol].position_value
        return Decimal("0")

    async def _create_paper_order(self, symbol: str, side: str, quantity: Decimal, price: Decimal):
        """Create and execute paper order"""
        order_value = quantity * price
        fees = order_value * self.fee_rate
        slippage_bps = Decimal("10")
        if side == "buy":
            filled_price = price * (1 + slippage_bps / 10000)
        else:
            filled_price = price * (1 - slippage_bps / 10000)
        slippage = abs(filled_price - price) * quantity
        order = PaperOrder(
            order_id=f"PAPER-{datetime.now().timestamp():.0f}",
            symbol=symbol,
            side=side,
            order_type="market",
            quantity=quantity,
            price=price,
            timestamp=datetime.now(),
            status="filled",
            filled_price=filled_price,
            filled_quantity=quantity,
            fees=fees,
            slippage=slippage,
        )
        self.orders.append(order)
        self._update_position_from_order(order)
        if side == "buy":
            cost = filled_price * quantity + fees
            self.balance -= cost
        else:
            proceeds = filled_price * quantity - fees
            self.balance += proceeds
            if symbol in self.positions:
                position = self.positions[symbol]
                realized_pnl = (filled_price - position.entry_price) * min(
                    quantity, position.quantity
                )
                position.realized_pnl += realized_pnl - fees
                self.daily_pnl += realized_pnl - fees
                self.total_pnl += realized_pnl - fees
                if realized_pnl > 0:
                    self.win_count += 1
        self.trade_count += 1
        logger.info(
            f"Paper order executed: {side} {quantity} {symbol} @ {filled_price:.2f} (fees: {fees:.2f}, slippage: {slippage:.2f})"
        )

    def _update_position_from_order(self, order: PaperOrder):
        """Update position from executed order"""
        symbol = order.symbol
        if symbol not in self.positions:
            if order.side == "buy":
                self.positions[symbol] = PaperPosition(
                    symbol=symbol,
                    quantity=order.filled_quantity,
                    entry_price=order.filled_price,
                    current_price=order.filled_price,
                    unrealized_pnl=Decimal("0"),
                    realized_pnl=Decimal("0"),
                    total_fees=order.fees,
                    position_value=order.filled_quantity * order.filled_price,
                )
        else:
            position = self.positions[symbol]
            if order.side == "buy":
                total_value = (
                    position.quantity * position.entry_price
                    + order.filled_quantity * order.filled_price
                )
                total_quantity = position.quantity + order.filled_quantity
                position.entry_price = total_value / total_quantity
                position.quantity = total_quantity
                position.total_fees += order.fees
            else:
                position.quantity -= order.filled_quantity
                position.total_fees += order.fees
                if position.quantity <= 0:
                    del self.positions[symbol]

    def _update_positions(self):
        """Update position values and unrealized P&L"""
        for symbol, position in self.positions.items():
            if symbol in self.current_prices:
                position.current_price = self.current_prices[symbol]
                position.unrealized_pnl = (
                    position.current_price - position.entry_price
                ) * position.quantity
                position.position_value = position.quantity * position.current_price

    async def _check_risk_limits(self):
        """Check and enforce risk limits"""
        if self.daily_pnl < -self.max_daily_loss:
            logger.critical(f"Daily loss limit breached: {self.daily_pnl}")
            if self.risk_engine:
                self.risk_engine.update_kill_switch("ON")
            self.running = False
        total_exposure = self._get_total_exposure()
        if total_exposure > self.max_position_usd:
            logger.warning(f"Total exposure {total_exposure} exceeds limit {self.max_position_usd}")

    def _log_state(self):
        """Log current trading state"""
        total_unrealized = sum(p.unrealized_pnl for p in self.positions.values())
        win_rate = self.win_count / self.trade_count * 100 if self.trade_count > 0 else 0
        logger.info(
            f"Paper Trading State - Balance: ${self.balance:.2f}, Daily P&L: ${self.daily_pnl:.2f}, Total P&L: ${self.total_pnl:.2f}, Unrealized: ${total_unrealized:.2f}, Positions: {len(self.positions)}, Trades: {self.trade_count}, Win Rate: {win_rate:.1f}%"
        )

    def get_state(self) -> Dict[str, Any]:
        """Get current paper trading state"""
        total_unrealized = sum(p.unrealized_pnl for p in self.positions.values())
        return {
            "timestamp": datetime.now().isoformat(),
            "mode": self.mode,
            "balance": str(self.balance),
            "daily_pnl": str(self.daily_pnl),
            "total_pnl": str(self.total_pnl),
            "unrealized_pnl": str(total_unrealized),
            "positions": {
                symbol: {
                    "quantity": str(pos.quantity),
                    "entry_price": str(pos.entry_price),
                    "current_price": str(pos.current_price),
                    "unrealized_pnl": str(pos.unrealized_pnl),
                    "position_value": str(pos.position_value),
                }
                for symbol, pos in self.positions.items()
            },
            "trade_count": self.trade_count,
            "win_count": self.win_count,
            "win_rate": self.win_count / self.trade_count if self.trade_count > 0 else 0,
            "k_factor": str(self.k_factor),
            "running": self.running,
        }

    def reset_daily_stats(self):
        """Reset daily statistics"""
        self.daily_pnl = Decimal("0")
        logger.info("Daily stats reset")

    async def stop(self):
        """Stop paper trading"""
        self.running = False
        logger.info("Paper trading stopped")
        if self.exchange:
            await self.exchange.close()


async def main():
    """Main entry point"""
    runner = PaperTradingRunner()
    try:
        await runner.run()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        await runner.stop()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        await runner.stop()


if __name__ == "__main__":
    asyncio.run(main())
