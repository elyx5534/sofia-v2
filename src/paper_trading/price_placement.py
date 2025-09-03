"""
Tick-Aware Price Placement for Maker Orders
Join/Step-In strategies to improve fill rates while maintaining maker status
"""

import logging
from decimal import ROUND_DOWN, ROUND_UP, Decimal
from typing import Dict, Tuple

import ccxt

logger = logging.getLogger(__name__)


class PricePlacement:
    """Smart price placement for maker orders"""

    def __init__(self, exchange=None):
        self.exchange = exchange or ccxt.binance()
        self.tick_sizes = {}
        self.markets = {}
        self._load_markets()

    def _load_markets(self):
        """Load market metadata for tick sizes"""
        try:
            if hasattr(self.exchange, "load_markets"):
                self.markets = self.exchange.load_markets()
                for symbol, market in self.markets.items():
                    if "limits" in market and "price" in market["limits"]:
                        tick = market["limits"]["price"].get("min", 0.01)
                        self.tick_sizes[symbol] = Decimal(str(tick))
        except Exception as e:
            logger.warning(f"Failed to load markets: {e}")

    def get_tick_size(self, symbol: str) -> Decimal:
        """Get tick size for symbol"""
        if symbol in self.tick_sizes:
            return self.tick_sizes[symbol]
        defaults = {
            "BTC/USDT": Decimal("0.01"),
            "ETH/USDT": Decimal("0.01"),
            "SOL/USDT": Decimal("0.001"),
        }
        return defaults.get(symbol, Decimal("0.01"))

    def round_to_tick(self, price: Decimal, symbol: str, round_up: bool = False) -> Decimal:
        """Round price to nearest tick"""
        tick = self.get_tick_size(symbol)
        if round_up:
            return (price / tick).quantize(Decimal("1"), rounding=ROUND_UP) * tick
        else:
            return (price / tick).quantize(Decimal("1"), rounding=ROUND_DOWN) * tick

    def join_best(self, side: str, best_bid: Decimal, best_ask: Decimal, symbol: str) -> Decimal:
        """Join the best price on our side (one tick better)"""
        tick = self.get_tick_size(symbol)
        if side == "buy":
            price = best_bid + tick
            return self.round_to_tick(price, symbol, round_up=False)
        else:
            price = best_ask - tick
            return self.round_to_tick(price, symbol, round_up=True)

    def step_in_limit(
        self,
        side: str,
        best_bid: Decimal,
        best_ask: Decimal,
        symbol: str,
        k: int = 1,
        min_edge_bps: float = 5,
    ) -> Tuple[Decimal, str]:
        """
        Step into the spread by k ticks while maintaining maker status
        Returns: (price, strategy_used)
        """
        tick = self.get_tick_size(symbol)
        spread = best_ask - best_bid
        mid = (best_bid + best_ask) / 2
        min_edge = mid * Decimal(str(min_edge_bps / 10000))
        if spread <= tick * 3:
            price = self.join_best(side, best_bid, best_ask, symbol)
            return (price, "join")
        if side == "buy":
            step_in_price = best_bid + tick * k
            edge = best_ask - step_in_price
            if edge < min_edge:
                price = self.join_best(side, best_bid, best_ask, symbol)
                return (price, "join")
            if step_in_price >= best_ask:
                price = best_ask - tick
                return (self.round_to_tick(price, symbol), "join")
            return (self.round_to_tick(step_in_price, symbol), f"step-in-{k}")
        else:
            step_in_price = best_ask - tick * k
            edge = step_in_price - best_bid
            if edge < min_edge:
                price = self.join_best(side, best_bid, best_ask, symbol)
                return (price, "join")
            if step_in_price <= best_bid:
                price = best_bid + tick
                return (self.round_to_tick(price, symbol, round_up=True), "join")
            return (self.round_to_tick(step_in_price, symbol, round_up=True), f"step-in-{k}")

    def calculate_k_from_volatility(self, atr_pct: float) -> int:
        """Calculate step-in depth based on volatility"""
        if atr_pct < 1.0:
            return 1
        elif atr_pct < 2.0:
            return 2
        else:
            return 3

    def get_smart_price(
        self, side: str, orderbook: Dict, symbol: str, atr_pct: float = 1.0, min_edge_bps: float = 5
    ) -> Tuple[Decimal, str]:
        """
        Get smart maker price based on market conditions
        Returns: (price, strategy)
        """
        if not orderbook or "bids" not in orderbook or "asks" not in orderbook:
            raise ValueError("Invalid orderbook")
        if not orderbook["bids"] or not orderbook["asks"]:
            raise ValueError("Empty orderbook")
        best_bid = Decimal(str(orderbook["bids"][0][0]))
        best_ask = Decimal(str(orderbook["asks"][0][0]))
        k = self.calculate_k_from_volatility(atr_pct)
        price, strategy = self.step_in_limit(side, best_bid, best_ask, symbol, k, min_edge_bps)
        logger.info(
            f"Price placement for {symbol} {side}: ${price} using {strategy} (bid={best_bid}, ask={best_ask}, k={k})"
        )
        return (price, strategy)


price_placement = PricePlacement()
