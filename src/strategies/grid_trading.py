"""
Grid Trading Strategy - Stable profits in ranging markets

How it works:
- Places buy/sell orders at regular price intervals
- Profits from price oscillations
- Perfect for sideways/ranging markets
- Low risk, consistent returns
"""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel


class GridLevel(BaseModel):
    """Single grid level."""

    price: float
    side: str  # buy/sell
    quantity: float
    order_id: Optional[str] = None
    filled: bool = False
    filled_at: Optional[datetime] = None


class GridConfig(BaseModel):
    """Grid trading configuration."""

    symbol: str
    grid_levels: int = 10  # Number of grid levels
    grid_spacing: float = 0.005  # 0.5% spacing
    quantity_per_grid: float = 100  # USD per grid
    upper_price: Optional[float] = None  # Auto-calculate if None
    lower_price: Optional[float] = None  # Auto-calculate if None
    take_profit_grids: int = 2  # Close after X profitable grids
    stop_loss_pct: float = 0.1  # 10% stop loss from range


class GridStats(BaseModel):
    """Grid trading statistics."""

    total_trades: int = 0
    profitable_trades: int = 0
    total_profit: float = 0.0
    current_position: float = 0.0
    grids_filled: int = 0
    active_orders: int = 0


class GridTradingStrategy:
    """
    Grid trading strategy for ranging markets.

    Features:
    - Automatic grid placement
    - Dynamic grid adjustment
    - Risk management
    - Profit optimization
    """

    def __init__(self, config: GridConfig):
        """Initialize grid trading strategy."""
        self.config = config
        self.grids: List[GridLevel] = []
        self.active = False
        self.stats = GridStats()
        self.current_price = 0.0
        self.base_price = 0.0

    async def initialize(self, current_price: float) -> List[GridLevel]:
        """Initialize grid levels."""
        self.current_price = current_price
        self.base_price = current_price

        # Calculate grid range if not specified
        if not self.config.upper_price:
            self.config.upper_price = current_price * (
                1 + self.config.grid_spacing * self.config.grid_levels / 2
            )

        if not self.config.lower_price:
            self.config.lower_price = current_price * (
                1 - self.config.grid_spacing * self.config.grid_levels / 2
            )

        # Create grid levels
        self.grids = self._create_grid_levels()

        return self.grids

    def _create_grid_levels(self) -> List[GridLevel]:
        """Create grid levels."""
        grids = []

        # Calculate price step
        price_range = self.config.upper_price - self.config.lower_price
        price_step = price_range / (self.config.grid_levels - 1)

        # Create buy and sell grids
        for i in range(self.config.grid_levels):
            price = self.config.lower_price + (price_step * i)

            # Determine side based on current price
            if price < self.current_price:
                side = "buy"
            elif price > self.current_price:
                side = "sell"
            else:
                continue  # Skip grid at current price

            quantity = self.config.quantity_per_grid / price

            grid = GridLevel(price=price, side=side, quantity=quantity, filled=False)
            grids.append(grid)

        return grids

    def analyze(self, market_data: Dict) -> Dict:
        """Analyze market and generate signals."""
        if not self.active or not self.grids:
            return {"action": "hold"}

        # Update current price
        if "price" in market_data:
            self.current_price = market_data["price"]
        elif "close" in market_data:
            self.current_price = market_data["close"]

        # Check for grid triggers
        signal = self._check_grid_triggers()

        # Check for stop loss
        if self._check_stop_loss():
            return {"action": "close_all", "reason": "stop_loss", "price": self.current_price}

        # Check for rebalancing
        if self._should_rebalance():
            return {"action": "rebalance", "grids": self._calculate_rebalance()}

        return signal

    def _check_grid_triggers(self) -> Dict:
        """Check if any grid should be triggered."""
        for grid in self.grids:
            if grid.filled:
                continue

            # Check buy grids
            if grid.side == "buy" and self.current_price <= grid.price:
                return {
                    "action": "buy",
                    "price": grid.price,
                    "quantity": grid.quantity,
                    "grid_id": self.grids.index(grid),
                    "reason": f"Grid buy at {grid.price}",
                }

            # Check sell grids
            elif grid.side == "sell" and self.current_price >= grid.price:
                # Only sell if we have position
                if self.stats.current_position > 0:
                    return {
                        "action": "sell",
                        "price": grid.price,
                        "quantity": min(grid.quantity, self.stats.current_position),
                        "grid_id": self.grids.index(grid),
                        "reason": f"Grid sell at {grid.price}",
                    }

        return {"action": "hold"}

    def _check_stop_loss(self) -> bool:
        """Check if stop loss is triggered."""
        # Stop loss if price breaks out of range significantly
        range_break = self.config.stop_loss_pct

        if self.current_price > self.config.upper_price * (1 + range_break):
            return True
        elif self.current_price < self.config.lower_price * (1 - range_break):
            return True

        return False

    def _should_rebalance(self) -> bool:
        """Check if grid should be rebalanced."""
        # Rebalance if price moved significantly from base
        price_change = abs(self.current_price - self.base_price) / self.base_price

        if price_change > 0.1:  # 10% move
            return True

        # Rebalance if most grids are filled
        filled_count = sum(1 for g in self.grids if g.filled)
        if filled_count > len(self.grids) * 0.7:
            return True

        return False

    def _calculate_rebalance(self) -> List[GridLevel]:
        """Calculate new grid levels for rebalancing."""
        # Reset base price
        self.base_price = self.current_price

        # Recalculate range
        self.config.upper_price = self.current_price * (
            1 + self.config.grid_spacing * self.config.grid_levels / 2
        )
        self.config.lower_price = self.current_price * (
            1 - self.config.grid_spacing * self.config.grid_levels / 2
        )

        # Create new grids
        return self._create_grid_levels()

    def update_grid_status(self, grid_id: int, filled: bool, order_id: str = None) -> None:
        """Update grid status after order execution."""
        if 0 <= grid_id < len(self.grids):
            grid = self.grids[grid_id]
            grid.filled = filled
            grid.order_id = order_id

            if filled:
                grid.filled_at = datetime.utcnow()
                self.stats.grids_filled += 1

                # Update position
                if grid.side == "buy":
                    self.stats.current_position += grid.quantity
                else:
                    self.stats.current_position -= grid.quantity
                    self.stats.profitable_trades += 1

                self.stats.total_trades += 1

    def calculate_profit(self) -> float:
        """Calculate current profit from grid trading."""
        profit = 0.0

        # Calculate profit from completed buy-sell pairs
        buy_grids = [g for g in self.grids if g.side == "buy" and g.filled]
        sell_grids = [g for g in self.grids if g.side == "sell" and g.filled]

        # Match buy and sell grids
        for sell_grid in sell_grids:
            # Find corresponding buy grid
            for buy_grid in buy_grids:
                if buy_grid.quantity <= sell_grid.quantity:
                    profit += (sell_grid.price - buy_grid.price) * buy_grid.quantity

        self.stats.total_profit = profit
        return profit

    def get_active_orders(self) -> List[GridLevel]:
        """Get list of active (unfilled) grid orders."""
        return [g for g in self.grids if not g.filled]

    def get_statistics(self) -> Dict:
        """Get strategy statistics."""
        self.calculate_profit()

        return {
            "stats": self.stats.dict(),
            "config": self.config.dict(),
            "active_grids": len(self.get_active_orders()),
            "filled_grids": self.stats.grids_filled,
            "current_price": self.current_price,
            "price_range": f"{self.config.lower_price:.2f} - {self.config.upper_price:.2f}",
            "position": self.stats.current_position,
            "profit": self.stats.total_profit,
        }

    def reset(self) -> None:
        """Reset strategy."""
        self.grids = []
        self.stats = GridStats()
        self.active = False

    def start(self) -> None:
        """Start grid trading."""
        self.active = True

    def stop(self) -> None:
        """Stop grid trading."""
        self.active = False


