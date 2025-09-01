"""
Base strategy interface and signal definitions for Sofia V2.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field


class SignalType(str, Enum):
    """Trading signal types"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    CANCEL = "cancel"
    CLOSE = "close"


@dataclass
class Signal:
    """Trading signal representation"""
    signal_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    symbol: str = ""
    signal_type: SignalType = SignalType.HOLD
    strategy: str = ""
    price: Optional[float] = None
    quantity: float = 0.0
    strength: float = 0.0  # Signal confidence [0-1]
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    params_hash: str = ""
    
    def to_dict(self) -> Dict:
        """Convert signal to dictionary"""
        return {
            "signal_id": self.signal_id,
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "signal_type": self.signal_type.value,
            "strategy": self.strategy,
            "price": self.price,
            "quantity": self.quantity,
            "strength": self.strength,
            "reason": self.reason,
            "metadata": self.metadata,
            "params_hash": self.params_hash
        }


class StrategyState(BaseModel):
    """Base strategy state for persistence"""
    strategy_name: str
    symbol: str
    last_update: datetime
    positions: Dict[str, Any] = Field(default_factory=dict)
    metrics: Dict[str, float] = Field(default_factory=dict)
    config: Dict[str, Any] = Field(default_factory=dict)


class Strategy(ABC):
    """Abstract base class for trading strategies"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = self.__class__.__name__
        self.state: Dict[str, Any] = {}
        self.positions: Dict[str, float] = {}
        self.metrics: Dict[str, float] = {
            "total_signals": 0,
            "buy_signals": 0,
            "sell_signals": 0,
            "win_rate": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "total_pnl": 0.0
        }
        self._params_hash = self._compute_params_hash()
    
    def _compute_params_hash(self) -> str:
        """Compute hash of strategy parameters"""
        import hashlib
        import json
        params_str = json.dumps(self.config, sort_keys=True)
        return hashlib.md5(params_str.encode()).hexdigest()[:8]
    
    @abstractmethod
    def initialize(self, symbol: str, historical_data: Optional[pd.DataFrame] = None):
        """Initialize strategy with historical data"""
        pass
    
    @abstractmethod
    def on_tick(self, tick: Dict[str, Any]) -> List[Signal]:
        """Process tick data and generate signals"""
        pass
    
    @abstractmethod
    def on_bar(self, bar: Dict[str, Any]) -> List[Signal]:
        """Process bar/candle data and generate signals"""
        pass
    
    def update_metrics(self, signal: Signal, result: Optional[Dict] = None):
        """Update strategy metrics"""
        self.metrics["total_signals"] += 1
        
        if signal.signal_type == SignalType.BUY:
            self.metrics["buy_signals"] += 1
        elif signal.signal_type == SignalType.SELL:
            self.metrics["sell_signals"] += 1
        
        if result and "pnl" in result:
            self.metrics["total_pnl"] += result["pnl"]
            if result["pnl"] > 0:
                wins = self.metrics.get("wins", 0) + 1
                self.metrics["wins"] = wins
                self.metrics["win_rate"] = wins / self.metrics["total_signals"]
    
    def get_state(self) -> StrategyState:
        """Get current strategy state"""
        return StrategyState(
            strategy_name=self.name,
            symbol=self.state.get("symbol", ""),
            last_update=datetime.now(UTC),
            positions=self.positions,
            metrics=self.metrics,
            config=self.config
        )
    
    def load_state(self, state: StrategyState):
        """Load strategy state"""
        self.state = {"symbol": state.symbol}
        self.positions = state.positions
        self.metrics = state.metrics
        self.config = state.config
        self._params_hash = self._compute_params_hash()
    
    @staticmethod
    def kelly_criterion(win_prob: float, win_loss_ratio: float, 
                       kelly_fraction: float = 0.25) -> float:
        """
        Calculate position size using Kelly Criterion
        
        Args:
            win_prob: Probability of winning
            win_loss_ratio: Average win / average loss
            kelly_fraction: Fraction of Kelly to use (default 0.25 for safety)
        
        Returns:
            Fraction of capital to risk
        """
        if win_loss_ratio <= 0:
            return 0.0
        
        q = 1 - win_prob
        f = (win_prob * win_loss_ratio - q) / win_loss_ratio
        
        # Cap at kelly_fraction for safety
        return max(0, min(f * kelly_fraction, kelly_fraction))
    
    @staticmethod
    def calculate_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, 
                      period: int = 14) -> float:
        """Calculate Average True Range"""
        if len(high) < period + 1:
            return 0.0
        
        tr = np.maximum(
            high[1:] - low[1:],
            np.abs(high[1:] - close[:-1]),
            np.abs(low[1:] - close[:-1])
        )
        
        return np.mean(tr[-period:])
    
    @staticmethod
    def calculate_ema(values: np.ndarray, period: int) -> float:
        """Calculate Exponential Moving Average"""
        if len(values) < period:
            return np.mean(values) if len(values) > 0 else 0.0
        
        alpha = 2.0 / (period + 1)
        ema = values[0]
        for value in values[1:]:
            ema = alpha * value + (1 - alpha) * ema
        
        return ema