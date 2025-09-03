"""
Simple RSI Trading Bot with Paper Trading
Real data, real strategy, virtual money!
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class BotStatus(Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    ERROR = "error"


class TradingBot:
    def __init__(self, symbol: str = "BTC/USDT", initial_balance: float = 10000.0):
        self.symbol = symbol
        self.status = BotStatus.STOPPED
        self.balance = initial_balance
        self.initial_balance = initial_balance
        self.position = 0.0
        self.trades = []
        self.current_price = 0.0
        self.rsi_value = 50.0
        self.last_signal = None
        self.rsi_period = 14
        self.rsi_oversold = 30
        self.rsi_overbought = 70
        self.position_size = 0.1

    def calculate_rsi(self, prices: List[float]) -> float:
        """Calculate RSI indicator"""
        if len(prices) < self.rsi_period + 1:
            return 50.0
        prices = np.array(prices)
        deltas = np.diff(prices)
        seed = deltas[: self.rsi_period]
        up = seed[seed >= 0].sum() / self.rsi_period
        down = -seed[seed < 0].sum() / self.rsi_period
        if down == 0:
            return 100.0
        rs = up / down
        rsi = 100 - 100 / (1 + rs)
        for delta in deltas[self.rsi_period :]:
            if delta > 0:
                up = (up * (self.rsi_period - 1) + delta) / self.rsi_period
                down = down * (self.rsi_period - 1) / self.rsi_period
            else:
                up = up * (self.rsi_period - 1) / self.rsi_period
                down = (down * (self.rsi_period - 1) - delta) / self.rsi_period
            if down == 0:
                rsi = 100
            else:
                rs = up / down
                rsi = 100 - 100 / (1 + rs)
        return round(rsi, 2)

    def check_signal(self, prices: List[float]) -> Optional[str]:
        """Check for buy/sell signal based on RSI"""
        self.rsi_value = self.calculate_rsi(prices)
        if self.rsi_value < self.rsi_oversold and self.position == 0:
            return "BUY"
        elif self.rsi_value > self.rsi_overbought and self.position > 0:
            return "SELL"
        return None

    def execute_trade(self, signal: str, price: float) -> Dict:
        """Execute a paper trade"""
        trade = {
            "timestamp": datetime.now().isoformat(),
            "signal": signal,
            "price": price,
            "amount": 0,
            "value": 0,
            "balance_after": self.balance,
            "pnl": 0,
            "rsi": self.rsi_value,
        }
        if signal == "BUY":
            trade_value = self.balance * self.position_size
            amount = trade_value / price
            if trade_value <= self.balance:
                self.balance -= trade_value
                self.position += amount
                trade["amount"] = amount
                trade["value"] = trade_value
                trade["balance_after"] = self.balance
                logger.info(f"BUY: {amount:.6f} @ ${price:.2f} (RSI: {self.rsi_value})")
        elif signal == "SELL" and self.position > 0:
            trade_value = self.position * price
            self.balance += trade_value
            trade["amount"] = self.position
            trade["value"] = trade_value
            trade["balance_after"] = self.balance
            if len(self.trades) > 0:
                last_buy = next((t for t in reversed(self.trades) if t["signal"] == "BUY"), None)
                if last_buy:
                    trade["pnl"] = trade_value - last_buy["value"]
            logger.info(
                f"SELL: {self.position:.6f} @ ${price:.2f} P&L: ${trade['pnl']:.2f} (RSI: {self.rsi_value})"
            )
            self.position = 0
        self.trades.append(trade)
        return trade

    def get_stats(self) -> Dict:
        """Get bot statistics"""
        total_value = self.balance + self.position * self.current_price
        total_pnl = total_value - self.initial_balance
        pnl_percent = total_pnl / self.initial_balance * 100
        winning_trades = [t for t in self.trades if t.get("pnl", 0) > 0]
        losing_trades = [t for t in self.trades if t.get("pnl", 0) < 0]
        return {
            "status": self.status.value,
            "symbol": self.symbol,
            "balance": round(self.balance, 2),
            "position": round(self.position, 6),
            "position_value": round(self.position * self.current_price, 2),
            "total_value": round(total_value, 2),
            "initial_balance": self.initial_balance,
            "total_pnl": round(total_pnl, 2),
            "pnl_percent": round(pnl_percent, 2),
            "current_price": round(self.current_price, 2),
            "rsi": round(self.rsi_value, 2),
            "total_trades": len(self.trades),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": (
                round(len(winning_trades) / len(self.trades) * 100, 1) if self.trades else 0
            ),
            "last_signal": self.last_signal,
            "trades": self.trades[-10:],
        }

    def start(self):
        """Start the bot"""
        self.status = BotStatus.RUNNING
        logger.info(f"Bot started for {self.symbol}")

    def stop(self):
        """Stop the bot"""
        self.status = BotStatus.STOPPED
        logger.info(f"Bot stopped for {self.symbol}")

    def reset(self):
        """Reset bot to initial state"""
        self.balance = self.initial_balance
        self.position = 0.0
        self.trades = []
        self.current_price = 0.0
        self.rsi_value = 50.0
        self.last_signal = None
        self.status = BotStatus.STOPPED
        logger.info("Bot reset to initial state")
