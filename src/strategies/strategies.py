"""
Advanced Trading Strategies
Multiple indicators and strategies for smarter trading
"""

import numpy as np
from typing import List, Dict, Optional, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class StrategyType(Enum):
    RSI = "rsi"
    MACD = "macd"
    MA_CROSSOVER = "ma_crossover"
    BOLLINGER = "bollinger"
    COMBINED = "combined"

class TradingStrategies:
    """Collection of trading strategies"""
    
    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> float:
        """Calculate RSI (Relative Strength Index)"""
        if len(prices) < period + 1:
            return 50.0
            
        prices = np.array(prices)
        deltas = np.diff(prices)
        seed = deltas[:period]
        up = seed[seed >= 0].sum() / period
        down = -seed[seed < 0].sum() / period
        
        if down == 0:
            return 100.0
            
        rs = up / down
        rsi = 100 - (100 / (1 + rs))
        
        for delta in deltas[period:]:
            if delta > 0:
                up = (up * (period - 1) + delta) / period
                down = (down * (period - 1)) / period
            else:
                up = (up * (period - 1)) / period
                down = (down * (period - 1) - delta) / period
                
            if down == 0:
                rsi = 100
            else:
                rs = up / down
                rsi = 100 - (100 / (1 + rs))
                
        return round(rsi, 2)
    
    @staticmethod
    def calculate_macd(prices: List[float]) -> Dict[str, float]:
        """Calculate MACD (Moving Average Convergence Divergence)"""
        if len(prices) < 26:
            return {"macd": 0, "signal": 0, "histogram": 0}
        
        prices = np.array(prices)
        
        # Calculate EMAs
        ema_12 = TradingStrategies._calculate_ema(prices, 12)
        ema_26 = TradingStrategies._calculate_ema(prices, 26)
        
        # MACD line
        macd_line = ema_12 - ema_26
        
        # Signal line (9-day EMA of MACD)
        signal_line = TradingStrategies._calculate_ema(macd_line[-20:], 9) if len(macd_line) >= 20 else 0
        
        # MACD histogram
        histogram = macd_line[-1] - signal_line
        
        return {
            "macd": round(macd_line[-1], 4),
            "signal": round(signal_line, 4),
            "histogram": round(histogram, 4)
        }
    
    @staticmethod
    def calculate_ma_crossover(prices: List[float], fast_period: int = 10, slow_period: int = 20) -> Dict[str, float]:
        """Calculate Moving Average Crossover"""
        if len(prices) < slow_period:
            return {"fast_ma": 0, "slow_ma": 0, "difference": 0}
        
        prices = np.array(prices)
        
        # Simple Moving Averages
        fast_ma = np.mean(prices[-fast_period:])
        slow_ma = np.mean(prices[-slow_period:])
        
        return {
            "fast_ma": round(fast_ma, 2),
            "slow_ma": round(slow_ma, 2),
            "difference": round(fast_ma - slow_ma, 2),
            "difference_pct": round((fast_ma - slow_ma) / slow_ma * 100, 2) if slow_ma > 0 else 0
        }
    
    @staticmethod
    def calculate_bollinger_bands(prices: List[float], period: int = 20, std_dev: int = 2) -> Dict[str, float]:
        """Calculate Bollinger Bands"""
        if len(prices) < period:
            current_price = prices[-1] if prices else 0
            return {
                "upper": current_price,
                "middle": current_price,
                "lower": current_price,
                "bandwidth": 0,
                "percent_b": 0.5
            }
        
        prices = np.array(prices[-period:])
        
        # Middle Band (SMA)
        middle = np.mean(prices)
        
        # Standard Deviation
        std = np.std(prices)
        
        # Upper and Lower Bands
        upper = middle + (std_dev * std)
        lower = middle - (std_dev * std)
        
        # Current price
        current_price = prices[-1]
        
        # Bandwidth and %B
        bandwidth = upper - lower
        percent_b = (current_price - lower) / bandwidth if bandwidth > 0 else 0.5
        
        return {
            "upper": round(upper, 2),
            "middle": round(middle, 2),
            "lower": round(lower, 2),
            "bandwidth": round(bandwidth, 2),
            "percent_b": round(percent_b, 3),
            "current_price": round(current_price, 2)
        }
    
    @staticmethod
    def _calculate_ema(prices: np.ndarray, period: int) -> float:
        """Calculate Exponential Moving Average"""
        if len(prices) < period:
            return np.mean(prices) if len(prices) > 0 else 0
        
        alpha = 2 / (period + 1)
        ema = prices[0]
        
        for price in prices[1:]:
            ema = alpha * price + (1 - alpha) * ema
        
        return ema
    
    @staticmethod
    def get_rsi_signal(prices: List[float], oversold: int = 30, overbought: int = 70) -> Optional[str]:
        """Get trading signal from RSI"""
        rsi = TradingStrategies.calculate_rsi(prices)
        
        if rsi < oversold:
            return "BUY"
        elif rsi > overbought:
            return "SELL"
        return None
    
    @staticmethod
    def get_macd_signal(prices: List[float]) -> Optional[str]:
        """Get trading signal from MACD"""
        macd = TradingStrategies.calculate_macd(prices)
        
        # Buy when MACD crosses above signal line
        if macd["histogram"] > 0 and abs(macd["histogram"]) > abs(macd["macd"]) * 0.01:
            return "BUY"
        # Sell when MACD crosses below signal line
        elif macd["histogram"] < 0 and abs(macd["histogram"]) > abs(macd["macd"]) * 0.01:
            return "SELL"
        return None
    
    @staticmethod
    def get_ma_crossover_signal(prices: List[float]) -> Optional[str]:
        """Get trading signal from MA Crossover"""
        ma = TradingStrategies.calculate_ma_crossover(prices)
        
        # Buy when fast MA crosses above slow MA
        if ma["difference_pct"] > 0.5:  # Fast MA is 0.5% above slow MA
            return "BUY"
        # Sell when fast MA crosses below slow MA
        elif ma["difference_pct"] < -0.5:  # Fast MA is 0.5% below slow MA
            return "SELL"
        return None
    
    @staticmethod
    def get_bollinger_signal(prices: List[float]) -> Optional[str]:
        """Get trading signal from Bollinger Bands"""
        bb = TradingStrategies.calculate_bollinger_bands(prices)
        
        # Buy when price touches lower band (oversold)
        if bb["percent_b"] < 0.2:
            return "BUY"
        # Sell when price touches upper band (overbought)
        elif bb["percent_b"] > 0.8:
            return "SELL"
        return None
    
    @staticmethod
    def get_combined_signal(prices: List[float]) -> Tuple[Optional[str], Dict[str, any]]:
        """Get combined signal from multiple strategies"""
        signals = {
            "rsi": TradingStrategies.get_rsi_signal(prices),
            "macd": TradingStrategies.get_macd_signal(prices),
            "ma_crossover": TradingStrategies.get_ma_crossover_signal(prices),
            "bollinger": TradingStrategies.get_bollinger_signal(prices)
        }
        
        # Count buy and sell signals
        buy_count = sum(1 for s in signals.values() if s == "BUY")
        sell_count = sum(1 for s in signals.values() if s == "SELL")
        
        # Strong signal if 3+ strategies agree
        if buy_count >= 3:
            return "BUY", {"confidence": "high", "buy_signals": buy_count, "signals": signals}
        elif sell_count >= 3:
            return "SELL", {"confidence": "high", "sell_signals": sell_count, "signals": signals}
        # Medium signal if 2 strategies agree
        elif buy_count >= 2:
            return "BUY", {"confidence": "medium", "buy_signals": buy_count, "signals": signals}
        elif sell_count >= 2:
            return "SELL", {"confidence": "medium", "sell_signals": sell_count, "signals": signals}
        
        return None, {"confidence": "low", "signals": signals}


