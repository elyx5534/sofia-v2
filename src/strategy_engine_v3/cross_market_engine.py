"""
Cross-Market Trading Engine - Execute strategies across multiple markets.

Manages:
- Multi-market strategy execution
- Cross-market position management
- Risk aggregation across markets
- Order routing optimization
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel

from .market_adapter import (
    MarketAdapter,
    MarketAdapterFactory,
    MarketData,
    MarketType,
    Order,
    OrderSide,
    OrderType,
    Position,
)


class CrossMarketStrategy(BaseModel):
    """Cross-market trading strategy configuration."""

    name: str
    markets: List[MarketType]
    symbols: Dict[MarketType, List[str]]  # Symbols per market
    allocation: Dict[MarketType, float]  # Capital allocation per market
    max_positions: int = 10
    risk_limit: float = 0.02  # Max 2% risk per trade
    correlation_threshold: float = 0.7


class CrossMarketSignal(BaseModel):
    """Trading signal for cross-market execution."""

    timestamp: datetime
    market_type: MarketType
    symbol: str
    action: str  # buy/sell/hold
    strength: float  # Signal strength 0-1
    quantity: float
    price: Optional[float] = None
    reason: str


class CrossMarketPosition(BaseModel):
    """Aggregated position across markets."""

    positions: List[Position]
    total_value: float
    total_pnl: float
    risk_exposure: float
    correlation_risk: float


class CrossMarketEngine:
    """
    Engine for executing strategies across multiple markets.

    Features:
    - Simultaneous multi-market execution
    - Cross-market risk management
    - Position correlation analysis
    - Smart order routing
    """

    def __init__(self):
        """Initialize cross-market engine."""
        self.adapters: Dict[MarketType, MarketAdapter] = {}
        self.active_strategies: Dict[str, CrossMarketStrategy] = {}
        self.positions: Dict[str, CrossMarketPosition] = {}
        self.signals_queue: asyncio.Queue = asyncio.Queue()
        self.is_running = False

    async def add_market(self, market_type: MarketType, config: Dict) -> bool:
        """Add a market adapter to the engine."""
        try:
            adapter = MarketAdapterFactory.create(market_type, config)
            if await adapter.connect():
                self.adapters[market_type] = adapter
                return True
        except Exception as e:
            print(f"Failed to add market {market_type}: {e}")
        return False

    async def remove_market(self, market_type: MarketType) -> None:
        """Remove a market adapter from the engine."""
        if market_type in self.adapters:
            await self.adapters[market_type].disconnect()
            del self.adapters[market_type]

    def add_strategy(self, strategy: CrossMarketStrategy) -> None:
        """Add a cross-market strategy."""
        self.active_strategies[strategy.name] = strategy

    def remove_strategy(self, strategy_name: str) -> None:
        """Remove a strategy."""
        if strategy_name in self.active_strategies:
            del self.active_strategies[strategy_name]

    async def get_market_data(self, market_type: MarketType, symbol: str) -> Optional[MarketData]:
        """Get market data for a specific symbol."""
        adapter = self.adapters.get(market_type)
        if adapter:
            return await adapter.get_market_data(symbol)
        return None

    async def execute_signal(self, signal: CrossMarketSignal) -> Optional[Order]:
        """Execute a trading signal."""
        adapter = self.adapters.get(signal.market_type)
        if not adapter:
            return None

        # Create order from signal
        order = Order(
            symbol=signal.symbol,
            market_type=signal.market_type,
            side=OrderSide.BUY if signal.action == "buy" else OrderSide.SELL,
            type=OrderType.LIMIT if signal.price else OrderType.MARKET,
            quantity=signal.quantity,
            price=signal.price,
        )

        # Risk check
        if not await self._check_risk(order):
            return None

        # Execute order
        return await adapter.place_order(order)

    async def _check_risk(self, order: Order) -> bool:
        """Check if order passes risk management rules."""
        # Get current positions
        positions = await self.get_all_positions()

        # Calculate total exposure
        total_exposure = sum(p.quantity * p.current_price for p in positions)

        # Check position limits
        if len(positions) >= 10:  # Max positions
            return False

        # Check exposure limits
        order_value = order.quantity * (order.price or 0)
        if total_exposure + order_value > 100000:  # Max exposure
            return False

        return True

    async def get_all_positions(self) -> List[Position]:
        """Get all positions across all markets."""
        all_positions = []
        for adapter in self.adapters.values():
            positions = await adapter.get_positions()
            all_positions.extend(positions)
        return all_positions

    async def get_aggregated_position(self, symbol: str) -> CrossMarketPosition:
        """Get aggregated position for a symbol across markets."""
        positions = []
        total_value = 0.0
        total_pnl = 0.0

        for adapter in self.adapters.values():
            market_positions = await adapter.get_positions()
            symbol_positions = [p for p in market_positions if p.symbol == symbol]
            positions.extend(symbol_positions)

            for pos in symbol_positions:
                value = pos.quantity * pos.current_price
                total_value += value
                total_pnl += pos.unrealized_pnl + pos.realized_pnl

        return CrossMarketPosition(
            positions=positions,
            total_value=total_value,
            total_pnl=total_pnl,
            risk_exposure=total_value * 0.02,  # 2% risk
            correlation_risk=0.0,  # TODO: Calculate correlation
        )

    async def get_total_balance(self) -> Dict[str, float]:
        """Get total balance across all markets."""
        total_balance = {}

        for market_type, adapter in self.adapters.items():
            balance = await adapter.get_balance()
            for currency, amount in balance.items():
                key = f"{market_type.value}_{currency}"
                total_balance[key] = amount

        return total_balance

    async def analyze_correlations(self) -> Dict[str, float]:
        """Analyze correlations between positions."""
        positions = await self.get_all_positions()
        correlations = {}

        # Simple correlation analysis (mock for now)
        for i, pos1 in enumerate(positions):
            for pos2 in positions[i + 1 :]:
                pair = f"{pos1.symbol}_{pos2.symbol}"
                # Mock correlation value
                correlations[pair] = 0.5

        return correlations

    async def optimize_execution(self, signals: List[CrossMarketSignal]) -> List[Order]:
        """Optimize execution across multiple signals."""
        # Sort signals by strength
        sorted_signals = sorted(signals, key=lambda s: s.strength, reverse=True)

        orders = []
        for signal in sorted_signals:
            # Check if we can execute
            if await self._check_risk_for_signal(signal):
                order = await self.execute_signal(signal)
                if order:
                    orders.append(order)

        return orders

    async def _check_risk_for_signal(self, signal: CrossMarketSignal) -> bool:
        """Check risk for a specific signal."""
        # Simplified risk check
        return signal.strength > 0.6

    async def rebalance_portfolio(self) -> List[Order]:
        """Rebalance portfolio according to strategy allocations."""
        orders = []

        for strategy in self.active_strategies.values():
            # Get current allocations
            current_allocation = await self._get_current_allocation(strategy)

            # Calculate rebalancing orders
            for market_type, target_pct in strategy.allocation.items():
                current_pct = current_allocation.get(market_type, 0.0)
                diff = target_pct - current_pct

                if abs(diff) > 0.05:  # 5% threshold
                    # Create rebalancing orders
                    # (Simplified - would need actual position adjustments)
                    pass

        return orders

    async def _get_current_allocation(
        self, strategy: CrossMarketStrategy
    ) -> Dict[MarketType, float]:
        """Get current allocation for a strategy."""
        allocation = {}
        total_value = 0.0

        for market_type in strategy.markets:
            adapter = self.adapters.get(market_type)
            if adapter:
                positions = await adapter.get_positions()
                market_value = sum(p.quantity * p.current_price for p in positions)
                allocation[market_type] = market_value
                total_value += market_value

        # Convert to percentages
        if total_value > 0:
            for market_type in allocation:
                allocation[market_type] /= total_value

        return allocation

    async def start(self) -> None:
        """Start the cross-market engine."""
        self.is_running = True

        # Start signal processing loop
        asyncio.create_task(self._process_signals())

        # Start monitoring loop
        asyncio.create_task(self._monitor_positions())

    async def stop(self) -> None:
        """Stop the cross-market engine."""
        self.is_running = False

        # Disconnect all adapters
        for adapter in self.adapters.values():
            await adapter.disconnect()

    async def _process_signals(self) -> None:
        """Process signals from the queue."""
        while self.is_running:
            try:
                signal = await asyncio.wait_for(self.signals_queue.get(), timeout=1.0)
                await self.execute_signal(signal)
            except asyncio.TimeoutError:
                continue

    async def _monitor_positions(self) -> None:
        """Monitor positions and risk."""
        while self.is_running:
            try:
                # Check positions
                positions = await self.get_all_positions()

                # Check risk limits
                for position in positions:
                    if position.unrealized_pnl < -1000:  # Stop loss
                        # Create close order
                        pass

                await asyncio.sleep(5)  # Check every 5 seconds
            except Exception as e:
                print(f"Monitoring error: {e}")
                await asyncio.sleep(5)
