"""
Smart Order Router - Intelligent order routing and execution.

Features:
- Best execution routing
- Order splitting
- Iceberg orders
- TWAP/VWAP execution
"""

import asyncio
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel

from .market_adapter import Order, OrderStatus, OrderType


class ExecutionAlgorithm(str, Enum):
    """Execution algorithm types."""

    IMMEDIATE = "immediate"
    TWAP = "twap"
    VWAP = "vwap"
    ICEBERG = "iceberg"
    SMART = "smart"


class RouteDecision(BaseModel):
    """Routing decision for an order."""

    market: str
    quantity: float
    price: Optional[float]
    algorithm: ExecutionAlgorithm
    priority: int
    estimated_cost: float


class ExecutionPlan(BaseModel):
    """Execution plan for complex orders."""

    original_order: Order
    routes: List[RouteDecision]
    total_quantity: float
    avg_price: float
    estimated_time: int
    estimated_slippage: float


class ExecutionReport(BaseModel):
    """Report of order execution."""

    order_id: str
    status: OrderStatus
    filled_quantity: float
    remaining_quantity: float
    average_price: float
    total_cost: float
    slippage: float
    execution_time: float
    routes_used: List[str]
    timestamp: datetime


class SmartOrderRouter:
    """
    Intelligent order routing system.

    Features:
    - Multi-venue routing
    - Algorithmic execution
    - Cost optimization
    - Latency monitoring
    """

    def __init__(self):
        """Initialize smart order router."""
        self.market_depths: Dict[str, Dict] = {}
        self.execution_costs: Dict[str, float] = {
            "binance": 0.001,
            "coinbase": 0.005,
            "kraken": 0.002,
            "nasdaq": 0.003,
            "nyse": 0.003,
        }
        self.latencies: Dict[str, float] = {
            "binance": 50,
            "coinbase": 100,
            "kraken": 75,
            "nasdaq": 10,
            "nyse": 10,
        }
        self.active_orders: Dict[str, ExecutionPlan] = {}

    def update_market_depth(self, market: str, symbol: str, depth: Dict) -> None:
        """Update market depth for routing decisions."""
        if market not in self.market_depths:
            self.market_depths[market] = {}
        self.market_depths[market][symbol] = depth

    def analyze_liquidity(self, symbol: str, quantity: float) -> Dict[str, float]:
        """Analyze liquidity across markets."""
        liquidity = {}
        for market, depths in self.market_depths.items():
            if symbol in depths:
                depth = depths[symbol]
                if "bids" in depth and "asks" in depth:
                    bid_liquidity = sum(level[1] for level in depth["bids"][:5])
                    ask_liquidity = sum(level[1] for level in depth["asks"][:5])
                    liquidity[market] = min(bid_liquidity, ask_liquidity)
        return liquidity

    def calculate_execution_cost(self, market: str, quantity: float, price: float) -> float:
        """Calculate total execution cost."""
        notional = quantity * price
        fee = self.execution_costs.get(market, 0.003) * notional
        slippage = self._estimate_slippage(market, quantity) * notional
        return fee + slippage

    def _estimate_slippage(self, market: str, quantity: float) -> float:
        """Estimate slippage for given quantity."""
        base_slippage = 0.0001
        if quantity > 10000:
            return base_slippage * 3
        elif quantity > 1000:
            return base_slippage * 2
        else:
            return base_slippage

    async def create_execution_plan(self, order: Order) -> ExecutionPlan:
        """Create optimal execution plan for an order."""
        routes = []
        if order.type == OrderType.MARKET:
            routes = await self._plan_immediate_execution(order)
        elif order.quantity > 10000:
            routes = await self._plan_twap_execution(order)
        else:
            routes = await self._plan_smart_routing(order)
        total_cost = sum(r.estimated_cost for r in routes)
        avg_price = total_cost / order.quantity if order.quantity > 0 else 0
        plan = ExecutionPlan(
            original_order=order,
            routes=routes,
            total_quantity=order.quantity,
            avg_price=avg_price,
            estimated_time=self._estimate_execution_time(routes),
            estimated_slippage=self._calculate_total_slippage(routes),
        )
        if order.id:
            self.active_orders[order.id] = plan
        return plan

    async def _plan_immediate_execution(self, order: Order) -> List[RouteDecision]:
        """Plan immediate market execution."""
        liquidity = self.analyze_liquidity(order.symbol, order.quantity)
        best_market = max(liquidity.items(), key=lambda x: x[1])[0] if liquidity else "binance"
        return [
            RouteDecision(
                market=best_market,
                quantity=order.quantity,
                price=order.price,
                algorithm=ExecutionAlgorithm.IMMEDIATE,
                priority=1,
                estimated_cost=self.calculate_execution_cost(
                    best_market, order.quantity, order.price or 0
                ),
            )
        ]

    async def _plan_twap_execution(self, order: Order) -> List[RouteDecision]:
        """Plan time-weighted average price execution."""
        num_slices = 10
        slice_quantity = order.quantity / num_slices
        routes = []
        for i in range(num_slices):
            market = ["binance", "coinbase", "kraken"][i % 3]
            routes.append(
                RouteDecision(
                    market=market,
                    quantity=slice_quantity,
                    price=order.price,
                    algorithm=ExecutionAlgorithm.TWAP,
                    priority=i + 1,
                    estimated_cost=self.calculate_execution_cost(
                        market, slice_quantity, order.price or 0
                    ),
                )
            )
        return routes

    async def _plan_smart_routing(self, order: Order) -> List[RouteDecision]:
        """Plan smart order routing."""
        liquidity = self.analyze_liquidity(order.symbol, order.quantity)
        routes = []
        remaining = order.quantity
        market_scores = {}
        for market, liq in liquidity.items():
            if liq > 0:
                cost = self.execution_costs.get(market, 0.003)
                latency = self.latencies.get(market, 100)
                score = cost * 1000 + latency * 0.001
                market_scores[market] = score
        sorted_markets = sorted(market_scores.items(), key=lambda x: x[1])
        for market, _ in sorted_markets[:3]:
            if remaining <= 0:
                break
            available = liquidity.get(market, 0)
            quantity = min(remaining, available * 0.5)
            if quantity > 0:
                routes.append(
                    RouteDecision(
                        market=market,
                        quantity=quantity,
                        price=order.price,
                        algorithm=ExecutionAlgorithm.SMART,
                        priority=len(routes) + 1,
                        estimated_cost=self.calculate_execution_cost(
                            market, quantity, order.price or 0
                        ),
                    )
                )
                remaining -= quantity
        return routes

    def _estimate_execution_time(self, routes: List[RouteDecision]) -> int:
        """Estimate total execution time."""
        if not routes:
            return 0
        if routes[0].algorithm == ExecutionAlgorithm.TWAP:
            return len(routes) * 60
        max_latency = max(self.latencies.get(r.market, 100) for r in routes)
        return int(max_latency / 1000) + 1

    def _calculate_total_slippage(self, routes: List[RouteDecision]) -> float:
        """Calculate total expected slippage."""
        total_slippage = 0.0
        for route in routes:
            slippage = self._estimate_slippage(route.market, route.quantity)
            total_slippage += slippage * route.quantity * (route.price or 0)
        total_value = sum(r.quantity * (r.price or 0) for r in routes)
        return total_slippage / total_value if total_value > 0 else 0.0

    async def execute_plan(self, plan: ExecutionPlan) -> ExecutionReport:
        """Execute an order plan."""
        start_time = datetime.utcnow()
        filled = 0.0
        total_cost = 0.0
        routes_used = []
        for route in plan.routes:
            latency = self.latencies.get(route.market, 100)
            await asyncio.sleep(latency / 1000)
            filled += route.quantity
            total_cost += route.estimated_cost
            routes_used.append(route.market)
            if filled >= plan.total_quantity:
                break
        execution_time = (datetime.utcnow() - start_time).total_seconds()
        report = ExecutionReport(
            order_id=plan.original_order.id or f"order_{datetime.utcnow().timestamp()}",
            status=OrderStatus.FILLED if filled >= plan.total_quantity else OrderStatus.PARTIAL,
            filled_quantity=filled,
            remaining_quantity=max(0, plan.total_quantity - filled),
            average_price=total_cost / filled if filled > 0 else 0,
            total_cost=total_cost,
            slippage=plan.estimated_slippage,
            execution_time=execution_time,
            routes_used=routes_used,
            timestamp=datetime.utcnow(),
        )
        return report

    async def execute_iceberg_order(
        self, order: Order, visible_quantity: float
    ) -> List[ExecutionReport]:
        """Execute iceberg order with hidden quantity."""
        reports = []
        remaining = order.quantity
        while remaining > 0:
            slice_quantity = min(visible_quantity, remaining)
            slice_order = Order(
                symbol=order.symbol,
                market_type=order.market_type,
                side=order.side,
                type=order.type,
                quantity=slice_quantity,
                price=order.price,
            )
            plan = await self.create_execution_plan(slice_order)
            report = await self.execute_plan(plan)
            reports.append(report)
            remaining -= report.filled_quantity
            await asyncio.sleep(5)
        return reports

    async def execute_vwap(self, order: Order, duration_minutes: int = 30) -> ExecutionReport:
        """Execute volume-weighted average price order."""
        volume_profile = await self._get_volume_profile(order.symbol)
        schedule = self._create_vwap_schedule(order, volume_profile, duration_minutes)
        filled = 0.0
        total_cost = 0.0
        for time_slot, quantity in schedule:
            slice_order = Order(
                symbol=order.symbol,
                market_type=order.market_type,
                side=order.side,
                type=OrderType.LIMIT,
                quantity=quantity,
                price=order.price,
            )
            plan = await self.create_execution_plan(slice_order)
            report = await self.execute_plan(plan)
            filled += report.filled_quantity
            total_cost += report.total_cost
            await asyncio.sleep(60)
        return ExecutionReport(
            order_id=order.id or f"vwap_{datetime.utcnow().timestamp()}",
            status=OrderStatus.FILLED if filled >= order.quantity else OrderStatus.PARTIAL,
            filled_quantity=filled,
            remaining_quantity=max(0, order.quantity - filled),
            average_price=total_cost / filled if filled > 0 else 0,
            total_cost=total_cost,
            slippage=0.001,
            execution_time=duration_minutes * 60,
            routes_used=["multiple"],
            timestamp=datetime.utcnow(),
        )

    async def _get_volume_profile(self, symbol: str) -> List[float]:
        """Get volume profile for VWAP calculation."""
        return [100, 80, 60, 50, 40, 40, 50, 60, 80, 100, 100, 80, 60, 50, 40, 40, 50, 60, 80, 100]

    def _create_vwap_schedule(
        self, order: Order, volume_profile: List[float], duration_minutes: int
    ) -> List[Tuple[datetime, float]]:
        """Create VWAP execution schedule."""
        total_volume = sum(volume_profile)
        schedule = []
        for i, volume in enumerate(volume_profile[:duration_minutes]):
            quantity = order.quantity * (volume / total_volume)
            time_slot = datetime.utcnow() + timedelta(minutes=i)
            schedule.append((time_slot, quantity))
        return schedule

    def get_best_execution_venue(self, order: Order) -> str:
        """Get best execution venue for an order."""
        liquidity = self.analyze_liquidity(order.symbol, order.quantity)
        best_market = None
        best_score = float("inf")
        for market, liq in liquidity.items():
            if liq >= order.quantity:
                cost = self.calculate_execution_cost(market, order.quantity, order.price or 0)
                latency = self.latencies.get(market, 100)
                score = cost + latency * 0.01
                if score < best_score:
                    best_score = score
                    best_market = market
        return best_market or "binance"
