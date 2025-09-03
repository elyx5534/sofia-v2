"""
Strategy Engine v2 - Advanced Trading Strategies
Grid Trading, Mean Reversion, and Multi-Market Arbitrage
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


class SignalStrength(Enum):
    """Signal strength levels"""

    STRONG_BUY = 2
    BUY = 1
    NEUTRAL = 0
    SELL = -1
    STRONG_SELL = -2


@dataclass
class TradingSignal:
    """Trading signal data structure"""

    timestamp: datetime
    symbol: str
    strategy: str
    action: str
    strength: SignalStrength
    confidence: float
    size: float
    entry_price: float
    stop_loss: float
    take_profit: float
    metadata: Dict[str, Any]


class GridTradingStrategy:
    """
    Grid Trading Strategy
    Places buy/sell orders at regular price intervals
    """

    def __init__(self, config: Dict[str, Any]):
        self.symbol = config.get("symbol", "BTC/USDT")
        self.grid_levels = config.get("grid_levels", 10)
        self.grid_spacing = config.get("grid_spacing", 0.01)
        self.position_size = config.get("position_size", 0.1)
        self.upper_limit = config.get("upper_limit", 1.1)
        self.lower_limit = config.get("lower_limit", 0.9)
        self.grids = []
        self.active_orders = {}

    def initialize_grid(self, current_price: float):
        """Initialize grid levels"""
        self.grids = []
        for i in range(self.grid_levels):
            buy_price = current_price * (1 - self.grid_spacing * (i + 1))
            sell_price = current_price * (1 + self.grid_spacing * (i + 1))
            if buy_price >= current_price * self.lower_limit:
                self.grids.append(
                    {
                        "type": "buy",
                        "price": buy_price,
                        "size": self.position_size / self.grid_levels,
                        "filled": False,
                    }
                )
            if sell_price <= current_price * self.upper_limit:
                self.grids.append(
                    {
                        "type": "sell",
                        "price": sell_price,
                        "size": self.position_size / self.grid_levels,
                        "filled": False,
                    }
                )

    def generate_signal(self, current_price: float, market_data: Dict) -> Optional[TradingSignal]:
        """Generate grid trading signals"""
        if not self.grids:
            self.initialize_grid(current_price)
        for grid in self.grids:
            if not grid["filled"]:
                if grid["type"] == "buy" and current_price <= grid["price"]:
                    grid["filled"] = True
                    return TradingSignal(
                        timestamp=datetime.now(),
                        symbol=self.symbol,
                        strategy="grid_trading",
                        action="buy",
                        strength=SignalStrength.BUY,
                        confidence=0.8,
                        size=grid["size"],
                        entry_price=current_price,
                        stop_loss=current_price * 0.95,
                        take_profit=current_price * (1 + self.grid_spacing),
                        metadata={"grid_level": grid["price"]},
                    )
                elif grid["type"] == "sell" and current_price >= grid["price"]:
                    grid["filled"] = True
                    return TradingSignal(
                        timestamp=datetime.now(),
                        symbol=self.symbol,
                        strategy="grid_trading",
                        action="sell",
                        strength=SignalStrength.SELL,
                        confidence=0.8,
                        size=grid["size"],
                        entry_price=current_price,
                        stop_loss=current_price * 1.05,
                        take_profit=current_price * (1 - self.grid_spacing),
                        metadata={"grid_level": grid["price"]},
                    )
        return None

    def rebalance_grid(self, current_price: float):
        """Rebalance grid if price moves outside range"""
        max_price = max(g["price"] for g in self.grids if g["type"] == "sell")
        min_price = min(g["price"] for g in self.grids if g["type"] == "buy")
        if current_price > max_price * 0.95 or current_price < min_price * 1.05:
            self.initialize_grid(current_price)


class MeanReversionStrategy:
    """
    Mean Reversion Strategy
    Trades based on deviation from moving average
    """

    def __init__(self, config: Dict[str, Any]):
        self.symbol = config.get("symbol", "BTC/USDT")
        self.lookback_period = config.get("lookback_period", 20)
        self.entry_threshold = config.get("entry_threshold", 2.0)
        self.exit_threshold = config.get("exit_threshold", 0.5)
        self.position_size = config.get("position_size", 0.2)
        self.use_bollinger = config.get("use_bollinger", True)
        self.price_history = []

    def calculate_zscore(self, prices: List[float]) -> float:
        """Calculate z-score of current price"""
        if len(prices) < self.lookback_period:
            return 0
        mean = np.mean(prices[-self.lookback_period :])
        std = np.std(prices[-self.lookback_period :])
        if std == 0:
            return 0
        return (prices[-1] - mean) / std

    def calculate_bollinger_bands(self, prices: List[float]) -> Tuple[float, float, float]:
        """Calculate Bollinger Bands"""
        if len(prices) < self.lookback_period:
            return (0, 0, 0)
        sma = np.mean(prices[-self.lookback_period :])
        std = np.std(prices[-self.lookback_period :])
        upper_band = sma + 2 * std
        lower_band = sma - 2 * std
        return (upper_band, sma, lower_band)

    def generate_signal(self, current_price: float, market_data: Dict) -> Optional[TradingSignal]:
        """Generate mean reversion signals"""
        self.price_history.append(current_price)
        if len(self.price_history) < self.lookback_period:
            return None
        self.price_history = self.price_history[-self.lookback_period * 2 :]
        z_score = self.calculate_zscore(self.price_history)
        upper_band, middle_band, lower_band = self.calculate_bollinger_bands(self.price_history)
        signal = None
        if z_score < -self.entry_threshold or (self.use_bollinger and current_price < lower_band):
            confidence = min(0.95, abs(z_score) / 3)
            signal = TradingSignal(
                timestamp=datetime.now(),
                symbol=self.symbol,
                strategy="mean_reversion",
                action="buy",
                strength=SignalStrength.STRONG_BUY if z_score < -3 else SignalStrength.BUY,
                confidence=confidence,
                size=self.position_size * (1 + abs(z_score) / 10),
                entry_price=current_price,
                stop_loss=current_price * 0.95,
                take_profit=middle_band,
                metadata={
                    "z_score": z_score,
                    "bollinger_position": "below_lower",
                    "mean_price": middle_band,
                },
            )
        elif z_score > self.entry_threshold or (self.use_bollinger and current_price > upper_band):
            confidence = min(0.95, z_score / 3)
            signal = TradingSignal(
                timestamp=datetime.now(),
                symbol=self.symbol,
                strategy="mean_reversion",
                action="sell",
                strength=SignalStrength.STRONG_SELL if z_score > 3 else SignalStrength.SELL,
                confidence=confidence,
                size=self.position_size * (1 + z_score / 10),
                entry_price=current_price,
                stop_loss=current_price * 1.05,
                take_profit=middle_band,
                metadata={
                    "z_score": z_score,
                    "bollinger_position": "above_upper",
                    "mean_price": middle_band,
                },
            )
        elif abs(z_score) < self.exit_threshold:
            signal = TradingSignal(
                timestamp=datetime.now(),
                symbol=self.symbol,
                strategy="mean_reversion",
                action="close",
                strength=SignalStrength.NEUTRAL,
                confidence=0.7,
                size=0,
                entry_price=current_price,
                stop_loss=0,
                take_profit=0,
                metadata={"z_score": z_score, "reason": "returned_to_mean"},
            )
        return signal


class ArbitrageStrategy:
    """
    Multi-Market Arbitrage Strategy
    Exploits price differences across exchanges/pairs
    """

    def __init__(self, config: Dict[str, Any]):
        self.pairs = config.get("pairs", ["BTC/USDT", "ETH/USDT"])
        self.exchanges = config.get("exchanges", ["binance", "coinbase"])
        self.min_spread = config.get("min_spread", 0.002)
        self.position_size = config.get("position_size", 0.3)
        self.max_exposure = config.get("max_exposure", 0.5)
        self.price_cache = {}

    async def fetch_prices(self) -> Dict[str, Dict[str, float]]:
        """Fetch prices from multiple sources"""
        prices = {}
        for exchange in self.exchanges:
            prices[exchange] = {}
            for pair in self.pairs:
                base_price = 95000 if "BTC" in pair else 3300
                variation = np.random.uniform(-0.005, 0.005)
                prices[exchange][pair] = base_price * (1 + variation)
        return prices

    def find_arbitrage_opportunity(self, prices: Dict[str, Dict[str, float]]) -> Optional[Dict]:
        """Find arbitrage opportunities across exchanges"""
        opportunities = []
        for pair in self.pairs:
            exchange_prices = []
            for exchange in self.exchanges:
                if pair in prices.get(exchange, {}):
                    exchange_prices.append({"exchange": exchange, "price": prices[exchange][pair]})
            if len(exchange_prices) < 2:
                continue
            exchange_prices.sort(key=lambda x: x["price"])
            min_price = exchange_prices[0]["price"]
            max_price = exchange_prices[-1]["price"]
            spread = (max_price - min_price) / min_price
            if spread >= self.min_spread:
                opportunities.append(
                    {
                        "pair": pair,
                        "buy_exchange": exchange_prices[0]["exchange"],
                        "buy_price": min_price,
                        "sell_exchange": exchange_prices[-1]["exchange"],
                        "sell_price": max_price,
                        "spread": spread,
                        "profit_estimate": spread * self.position_size,
                    }
                )
        if opportunities:
            return max(opportunities, key=lambda x: x["spread"])
        return None

    async def generate_signal(self, market_data: Dict) -> Optional[TradingSignal]:
        """Generate arbitrage signals"""
        prices = await self.fetch_prices()
        opportunity = self.find_arbitrage_opportunity(prices)
        if opportunity:
            return TradingSignal(
                timestamp=datetime.now(),
                symbol=opportunity["pair"],
                strategy="arbitrage",
                action="arbitrage",
                strength=(
                    SignalStrength.STRONG_BUY
                    if opportunity["spread"] > 0.005
                    else SignalStrength.BUY
                ),
                confidence=min(0.95, opportunity["spread"] / 0.01),
                size=self.position_size,
                entry_price=opportunity["buy_price"],
                stop_loss=0,
                take_profit=opportunity["sell_price"],
                metadata={
                    "buy_exchange": opportunity["buy_exchange"],
                    "sell_exchange": opportunity["sell_exchange"],
                    "spread": opportunity["spread"],
                    "profit_estimate": opportunity["profit_estimate"],
                },
            )
        return None


class StrategyEngine:
    """
    Main Strategy Engine combining multiple strategies
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.strategies = []
        self.active_signals = []
        if config.get("enable_grid", True):
            self.strategies.append(GridTradingStrategy(config.get("grid_config", {})))
        if config.get("enable_mean_reversion", True):
            self.strategies.append(MeanReversionStrategy(config.get("mean_reversion_config", {})))
        if config.get("enable_arbitrage", True):
            self.strategies.append(ArbitrageStrategy(config.get("arbitrage_config", {})))

    async def evaluate_strategies(self, market_data: Dict) -> List[TradingSignal]:
        """Evaluate all strategies and generate signals"""
        signals = []
        current_price = market_data.get("price", 0)
        for strategy in self.strategies:
            try:
                if isinstance(strategy, ArbitrageStrategy):
                    signal = await strategy.generate_signal(market_data)
                else:
                    signal = strategy.generate_signal(current_price, market_data)
                if signal:
                    signals.append(signal)
            except Exception as e:
                print(f"Error in strategy {strategy.__class__.__name__}: {e}")
        return signals

    def combine_signals(self, signals: List[TradingSignal]) -> Optional[TradingSignal]:
        """Combine multiple signals into consensus signal"""
        if not signals:
            return None
        total_weight = sum(s.confidence for s in signals)
        if total_weight == 0:
            return None
        weighted_strength = sum(s.strength.value * s.confidence for s in signals) / total_weight
        if weighted_strength > 1:
            action = "buy"
            strength = SignalStrength.STRONG_BUY if weighted_strength > 1.5 else SignalStrength.BUY
        elif weighted_strength < -1:
            action = "sell"
            strength = (
                SignalStrength.STRONG_SELL if weighted_strength < -1.5 else SignalStrength.SELL
            )
        else:
            action = "hold"
            strength = SignalStrength.NEUTRAL
        combined_metadata = {
            "strategies": [s.strategy for s in signals],
            "individual_signals": len(signals),
            "consensus_score": weighted_strength,
        }
        best_signal = max(signals, key=lambda s: s.confidence)
        return TradingSignal(
            timestamp=datetime.now(),
            symbol=best_signal.symbol,
            strategy="combined",
            action=action,
            strength=strength,
            confidence=min(0.95, total_weight / len(signals)),
            size=np.mean([s.size for s in signals]),
            entry_price=best_signal.entry_price,
            stop_loss=best_signal.stop_loss,
            take_profit=best_signal.take_profit,
            metadata=combined_metadata,
        )

    async def run(self):
        """Main strategy engine loop"""
        while True:
            try:
                market_data = await self.fetch_market_data()
                signals = await self.evaluate_strategies(market_data)
                final_signal = self.combine_signals(signals)
                if final_signal:
                    print(
                        f"Signal generated: {final_signal.action} {final_signal.symbol} with confidence {final_signal.confidence:.2f}"
                    )
                    self.active_signals.append(final_signal)
            except Exception as e:
                print(f"Error in strategy engine: {e}")
            await asyncio.sleep(30)

    async def fetch_market_data(self) -> Dict:
        """Fetch current market data"""
        return {
            "price": 95000 + np.random.uniform(-1000, 1000),
            "volume": 1000000,
            "timestamp": datetime.now(),
        }


DEFAULT_CONFIG = {
    "enable_grid": True,
    "enable_mean_reversion": True,
    "enable_arbitrage": True,
    "grid_config": {
        "symbol": "BTC/USDT",
        "grid_levels": 10,
        "grid_spacing": 0.01,
        "position_size": 0.1,
    },
    "mean_reversion_config": {
        "symbol": "BTC/USDT",
        "lookback_period": 20,
        "entry_threshold": 2.0,
        "position_size": 0.2,
    },
    "arbitrage_config": {
        "pairs": ["BTC/USDT", "ETH/USDT"],
        "exchanges": ["binance", "coinbase"],
        "min_spread": 0.002,
        "position_size": 0.3,
    },
}
if __name__ == "__main__":
    engine = StrategyEngine(DEFAULT_CONFIG)
    asyncio.run(engine.run())
