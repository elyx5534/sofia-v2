"""
Binance Futures Liquidation Hunter Bot
Profits from liquidation cascades by entering opposite positions
"""

import asyncio
import logging
import json
from decimal import Decimal
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from enum import Enum
from collections import deque
import time
import numpy as np
import aiohttp
import websockets

logger = logging.getLogger(__name__)

class LiquidationSide(Enum):
    LONG = "LONG"   # Long positions liquidated (price fell)
    SHORT = "SHORT"  # Short positions liquidated (price rose)

class PositionStatus(Enum):
    WAITING = "waiting"
    ENTERING = "entering"
    ACTIVE = "active"
    CLOSING = "closing"
    CLOSED = "closed"

class TimeFrame(Enum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"

@dataclass
class Liquidation:
    """Liquidation event data"""
    symbol: str
    side: LiquidationSide
    price: Decimal
    quantity: Decimal
    value_usdt: Decimal
    timestamp: float
    
    @property
    def is_significant(self) -> bool:
        """Check if liquidation is significant (>$100K)"""
        return self.value_usdt >= 100000

@dataclass
class LiquidationCascade:
    """Cascade of liquidations"""
    symbol: str
    side: LiquidationSide
    liquidations: List[Liquidation]
    start_time: float
    end_time: Optional[float] = None
    
    @property
    def total_value(self) -> Decimal:
        """Total value of cascade"""
        return sum(liq.value_usdt for liq in self.liquidations)
    
    @property
    def count(self) -> int:
        """Number of liquidations in cascade"""
        return len(self.liquidations)
    
    @property
    def duration(self) -> float:
        """Duration of cascade in seconds"""
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time
    
    @property
    def intensity(self) -> Decimal:
        """Cascade intensity (value per second)"""
        if self.duration > 0:
            return self.total_value / Decimal(str(self.duration))
        return Decimal(0)
    
    @property
    def avg_liquidation_size(self) -> Decimal:
        """Average liquidation size"""
        if self.count > 0:
            return self.total_value / self.count
        return Decimal(0)

@dataclass
class TradingPosition:
    """Active trading position"""
    id: str
    symbol: str
    side: str  # LONG or SHORT
    entry_price: Decimal
    current_price: Decimal
    size: Decimal
    leverage: Decimal
    take_profit: Decimal
    stop_loss: Decimal
    entry_time: float
    status: PositionStatus
    pnl: Decimal = Decimal(0)
    pnl_percentage: Decimal = Decimal(0)
    
    def update_pnl(self, current_price: Decimal):
        """Update P&L based on current price"""
        self.current_price = current_price
        
        if self.side == "LONG":
            price_change = current_price - self.entry_price
        else:
            price_change = self.entry_price - current_price
        
        self.pnl = price_change * self.size
        self.pnl_percentage = (price_change / self.entry_price) * 100 * self.leverage

@dataclass
class MarketContext:
    """Market context for decision making"""
    symbol: str
    price: Decimal
    volume_24h: Decimal
    funding_rate: Decimal
    open_interest: Decimal
    volatility: Decimal
    trend_1m: str  # UP, DOWN, NEUTRAL
    trend_5m: str
    trend_15m: str
    rsi: Decimal
    timestamp: float

class LiquidationHunterBot:
    """Hunts liquidation cascades for profit"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # Trading parameters
        self.min_liquidation_value = Decimal(str(config.get("min_liquidation_value", 100000)))
        self.cascade_wait_min = config.get("cascade_wait_min", 3)
        self.cascade_wait_max = config.get("cascade_wait_max", 7)
        self.take_profit_pct = Decimal(str(config.get("take_profit_pct", 0.015)))
        self.stop_loss_pct = Decimal(str(config.get("stop_loss_pct", 0.005)))
        self.max_hold_minutes = config.get("max_hold_minutes", 5)
        self.max_leverage = Decimal(str(config.get("max_leverage", 3)))
        
        # Filters
        self.allowed_symbols = config.get("allowed_symbols", ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"])
        self.max_funding_rate = Decimal(str(config.get("max_funding_rate", 0.0001)))  # 0.01%
        self.max_daily_trades = config.get("max_daily_trades", 10)
        
        # Smart features
        self.min_cascade_value = Decimal(str(config.get("min_cascade_value", 500000)))
        self.min_cascade_count = config.get("min_cascade_count", 3)
        self.position_size_multiplier = Decimal(str(config.get("position_size_multiplier", 0.001)))
        
        # API configuration
        self.api_key = config.get("api_key", "")
        self.api_secret = config.get("api_secret", "")
        self.testnet = config.get("testnet", True)
        
        # WebSocket URLs
        self.ws_url = "wss://fstream.binance.com/ws" if not self.testnet else "wss://stream.binancefuture.com/ws"
        self.liquidation_stream = "!forceOrder@arr"
        
        # State tracking
        self.liquidations: Dict[str, deque] = {symbol: deque(maxlen=100) for symbol in self.allowed_symbols}
        self.cascades: Dict[str, LiquidationCascade] = {}
        self.positions: Dict[str, TradingPosition] = {}
        self.market_context: Dict[str, MarketContext] = {}
        self.daily_trades = 0
        self.total_pnl = Decimal(0)
        self.win_count = 0
        self.loss_count = 0
        
        # Historical data for analysis
        self.cascade_history: List[LiquidationCascade] = []
        self.position_history: List[TradingPosition] = []
        
        # Tasks
        self.ws_task = None
        self.monitor_task = None
        self.context_task = None
    
    async def initialize(self):
        """Initialize the liquidation hunter bot"""
        logger.info("Initializing Liquidation Hunter Bot")
        
        # Start tasks
        self.ws_task = asyncio.create_task(self._connect_websocket())
        self.monitor_task = asyncio.create_task(self._monitor_positions())
        self.context_task = asyncio.create_task(self._update_market_context())
        
        logger.info("Liquidation Hunter Bot initialized")
    
    async def shutdown(self):
        """Shutdown the bot"""
        if self.ws_task:
            self.ws_task.cancel()
        if self.monitor_task:
            self.monitor_task.cancel()
        if self.context_task:
            self.context_task.cancel()
        
        # Close all positions
        for position in list(self.positions.values()):
            if position.status == PositionStatus.ACTIVE:
                await self._close_position(position, "Shutdown")
    
    async def _connect_websocket(self):
        """Connect to Binance liquidation stream"""
        while True:
            try:
                url = f"{self.ws_url}/{self.liquidation_stream}"
                
                async with websockets.connect(url) as ws:
                    logger.info("Connected to Binance liquidation stream")
                    
                    async for message in ws:
                        data = json.loads(message)
                        await self._process_liquidation(data)
                        
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                await asyncio.sleep(5)  # Reconnect after 5 seconds
    
    async def _process_liquidation(self, data: Dict):
        """Process liquidation event from WebSocket"""
        try:
            # Parse liquidation data
            order = data.get("o", {})
            symbol = order.get("s")
            
            if symbol not in self.allowed_symbols:
                return
            
            # Extract liquidation details
            side = LiquidationSide.LONG if order.get("S") == "SELL" else LiquidationSide.SHORT
            price = Decimal(str(order.get("p", 0)))
            quantity = Decimal(str(order.get("q", 0)))
            value_usdt = price * quantity
            
            liquidation = Liquidation(
                symbol=symbol,
                side=side,
                price=price,
                quantity=quantity,
                value_usdt=value_usdt,
                timestamp=time.time()
            )
            
            # Store liquidation
            self.liquidations[symbol].append(liquidation)
            
            # Check if significant
            if liquidation.is_significant:
                logger.info(
                    f"Significant liquidation: {symbol} {side.value} "
                    f"${value_usdt:,.0f} @ {price}"
                )
                
                # Update or create cascade
                await self._update_cascade(liquidation)
            
        except Exception as e:
            logger.error(f"Error processing liquidation: {e}")
    
    async def _update_cascade(self, liquidation: Liquidation):
        """Update liquidation cascade tracking"""
        symbol = liquidation.symbol
        cascade_key = f"{symbol}_{liquidation.side.value}"
        
        # Check for existing cascade
        if cascade_key in self.cascades:
            cascade = self.cascades[cascade_key]
            
            # Check if part of same cascade (within 10 seconds)
            if time.time() - cascade.liquidations[-1].timestamp < 10:
                cascade.liquidations.append(liquidation)
                
                # Check if cascade is significant enough
                if self._is_cascade_tradeable(cascade):
                    asyncio.create_task(self._execute_cascade_trade(cascade))
            else:
                # Cascade ended, start new one
                cascade.end_time = cascade.liquidations[-1].timestamp
                self.cascade_history.append(cascade)
                
                # Create new cascade
                self.cascades[cascade_key] = LiquidationCascade(
                    symbol=symbol,
                    side=liquidation.side,
                    liquidations=[liquidation],
                    start_time=time.time()
                )
        else:
            # Create new cascade
            self.cascades[cascade_key] = LiquidationCascade(
                symbol=symbol,
                side=liquidation.side,
                liquidations=[liquidation],
                start_time=time.time()
            )
    
    def _is_cascade_tradeable(self, cascade: LiquidationCascade) -> bool:
        """Check if cascade meets trading criteria"""
        return (
            cascade.total_value >= self.min_cascade_value and
            cascade.count >= self.min_cascade_count and
            cascade.duration < 30  # Not too old
        )
    
    async def _execute_cascade_trade(self, cascade: LiquidationCascade):
        """Execute trade based on cascade"""
        try:
            # Check daily trade limit
            if self.daily_trades >= self.max_daily_trades:
                logger.warning("Daily trade limit reached")
                return
            
            # Check if already have position for this symbol
            if cascade.symbol in self.positions:
                logger.info(f"Already have position for {cascade.symbol}")
                return
            
            # Get market context
            context = await self._get_market_context(cascade.symbol)
            
            # Check funding rate
            if context and abs(context.funding_rate) > self.max_funding_rate:
                logger.warning(f"Funding rate too high: {context.funding_rate}")
                return
            
            # Wait for cascade to end (smart timing)
            wait_time = await self._calculate_entry_delay(cascade)
            logger.info(f"Waiting {wait_time:.1f} seconds for cascade to end")
            await asyncio.sleep(wait_time)
            
            # Determine position side (opposite of liquidations)
            if cascade.side == LiquidationSide.LONG:
                # Longs liquidated = price fell = enter LONG for bounce
                position_side = "LONG"
            else:
                # Shorts liquidated = price rose = enter SHORT for pullback
                position_side = "SHORT"
            
            # Calculate position size based on cascade intensity
            position_size = self._calculate_position_size(cascade, context)
            
            # Get current price
            current_price = await self._get_current_price(cascade.symbol)
            
            # Calculate TP and SL
            if position_side == "LONG":
                take_profit = current_price * (1 + self.take_profit_pct)
                stop_loss = current_price * (1 - self.stop_loss_pct)
            else:
                take_profit = current_price * (1 - self.take_profit_pct)
                stop_loss = current_price * (1 + self.stop_loss_pct)
            
            # Create position
            position = TradingPosition(
                id=f"POS_{cascade.symbol}_{int(time.time()*1000)}",
                symbol=cascade.symbol,
                side=position_side,
                entry_price=current_price,
                current_price=current_price,
                size=position_size,
                leverage=self.max_leverage,
                take_profit=take_profit,
                stop_loss=stop_loss,
                entry_time=time.time(),
                status=PositionStatus.ENTERING
            )
            
            # Execute trade
            success = await self._place_order(position)
            
            if success:
                position.status = PositionStatus.ACTIVE
                self.positions[cascade.symbol] = position
                self.daily_trades += 1
                
                logger.info(
                    f"Position opened: {position.side} {position.symbol} "
                    f"Size: {position.size} @ {position.entry_price} "
                    f"TP: {position.take_profit} SL: {position.stop_loss}"
                )
                
                # Mark cascade as traded
                cascade.end_time = time.time()
                cascade_key = f"{cascade.symbol}_{cascade.side.value}"
                if cascade_key in self.cascades:
                    del self.cascades[cascade_key]
            else:
                logger.error("Failed to open position")
                
        except Exception as e:
            logger.error(f"Error executing cascade trade: {e}")
    
    async def _calculate_entry_delay(self, cascade: LiquidationCascade) -> float:
        """Calculate optimal entry delay based on cascade analysis"""
        # Base delay
        delay = self.cascade_wait_min
        
        # Adjust based on cascade intensity
        if cascade.intensity > 1000000:  # Very intense cascade
            delay = self.cascade_wait_max
        elif cascade.intensity > 500000:
            delay = (self.cascade_wait_min + self.cascade_wait_max) / 2
        
        # Adjust based on cascade duration
        if cascade.duration > 15:  # Long cascade
            delay = max(self.cascade_wait_min, delay - 1)
        
        return delay
    
    def _calculate_position_size(
        self,
        cascade: LiquidationCascade,
        context: Optional[MarketContext]
    ) -> Decimal:
        """Calculate position size based on cascade and market context"""
        # Base size from cascade value
        base_size = cascade.total_value * self.position_size_multiplier
        
        # Adjust for volatility if context available
        if context and context.volatility > 0:
            volatility_factor = min(Decimal("2"), Decimal("1") / context.volatility)
            base_size *= volatility_factor
        
        # Apply leverage
        leveraged_size = base_size / self.max_leverage
        
        # Cap at maximum position size
        max_size = Decimal(str(self.config.get("max_position_size", 10000)))
        
        return min(leveraged_size, max_size)
    
    async def _get_current_price(self, symbol: str) -> Decimal:
        """Get current price for symbol"""
        try:
            # In production, fetch from API
            # For now, return mock price
            base_prices = {
                "BTCUSDT": Decimal("65000"),
                "ETHUSDT": Decimal("3500"),
                "BNBUSDT": Decimal("600"),
                "SOLUSDT": Decimal("150")
            }
            
            return base_prices.get(symbol, Decimal("100"))
            
        except Exception as e:
            logger.error(f"Error getting price: {e}")
            return Decimal("0")
    
    async def _get_market_context(self, symbol: str) -> Optional[MarketContext]:
        """Get market context for symbol"""
        try:
            # In production, fetch real data
            # For now, return mock context
            return MarketContext(
                symbol=symbol,
                price=await self._get_current_price(symbol),
                volume_24h=Decimal("1000000000"),
                funding_rate=Decimal("0.00005"),
                open_interest=Decimal("500000000"),
                volatility=Decimal("0.02"),
                trend_1m="NEUTRAL",
                trend_5m="UP",
                trend_15m="UP",
                rsi=Decimal("50"),
                timestamp=time.time()
            )
            
        except Exception as e:
            logger.error(f"Error getting market context: {e}")
            return None
    
    async def _place_order(self, position: TradingPosition) -> bool:
        """Place order on exchange"""
        try:
            # In production, place actual order
            # For now, simulate success
            await asyncio.sleep(0.1)
            return True
            
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return False
    
    async def _close_position(self, position: TradingPosition, reason: str):
        """Close trading position"""
        try:
            # Get current price
            current_price = await self._get_current_price(position.symbol)
            position.update_pnl(current_price)
            
            # In production, place close order
            # For now, simulate close
            position.status = PositionStatus.CLOSED
            
            # Update statistics
            self.total_pnl += position.pnl
            if position.pnl > 0:
                self.win_count += 1
            else:
                self.loss_count += 1
            
            # Store in history
            self.position_history.append(position)
            
            # Remove from active positions
            if position.symbol in self.positions:
                del self.positions[position.symbol]
            
            logger.info(
                f"Position closed ({reason}): {position.symbol} "
                f"P&L: ${position.pnl:.2f} ({position.pnl_percentage:.2f}%)"
            )
            
        except Exception as e:
            logger.error(f"Error closing position: {e}")
    
    async def _monitor_positions(self):
        """Monitor active positions for TP/SL/timeout"""
        while True:
            try:
                await asyncio.sleep(1)  # Check every second
                
                for position in list(self.positions.values()):
                    if position.status != PositionStatus.ACTIVE:
                        continue
                    
                    # Update current price and P&L
                    current_price = await self._get_current_price(position.symbol)
                    position.update_pnl(current_price)
                    
                    # Check take profit
                    if position.side == "LONG":
                        if current_price >= position.take_profit:
                            await self._close_position(position, "Take Profit")
                        elif current_price <= position.stop_loss:
                            await self._close_position(position, "Stop Loss")
                    else:
                        if current_price <= position.take_profit:
                            await self._close_position(position, "Take Profit")
                        elif current_price >= position.stop_loss:
                            await self._close_position(position, "Stop Loss")
                    
                    # Check max hold time
                    hold_time = (time.time() - position.entry_time) / 60
                    if hold_time >= self.max_hold_minutes:
                        await self._close_position(position, "Max Hold Time")
                        
            except Exception as e:
                logger.error(f"Position monitoring error: {e}")
    
    async def _update_market_context(self):
        """Update market context periodically"""
        while True:
            try:
                await asyncio.sleep(30)  # Update every 30 seconds
                
                for symbol in self.allowed_symbols:
                    context = await self._get_market_context(symbol)
                    if context:
                        self.market_context[symbol] = context
                        
            except Exception as e:
                logger.error(f"Context update error: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get bot statistics"""
        win_rate = 0
        if self.win_count + self.loss_count > 0:
            win_rate = (self.win_count / (self.win_count + self.loss_count)) * 100
        
        active_positions = []
        for pos in self.positions.values():
            active_positions.append({
                "symbol": pos.symbol,
                "side": pos.side,
                "entry": float(pos.entry_price),
                "current": float(pos.current_price),
                "pnl": float(pos.pnl),
                "pnl_pct": float(pos.pnl_percentage),
                "hold_time": (time.time() - pos.entry_time) / 60
            })
        
        recent_cascades = []
        for cascade in self.cascade_history[-10:]:
            recent_cascades.append({
                "symbol": cascade.symbol,
                "side": cascade.side.value,
                "total_value": float(cascade.total_value),
                "count": cascade.count,
                "duration": cascade.duration,
                "intensity": float(cascade.intensity)
            })
        
        return {
            "total_pnl": float(self.total_pnl),
            "win_count": self.win_count,
            "loss_count": self.loss_count,
            "win_rate": win_rate,
            "daily_trades": self.daily_trades,
            "active_positions": active_positions,
            "recent_cascades": recent_cascades,
            "total_cascades_detected": len(self.cascade_history)
        }
    
    async def simulate_cascade(self, symbol: str, side: str, num_liquidations: int = 5):
        """Simulate a liquidation cascade for testing"""
        logger.info(f"Simulating {side} cascade for {symbol}")
        
        base_price = await self._get_current_price(symbol)
        
        for i in range(num_liquidations):
            # Generate liquidation
            value = Decimal(str(np.random.uniform(100000, 500000)))
            quantity = value / base_price
            
            liquidation = Liquidation(
                symbol=symbol,
                side=LiquidationSide[side],
                price=base_price * Decimal(str(1 + np.random.uniform(-0.001, 0.001))),
                quantity=quantity,
                value_usdt=value,
                timestamp=time.time()
            )
            
            # Process liquidation
            await self._update_cascade(liquidation)
            
            # Small delay between liquidations
            await asyncio.sleep(np.random.uniform(0.5, 2))
        
        logger.info(f"Cascade simulation complete for {symbol}")
    
    def analyze_cascade_patterns(self) -> Dict[str, Any]:
        """Analyze historical cascade patterns"""
        if not self.cascade_history:
            return {}
        
        # Analyze by symbol
        symbol_stats = {}
        for cascade in self.cascade_history:
            if cascade.symbol not in symbol_stats:
                symbol_stats[cascade.symbol] = {
                    "count": 0,
                    "total_value": Decimal(0),
                    "avg_duration": 0,
                    "avg_intensity": Decimal(0)
                }
            
            stats = symbol_stats[cascade.symbol]
            stats["count"] += 1
            stats["total_value"] += cascade.total_value
            stats["avg_duration"] = (
                (stats["avg_duration"] * (stats["count"] - 1) + cascade.duration) /
                stats["count"]
            )
            stats["avg_intensity"] = (
                (stats["avg_intensity"] * (stats["count"] - 1) + cascade.intensity) /
                stats["count"]
            )
        
        # Convert to float for JSON serialization
        for symbol, stats in symbol_stats.items():
            stats["total_value"] = float(stats["total_value"])
            stats["avg_intensity"] = float(stats["avg_intensity"])
        
        return {
            "total_cascades": len(self.cascade_history),
            "by_symbol": symbol_stats,
            "avg_cascade_value": float(
                sum(c.total_value for c in self.cascade_history) / len(self.cascade_history)
            ),
            "avg_cascade_duration": sum(c.duration for c in self.cascade_history) / len(self.cascade_history)
        }