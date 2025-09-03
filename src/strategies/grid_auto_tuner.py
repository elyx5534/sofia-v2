"""
Grid Trading Parameter Auto-Tuner
Dynamically adjusts grid parameters based on ATR (Average True Range) and market conditions
"""

import logging
from dataclasses import dataclass
from typing import Dict, List

logger = logging.getLogger(__name__)


@dataclass
class GridParameters:
    """Grid trading parameters"""

    num_grids: int = 10
    grid_spacing_pct: float = 0.5
    upper_price: float = 0
    lower_price: float = 0
    position_size_per_grid: float = 100
    rebalance_threshold_pct: float = 5

    def to_dict(self) -> Dict:
        return {
            "num_grids": self.num_grids,
            "grid_spacing_pct": self.grid_spacing_pct,
            "upper_price": self.upper_price,
            "lower_price": self.lower_price,
            "position_size_per_grid": self.position_size_per_grid,
            "rebalance_threshold_pct": self.rebalance_threshold_pct,
            "grid_levels": self.calculate_grid_levels(),
        }

    def calculate_grid_levels(self) -> List[float]:
        """Calculate actual grid price levels"""
        if not self.upper_price or not self.lower_price:
            return []
        levels = []
        price_range = self.upper_price - self.lower_price
        step = price_range / (self.num_grids - 1)
        for i in range(self.num_grids):
            level = self.lower_price + step * i
            levels.append(round(level, 2))
        return levels


@dataclass
class MarketConditions:
    """Current market conditions"""

    atr: float = 0
    atr_pct: float = 0
    volatility_regime: str = "normal"
    trend_direction: str = "neutral"
    volume_profile: str = "normal"
    spread_bps: float = 0