class RiskManager:
    """Risk management for trading"""
    
    def __init__(self, 
                 stop_loss_pct: float = 0.02,  # 2% stop loss
                 take_profit_pct: float = 0.05,  # 5% take profit
                 trailing_stop_pct: float = 0.015,  # 1.5% trailing stop
                 max_position_size: float = 0.2):  # Max 20% of portfolio per position
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.trailing_stop_pct = trailing_stop_pct
        self.max_position_size = max_position_size
        self.positions = {}
    
    def calculate_position_size(self, balance: float, confidence: str = "medium") -> float:
        """Calculate position size based on risk and confidence"""
        base_size = balance * self.max_position_size
        
        if confidence == "high":
            return base_size
        elif confidence == "medium":
            return base_size * 0.7
        else:  # low confidence
            return base_size * 0.4
    
    def should_stop_loss(self, entry_price: float, current_price: float, position_type: str = "long") -> bool:
        """Check if stop loss should trigger"""
        if position_type == "long":
            loss_pct = (entry_price - current_price) / entry_price
            return loss_pct >= self.stop_loss_pct
        else:  # short position
            loss_pct = (current_price - entry_price) / entry_price
            return loss_pct >= self.stop_loss_pct
    
    def should_take_profit(self, entry_price: float, current_price: float, position_type: str = "long") -> bool:
        """Check if take profit should trigger"""
        if position_type == "long":
            profit_pct = (current_price - entry_price) / entry_price
            return profit_pct >= self.take_profit_pct
        else:  # short position
            profit_pct = (entry_price - current_price) / entry_price
            return profit_pct >= self.take_profit_pct
    
    def update_trailing_stop(self, symbol: str, entry_price: float, current_price: float, highest_price: float) -> float:
        """Update trailing stop price"""
        if symbol not in self.positions:
            self.positions[symbol] = {
                "entry_price": entry_price,
                "highest_price": current_price,
                "trailing_stop": entry_price * (1 - self.trailing_stop_pct)
            }
        
        position = self.positions[symbol]
        
        # Update highest price if current is higher
        if current_price > position["highest_price"]:
            position["highest_price"] = current_price
            # Update trailing stop
            position["trailing_stop"] = current_price * (1 - self.trailing_stop_pct)
        
        return position["trailing_stop"]
    
    def should_trailing_stop(self, symbol: str, current_price: float) -> bool:
        """Check if trailing stop should trigger"""
        if symbol not in self.positions:
            return False
        
        return current_price <= self.positions[symbol]["trailing_stop"]