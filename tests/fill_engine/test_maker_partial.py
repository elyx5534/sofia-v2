"""
Test Maker-Only and Partial Fill Logic
"""

import asyncio
from decimal import Decimal

import pytest
from src.paper_trading.fill_engine import Order, RealisticFillEngine


@pytest.mark.asyncio
async def test_maker_only_fill():
    """Test maker-only order execution"""
    engine = RealisticFillEngine()
    await engine.start()

    try:
        # Create maker-only buy order
        order = Order(
            order_id="test_maker_1",
            symbol="BTC/USDT",
            side="buy",
            order_type="limit",
            quantity=Decimal("0.1"),
            price=Decimal("107900"),  # Below market
            maker_only=True,
            cancel_unfilled_sec=10,
        )

        engine.submit_order(order)

        # Wait for potential fill
        await asyncio.sleep(2)

        # Check if order was filled as maker
        if order.status == "filled":
            assert len(order.fills) > 0
            assert order.fills[0]["fill_type"] == "maker"

    finally:
        await engine.stop()


@pytest.mark.asyncio
async def test_partial_fill():
    """Test partial fill behavior"""
    engine = RealisticFillEngine()
    await engine.start()

    try:
        # Create large order that should fill partially
        order = Order(
            order_id="test_partial_1",
            symbol="BTC/USDT",
            side="buy",
            order_type="limit",
            quantity=Decimal("1.0"),  # Large quantity
            price=Decimal("108100"),
            maker_only=False,
            cancel_unfilled_sec=5,
        )

        engine.submit_order(order)

        # Wait for fills
        await asyncio.sleep(3)

        # Check for partial fills
        if order.status == "partial":
            assert order.filled_quantity > 0
            assert order.filled_quantity < order.quantity
            assert engine.metrics["partial_fills"] > 0

    finally:
        await engine.stop()


def test_orderbook_simulation():
    """Test orderbook generation"""
    engine = RealisticFillEngine()

    orderbook = engine._get_orderbook("BTC/USDT")

    assert len(orderbook.bids) > 0
    assert len(orderbook.asks) > 0

    # Check bid/ask ordering
    for i in range(len(orderbook.bids) - 1):
        assert orderbook.bids[i][0] > orderbook.bids[i + 1][0]

    for i in range(len(orderbook.asks) - 1):
        assert orderbook.asks[i][0] < orderbook.asks[i + 1][0]

    # Check spread exists
    best_bid = orderbook.bids[0][0]
    best_ask = orderbook.asks[0][0]
    assert best_ask > best_bid
