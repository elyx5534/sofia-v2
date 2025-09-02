"""
Multi-Coin Trading Bot with Advanced Strategies
Supports multiple cryptocurrencies and strategies
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from .strategies import RiskManager, StrategyType, TradingStrategies

logger = logging.getLogger(__name__)


class BotStatus(Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    ERROR = "error"


class CoinPosition:
    """Track position for a single coin"""

    def __init__(self, symbol: str):
        self.symbol = symbol
        self.amount = 0.0
        self.entry_price = 0.0
        self.current_price = 0.0
        self.highest_price = 0.0
        self.unrealized_pnl = 0.0
        self.realized_pnl = 0.0
        self.trades = []

    def update_pnl(self, current_price: float):
        """Update P&L calculations"""
        self.current_price = current_price
        if self.amount > 0:
            self.unrealized_pnl = (current_price - self.entry_price) * self.amount
            self.highest_price = max(current_price, self.highest_price)


class MultiCoinBot:
    """Advanced multi-coin trading bot"""

    def __init__(self, initial_balance: float = 10000.0):
        self.status = BotStatus.STOPPED
        self.balance = initial_balance
        self.initial_balance = initial_balance
        self.positions = {}  # symbol -> CoinPosition
        self.active_coins = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]
        self.strategy_type = StrategyType.COMBINED
        self.risk_manager = RiskManager()
        self.strategies = TradingStrategies()
        self.all_trades = []
        self.indicators = {}  # Store latest indicators for each coin

    def add_coin(self, symbol: str):
        """Add a coin to track"""
        if symbol not in self.active_coins:
            self.active_coins.append(symbol)
            logger.info(f"Added {symbol} to tracking")

    def remove_coin(self, symbol: str):
        """Remove a coin from tracking"""
        if symbol in self.active_coins:
            self.active_coins.remove(symbol)
            logger.info(f"Removed {symbol} from tracking")

    def set_strategy(self, strategy: StrategyType):
        """Set trading strategy"""
        self.strategy_type = strategy
        logger.info(f"Strategy changed to {strategy.value}")

    def get_signal(self, symbol: str, prices: List[float]) -> tuple[Optional[str], Dict]:
        """Get trading signal based on selected strategy"""
        # Calculate all indicators
        indicators = {
            "rsi": self.strategies.calculate_rsi(prices),
            "macd": self.strategies.calculate_macd(prices),
            "ma_crossover": self.strategies.calculate_ma_crossover(prices),
            "bollinger": self.strategies.calculate_bollinger_bands(prices),
        }

        # Store indicators for this coin
        self.indicators[symbol] = indicators

        # Get signal based on strategy
        if self.strategy_type == StrategyType.RSI:
            signal = self.strategies.get_rsi_signal(prices)
            confidence = "high" if indicators["rsi"] < 25 or indicators["rsi"] > 75 else "medium"
            return signal, {"confidence": confidence, "indicators": indicators}

        elif self.strategy_type == StrategyType.MACD:
            signal = self.strategies.get_macd_signal(prices)
            confidence = "high" if abs(indicators["macd"]["histogram"]) > 10 else "medium"
            return signal, {"confidence": confidence, "indicators": indicators}

        elif self.strategy_type == StrategyType.MA_CROSSOVER:
            signal = self.strategies.get_ma_crossover_signal(prices)
            confidence = (
                "high" if abs(indicators["ma_crossover"]["difference_pct"]) > 1 else "medium"
            )
            return signal, {"confidence": confidence, "indicators": indicators}

        elif self.strategy_type == StrategyType.BOLLINGER:
            signal = self.strategies.get_bollinger_signal(prices)
            confidence = (
                "high"
                if indicators["bollinger"]["percent_b"] < 0.1
                or indicators["bollinger"]["percent_b"] > 0.9
                else "medium"
            )
            return signal, {"confidence": confidence, "indicators": indicators}

        else:  # COMBINED
            return self.strategies.get_combined_signal(prices)

    def execute_trade(
        self, symbol: str, signal: str, price: float, confidence: str = "medium"
    ) -> Dict:
        """Execute a paper trade for a specific coin"""
        if symbol not in self.positions:
            self.positions[symbol] = CoinPosition(symbol)

        position = self.positions[symbol]

        trade = {
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "signal": signal,
            "price": price,
            "amount": 0,
            "value": 0,
            "balance_after": self.balance,
            "pnl": 0,
            "confidence": confidence,
            "indicators": self.indicators.get(symbol, {}),
        }

        if signal == "BUY" and position.amount == 0:
            # Calculate position size based on risk
            trade_value = self.risk_manager.calculate_position_size(self.balance, confidence)

            # Don't use more than available balance
            trade_value = min(trade_value, self.balance * 0.9)  # Keep 10% reserve

            if trade_value > 100:  # Minimum trade size
                amount = trade_value / price
                self.balance -= trade_value

                position.amount = amount
                position.entry_price = price
                position.current_price = price
                position.highest_price = price

                trade["amount"] = amount
                trade["value"] = trade_value
                trade["balance_after"] = self.balance

                logger.info(f"BUY {symbol}: {amount:.6f} @ ${price:.2f} (Confidence: {confidence})")

        elif signal == "SELL" and position.amount > 0:
            # Sell all position
            trade_value = position.amount * price
            self.balance += trade_value

            # Calculate P&L
            trade["pnl"] = trade_value - (position.amount * position.entry_price)
            position.realized_pnl += trade["pnl"]

            trade["amount"] = position.amount
            trade["value"] = trade_value
            trade["balance_after"] = self.balance

            logger.info(
                f"SELL {symbol}: {position.amount:.6f} @ ${price:.2f} P&L: ${trade['pnl']:.2f}"
            )

            # Reset position
            position.amount = 0
            position.entry_price = 0
            position.unrealized_pnl = 0

        # Check risk management
        if position.amount > 0:
            # Check stop loss
            if self.risk_manager.should_stop_loss(position.entry_price, price):
                logger.warning(f"STOP LOSS triggered for {symbol}")
                return self.execute_trade(symbol, "SELL", price, "risk_management")

            # Check take profit
            if self.risk_manager.should_take_profit(position.entry_price, price):
                logger.info(f"TAKE PROFIT triggered for {symbol}")
                return self.execute_trade(symbol, "SELL", price, "risk_management")

            # Update trailing stop
            trailing_stop = self.risk_manager.update_trailing_stop(
                symbol, position.entry_price, price, position.highest_price
            )
            if self.risk_manager.should_trailing_stop(symbol, price):
                logger.info(f"TRAILING STOP triggered for {symbol} at ${trailing_stop:.2f}")
                return self.execute_trade(symbol, "SELL", price, "risk_management")

        if trade["amount"] > 0:
            position.trades.append(trade)
            self.all_trades.append(trade)

        return trade

    def get_portfolio_stats(self) -> Dict:
        """Get complete portfolio statistics"""
        # Calculate total portfolio value
        total_position_value = sum(
            pos.amount * pos.current_price for pos in self.positions.values()
        )
        total_value = self.balance + total_position_value

        # Calculate total P&L
        total_unrealized_pnl = sum(pos.unrealized_pnl for pos in self.positions.values())
        total_realized_pnl = sum(pos.realized_pnl for pos in self.positions.values())
        total_pnl = total_value - self.initial_balance
        pnl_percent = (total_pnl / self.initial_balance) * 100

        # Win/loss statistics
        winning_trades = [t for t in self.all_trades if t.get("pnl", 0) > 0]
        losing_trades = [t for t in self.all_trades if t.get("pnl", 0) < 0]

        # Position details
        positions_data = {}
        for symbol, pos in self.positions.items():
            positions_data[symbol] = {
                "amount": round(pos.amount, 6),
                "entry_price": round(pos.entry_price, 2),
                "current_price": round(pos.current_price, 2),
                "unrealized_pnl": round(pos.unrealized_pnl, 2),
                "realized_pnl": round(pos.realized_pnl, 2),
                "value": round(pos.amount * pos.current_price, 2),
            }

        return {
            "status": self.status.value,
            "strategy": self.strategy_type.value,
            "balance": round(self.balance, 2),
            "total_value": round(total_value, 2),
            "initial_balance": self.initial_balance,
            "total_pnl": round(total_pnl, 2),
            "pnl_percent": round(pnl_percent, 2),
            "unrealized_pnl": round(total_unrealized_pnl, 2),
            "realized_pnl": round(total_realized_pnl, 2),
            "total_trades": len(self.all_trades),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": (
                round(len(winning_trades) / len(self.all_trades) * 100, 1) if self.all_trades else 0
            ),
            "active_coins": self.active_coins,
            "positions": positions_data,
            "recent_trades": self.all_trades[-10:],
            "indicators": self.indicators,
            "risk_settings": {
                "stop_loss": f"{self.risk_manager.stop_loss_pct * 100}%",
                "take_profit": f"{self.risk_manager.take_profit_pct * 100}%",
                "trailing_stop": f"{self.risk_manager.trailing_stop_pct * 100}%",
                "max_position": f"{self.risk_manager.max_position_size * 100}%",
            },
        }

    def start(self):
        """Start the bot"""
        self.status = BotStatus.RUNNING
        logger.info(f"Multi-coin bot started with strategy: {self.strategy_type.value}")

    def stop(self):
        """Stop the bot"""
        self.status = BotStatus.STOPPED
        logger.info("Multi-coin bot stopped")

    def reset(self):
        """Reset bot to initial state"""
        self.balance = self.initial_balance
        self.positions = {}
        self.all_trades = []
        self.indicators = {}
        self.status = BotStatus.STOPPED
        logger.info("Bot reset to initial state")
