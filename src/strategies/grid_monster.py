#!/usr/bin/env python3
"""
High-Frequency Grid Trading Monster
Dynamic grid trading with volatility-based adjustments
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime, timedelta
from enum import Enum
import numpy as np
from collections import deque
import time

logger = logging.getLogger(__name__)

class GridState(Enum):
    """Grid trading state"""
    IDLE = "idle"
    SETTING_UP = "setting_up"
    ACTIVE = "active"
    ADJUSTING = "adjusting"
    RESETTING = "resetting"
    PAUSED = "paused"

class TrendDirection(Enum):
    """Market trend direction"""
    STRONG_UP = "strong_up"
    UP = "up"
    NEUTRAL = "neutral"
    DOWN = "down"
    STRONG_DOWN = "strong_down"

@dataclass
class CoinMetrics:
    """Metrics for coin selection"""
    symbol: str
    atr_percentage: float
    volume_24h: float
    trend_strength: float
    trend_direction: TrendDirection
    volatility: float
    spread: float
    liquidity_score: float
    suitable_for_grid: bool
    last_updated: datetime

@dataclass
class GridLevel:
    """Single grid level"""
    level_id: int
    price: Decimal
    side: str  # "buy" or "sell"
    order_id: Optional[str] = None
    filled: bool = False
    filled_at: Optional[datetime] = None
    paired_order_id: Optional[str] = None
    size: Decimal = Decimal("0")

@dataclass
class GridSetup:
    """Grid configuration"""
    symbol: str
    num_levels: int
    spacing_percentage: float
    upper_price: Decimal
    lower_price: Decimal
    base_size: Decimal
    total_capital: Decimal
    bb_period: int
    bb_std: float
    grid_shift_enabled: bool
    volatility_adjustment: bool

@dataclass
class ActiveGrid:
    """Active grid instance"""
    grid_id: str
    symbol: str
    setup: GridSetup
    levels: List[GridLevel]
    state: GridState
    start_time: datetime
    total_trades: int
    profit_realized: Decimal
    last_adjustment: datetime
    current_atr: float
    current_volatility: float
    bb_upper: Decimal
    bb_lower: Decimal
    bb_middle: Decimal

class GridMonster:
    """High-frequency grid trading system"""
    
    def __init__(self, config: Dict[str, Any]):
        # Selection criteria
        self.min_atr_percentage = config.get("min_atr_percentage", 3.0)
        self.min_volume_24h = config.get("min_volume_24h", 50000000)
        self.max_trend_strength = config.get("max_trend_strength", 0.7)
        
        # Grid parameters
        self.default_num_levels = config.get("default_num_levels", 20)
        self.default_spacing = config.get("default_spacing", 0.003)  # 0.3%
        self.bb_period = config.get("bb_period", 20)
        self.bb_std = config.get("bb_std", 2.0)
        
        # Dynamic adjustment
        self.volatility_multiplier = config.get("volatility_multiplier", 1.5)
        self.trend_shift_factor = config.get("trend_shift_factor", 0.002)
        self.volume_reduction_threshold = config.get("volume_reduction_threshold", 0.5)
        self.max_grid_shift = config.get("max_grid_shift", 0.05)  # 5% max shift
        
        # Risk management
        self.max_grids = config.get("max_grids", 5)
        self.max_capital_per_grid = config.get("max_capital_per_grid", 10000)
        self.stop_loss_percentage = config.get("stop_loss_percentage", 0.1)  # 10%
        self.min_profit_percentage = config.get("min_profit_percentage", 0.001)  # 0.1%
        
        # Execution
        self.order_timeout = config.get("order_timeout", 30)
        self.rebalance_interval = config.get("rebalance_interval", 300)  # 5 minutes
        self.adjustment_cooldown = config.get("adjustment_cooldown", 60)
        
        # API credentials
        self.api_key = config.get("api_key")
        self.api_secret = config.get("api_secret")
        self.testnet = config.get("testnet", True)
        
        # State
        self.active_grids: Dict[str, ActiveGrid] = {}
        self.coin_metrics: Dict[str, CoinMetrics] = {}
        self.order_map: Dict[str, Tuple[str, int]] = {}  # order_id -> (grid_id, level_id)
        self.price_history: Dict[str, deque] = {}
        self.volume_history: Dict[str, deque] = {}
        
        # Statistics
        self.total_profit = Decimal("0")
        self.total_trades = 0
        self.successful_grids = 0
        self.failed_grids = 0
        
        self.running = False
        self.tasks = []
    
    async def initialize(self):
        """Initialize the grid monster"""
        logger.info("Initializing Grid Monster...")
        
        # Initialize connection (mock for testing)
        await self._connect_exchange()
        
        # Start background tasks
        self.running = True
        self.tasks = [
            asyncio.create_task(self._coin_scanner()),
            asyncio.create_task(self._grid_monitor()),
            asyncio.create_task(self._adjustment_monitor()),
            asyncio.create_task(self._order_fill_handler())
        ]
        
        logger.info("Grid Monster initialized")
    
    async def _connect_exchange(self):
        """Connect to exchange (mock)"""
        logger.info(f"Connecting to {'testnet' if self.testnet else 'mainnet'}...")
        await asyncio.sleep(0.5)
        logger.info("Connected to exchange")
    
    async def _coin_scanner(self):
        """Continuously scan for suitable coins"""
        while self.running:
            try:
                # Get all symbols
                symbols = await self._get_active_symbols()
                
                for symbol in symbols:
                    metrics = await self._analyze_coin(symbol)
                    
                    if metrics and metrics.suitable_for_grid:
                        self.coin_metrics[symbol] = metrics
                        
                        # Start grid if not active
                        if symbol not in self.active_grids and len(self.active_grids) < self.max_grids:
                            await self.start_grid(symbol)
                
                await asyncio.sleep(30)  # Scan every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in coin scanner: {e}")
                await asyncio.sleep(10)
    
    async def _get_active_symbols(self) -> List[str]:
        """Get list of active trading symbols (mock)"""
        # Mock implementation
        return ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT", 
                "DOGEUSDT", "XRPUSDT", "DOTUSDT", "UNIUSDT", "LINKUSDT"]
    
    async def _analyze_coin(self, symbol: str) -> Optional[CoinMetrics]:
        """Analyze coin for grid suitability"""
        try:
            # Get price history
            prices = await self._get_price_history(symbol, 100)
            if not prices or len(prices) < 50:
                return None
            
            # Calculate ATR
            atr = self._calculate_atr(prices, 14)
            atr_percentage = (atr / prices[-1]) * 100
            
            # Get volume
            volume_24h = await self._get_24h_volume(symbol)
            
            # Calculate trend
            trend_direction, trend_strength = self._calculate_trend(prices)
            
            # Calculate volatility
            volatility = np.std([p for p in prices[-20:]]) / np.mean(prices[-20:])
            
            # Get spread
            spread = await self._get_spread(symbol)
            
            # Calculate liquidity score
            liquidity_score = min(volume_24h / 1000000, 100)  # Normalize to 0-100
            
            # Determine suitability
            suitable = (
                atr_percentage >= self.min_atr_percentage and
                volume_24h >= self.min_volume_24h and
                trend_strength <= self.max_trend_strength and
                trend_direction not in [TrendDirection.STRONG_UP, TrendDirection.STRONG_DOWN]
            )
            
            return CoinMetrics(
                symbol=symbol,
                atr_percentage=atr_percentage,
                volume_24h=volume_24h,
                trend_strength=trend_strength,
                trend_direction=trend_direction,
                volatility=volatility,
                spread=spread,
                liquidity_score=liquidity_score,
                suitable_for_grid=suitable,
                last_updated=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}")
            return None
    
    async def _get_price_history(self, symbol: str, limit: int) -> List[float]:
        """Get price history (mock)"""
        # Mock implementation with realistic data
        base_price = {
            "BTCUSDT": 65000, "ETHUSDT": 3500, "BNBUSDT": 600,
            "SOLUSDT": 150, "ADAUSDT": 0.65
        }.get(symbol, 100)
        
        prices = []
        for i in range(limit):
            variation = np.random.normal(0, base_price * 0.01)
            prices.append(base_price + variation)
        
        return prices
    
    def _calculate_atr(self, prices: List[float], period: int = 14) -> float:
        """Calculate Average True Range"""
        if len(prices) < period + 1:
            return 0
        
        high = prices
        low = [p * 0.995 for p in prices]  # Mock low prices
        close = prices
        
        tr = []
        for i in range(1, len(prices)):
            hl = high[i] - low[i]
            hc = abs(high[i] - close[i-1])
            lc = abs(low[i] - close[i-1])
            tr.append(max(hl, hc, lc))
        
        atr = np.mean(tr[-period:])
        return atr
    
    async def _get_24h_volume(self, symbol: str) -> float:
        """Get 24h volume (mock)"""
        base_volumes = {
            "BTCUSDT": 1500000000, "ETHUSDT": 800000000,
            "BNBUSDT": 200000000, "SOLUSDT": 300000000,
            "ADAUSDT": 150000000
        }
        return base_volumes.get(symbol, 60000000)
    
    def _calculate_trend(self, prices: List[float]) -> Tuple[TrendDirection, float]:
        """Calculate trend direction and strength"""
        if len(prices) < 20:
            return TrendDirection.NEUTRAL, 0
        
        # Simple linear regression
        x = np.arange(len(prices))
        y = np.array(prices)
        
        slope = np.polyfit(x, y, 1)[0]
        avg_price = np.mean(prices)
        
        # Normalize slope
        trend_strength = abs(slope / avg_price) * 100
        
        if slope > avg_price * 0.01:
            direction = TrendDirection.STRONG_UP if trend_strength > 1 else TrendDirection.UP
        elif slope < -avg_price * 0.01:
            direction = TrendDirection.STRONG_DOWN if trend_strength > 1 else TrendDirection.DOWN
        else:
            direction = TrendDirection.NEUTRAL
        
        return direction, min(trend_strength, 1.0)
    
    async def _get_spread(self, symbol: str) -> float:
        """Get bid-ask spread (mock)"""
        return np.random.uniform(0.0001, 0.0005)
    
    async def start_grid(self, symbol: str) -> Optional[str]:
        """Start a new grid for symbol"""
        try:
            if symbol in self.active_grids:
                logger.warning(f"Grid already active for {symbol}")
                return None
            
            logger.info(f"Starting grid for {symbol}")
            
            # Get current metrics
            metrics = self.coin_metrics.get(symbol)
            if not metrics or not metrics.suitable_for_grid:
                logger.warning(f"{symbol} not suitable for grid")
                return None
            
            # Calculate grid setup
            setup = await self._calculate_grid_setup(symbol, metrics)
            
            # Create grid levels
            levels = self._create_grid_levels(setup)
            
            # Create active grid
            grid_id = f"grid_{symbol}_{int(time.time())}"
            grid = ActiveGrid(
                grid_id=grid_id,
                symbol=symbol,
                setup=setup,
                levels=levels,
                state=GridState.SETTING_UP,
                start_time=datetime.now(),
                total_trades=0,
                profit_realized=Decimal("0"),
                last_adjustment=datetime.now(),
                current_atr=metrics.atr_percentage,
                current_volatility=metrics.volatility,
                bb_upper=setup.upper_price,
                bb_lower=setup.lower_price,
                bb_middle=(setup.upper_price + setup.lower_price) / 2
            )
            
            self.active_grids[symbol] = grid
            
            # Place initial orders
            await self._place_grid_orders(grid)
            
            grid.state = GridState.ACTIVE
            logger.info(f"Grid {grid_id} activated with {len(levels)} levels")
            
            return grid_id
            
        except Exception as e:
            logger.error(f"Error starting grid for {symbol}: {e}")
            return None
    
    async def _calculate_grid_setup(self, symbol: str, metrics: CoinMetrics) -> GridSetup:
        """Calculate optimal grid setup"""
        # Get current price
        current_price = await self._get_current_price(symbol)
        
        # Calculate Bollinger Bands
        prices = await self._get_price_history(symbol, self.bb_period)
        bb_middle = np.mean(prices)
        bb_std = np.std(prices)
        bb_upper = bb_middle + (self.bb_std * bb_std)
        bb_lower = bb_middle - (self.bb_std * bb_std)
        
        # Adjust spacing based on volatility
        base_spacing = self.default_spacing
        adjusted_spacing = base_spacing * (1 + metrics.volatility * self.volatility_multiplier)
        
        # Adjust number of levels based on range
        price_range = (bb_upper - bb_lower) / bb_middle
        num_levels = min(
            self.default_num_levels,
            int(price_range / adjusted_spacing)
        )
        
        # Calculate grid size
        total_capital = min(
            self.max_capital_per_grid,
            Decimal("10000")  # Mock available capital
        )
        
        base_size = total_capital / Decimal(str(num_levels))
        
        return GridSetup(
            symbol=symbol,
            num_levels=num_levels,
            spacing_percentage=adjusted_spacing,
            upper_price=Decimal(str(bb_upper)),
            lower_price=Decimal(str(bb_lower)),
            base_size=base_size,
            total_capital=total_capital,
            bb_period=self.bb_period,
            bb_std=self.bb_std,
            grid_shift_enabled=True,
            volatility_adjustment=True
        )
    
    async def _get_current_price(self, symbol: str) -> Decimal:
        """Get current price (mock)"""
        base_prices = {
            "BTCUSDT": 65000, "ETHUSDT": 3500, "BNBUSDT": 600,
            "SOLUSDT": 150, "ADAUSDT": 0.65
        }
        price = base_prices.get(symbol, 100)
        return Decimal(str(price * (1 + np.random.uniform(-0.001, 0.001))))
    
    def _create_grid_levels(self, setup: GridSetup) -> List[GridLevel]:
        """Create grid levels"""
        levels = []
        
        # Calculate price for each level
        price_range = setup.upper_price - setup.lower_price
        level_spacing = price_range / Decimal(str(setup.num_levels - 1))
        
        for i in range(setup.num_levels):
            price = setup.lower_price + (level_spacing * Decimal(str(i)))
            
            # Determine side (buy below middle, sell above)
            middle_price = (setup.upper_price + setup.lower_price) / 2
            side = "buy" if price < middle_price else "sell"
            
            level = GridLevel(
                level_id=i,
                price=price,
                side=side,
                size=setup.base_size / price  # Size in base currency
            )
            levels.append(level)
        
        return levels
    
    async def _place_grid_orders(self, grid: ActiveGrid):
        """Place all grid orders"""
        logger.info(f"Placing {len(grid.levels)} orders for {grid.symbol}")
        
        for level in grid.levels:
            if not level.filled and not level.order_id:
                order_id = await self._place_limit_order(
                    grid.symbol,
                    level.side,
                    level.price,
                    level.size
                )
                
                if order_id:
                    level.order_id = order_id
                    self.order_map[order_id] = (grid.grid_id, level.level_id)
                
                await asyncio.sleep(0.1)  # Rate limiting
    
    async def _place_limit_order(self, symbol: str, side: str, price: Decimal, size: Decimal) -> str:
        """Place limit order (mock)"""
        order_id = f"order_{symbol}_{side}_{int(time.time() * 1000)}"
        logger.debug(f"Placed {side} order {order_id}: {size:.4f} @ {price:.2f}")
        return order_id
    
    async def _grid_monitor(self):
        """Monitor active grids"""
        while self.running:
            try:
                for symbol, grid in list(self.active_grids.items()):
                    if grid.state == GridState.ACTIVE:
                        # Check if price left range
                        current_price = await self._get_current_price(symbol)
                        
                        if current_price > grid.setup.upper_price * Decimal("1.02") or \
                           current_price < grid.setup.lower_price * Decimal("0.98"):
                            logger.info(f"Price left range for {symbol}, resetting grid")
                            await self._reset_grid(grid)
                        
                        # Check profitability
                        if grid.profit_realized > grid.setup.total_capital * Decimal("0.1"):
                            logger.info(f"Grid {grid.grid_id} reached profit target")
                            await self._close_grid(grid)
                
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"Error in grid monitor: {e}")
                await asyncio.sleep(5)
    
    async def _adjustment_monitor(self):
        """Monitor and adjust grids based on market conditions"""
        while self.running:
            try:
                for symbol, grid in list(self.active_grids.items()):
                    if grid.state != GridState.ACTIVE:
                        continue
                    
                    # Check if adjustment needed
                    time_since_adjustment = (datetime.now() - grid.last_adjustment).seconds
                    
                    if time_since_adjustment > self.adjustment_cooldown:
                        metrics = self.coin_metrics.get(symbol)
                        if metrics:
                            await self._adjust_grid(grid, metrics)
                
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Error in adjustment monitor: {e}")
                await asyncio.sleep(30)
    
    async def _adjust_grid(self, grid: ActiveGrid, metrics: CoinMetrics):
        """Dynamically adjust grid parameters"""
        try:
            grid.state = GridState.ADJUSTING
            adjustments_made = False
            
            # 1. Volatility adjustment
            if abs(metrics.volatility - grid.current_volatility) > 0.1:
                await self._adjust_spacing(grid, metrics.volatility)
                adjustments_made = True
            
            # 2. Trend adjustment
            if metrics.trend_direction in [TrendDirection.UP, TrendDirection.DOWN]:
                await self._shift_grid(grid, metrics.trend_direction, metrics.trend_strength)
                adjustments_made = True
            
            # 3. Volume adjustment
            if metrics.volume_24h < self.min_volume_24h * self.volume_reduction_threshold:
                await self._reduce_grid_levels(grid)
                adjustments_made = True
            
            if adjustments_made:
                grid.last_adjustment = datetime.now()
                grid.current_volatility = metrics.volatility
                grid.current_atr = metrics.atr_percentage
                logger.info(f"Adjusted grid {grid.grid_id}")
            
            grid.state = GridState.ACTIVE
            
        except Exception as e:
            logger.error(f"Error adjusting grid: {e}")
            grid.state = GridState.ACTIVE
    
    async def _adjust_spacing(self, grid: ActiveGrid, new_volatility: float):
        """Adjust grid spacing based on volatility"""
        old_spacing = grid.setup.spacing_percentage
        new_spacing = self.default_spacing * (1 + new_volatility * self.volatility_multiplier)
        
        if abs(new_spacing - old_spacing) > 0.0005:  # Significant change
            logger.info(f"Adjusting spacing from {old_spacing:.3f}% to {new_spacing:.3f}%")
            
            # Cancel unfilled orders
            await self._cancel_unfilled_orders(grid)
            
            # Update spacing
            grid.setup.spacing_percentage = new_spacing
            
            # Recalculate levels
            grid.levels = self._create_grid_levels(grid.setup)
            
            # Replace orders
            await self._place_grid_orders(grid)
    
    async def _shift_grid(self, grid: ActiveGrid, direction: TrendDirection, strength: float):
        """Shift grid with trend"""
        shift_amount = self.trend_shift_factor * strength
        shift_amount = min(shift_amount, self.max_grid_shift)
        
        if direction == TrendDirection.UP:
            grid.setup.upper_price *= Decimal(str(1 + shift_amount))
            grid.setup.lower_price *= Decimal(str(1 + shift_amount))
        else:
            grid.setup.upper_price *= Decimal(str(1 - shift_amount))
            grid.setup.lower_price *= Decimal(str(1 - shift_amount))
        
        logger.info(f"Shifted grid {direction.value} by {shift_amount:.3f}%")
        
        # Update levels
        await self._update_grid_levels(grid)
    
    async def _reduce_grid_levels(self, grid: ActiveGrid):
        """Reduce number of grid levels"""
        if grid.setup.num_levels > 10:
            logger.info(f"Reducing grid levels from {grid.setup.num_levels} to {grid.setup.num_levels - 5}")
            
            # Cancel some orders
            orders_to_cancel = 5
            for level in grid.levels:
                if not level.filled and level.order_id and orders_to_cancel > 0:
                    await self._cancel_order(level.order_id)
                    level.order_id = None
                    orders_to_cancel -= 1
            
            grid.setup.num_levels -= 5
    
    async def _order_fill_handler(self):
        """Handle filled orders"""
        while self.running:
            try:
                # Check for filled orders (mock)
                for grid in self.active_grids.values():
                    for level in grid.levels:
                        if level.order_id and not level.filled:
                            # Mock fill simulation
                            if np.random.random() < 0.1:  # 10% chance of fill
                                await self._handle_filled_order(grid, level)
                
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in order fill handler: {e}")
                await asyncio.sleep(1)
    
    async def _handle_filled_order(self, grid: ActiveGrid, level: GridLevel):
        """Handle a filled order"""
        logger.info(f"Order filled: {level.side} @ {level.price:.2f}")
        
        level.filled = True
        level.filled_at = datetime.now()
        grid.total_trades += 1
        self.total_trades += 1
        
        # Place opposite order
        if level.side == "buy":
            # Place sell order above
            sell_price = level.price * Decimal(str(1 + grid.setup.spacing_percentage))
            
            # Find or create sell level
            sell_level = None
            for l in grid.levels:
                if l.side == "sell" and abs(l.price - sell_price) < sell_price * Decimal("0.0001"):
                    sell_level = l
                    break
            
            if sell_level and not sell_level.order_id:
                order_id = await self._place_limit_order(
                    grid.symbol,
                    "sell",
                    sell_level.price,
                    level.size
                )
                sell_level.order_id = order_id
                level.paired_order_id = order_id
                
        else:  # sell filled
            # Place buy order below
            buy_price = level.price * Decimal(str(1 - grid.setup.spacing_percentage))
            
            # Find or create buy level
            buy_level = None
            for l in grid.levels:
                if l.side == "buy" and abs(l.price - buy_price) < buy_price * Decimal("0.0001"):
                    buy_level = l
                    break
            
            if buy_level and not buy_level.order_id:
                order_id = await self._place_limit_order(
                    grid.symbol,
                    "buy",
                    buy_level.price,
                    level.size
                )
                buy_level.order_id = order_id
                level.paired_order_id = order_id
        
        # Calculate profit (simplified)
        if level.side == "sell":
            profit = level.size * level.price * grid.setup.spacing_percentage
            grid.profit_realized += profit
            self.total_profit += profit
    
    async def _reset_grid(self, grid: ActiveGrid):
        """Reset grid when price exits range"""
        try:
            grid.state = GridState.RESETTING
            
            # Cancel all orders
            await self._cancel_all_orders(grid)
            
            # Get new metrics
            metrics = self.coin_metrics.get(grid.symbol)
            if not metrics or not metrics.suitable_for_grid:
                await self._close_grid(grid)
                return
            
            # Recalculate setup
            grid.setup = await self._calculate_grid_setup(grid.symbol, metrics)
            
            # Create new levels
            grid.levels = self._create_grid_levels(grid.setup)
            
            # Place new orders
            await self._place_grid_orders(grid)
            
            grid.state = GridState.ACTIVE
            logger.info(f"Grid {grid.grid_id} reset successfully")
            
        except Exception as e:
            logger.error(f"Error resetting grid: {e}")
            await self._close_grid(grid)
    
    async def _close_grid(self, grid: ActiveGrid):
        """Close a grid"""
        try:
            logger.info(f"Closing grid {grid.grid_id}")
            
            # Cancel all orders
            await self._cancel_all_orders(grid)
            
            # Update statistics
            if grid.profit_realized > 0:
                self.successful_grids += 1
            else:
                self.failed_grids += 1
            
            # Remove from active grids
            del self.active_grids[grid.symbol]
            
            logger.info(f"Grid {grid.grid_id} closed. Profit: {grid.profit_realized:.2f}")
            
        except Exception as e:
            logger.error(f"Error closing grid: {e}")
    
    async def _cancel_unfilled_orders(self, grid: ActiveGrid):
        """Cancel unfilled orders"""
        for level in grid.levels:
            if level.order_id and not level.filled:
                await self._cancel_order(level.order_id)
                level.order_id = None
    
    async def _cancel_all_orders(self, grid: ActiveGrid):
        """Cancel all orders for a grid"""
        for level in grid.levels:
            if level.order_id:
                await self._cancel_order(level.order_id)
                level.order_id = None
    
    async def _cancel_order(self, order_id: str):
        """Cancel an order (mock)"""
        logger.debug(f"Cancelled order {order_id}")
        if order_id in self.order_map:
            del self.order_map[order_id]
    
    async def _update_grid_levels(self, grid: ActiveGrid):
        """Update grid levels after adjustment"""
        # Cancel current orders
        await self._cancel_unfilled_orders(grid)
        
        # Recreate levels
        grid.levels = self._create_grid_levels(grid.setup)
        
        # Place new orders
        await self._place_grid_orders(grid)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get trading statistics"""
        active_capital = sum(
            grid.setup.total_capital 
            for grid in self.active_grids.values()
        )
        
        return {
            "active_grids": len(self.active_grids),
            "total_trades": self.total_trades,
            "total_profit": float(self.total_profit),
            "successful_grids": self.successful_grids,
            "failed_grids": self.failed_grids,
            "success_rate": (self.successful_grids / max(self.successful_grids + self.failed_grids, 1)) * 100,
            "active_capital": float(active_capital),
            "suitable_coins": len([m for m in self.coin_metrics.values() if m.suitable_for_grid])
        }
    
    def get_grid_details(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get details of a specific grid"""
        grid = self.active_grids.get(symbol)
        if not grid:
            return None
        
        filled_orders = sum(1 for level in grid.levels if level.filled)
        pending_orders = sum(1 for level in grid.levels if level.order_id and not level.filled)
        
        return {
            "grid_id": grid.grid_id,
            "symbol": grid.symbol,
            "state": grid.state.value,
            "num_levels": grid.setup.num_levels,
            "spacing": grid.setup.spacing_percentage,
            "upper_price": float(grid.setup.upper_price),
            "lower_price": float(grid.setup.lower_price),
            "filled_orders": filled_orders,
            "pending_orders": pending_orders,
            "total_trades": grid.total_trades,
            "profit_realized": float(grid.profit_realized),
            "runtime_hours": (datetime.now() - grid.start_time).seconds / 3600,
            "current_atr": grid.current_atr,
            "current_volatility": grid.current_volatility
        }
    
    async def shutdown(self):
        """Shutdown the grid monster"""
        logger.info("Shutting down Grid Monster...")
        
        self.running = False
        
        # Close all grids
        for grid in list(self.active_grids.values()):
            await self._close_grid(grid)
        
        # Cancel tasks
        for task in self.tasks:
            task.cancel()
        
        await asyncio.gather(*self.tasks, return_exceptions=True)
        
        logger.info("Grid Monster shutdown complete")