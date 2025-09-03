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
    position_size: float = 0.1
    stop_loss: float = 0.02
    take_profit: float = 0.05
    trailing_stop: bool = True
    trailing_stop_distance: float = 0.01


class TradingSignal(BaseModel):
    """Trading signal from strategy."""

    symbol: str
    action: str
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
        if config.mode == TradingMode.PAPER:
            self.paper_engine = PaperTradingEngine(config.initial_balance)
            self.binance = None
        else:
            self.paper_engine = None
            binance_config = BinanceConfig()
            self.binance = BinanceConnector(binance_config)
        self.strategies: Dict[str, Strategy] = {}
        self.active_positions: Dict[str, Dict] = {}
        self.pending_orders: Dict[str, Dict] = {}
        self.signal_queue: asyncio.Queue = asyncio.Queue()
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
        if self.config.mode == TradingMode.LIVE and self.binance:
            await self.binance.connect()
        await asyncio.gather(
            self._strategy_loop(),
            self._signal_processor(),
            self._risk_monitor(),
            self._position_manager(),
        )

    async def stop(self) -> None:
        """Stop the trading bot."""
        self.is_running = False
        await self._close_all_positions()
        if self.binance:
            await self.binance.disconnect()
        self._save_state()

    async def _strategy_loop(self) -> None:
        """Run strategies and generate signals."""
        while self.is_running:
            try:
                for name, strategy in self.strategies.items():
                    symbols = strategy.get_symbols()
                    for symbol in symbols:
                        market_data = await self._get_market_data(symbol)
                        if market_data:
                            signal = strategy.analyze(market_data)
                            if signal and signal["action"] != "hold":
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
                                await self.signal_queue.put(trading_signal)
                                self.signal_history.append(trading_signal)
                await asyncio.sleep(60)
            except Exception as e:
                print(f"Strategy loop error: {e}")
                await asyncio.sleep(60)

    async def _signal_processor(self) -> None:
        """Process trading signals."""
        while self.is_running:
            try:
                signal = await asyncio.wait_for(self.signal_queue.get(), timeout=1.0)
                if await self._validate_signal(signal):
                    await self._execute_signal(signal)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"Signal processor error: {e}")

    async def _risk_monitor(self) -> None:
        """Monitor risk and positions."""
        while self.is_running:
            try:
                for symbol, position in self.active_positions.items():
                    current_price = await self._get_current_price(symbol)
                    if current_price:
                        entry_price = position["entry_price"]
                        quantity = position["quantity"]
                        pnl_pct = (current_price - entry_price) / entry_price
                        if pnl_pct <= -self.config.stop_loss:
                            print(f"Stop loss triggered for {symbol}")
                            await self._close_position(symbol, "stop_loss")
                        elif pnl_pct >= self.config.take_profit:
                            print(f"Take profit triggered for {symbol}")
                            await self._close_position(symbol, "take_profit")
                        elif self.config.trailing_stop:
                            await self._update_trailing_stop(symbol, current_price)
                await asyncio.sleep(5)
            except Exception as e:
                print(f"Risk monitor error: {e}")
                await asyncio.sleep(5)

    async def _position_manager(self) -> None:
        """Manage positions and orders."""
        while self.is_running:
            try:
                if self.config.mode == TradingMode.PAPER:
                    for symbol in self.active_positions:
                        price = await self._get_current_price(symbol)
                        if price:
                            self.paper_engine.update_market_price(symbol, price)
                elif self.binance:
                    account = await self.binance.get_account()
                await asyncio.sleep(10)
            except Exception as e:
                print(f"Position manager error: {e}")
                await asyncio.sleep(10)

    async def _validate_signal(self, signal: TradingSignal) -> bool:
        """Validate trading signal."""
        if signal.confidence < 0.6:
            return False
        if len(self.active_positions) >= self.config.max_positions:
            return False
        if signal.symbol in self.active_positions:
            return False
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
            position_value = self.config.initial_balance * self.config.position_size
            current_price = signal.price or await self._get_current_price(signal.symbol)
            quantity = position_value / current_price if current_price else 0
            if quantity <= 0:
                return
            if self.config.mode == TradingMode.PAPER:
                order = await self.paper_engine.place_order(
                    symbol=signal.symbol, side=signal.action, order_type="market", quantity=quantity
                )
                if order.status == "filled":
                    self.active_positions[signal.symbol] = {
                        "entry_price": order.average_price,
                        "quantity": order.filled_quantity,
                        "entry_time": datetime.utcnow(),
                        "signal": signal,
                    }
            elif self.binance:
                binance_order = BinanceOrder(
                    symbol=signal.symbol.replace("/", ""),
                    side=signal.action.upper(),
                    type="MARKET",
                    quantity=quantity,
                )
                result = await self.binance.place_order(binance_order)
                if result.get("status") == "FILLED":
                    self.active_positions[signal.symbol] = {
                        "entry_price": float(result["price"]),
                        "quantity": float(result["executedQty"]),
                        "entry_time": datetime.utcnow(),
                        "signal": signal,
                        "order_id": result["orderId"],
                    }
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
                order = await self.paper_engine.place_order(
                    symbol=symbol, side="sell", order_type="market", quantity=position["quantity"]
                )
            elif self.binance:
                binance_order = BinanceOrder(
                    symbol=symbol.replace("/", ""),
                    side="SELL",
                    type="MARKET",
                    quantity=position["quantity"],
                )
                await self.binance.place_order(binance_order)
            del self.active_positions[symbol]
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
        if "highest_price" not in position:
            position["highest_price"] = current_price
        else:
            position["highest_price"] = max(position["highest_price"], current_price)
        trailing_stop_price = position["highest_price"] * (1 - self.config.trailing_stop_distance)
        if current_price <= trailing_stop_price:
            print(f"Trailing stop triggered for {symbol}")
            await self._close_position(symbol, "trailing_stop")

    async def _get_market_data(self, symbol: str) -> Optional[Dict]:
        """Get market data for symbol."""
        try:
            if self.config.mode == TradingMode.PAPER:
                if not self.binance:
                    binance_config = BinanceConfig()
                    self.binance = BinanceConnector(binance_config)
                    await self.binance.connect()
                klines = await self.binance.get_klines(
                    symbol.replace("/", ""), interval="1h", limit=100
                )
                return {"symbol": symbol, "klines": klines, "timestamp": datetime.utcnow()}
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
