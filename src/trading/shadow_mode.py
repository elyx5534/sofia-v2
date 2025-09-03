"""
Shadow Mode Trading
Compares paper trading fills against real orderbook to measure realism
"""

import asyncio
import json
import logging
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, Tuple

import ccxt.async_support as ccxt

logger = logging.getLogger(__name__)


class ShadowMode:
    """Shadow mode to compare paper fills with real market"""

    def __init__(self, exchange_name: str = "binance"):
        self.exchange = None
        self.exchange_name = exchange_name
        self.shadow_diffs = []
        self._running = False

    async def initialize(self):
        """Initialize exchange connection"""
        if self.exchange_name == "binance":
            self.exchange = ccxt.binance(
                {"enableRateLimit": True, "options": {"defaultType": "spot"}}
            )
        else:
            raise ValueError(f"Unsupported exchange: {self.exchange_name}")
        await self.exchange.load_markets()
        logger.info(f"Shadow mode initialized with {self.exchange_name}")

    async def compare_fill(self, order: Dict, paper_fill: Dict) -> Dict:
        """Compare paper fill with real orderbook"""
        try:
            symbol = order["symbol"]
            side = order["side"]
            orderbook = await self.exchange.fetch_order_book(symbol, limit=10)
            real_fill_price, real_fill_prob = self._calculate_real_fill(
                orderbook, side, Decimal(str(order["price"])), Decimal(str(order["quantity"]))
            )
            paper_price = Decimal(str(paper_fill["price"]))
            price_diff_bps = abs((paper_price - real_fill_price) / real_fill_price * 10000)
            diff = {
                "timestamp": datetime.now().isoformat(),
                "symbol": symbol,
                "side": side,
                "paper_price": float(paper_price),
                "real_price": float(real_fill_price),
                "price_diff_bps": float(price_diff_bps),
                "fill_probability": float(real_fill_prob),
                "maker_only": order.get("maker_only", False),
            }
            self.shadow_diffs.append(diff)
            self._save_diff(diff)
            return diff
        except Exception as e:
            logger.error(f"Shadow comparison failed: {e}")
            return {}

    def _calculate_real_fill(
        self, orderbook: Dict, side: str, price: Decimal, quantity: Decimal
    ) -> Tuple[Decimal, Decimal]:
        """Calculate where order would fill in real orderbook"""
        if side == "buy":
            best_ask = Decimal(str(orderbook["asks"][0][0]))
            if price >= best_ask:
                return (best_ask, Decimal("1.0"))
            best_bid = Decimal(str(orderbook["bids"][0][0]))
            if price > best_bid:
                return (price, Decimal("0.8"))
            elif price == best_bid:
                bid_depth = sum(
                    Decimal(str(bid[1]))
                    for bid in orderbook["bids"]
                    if Decimal(str(bid[0])) == best_bid
                )
                fill_prob = min(Decimal("0.5") * (quantity / bid_depth), Decimal("0.7"))
                return (price, fill_prob)
            else:
                distance = (best_bid - price) / best_bid
                fill_prob = max(Decimal("0.1"), Decimal("0.3") - distance * 100)
                return (price, fill_prob)
        else:
            best_bid = Decimal(str(orderbook["bids"][0][0]))
            if price <= best_bid:
                return (best_bid, Decimal("1.0"))
            best_ask = Decimal(str(orderbook["asks"][0][0]))
            if price < best_ask:
                return (price, Decimal("0.8"))
            elif price == best_ask:
                ask_depth = sum(
                    Decimal(str(ask[1]))
                    for ask in orderbook["asks"]
                    if Decimal(str(ask[0])) == best_ask
                )
                fill_prob = min(Decimal("0.5") * (quantity / ask_depth), Decimal("0.7"))
                return (price, fill_prob)
            else:
                distance = (price - best_ask) / best_ask
                fill_prob = max(Decimal("0.1"), Decimal("0.3") - distance * 100)
                return (price, fill_prob)

    def _save_diff(self, diff: Dict):
        """Save shadow diff to log file"""
        log_file = Path("logs/shadow_diff.jsonl")
        log_file.parent.mkdir(exist_ok=True)
        with open(log_file, "a") as f:
            f.write(json.dumps(diff) + "\n")

    async def run_comparison_session(self, duration_minutes: int = 5):
        """Run shadow comparison session"""
        if not self.exchange:
            await self.initialize()
        self._running = True
        start_time = datetime.now()
        print(f"Starting {duration_minutes} minute shadow comparison...")
        try:
            while self._running and (datetime.now() - start_time).seconds < duration_minutes * 60:
                await asyncio.sleep(5)
                if len(self.shadow_diffs) > 0:
                    avg_diff = sum(d["price_diff_bps"] for d in self.shadow_diffs) / len(
                        self.shadow_diffs
                    )
                    avg_prob = sum(d["fill_probability"] for d in self.shadow_diffs) / len(
                        self.shadow_diffs
                    )
                    print(
                        f"[{datetime.now().strftime('%H:%M:%S')}] Comparisons: {len(self.shadow_diffs)} | Avg Price Diff: {avg_diff:.2f} bps | Avg Fill Prob: {avg_prob:.1%}"
                    )
        finally:
            await self.close()
            self._print_summary()

    def _print_summary(self):
        """Print shadow comparison summary"""
        if not self.shadow_diffs:
            print("No shadow comparisons recorded")
            return
        avg_diff = sum(d["price_diff_bps"] for d in self.shadow_diffs) / len(self.shadow_diffs)
        avg_prob = sum(d["fill_probability"] for d in self.shadow_diffs) / len(self.shadow_diffs)
        print("\n" + "=" * 60)
        print("SHADOW MODE SUMMARY")
        print("=" * 60)
        print(f"Total Comparisons: {len(self.shadow_diffs)}")
        print(f"Average Price Difference: {avg_diff:.2f} bps")
        print(f"Average Fill Probability: {avg_prob:.1%}")
        if avg_diff < 5:
            print("✅ Price differences within acceptable range (<5 bps)")
        else:
            print("⚠️ Price differences exceed target (>5 bps)")
        print("=" * 60)

    async def close(self):
        """Close exchange connection"""
        self._running = False
        if self.exchange:
            await self.exchange.close()


shadow_mode = ShadowMode()
