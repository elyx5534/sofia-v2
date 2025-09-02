"""
🚀 ULTIMATE TRADING SYSTEM - EN İYİLERİN BİRLEŞİMİ
Tüm sistemlerin en iyi özelliklerini tek bir süper sistemde toplar
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List

import numpy as np

from .aggressive_strategies import AggressiveStrategies
from .binance_data import BinanceDataProvider

# Import best components from existing systems
from .paper_trading_engine import Order, OrderSide, OrderStatus, OrderType, Portfolio, Position
from .strategies import TradingStrategies
from .unified_execution_engine import ExecutionMode

logger = logging.getLogger(__name__)


class MarketType(Enum):
    CRYPTO = "crypto"
    STOCK = "stock"
    FOREX = "forex"
    COMMODITY = "commodity"


class SignalStrength(Enum):
    VERY_STRONG = 0.9
    STRONG = 0.7
    MEDIUM = 0.5
    WEAK = 0.3
    VERY_WEAK = 0.1


@dataclass
class UltimateConfig:
    """Ultimate system configuration combining best of all systems"""

    # Balances and currencies
    initial_balance_usd: float = 10000.0
    initial_balance_try: float = 100000.0
    use_turkish_lira: bool = True
    usd_to_try: float = 34.5

    # Trading parameters
    max_positions: int = 50
    max_position_size: float = 0.02  # 2% per position
    risk_per_trade: float = 0.01  # 1% risk

    # Strategy settings
    use_ai_predictions: bool = True
    use_aggressive_strategies: bool = True
    use_market_scanner: bool = True
    use_real_binance_data: bool = True

    # Risk management
    stop_loss_percent: float = 0.03  # 3%
    take_profit_percent: float = 0.05  # 5%
    trailing_stop_percent: float = 0.02  # 2%

    # Execution modes
    execution_mode: ExecutionMode = ExecutionMode.FULL_AUTO
    min_confidence: float = 0.6

    # Coins to trade
    active_coins: List[str] = field(
        default_factory=lambda: [
            "BTC/USDT",
            "ETH/USDT",
            "BNB/USDT",
            "SOL/USDT",
            "XRP/USDT",
            "ADA/USDT",
            "AVAX/USDT",
            "DOGE/USDT",
            "DOT/USDT",
            "MATIC/USDT",
            "PEPE/USDT",
            "FLOKI/USDT",
            "BONK/USDT",
            "WIF/USDT",
            "MEME/USDT",
        ]
    )


class UltimateTradingSystem:
    """
    🎯 EN İYİ ÖZELLİKLER:
    ✅ Paper Trading Engine'den: Position/Order management
    ✅ Unified Engine'den: AI predictions, strategy system
    ✅ Turkish Bot'tan: TRY desteği, 500+ coin
    ✅ Binance Data'dan: Gerçek zamanlı veri
    ✅ Aggressive Strategies'den: Hızlı scalping
    ✅ Multi-coin Bot'tan: Çoklu coin yönetimi
    """

    def __init__(self, config: UltimateConfig = None):
        self.config = config or UltimateConfig()

        # Portfolio management
        self.portfolio = Portfolio(
            user_id="ultimate_trader",
            balance=(
                self.config.initial_balance_try
                if self.config.use_turkish_lira
                else self.config.initial_balance_usd
            ),
        )

        # Data providers
        self.binance_provider = BinanceDataProvider()

        # Strategy engines
        self.standard_strategies = TradingStrategies()
        self.aggressive_strategies = AggressiveStrategies()

        # Trading state
        self.positions: Dict[str, Position] = {}
        self.pending_orders: List[Order] = []
        self.trade_history: List[Dict] = []
        self.active_signals: Dict[str, Dict] = {}

        # Performance metrics
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_pnl = 0.0
        self.best_trade = None
        self.worst_trade = None

        # Real-time data cache
        self.price_cache: Dict[str, float] = {}
        self.kline_cache: Dict[str, List] = {}
        self.market_stats: Dict[str, Dict] = {}

        # WebSocket connections
        self.ws_connected = False
        self.price_stream_task = None

        logger.info(
            f"🚀 Ultimate Trading System initialized with {len(self.config.active_coins)} coins"
        )

    async def start(self):
        """Start the ultimate trading system"""
        logger.info("🔥 Starting Ultimate Trading System...")

        # Initialize Binance connection
        await self.binance_provider.__aenter__()

        # Start real-time price updates
        if self.config.use_real_binance_data:
            self.price_stream_task = asyncio.create_task(self._update_prices_loop())

        # Start trading loop
        asyncio.create_task(self._trading_loop())

        logger.info("✅ System started successfully!")
        return {"status": "running", "coins": self.config.active_coins}

    async def _update_prices_loop(self):
        """Continuously update prices from Binance"""
        while True:
            try:
                # Update all coin prices
                for symbol in self.config.active_coins:
                    price = await self.binance_provider.get_price(symbol)
                    if price:
                        self.price_cache[symbol] = price

                        # Update position P&L
                        if symbol in self.positions:
                            self.positions[symbol].update_unrealized_pnl(price)

                # Get 24hr stats for top coins
                for symbol in self.config.active_coins[:10]:
                    stats = await self.binance_provider.get_24hr_stats(symbol)
                    if stats:
                        self.market_stats[symbol] = stats

                await asyncio.sleep(5)  # Update every 5 seconds

            except Exception as e:
                logger.error(f"Price update error: {e}")
                await asyncio.sleep(10)

    async def _trading_loop(self):
        """Main trading loop - analyzes and executes trades"""
        iteration = 0

        while True:
            iteration += 1

            try:
                # Analyze all active coins
                signals = await self._analyze_all_coins()

                # Filter high-confidence signals
                strong_signals = {
                    symbol: signal
                    for symbol, signal in signals.items()
                    if signal["confidence"] >= self.config.min_confidence
                }

                # Execute trades based on signals
                if strong_signals and self.config.execution_mode != ExecutionMode.MANUAL:
                    await self._execute_signals(strong_signals)

                # Update portfolio metrics
                self._update_portfolio_metrics()

                # Log status every 10 iterations
                if iteration % 10 == 0:
                    self._log_status()

                await asyncio.sleep(10)  # Analyze every 10 seconds

            except Exception as e:
                logger.error(f"Trading loop error: {e}")
                await asyncio.sleep(30)

    async def _analyze_all_coins(self) -> Dict[str, Dict]:
        """Analyze all coins and generate signals"""
        signals = {}

        for symbol in self.config.active_coins:
            try:
                # Get price history
                klines = await self.binance_provider.get_klines(symbol, "5m", 100)
                if not klines:
                    continue

                prices = [k["close"] for k in klines]
                volumes = [k["volume"] for k in klines]

                # Run multiple strategies
                signal_data = {
                    "symbol": symbol,
                    "current_price": prices[-1] if prices else 0,
                    "signals": [],
                }

                # Standard strategies
                if len(prices) >= 30:
                    # RSI
                    rsi = self.standard_strategies.calculate_rsi(prices)
                    if rsi < 30:
                        signal_data["signals"].append(("BUY", "RSI_OVERSOLD", 0.7))
                    elif rsi > 70:
                        signal_data["signals"].append(("SELL", "RSI_OVERBOUGHT", 0.7))

                    # MACD
                    macd = self.standard_strategies.calculate_macd(prices)
                    if macd["histogram"] > 0 and macd["macd"] > macd["signal"]:
                        signal_data["signals"].append(("BUY", "MACD_BULLISH", 0.6))
                    elif macd["histogram"] < 0 and macd["macd"] < macd["signal"]:
                        signal_data["signals"].append(("SELL", "MACD_BEARISH", 0.6))

                # Aggressive strategies if enabled
                if self.config.use_aggressive_strategies:
                    # Scalping
                    scalp_signal, scalp_conf = self.aggressive_strategies.scalping_signal(
                        prices, volumes
                    )
                    if scalp_signal:
                        signal_data["signals"].append((scalp_signal, "SCALPING", scalp_conf))

                    # Momentum burst
                    momentum_signal, momentum_conf = self.aggressive_strategies.momentum_burst(
                        prices
                    )
                    if momentum_signal:
                        signal_data["signals"].append((momentum_signal, "MOMENTUM", momentum_conf))

                # Calculate final signal
                if signal_data["signals"]:
                    buy_signals = [(s, r, c) for s, r, c in signal_data["signals"] if s == "BUY"]
                    sell_signals = [(s, r, c) for s, r, c in signal_data["signals"] if s == "SELL"]

                    if len(buy_signals) > len(sell_signals):
                        signal_data["action"] = "BUY"
                        signal_data["confidence"] = np.mean([c for _, _, c in buy_signals])
                        signal_data["reasoning"] = ", ".join([r for _, r, _ in buy_signals])
                    elif len(sell_signals) > len(buy_signals):
                        signal_data["action"] = "SELL"
                        signal_data["confidence"] = np.mean([c for _, _, c in sell_signals])
                        signal_data["reasoning"] = ", ".join([r for _, r, _ in sell_signals])
                    else:
                        signal_data["action"] = "HOLD"
                        signal_data["confidence"] = 0.5
                        signal_data["reasoning"] = "Mixed signals"

                    signals[symbol] = signal_data

            except Exception as e:
                logger.error(f"Analysis error for {symbol}: {e}")

        return signals

    async def _execute_signals(self, signals: Dict[str, Dict]):
        """Execute trading signals"""
        for symbol, signal in signals.items():
            try:
                current_price = signal["current_price"]
                action = signal["action"]
                confidence = signal["confidence"]

                # Check if we have a position
                has_position = symbol in self.positions

                if action == "BUY" and not has_position:
                    # Calculate position size
                    position_value = self.portfolio.balance * self.config.max_position_size
                    quantity = position_value / current_price

                    # Create order
                    order = Order(
                        id=str(uuid.uuid4()),
                        symbol=symbol,
                        side=OrderSide.BUY,
                        order_type=OrderType.MARKET,
                        quantity=quantity,
                        price=current_price,
                        status=OrderStatus.PENDING,
                        created_at=datetime.now(timezone.utc),
                    )

                    # Execute order (paper trading)
                    await self._execute_order(order)

                    logger.info(
                        f"🟢 BUY {symbol}: {quantity:.6f} @ {current_price:.2f} (Confidence: {confidence:.2%})"
                    )

                elif action == "SELL" and has_position:
                    position = self.positions[symbol]

                    # Create sell order
                    order = Order(
                        id=str(uuid.uuid4()),
                        symbol=symbol,
                        side=OrderSide.SELL,
                        order_type=OrderType.MARKET,
                        quantity=position.quantity,
                        price=current_price,
                        status=OrderStatus.PENDING,
                        created_at=datetime.now(timezone.utc),
                    )

                    # Execute order
                    await self._execute_order(order)

                    pnl = position.unrealized_pnl
                    logger.info(
                        f"🔴 SELL {symbol}: {position.quantity:.6f} @ {current_price:.2f} | P&L: {pnl:+.2f}"
                    )

            except Exception as e:
                logger.error(f"Execution error for {symbol}: {e}")

    async def _execute_order(self, order: Order):
        """Execute a paper trading order"""
        try:
            # Simulate order execution
            order.status = OrderStatus.FILLED
            order.filled_at = datetime.now(timezone.utc)
            order.filled_price = order.price
            order.filled_quantity = order.quantity
            order.fee = order.quantity * order.price * 0.001  # 0.1% fee

            if order.side == OrderSide.BUY:
                # Create position
                self.positions[order.symbol] = Position(
                    symbol=order.symbol,
                    quantity=order.quantity,
                    avg_price=order.price,
                    entry_time=order.filled_at,
                    current_price=order.price,
                )

                # Update balance
                self.portfolio.balance -= order.quantity * order.price + order.fee

            elif order.side == OrderSide.SELL:
                # Close position
                if order.symbol in self.positions:
                    position = self.positions[order.symbol]

                    # Calculate P&L
                    pnl = (order.price - position.avg_price) * order.quantity - order.fee
                    self.total_pnl += pnl

                    if pnl > 0:
                        self.winning_trades += 1
                        if not self.best_trade or pnl > self.best_trade["pnl"]:
                            self.best_trade = {"symbol": order.symbol, "pnl": pnl}
                    else:
                        self.losing_trades += 1
                        if not self.worst_trade or pnl < self.worst_trade["pnl"]:
                            self.worst_trade = {"symbol": order.symbol, "pnl": pnl}

                    # Update balance
                    self.portfolio.balance += order.quantity * order.price - order.fee

                    # Remove position
                    del self.positions[order.symbol]

            # Add to history
            self.portfolio.orders.append(order)
            self.total_trades += 1

        except Exception as e:
            logger.error(f"Order execution error: {e}")
            order.status = OrderStatus.REJECTED

    def _update_portfolio_metrics(self):
        """Update portfolio performance metrics"""
        # Calculate total value
        position_value = sum(
            pos.quantity * self.price_cache.get(pos.symbol, pos.avg_price)
            for pos in self.positions.values()
        )
        self.portfolio.total_value = self.portfolio.balance + position_value

        # Calculate win rate
        if self.total_trades > 0:
            self.portfolio.win_rate = self.winning_trades / self.total_trades

        # Update P&L
        self.portfolio.total_pnl = self.total_pnl

    def _log_status(self):
        """Log current system status"""
        currency = "TRY" if self.config.use_turkish_lira else "USD"
        symbol = "₺" if self.config.use_turkish_lira else "$"

        logger.info(
            f"""
        ╔══════════════════════════════════════╗
        ║  ULTIMATE TRADING SYSTEM STATUS      ║
        ╠══════════════════════════════════════╣
        ║ Balance: {symbol}{self.portfolio.balance:,.2f} {currency}
        ║ Positions: {len(self.positions)}
        ║ Total P&L: {symbol}{self.total_pnl:+,.2f}
        ║ Win Rate: {self.portfolio.win_rate:.1%}
        ║ Trades: {self.total_trades} (W:{self.winning_trades} L:{self.losing_trades})
        ╚══════════════════════════════════════╝
        """
        )

    def get_status(self) -> Dict:
        """Get current system status"""
        currency = "TRY" if self.config.use_turkish_lira else "USD"

        return {
            "status": "running",
            "currency": currency,
            "balance": self.portfolio.balance,
            "total_value": self.portfolio.total_value,
            "positions": len(self.positions),
            "active_coins": self.config.active_coins,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.portfolio.win_rate,
            "total_pnl": self.total_pnl,
            "best_trade": self.best_trade,
            "worst_trade": self.worst_trade,
            "execution_mode": self.config.execution_mode.value,
            "positions_detail": {
                symbol: {
                    "quantity": pos.quantity,
                    "avg_price": pos.avg_price,
                    "current_price": self.price_cache.get(symbol, pos.avg_price),
                    "unrealized_pnl": pos.unrealized_pnl,
                }
                for symbol, pos in self.positions.items()
            },
        }

    async def stop(self):
        """Stop the trading system"""
        logger.info("Stopping Ultimate Trading System...")

        # Cancel price updates
        if self.price_stream_task:
            self.price_stream_task.cancel()

        # Close Binance connection
        await self.binance_provider.__aexit__(None, None, None)

        logger.info("System stopped.")


# Global instance
ultimate_system = None


async def get_ultimate_system() -> UltimateTradingSystem:
    """Get or create the ultimate trading system instance"""
    global ultimate_system
    if ultimate_system is None:
        ultimate_system = UltimateTradingSystem()
    return ultimate_system
