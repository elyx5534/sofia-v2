"""Main trading engine."""

import asyncio
import logging
from typing import Dict, Optional

from .order_manager import Order, OrderManager, OrderSide, OrderStatus, OrderType
from .portfolio import Portfolio
from .position_manager import PositionManager
from .risk_manager import RiskManager, RiskParameters

logger = logging.getLogger(__name__)


class TradingEngine:
    """Main trading engine orchestrator."""

    def __init__(
        self, initial_capital: float = 100000, risk_parameters: Optional[RiskParameters] = None
    ):
        """Initialize trading engine.

        Args:
            initial_capital: Starting capital in USD
            risk_parameters: Risk management configuration
        """
        self.order_manager = OrderManager()
        self.position_manager = PositionManager()
        self.risk_manager = RiskManager(risk_parameters)
        self.portfolio = Portfolio(initial_capital=initial_capital, cash_balance=initial_capital)
        self.is_running = False
        self.last_prices: Dict[str, float] = {}
        self.risk_manager.update_portfolio_value(initial_capital)

    async def start(self) -> None:
        """Start the trading engine.

        Starts background tasks for order processing, position updates, and risk monitoring.
        """
        self.is_running = True
        logger.info("Trading engine started")
        asyncio.create_task(self._process_orders())
        asyncio.create_task(self._update_positions())
        asyncio.create_task(self._monitor_risk())

    async def stop(self) -> None:
        """Stop the trading engine.

        Cancels all active orders and stops background tasks.
        """
        self.is_running = False
        for order in self.order_manager.get_active_orders():
            self.order_manager.cancel_order(order.id)
        logger.info("Trading engine stopped")

    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        price: Optional[float] = None,
    ) -> Optional[Order]:
        """Place a new order with risk checks.

        Args:
            symbol: Trading symbol (e.g., BTC/USDT)
            side: Order side (BUY or SELL)
            order_type: Order type (MARKET or LIMIT)
            quantity: Order quantity
            price: Limit price (required for LIMIT orders)

        Returns:
            Order object if successful, None if rejected by risk checks
        """
        position_value = quantity * (price or self.last_prices.get(symbol, 0))
        size_ok, size_msg = self.risk_manager.check_position_size(
            position_value, self.portfolio.total_value
        )
        if not size_ok:
            logger.warning(f"Order rejected: {size_msg}")
            return None
        loss_ok, loss_msg = self.risk_manager.check_daily_loss_limit()
        if not loss_ok:
            logger.warning(f"Order rejected: {loss_msg}")
            return None
        positions_ok, pos_msg = self.risk_manager.check_open_positions(
            len(self.position_manager.positions)
        )
        if not positions_ok and side == OrderSide.BUY:
            logger.warning(f"Order rejected: {pos_msg}")
            return None
        order = self.order_manager.create_order(
            symbol=symbol, side=side, order_type=order_type, quantity=quantity, price=price
        )
        logger.info(f"Order placed: {order.id} - {symbol} {side} {quantity} @ {price}")
        return order

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        success = self.order_manager.cancel_order(order_id)
        if success:
            logger.info(f"Order cancelled: {order_id}")
        return success

    def update_market_prices(self, prices: Dict[str, float]) -> None:
        """Update market prices."""
        self.last_prices.update(prices)
        self.portfolio.update_prices(prices)
        self.position_manager.update_prices(prices)
        self.risk_manager.update_portfolio_value(self.portfolio.total_value)

    async def execute_order(self, order: Order, execution_price: float) -> bool:
        """Execute a filled order."""
        if order.side == OrderSide.BUY:
            success = self.portfolio.add_asset(
                symbol=order.symbol, quantity=order.quantity, price=execution_price
            )
            if success:
                self.position_manager.open_position(
                    symbol=order.symbol, quantity=order.quantity, entry_price=execution_price
                )
                self.order_manager.update_order_status(
                    order_id=order.id,
                    status=OrderStatus.FILLED,
                    filled_quantity=order.quantity,
                    average_fill_price=execution_price,
                )
                logger.info(
                    f"Order executed: {order.id} - BUY {order.quantity} {order.symbol} @ {execution_price}"
                )
                return True
        elif order.side == OrderSide.SELL:
            pnl = self.portfolio.remove_asset(
                symbol=order.symbol, quantity=order.quantity, price=execution_price
            )
            if pnl is not None:
                self.position_manager.close_position(
                    symbol=order.symbol, exit_price=execution_price, quantity=order.quantity
                )
                self.risk_manager.update_metrics(pnl)
                self.order_manager.update_order_status(
                    order_id=order.id,
                    status=OrderStatus.FILLED,
                    filled_quantity=order.quantity,
                    average_fill_price=execution_price,
                )
                logger.info(
                    f"Order executed: {order.id} - SELL {order.quantity} {order.symbol} @ {execution_price}, PnL: {pnl:.2f}"
                )
                return True
        return False

    async def _process_orders(self) -> None:
        """Process active orders (background task)."""
        while self.is_running:
            try:
                for order in self.order_manager.get_active_orders():
                    if order.type == OrderType.MARKET:
                        price = self.last_prices.get(order.symbol)
                        if price:
                            await self.execute_order(order, price)
                    elif order.type == OrderType.LIMIT:
                        price = self.last_prices.get(order.symbol)
                        if price and order.price:
                            if (
                                order.side == OrderSide.BUY
                                and price <= order.price
                                or (order.side == OrderSide.SELL and price >= order.price)
                            ):
                                await self.execute_order(order, order.price)
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error processing orders: {e}")
                await asyncio.sleep(5)

    async def _update_positions(self) -> None:
        """Update position metrics (background task)."""
        while self.is_running:
            try:
                self.position_manager.update_prices(self.last_prices)
                for symbol, position in self.position_manager.positions.items():
                    price = self.last_prices.get(symbol)
                    if price:
                        stop_price = self.risk_manager.get_stop_loss_price(
                            position.entry_price, "buy" if position.quantity > 0 else "sell"
                        )
                        if (
                            position.quantity > 0
                            and price <= stop_price
                            or (position.quantity < 0 and price >= stop_price)
                        ):
                            await self.place_order(
                                symbol=symbol,
                                side=OrderSide.SELL if position.quantity > 0 else OrderSide.BUY,
                                order_type=OrderType.MARKET,
                                quantity=abs(position.quantity),
                            )
                            logger.warning(f"Stop loss triggered for {symbol} at {price}")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Error updating positions: {e}")
                await asyncio.sleep(10)

    async def _monitor_risk(self) -> None:
        """Monitor risk metrics (background task)."""
        while self.is_running:
            try:
                dd_ok, dd_msg = self.risk_manager.check_drawdown()
                if not dd_ok:
                    logger.error(f"Risk alert: {dd_msg}")
                loss_ok, loss_msg = self.risk_manager.check_daily_loss_limit()
                if not loss_ok:
                    logger.error(f"Risk alert: {loss_msg}")
                await asyncio.sleep(30)
            except Exception as e:
                logger.error(f"Error monitoring risk: {e}")
                await asyncio.sleep(60)

    def get_portfolio_summary(self) -> Dict:
        """Get portfolio summary."""
        return {
            "portfolio": self.portfolio.get_performance_metrics(),
            "positions": [p.model_dump() for p in self.position_manager.get_all_positions()],
            "active_orders": len(self.order_manager.get_active_orders()),
            "risk_metrics": self.risk_manager.metrics.model_dump(),
        }
