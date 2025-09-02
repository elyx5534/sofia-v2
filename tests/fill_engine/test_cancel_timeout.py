"""
Test Order Cancellation and Timeout
"""

import pytest
import asyncio
from decimal import Decimal
from src.paper_trading.fill_engine import RealisticFillEngine, Order


@pytest.mark.asyncio
async def test_order_timeout_cancellation():
    """Test order cancellation after timeout"""
    engine = RealisticFillEngine()
    await engine.start()
    
    try:
        # Create order with short timeout
        order = Order(
            order_id="test_timeout_1",
            symbol="BTC/USDT",
            side="buy",
            order_type="limit",
            quantity=Decimal("0.1"),
            price=Decimal("50000"),  # Far from market price
            maker_only=True,
            cancel_unfilled_sec=2  # 2 second timeout
        )
        
        engine.submit_order(order)
        
        # Wait for timeout
        await asyncio.sleep(3)
        
        # Check order was cancelled
        assert order.status == "cancelled"
        assert engine.metrics["cancelled_orders"] > 0
        assert engine.metrics["cancelled_quantity"] == Decimal("0.1")
        
    finally:
        await engine.stop()


@pytest.mark.asyncio
async def test_partial_fill_then_cancel():
    """Test partial fill followed by timeout cancellation"""
    engine = RealisticFillEngine()
    await engine.start()
    
    try:
        # Create order that might partially fill
        order = Order(
            order_id="test_partial_cancel_1",
            symbol="BTC/USDT",
            side="buy",
            order_type="limit",
            quantity=Decimal("10.0"),  # Very large quantity
            price=Decimal("108000"),
            maker_only=False,
            cancel_unfilled_sec=3
        )
        
        engine.submit_order(order)
        
        # Wait for timeout
        await asyncio.sleep(4)
        
        # Check order was cancelled with partial fill
        assert order.status == "cancelled"
        
        if order.filled_quantity > 0:
            # Had partial fills
            assert order.filled_quantity < order.quantity
            cancelled_qty = order.quantity - order.filled_quantity
            assert engine.metrics["cancelled_quantity"] >= cancelled_qty
            
    finally:
        await engine.stop()


def test_metrics_calculation():
    """Test metrics calculation"""
    engine = RealisticFillEngine()
    
    # Simulate some fills
    engine.metrics["maker_fills"] = 8
    engine.metrics["taker_fills"] = 2
    engine.metrics["fill_count"] = 10
    engine.metrics["total_fill_time_ms"] = 5000
    engine.metrics["partial_fills"] = 3
    engine.metrics["cancelled_orders"] = 2
    
    metrics = engine.get_metrics()
    
    assert metrics["maker_fill_rate"] == 80.0  # 8/10 * 100
    assert metrics["avg_time_to_fill_ms"] == 500  # 5000/10
    assert metrics["partial_fill_count"] == 3
    assert metrics["cancelled_orders"] == 2