class GridAutoTuner:
    """Automatically tune grid parameters based on market conditions"""

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.GridAutoTuner")
        self.current_params = GridParameters()
        self.market_conditions = MarketConditions()
        self.atr_multipliers = {"low": 1.5, "normal": 2.0, "high": 3.0, "extreme": 4.0}
        self.grid_counts = {"low": 15, "normal": 10, "high": 7, "extreme": 5}
        self.position_scaling = {"low": 1.2, "normal": 1.0, "high": 0.7, "extreme": 0.4}

    def calculate_atr(self, candles: List[Dict], period: int = 14) -> float:
        """Calculate Average True Range"""
        if len(candles) < period + 1:
            return 0
        true_ranges = []
        for i in range(1, len(candles)):
            high = candles[i]["high"]
            low = candles[i]["low"]
            prev_close = candles[i - 1]["close"]
            true_range = max(high - low, abs(high - prev_close), abs(low - prev_close))
            true_ranges.append(true_range)
        if len(true_ranges) < period:
            return 0
        atr = sum(true_ranges[:period]) / period
        for i in range(period, len(true_ranges)):
            atr = (atr * (period - 1) + true_ranges[i]) / period
        return atr

    def classify_volatility(self, atr_pct: float) -> str:
        """Classify volatility regime based on ATR percentage"""
        if atr_pct < 1.0:
            return "low"
        elif atr_pct < 2.0:
            return "normal"
        elif atr_pct < 4.0:
            return "high"
        else:
            return "extreme"

    def detect_trend(self, candles: List[Dict], period: int = 20) -> str:
        """Detect trend direction using simple moving average"""
        if len(candles) < period:
            return "neutral"
        recent_prices = [c["close"] for c in candles[-period:]]
        older_prices = [c["close"] for c in candles[-period * 2 : -period]]
        if not older_prices:
            return "neutral"
        recent_avg = sum(recent_prices) / len(recent_prices)
        older_avg = sum(older_prices) / len(older_prices)
        change_pct = (recent_avg - older_avg) / older_avg * 100
        if change_pct > 2:
            return "up"
        elif change_pct < -2:
            return "down"
        else:
            return "neutral"

    def analyze_market(self, candles: List[Dict], current_price: float) -> MarketConditions:
        """Analyze current market conditions"""
        conditions = MarketConditions()
        atr = self.calculate_atr(candles)
        conditions.atr = atr
        conditions.atr_pct = atr / current_price * 100 if current_price > 0 else 0
        conditions.volatility_regime = self.classify_volatility(conditions.atr_pct)
        conditions.trend_direction = self.detect_trend(candles)
        if candles:
            recent_volumes = [c.get("volume", 0) for c in candles[-10:]]
            avg_volume = sum(recent_volumes) / len(recent_volumes) if recent_volumes else 0
            last_volume = candles[-1].get("volume", 0)
            if last_volume > avg_volume * 1.5:
                conditions.volume_profile = "high"
            elif last_volume < avg_volume * 0.5:
                conditions.volume_profile = "low"
            else:
                conditions.volume_profile = "normal"
        self.market_conditions = conditions
        return conditions

    def tune_parameters(
        self, symbol: str, current_price: float, candles: List[Dict], base_capital: float = 1000
    ) -> GridParameters:
        """Tune grid parameters based on market conditions"""
        conditions = self.analyze_market(candles, current_price)
        volatility = conditions.volatility_regime
        atr_multiplier = self.atr_multipliers.get(volatility, 2.0)
        grid_count = self.grid_counts.get(volatility, 10)
        position_scale = self.position_scaling.get(volatility, 1.0)
        atr = conditions.atr
        price_range = atr * atr_multiplier
        if conditions.trend_direction == "up":
            lower_price = current_price - price_range * 0.4
            upper_price = current_price + price_range * 0.6
        elif conditions.trend_direction == "down":
            lower_price = current_price - price_range * 0.6
            upper_price = current_price + price_range * 0.4
        else:
            lower_price = current_price - price_range * 0.5
            upper_price = current_price + price_range * 0.5
        grid_spacing_pct = (upper_price - lower_price) / current_price / grid_count * 100
        position_size = base_capital / grid_count * position_scale
        if conditions.volume_profile == "low":
            position_size *= 0.7
        elif conditions.volume_profile == "high":
            position_size *= 1.2
        params = GridParameters(
            num_grids=grid_count,
            grid_spacing_pct=grid_spacing_pct,
            upper_price=upper_price,
            lower_price=lower_price,
            position_size_per_grid=position_size,
            rebalance_threshold_pct=max(5, conditions.atr_pct * 2),
        )
        self.current_params = params
        self.logger.info(
            f"Grid parameters tuned for {symbol}: Volatility={volatility}, Trend={conditions.trend_direction}, Grids={grid_count}, Range=${lower_price:.2f}-${upper_price:.2f}, Size/grid=${position_size:.2f}"
        )
        return params

    def should_rebalance(self, current_price: float) -> bool:
        """Check if grid should be rebalanced"""
        if not self.current_params.upper_price or not self.current_params.lower_price:
            return True
        threshold = self.current_params.rebalance_threshold_pct / 100
        upper_threshold = self.current_params.upper_price * (1 + threshold)
        lower_threshold = self.current_params.lower_price * (1 - threshold)
        if current_price > upper_threshold or current_price < lower_threshold:
            self.logger.info(
                f"Rebalance triggered: Price ${current_price:.2f} outside range ${lower_threshold:.2f}-${upper_threshold:.2f}"
            )
            return True
        return False

    def get_grid_orders(
        self, current_price: float, existing_orders: List[Dict] = None
    ) -> List[Dict]:
        """Generate grid orders based on current parameters"""
        if not self.current_params.upper_price:
            return []
        orders = []
        grid_levels = self.current_params.calculate_grid_levels()
        existing_levels = set()
        if existing_orders:
            for order in existing_orders:
                existing_levels.add(round(order["price"], 2))
        for level in grid_levels:
            if level in existing_levels:
                continue
            if level < current_price:
                orders.append(
                    {
                        "side": "buy",
                        "price": level,
                        "quantity": self.current_params.position_size_per_grid / level,
                        "type": "limit",
                    }
                )
            elif level > current_price:
                orders.append(
                    {
                        "side": "sell",
                        "price": level,
                        "quantity": self.current_params.position_size_per_grid / level,
                        "type": "limit",
                    }
                )
        return orders

    def adjust_for_bollinger_bands(self, candles: List[Dict], period: int = 20, num_std: float = 2):
        """Adjust grid parameters using Bollinger Bands"""
        if len(candles) < period:
            return
        closes = [c["close"] for c in candles[-period:]]
        sma = sum(closes) / period
        variance = sum((x - sma) ** 2 for x in closes) / period
        std_dev = variance**0.5
        upper_band = sma + std_dev * num_std
        lower_band = sma - std_dev * num_std
        self.current_params.upper_price = upper_band
        self.current_params.lower_price = lower_band
        self.logger.info(
            f"Grid adjusted to Bollinger Bands: Range=${lower_band:.2f}-${upper_band:.2f}"
        )

    def get_performance_metrics(self, filled_orders: List[Dict]) -> Dict:
        """Calculate grid trading performance metrics"""
        if not filled_orders:
            return {"total_trades": 0, "profit_loss": 0, "win_rate": 0, "avg_profit_per_trade": 0}
        total_trades = len(filled_orders)
        profits = []
        buys = [o for o in filled_orders if o["side"] == "buy"]
        sells = [o for o in filled_orders if o["side"] == "sell"]
        for sell in sells:
            for buy in buys:
                if buy.get("matched"):
                    continue
                profit = (sell["price"] - buy["price"]) * min(sell["quantity"], buy["quantity"])
                profits.append(profit)
                buy["matched"] = True
                break
        winning_trades = sum(1 for p in profits if p > 0)
        total_profit = sum(profits)
        return {
            "total_trades": total_trades,
            "profit_loss": total_profit,
            "win_rate": winning_trades / len(profits) * 100 if profits else 0,
            "avg_profit_per_trade": total_profit / len(profits) if profits else 0,
            "grid_efficiency": len(profits) / total_trades * 100 if total_trades > 0 else 0,
        }

    def get_status(self) -> Dict:
        """Get current auto-tuner status"""
        return {
            "market_conditions": {
                "atr": self.market_conditions.atr,
                "atr_pct": self.market_conditions.atr_pct,
                "volatility": self.market_conditions.volatility_regime,
                "trend": self.market_conditions.trend_direction,
                "volume": self.market_conditions.volume_profile,
            },
            "grid_parameters": self.current_params.to_dict(),
            "tuning_config": {
                "atr_multiplier": self.atr_multipliers.get(
                    self.market_conditions.volatility_regime, 2.0
                ),
                "position_scale": self.position_scaling.get(
                    self.market_conditions.volatility_regime, 1.0
                ),
            },
        }


grid_tuner = GridAutoTuner()
