"""
Live Trading Bot - Main trading system

Integrates:
- Binance connector
- Paper trading engine
- Strategy execution
- Risk management
- Real-time monitoring
"""

import asyncio
import json
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel

from ..exchanges.binance_connector import BinanceConfig, BinanceConnector, BinanceOrder
from ..paper_trading.paper_engine import PaperTradingEngine
from ..strategy_engine.strategies import Strategy


class TradingMode(str, Enum):
    """Trading modes."""

    PAPER = "paper"
    LIVE = "live"
    BACKTEST = "backtest"


class BotConfig(BaseModel):
    """Trading bot configuration."""

    mode: TradingMode = TradingMode.PAPER
    initial_balance: float = 10000.0
    max_positions: int = 5
    position_size: float = 0.1  # 10% per position
    stop_loss: float = 0.02  # 2% stop loss
    take_profit: float = 0.05  # 5% take profit
    trailing_stop: bool = True
    trailing_stop_distance: float = 0.01  # 1%


class TradingSignal(BaseModel):
    """Trading signal from strategy."""

    symbol: str
    action: str  # buy/sell/hold
    confidence: float
    price: Optional[float]
    quantity: Optional[float]
    reason: str
    strategy: str
    timestamp: datetime


class TradingBot:
    """
    Main trading bot that orchestrates all components.

    Features:
    - Multi-strategy support
    - Paper and live trading
    - Risk management
    - Real-time monitoring
    - Performance tracking
    """

    def __init__(self, config: BotConfig):
        """Initialize trading bot."""
        self.config = config
        self.is_running = False

        # Initialize components based on mode
        if config.mode == TradingMode.PAPER:
            self.paper_engine = PaperTradingEngine(config.initial_balance)
            self.binance = None
        else:
            self.paper_engine = None
            binance_config = BinanceConfig()  # Load from env
            self.binance = BinanceConnector(binance_config)

        self.strategies: Dict[str, Strategy] = {}
        self.active_positions: Dict[str, Dict] = {}
        self.pending_orders: Dict[str, Dict] = {}
        self.signal_queue: asyncio.Queue = asyncio.Queue()

        # Performance tracking
        self.trade_log: List[Dict] = []
        self.signal_history: List[TradingSignal] = []

    def add_strategy(self, name: str, strategy: Strategy) -> None:
        """Add a trading strategy."""
        self.strategies[name] = strategy

    def remove_strategy(self, name: str) -> None:
        """Remove a trading strategy."""
        if name in self.strategies:
            del self.strategies[name]

    async def start(self) -> None:
        """Start the trading bot."""
        self.is_running = True

        # Connect to exchange if live trading
        if self.config.mode == TradingMode.LIVE and self.binance:
            await self.binance.connect()

        # Start main loops
        await asyncio.gather(
            self._strategy_loop(),
            self._signal_processor(),
            self._risk_monitor(),
            self._position_manager(),
        )

    async def stop(self) -> None:
        """Stop the trading bot."""
        self.is_running = False

        # Close all positions
        await self._close_all_positions()

        # Disconnect from exchange
        if self.binance:
            await self.binance.disconnect()

        # Save state
        self._save_state()

    async def _strategy_loop(self) -> None:
        """Run strategies and generate signals."""
        while self.is_running:
            try:
                for name, strategy in self.strategies.items():
                    # Get market data
                    symbols = strategy.get_symbols()

                    for symbol in symbols:
                        # Get latest data
                        market_data = await self._get_market_data(symbol)

                        if market_data:
                            # Run strategy
                            signal = strategy.analyze(market_data)

                            if signal and signal["action"] != "hold":
                                # Create trading signal
                                trading_signal = TradingSignal(
                                    symbol=symbol,
                                    action=signal["action"],
                                    confidence=signal.get("confidence", 0.5),
                                    price=signal.get("price"),
                                    quantity=signal.get("quantity"),
                                    reason=signal.get("reason", ""),
                                    strategy=name,
                                    timestamp=datetime.utcnow(),
                                )

                                # Add to queue
                                await self.signal_queue.put(trading_signal)
                                self.signal_history.append(trading_signal)

                await asyncio.sleep(60)  # Run every minute

            except Exception as e:
                print(f"Strategy loop error: {e}")
                await asyncio.sleep(60)

    async def _signal_processor(self) -> None:
        """Process trading signals."""
        while self.is_running:
            try:
                # Get signal from queue
                signal = await asyncio.wait_for(self.signal_queue.get(), timeout=1.0)

                # Validate signal
                if await self._validate_signal(signal):
                    # Execute trade
                    await self._execute_signal(signal)

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"Signal processor error: {e}")

    async def _risk_monitor(self) -> None:
        """Monitor risk and positions."""
        while self.is_running:
            try:
                # Check all positions
                for symbol, position in self.active_positions.items():
                    current_price = await self._get_current_price(symbol)

                    if current_price:
                        # Update position P&L
                        entry_price = position["entry_price"]
                        quantity = position["quantity"]
                        pnl_pct = (current_price - entry_price) / entry_price

                        # Check stop loss
                        if pnl_pct <= -self.config.stop_loss:
                            print(f"Stop loss triggered for {symbol}")
                            await self._close_position(symbol, "stop_loss")

                        # Check take profit
                        elif pnl_pct >= self.config.take_profit:
                            print(f"Take profit triggered for {symbol}")
                            await self._close_position(symbol, "take_profit")

                        # Update trailing stop
                        elif self.config.trailing_stop:
                            await self._update_trailing_stop(symbol, current_price)

                await asyncio.sleep(5)  # Check every 5 seconds

            except Exception as e:
                print(f"Risk monitor error: {e}")
                await asyncio.sleep(5)

    async def _position_manager(self) -> None:
        """Manage positions and orders."""
        while self.is_running:
            try:
                # Update position values
                if self.config.mode == TradingMode.PAPER:
                    # Update paper positions
                    for symbol in self.active_positions:
                        price = await self._get_current_price(symbol)
                        if price:
                            self.paper_engine.update_market_price(symbol, price)
                # Check real positions
                elif self.binance:
                    account = await self.binance.get_account()
                    # Update positions from account

                await asyncio.sleep(10)  # Update every 10 seconds

            except Exception as e:
                print(f"Position manager error: {e}")
                await asyncio.sleep(10)

    async def _validate_signal(self, signal: TradingSignal) -> bool:
        """Validate trading signal."""
        # Check confidence threshold
        if signal.confidence < 0.6:
            return False

        # Check max positions
        if len(self.active_positions) >= self.config.max_positions:
            return False

        # Check if already have position
        if signal.symbol in self.active_positions:
            return False

        # Check available balance
        if self.config.mode == TradingMode.PAPER:
            account = self.paper_engine.get_account_summary()
            available = account["account"]["available_balance"]
        elif self.binance:
            balance = await self.binance.get_balance()
            available = balance.get("USDT", {}).get("free", 0)
        else:
            available = 0

        required = self.config.initial_balance * self.config.position_size
        if available < required:
            return False

        return True

    async def _execute_signal(self, signal: TradingSignal) -> None:
        """Execute trading signal."""
        try:
            # Calculate position size
            position_value = self.config.initial_balance * self.config.position_size
            current_price = signal.price or await self._get_current_price(signal.symbol)
            quantity = position_value / current_price if current_price else 0

            if quantity <= 0:
                return

            # Execute based on mode
            if self.config.mode == TradingMode.PAPER:
                # Paper trade
                order = await self.paper_engine.place_order(
                    symbol=signal.symbol, side=signal.action, order_type="market", quantity=quantity
                )

                if order.status == "filled":
                    # Track position
                    self.active_positions[signal.symbol] = {
                        "entry_price": order.average_price,
                        "quantity": order.filled_quantity,
                        "entry_time": datetime.utcnow(),
                        "signal": signal,
                    }

            # Live trade
            elif self.binance:
                binance_order = BinanceOrder(
                    symbol=signal.symbol.replace("/", ""),  # BTC/USDT -> BTCUSDT
                    side=signal.action.upper(),
                    type="MARKET",
                    quantity=quantity,
                )

                result = await self.binance.place_order(binance_order)

                if result.get("status") == "FILLED":
                    # Track position
                    self.active_positions[signal.symbol] = {
                        "entry_price": float(result["price"]),
                        "quantity": float(result["executedQty"]),
                        "entry_time": datetime.utcnow(),
                        "signal": signal,
                        "order_id": result["orderId"],
                    }

            # Log trade
            self.trade_log.append(
                {"signal": signal.dict(), "executed": True, "timestamp": datetime.utcnow()}
            )

        except Exception as e:
            print(f"Execution error: {e}")
            self.trade_log.append(
                {
                    "signal": signal.dict(),
                    "executed": False,
                    "error": str(e),
                    "timestamp": datetime.utcnow(),
                }
            )

    async def _close_position(self, symbol: str, reason: str) -> None:
        """Close a position."""
        if symbol not in self.active_positions:
            return

        position = self.active_positions[symbol]

        try:
            if self.config.mode == TradingMode.PAPER:
                # Paper close
                order = await self.paper_engine.place_order(
                    symbol=symbol, side="sell", order_type="market", quantity=position["quantity"]
                )

            # Live close
            elif self.binance:
                binance_order = BinanceOrder(
                    symbol=symbol.replace("/", ""),
                    side="SELL",
                    type="MARKET",
                    quantity=position["quantity"],
                )

                await self.binance.place_order(binance_order)

            # Remove from active positions
            del self.active_positions[symbol]

            # Log close
            self.trade_log.append(
                {
                    "action": "close",
                    "symbol": symbol,
                    "reason": reason,
                    "timestamp": datetime.utcnow(),
                }
            )

        except Exception as e:
            print(f"Close position error: {e}")

    async def _close_all_positions(self) -> None:
        """Close all open positions."""
        symbols = list(self.active_positions.keys())
        for symbol in symbols:
            await self._close_position(symbol, "shutdown")

    async def _update_trailing_stop(self, symbol: str, current_price: float) -> None:
        """Update trailing stop for position."""
        position = self.active_positions.get(symbol)
        if not position:
            return

        # Calculate trailing stop price
        if "highest_price" not in position:
            position["highest_price"] = current_price
        else:
            position["highest_price"] = max(position["highest_price"], current_price)

        trailing_stop_price = position["highest_price"] * (1 - self.config.trailing_stop_distance)

        # Check if stop triggered
        if current_price <= trailing_stop_price:
            print(f"Trailing stop triggered for {symbol}")
            await self._close_position(symbol, "trailing_stop")

    async def _get_market_data(self, symbol: str) -> Optional[Dict]:
        """Get market data for symbol."""
        try:
            if self.config.mode == TradingMode.PAPER:
                # Get from Binance API (public data)
                if not self.binance:
                    binance_config = BinanceConfig()
                    self.binance = BinanceConnector(binance_config)
                    await self.binance.connect()

                klines = await self.binance.get_klines(
                    symbol.replace("/", ""), interval="1h", limit=100
                )

                return {"symbol": symbol, "klines": klines, "timestamp": datetime.utcnow()}

            # Live mode
            elif self.binance:
                klines = await self.binance.get_klines(
                    symbol.replace("/", ""), interval="1h", limit=100
                )

                return {"symbol": symbol, "klines": klines, "timestamp": datetime.utcnow()}

        except Exception as e:
            print(f"Market data error: {e}")

        return None

    async def _get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for symbol."""
        try:
            if self.binance:
                ticker = await self.binance.get_ticker(symbol.replace("/", ""))
                return float(ticker.get("lastPrice", 0))
            else:
                # Mock price
                return 45000.0 if "BTC" in symbol else 100.0

        except Exception as e:
            print(f"Price error: {e}")
            return None

    def get_status(self) -> Dict:
        """Get bot status."""
        if self.config.mode == TradingMode.PAPER:
            account = self.paper_engine.get_account_summary()
        else:
            account = {"balance": 0, "positions": []}

        return {
            "mode": self.config.mode,
            "is_running": self.is_running,
            "strategies": list(self.strategies.keys()),
            "active_positions": len(self.active_positions),
            "pending_signals": self.signal_queue.qsize(),
            "account": account,
            "recent_signals": [s.dict() for s in self.signal_history[-10:]],
            "recent_trades": self.trade_log[-10:],
        }

    def _save_state(self) -> None:
        """Save bot state."""
        state = {
            "config": self.config.dict(),
            "active_positions": self.active_positions,
            "trade_log": self.trade_log,
            "signal_history": [s.dict() for s in self.signal_history],
        }

        with open("bot_state.json", "w") as f:
            json.dump(state, f, indent=2, default=str)