class EnhancedGridTrading(GridTradingStrategy):
    """
    Enhanced grid trading with advanced features.

    Additional features:
    - Martingale option
    - Dynamic spacing
    - Trend following
    - Volume analysis
    """

    def __init__(self, config: GridConfig):
        """Initialize enhanced grid trading."""
        super().__init__(config)
        self.enable_martingale = False
        self.enable_dynamic_spacing = True
        self.trend_bias = 0.0  # -1 to 1

    def analyze_with_trend(self, market_data: Dict) -> Dict:
        """Analyze with trend consideration."""
        # Calculate trend from moving averages
        if "sma20" in market_data and "sma50" in market_data:
            if market_data["sma20"] > market_data["sma50"]:
                self.trend_bias = 0.3  # Bullish bias
            else:
                self.trend_bias = -0.3  # Bearish bias

        # Adjust grid based on trend
        signal = self.analyze(market_data)

        if signal["action"] == "buy" and self.trend_bias > 0:
            # Increase buy quantity in uptrend
            signal["quantity"] *= 1 + self.trend_bias
        elif signal["action"] == "sell" and self.trend_bias < 0:
            # Increase sell quantity in downtrend
            signal["quantity"] *= 1 - self.trend_bias

        return signal

    def calculate_dynamic_spacing(self, volatility: float) -> float:
        """Calculate dynamic grid spacing based on volatility."""
        # Base spacing
        base_spacing = self.config.grid_spacing

        # Adjust based on volatility (ATR or std deviation)
        if volatility < 0.01:  # Low volatility
            return base_spacing * 0.5  # Tighter grids
        elif volatility > 0.03:  # High volatility
            return base_spacing * 2.0  # Wider grids
        else:
            return base_spacing

    def apply_martingale(self, grid_id: int) -> float:
        """Apply martingale to grid quantity."""
        if not self.enable_martingale:
            return self.config.quantity_per_grid

        # Double quantity for each level away from center
        center = len(self.grids) // 2
        distance = abs(grid_id - center)

        return self.config.quantity_per_grid * (1.5**distance)

    def optimize_grid_placement(self, support_resistance: List[float]) -> None:
        """Optimize grid placement around support/resistance levels."""
        if not support_resistance:
            return

        # Cluster grids around support/resistance
        for level in support_resistance:
            # Add extra grids near important levels
            for grid in self.grids:
                if abs(grid.price - level) / level < 0.01:  # Within 1%
                    # Increase quantity at these levels
                    grid.quantity *= 1.5
