"""
Arbitrage Pricer with Depth & Fee Model
Calculates effective prices with VWAP and fees
"""

import logging
from pathlib import Path
from typing import Dict, List, Tuple

import yaml

logger = logging.getLogger(__name__)


class ArbitragePricer:
    """Depth-aware arbitrage pricing with fee model"""

    def __init__(self, config_path: str = "config/fees.yaml"):
        self.fees = self._load_fees(config_path)
        self.min_profitable_spread = 30  # basis points

    def _load_fees(self, config_path: str) -> Dict:
        """Load fee configuration"""
        config_file = Path(config_path)
        if config_file.exists():
            with open(config_file) as f:
                return yaml.safe_load(f)
        else:
            # Default fees if config not found
            return {
                "binance": {"spot": {"maker": 0.10, "taker": 0.10}},
                "btcturk": {"spot": {"maker": 0.08, "taker": 0.12}},
                "tl_gateway": {"withdrawal_fee": 0.5},
                "slippage": {"binance": {"small_order": 2}, "btcturk": {"small_order": 5}},
            }

    def calculate_vwap(
        self, orderbook: List[List[float]], target_amount: float, side: str
    ) -> Tuple[float, float]:
        """
        Calculate Volume Weighted Average Price

        Args:
            orderbook: List of [price, size] levels
            target_amount: Target amount to execute
            side: 'buy' or 'sell'

        Returns:
            (vwap_price, actual_amount)
        """
        if not orderbook:
            return 0.0, 0.0

        total_cost = 0.0
        total_amount = 0.0

        for price, size in orderbook:
            if total_amount >= target_amount:
                break

            remaining = target_amount - total_amount
            fill_amount = min(size, remaining)

            total_cost += price * fill_amount
            total_amount += fill_amount

        if total_amount == 0:
            return 0.0, 0.0

        vwap = total_cost / total_amount
        return vwap, total_amount

    def get_effective_price(
        self, exchange: str, orderbook: Dict, amount: float, side: str, use_maker: bool = False
    ) -> Dict:
        """
        Calculate effective price including fees and slippage

        Args:
            exchange: 'binance' or 'btcturk'
            orderbook: {'bids': [[price, size]], 'asks': [[price, size]]}
            amount: Amount to trade
            side: 'buy' or 'sell'
            use_maker: Whether to use maker fee (limit order)

        Returns:
            {
                'raw_price': float,
                'vwap_price': float,
                'fee_pct': float,
                'slippage_bps': float,
                'effective_price': float,
                'available_depth': float
            }
        """
        # Determine which side of orderbook to use
        if side == "buy":
            levels = orderbook.get("asks", [])
        else:
            levels = orderbook.get("bids", [])

        if not levels:
            return {
                "raw_price": 0,
                "vwap_price": 0,
                "fee_pct": 0,
                "slippage_bps": 0,
                "effective_price": 0,
                "available_depth": 0,
            }

        # Best price
        raw_price = levels[0][0]

        # Calculate VWAP
        vwap_price, filled_amount = self.calculate_vwap(levels, amount, side)

        # Get fee
        fee_type = "maker" if use_maker else "taker"
        fee_pct = self.fees[exchange]["spot"][fee_type]

        # Calculate slippage
        slippage_bps = ((vwap_price - raw_price) / raw_price) * 10000
        if side == "sell":
            slippage_bps = -slippage_bps

        # Calculate effective price
        if side == "buy":
            # When buying, we pay more (price + fees)
            effective_price = vwap_price * (1 + fee_pct / 100)
        else:
            # When selling, we receive less (price - fees)
            effective_price = vwap_price * (1 - fee_pct / 100)

        return {
            "raw_price": raw_price,
            "vwap_price": vwap_price,
            "fee_pct": fee_pct,
            "slippage_bps": abs(slippage_bps),
            "effective_price": effective_price,
            "available_depth": filled_amount,
        }

    def calculate_arbitrage_profit(
        self, binance_book: Dict, btcturk_book: Dict, amount_usdt: float, fx_rate: float
    ) -> Dict:
        """
        Calculate arbitrage profit for Binance -> BTCTurk route

        Args:
            binance_book: Binance orderbook
            btcturk_book: BTCTurk orderbook
            amount_usdt: Amount in USDT
            fx_rate: USDTRY exchange rate

        Returns:
            Detailed profit calculation
        """
        # Calculate BTC amount from USDT
        binance_buy = self.get_effective_price(
            "binance", binance_book, amount_usdt, "buy", use_maker=False
        )

        if binance_buy["vwap_price"] == 0:
            return {"profitable": False, "reason": "No Binance depth"}

        btc_amount = amount_usdt / binance_buy["effective_price"]

        # Calculate BTCTurk sell
        btcturk_sell = self.get_effective_price(
            "btcturk", btcturk_book, btc_amount, "sell", use_maker=False
        )

        if btcturk_sell["vwap_price"] == 0:
            return {"profitable": False, "reason": "No BTCTurk depth"}

        # Calculate profit
        tl_received = btc_amount * btcturk_sell["effective_price"]

        # Apply TL gateway fee
        gateway_fee_pct = self.fees["tl_gateway"]["withdrawal_fee"]
        tl_after_gateway = tl_received * (1 - gateway_fee_pct / 100)

        # Convert back to USDT
        usdt_final = tl_after_gateway / fx_rate

        # Calculate profit
        profit_usdt = usdt_final - amount_usdt
        profit_pct = (profit_usdt / amount_usdt) * 100

        # Check if profitable
        spread_bps = profit_pct * 100
        min_spread = self.fees.get("min_profitable_spread", {}).get("default", 30)

        return {
            "profitable": spread_bps > min_spread,
            "btc_amount": btc_amount,
            "binance_buy_price": binance_buy["effective_price"],
            "binance_fee_pct": binance_buy["fee_pct"],
            "binance_slippage_bps": binance_buy["slippage_bps"],
            "btcturk_sell_price": btcturk_sell["effective_price"],
            "btcturk_fee_pct": btcturk_sell["fee_pct"],
            "btcturk_slippage_bps": btcturk_sell["slippage_bps"],
            "tl_received": tl_received,
            "tl_after_gateway": tl_after_gateway,
            "gateway_fee_pct": gateway_fee_pct,
            "usdt_final": usdt_final,
            "profit_usdt": profit_usdt,
            "profit_pct": profit_pct,
            "spread_bps": spread_bps,
            "min_spread_bps": min_spread,
        }

    def find_optimal_size(
        self, binance_book: Dict, btcturk_book: Dict, fx_rate: float, max_size: float = 10000
    ) -> Dict:
        """
        Find optimal trade size for maximum profit

        Args:
            binance_book: Binance orderbook
            btcturk_book: BTCTurk orderbook
            fx_rate: USDTRY rate
            max_size: Maximum position size in USDT

        Returns:
            Optimal size and expected profit
        """
        test_sizes = [100, 500, 1000, 2000, 5000, 10000]
        test_sizes = [s for s in test_sizes if s <= max_size]

        best_profit = 0
        best_size = 0
        best_result = None

        for size in test_sizes:
            result = self.calculate_arbitrage_profit(binance_book, btcturk_book, size, fx_rate)

            if result.get("profitable", False):
                profit_usdt = result["profit_usdt"]
                if profit_usdt > best_profit:
                    best_profit = profit_usdt
                    best_size = size
                    best_result = result

        if best_result:
            return {
                "optimal_size": best_size,
                "expected_profit": best_profit,
                "profit_pct": best_result["profit_pct"],
                "details": best_result,
            }
        else:
            return {
                "optimal_size": 0,
                "expected_profit": 0,
                "profit_pct": 0,
                "details": {"profitable": False, "reason": "No profitable size found"},
            }

    def get_depth_analysis(self, orderbook: Dict, max_amount: float = 10000) -> Dict:
        """
        Analyze orderbook depth and price impact

        Args:
            orderbook: {'bids': [], 'asks': []}
            max_amount: Maximum amount to analyze

        Returns:
            Depth analysis with price impacts
        """
        analysis = {
            "bid": {"levels": [], "total_volume": 0, "avg_price": 0},
            "ask": {"levels": [], "total_volume": 0, "avg_price": 0},
        }

        # Analyze bid side
        if orderbook.get("bids"):
            total_volume = 0
            total_value = 0

            for i, (price, size) in enumerate(orderbook["bids"][:10]):
                total_volume += size
                total_value += price * size

                level_info = {
                    "level": i + 1,
                    "price": price,
                    "size": size,
                    "cumulative_volume": total_volume,
                    "vwap": total_value / total_volume if total_volume > 0 else 0,
                    "spread_bps": 0,
                }

                if i == 0:
                    best_bid = price
                else:
                    level_info["spread_bps"] = ((best_bid - price) / best_bid) * 10000

                analysis["bid"]["levels"].append(level_info)

            analysis["bid"]["total_volume"] = total_volume
            analysis["bid"]["avg_price"] = total_value / total_volume if total_volume > 0 else 0

        # Analyze ask side
        if orderbook.get("asks"):
            total_volume = 0
            total_value = 0

            for i, (price, size) in enumerate(orderbook["asks"][:10]):
                total_volume += size
                total_value += price * size

                level_info = {
                    "level": i + 1,
                    "price": price,
                    "size": size,
                    "cumulative_volume": total_volume,
                    "vwap": total_value / total_volume if total_volume > 0 else 0,
                    "spread_bps": 0,
                }

                if i == 0:
                    best_ask = price
                else:
                    level_info["spread_bps"] = ((price - best_ask) / best_ask) * 10000

                analysis["ask"]["levels"].append(level_info)

            analysis["ask"]["total_volume"] = total_volume
            analysis["ask"]["avg_price"] = total_value / total_volume if total_volume > 0 else 0

        # Calculate mid-market spread
        if analysis["bid"]["levels"] and analysis["ask"]["levels"]:
            best_bid = analysis["bid"]["levels"][0]["price"]
            best_ask = analysis["ask"]["levels"][0]["price"]
            analysis["spread_bps"] = ((best_ask - best_bid) / best_bid) * 10000
        else:
            analysis["spread_bps"] = 0

        return analysis
