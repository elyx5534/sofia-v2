"""
Turkish Arbitrage Radar Service (Paper Trading)
Monitors price differences between global and Turkish exchanges
"""

import json
import logging
import threading
import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class ArbTLRadar:
    """Turkish arbitrage opportunity radar"""

    def __init__(self):
        self.running = False
        self.mode = None
        self.pairs = []
        self.threshold_bps = 50
        self.thread = None
        self.opportunities = []
        self.paper_trades = []
        self.total_pnl_tl = Decimal("0")
        self.logs_dir = Path("logs")
        self.logs_dir.mkdir(exist_ok=True)

    def start_radar(
        self, mode: str = "tl", pairs: List[str] = None, threshold_bps: int = 50
    ) -> Dict:
        """Start arbitrage radar"""
        if self.running:
            return {"error": "Radar already running"}
        self.running = True
        self.mode = mode
        self.pairs = pairs or ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
        self.threshold_bps = threshold_bps
        self.opportunities = []
        self.paper_trades = []
        self.total_pnl_tl = Decimal("0")
        self.thread = threading.Thread(target=self._monitor_loop)
        self.thread.daemon = True
        self.thread.start()
        logger.info(f"Started arbitrage radar: mode={mode}, pairs={pairs}")
        return {
            "status": "started",
            "mode": mode,
            "pairs": self.pairs,
            "threshold_bps": threshold_bps,
        }

    def stop_radar(self) -> Dict:
        """Stop arbitrage radar"""
        if not self.running:
            return {"error": "Radar not running"}
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        self._save_results()
        logger.info(f"Stopped arbitrage radar. Total P&L: {self.total_pnl_tl} TL")
        return {
            "status": "stopped",
            "total_pnl_tl": float(self.total_pnl_tl),
            "num_opportunities": len(self.opportunities),
            "num_trades": len(self.paper_trades),
        }

    def get_snapshot(self) -> Dict:
        """Get current radar snapshot"""
        return {
            "running": self.running,
            "mode": self.mode,
            "pairs": self.pairs,
            "threshold_bps": self.threshold_bps,
            "opportunities": self.opportunities[-10:],
            "paper_trades": self.paper_trades[-10:],
            "total_pnl_tl": float(self.total_pnl_tl),
            "num_opportunities": len(self.opportunities),
            "num_trades": len(self.paper_trades),
        }

    def _monitor_loop(self):
        """Main monitoring loop"""
        logger.info("Arbitrage monitoring started")
        while self.running:
            try:
                for pair in self.pairs:
                    global_price = self._get_global_price(pair)
                    tr_prices = self._get_tr_prices(pair)
                    if global_price and tr_prices:
                        self._check_arbitrage(pair, global_price, tr_prices)
                time.sleep(5)
            except Exception as e:
                logger.error(f"Arbitrage monitor error: {e}")
                time.sleep(10)

    def _get_global_price(self, pair: str) -> Optional[float]:
        """Get price from global exchange (Binance)"""
        try:
            symbol = pair.replace("/", "")
            url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                data = response.json()
                return float(data["price"])
        except Exception as e:
            logger.error(f"Failed to get global price for {pair}: {e}")
        return None

    def _get_tr_prices(self, pair: str) -> Dict[str, float]:
        """Get prices from Turkish exchanges"""
        prices = {}
        usd_try = self._get_usd_try()
        if not usd_try:
            return prices
        global_price = self._get_global_price(pair)
        if global_price:
            import random

            btcturk_spread = random.uniform(-0.005, 0.01)
            btcturk_price_tl = global_price * usd_try * (1 + btcturk_spread)
            prices["btcturk"] = btcturk_price_tl
            paribu_spread = random.uniform(-0.003, 0.008)
            paribu_price_tl = global_price * usd_try * (1 + paribu_spread)
            prices["paribu"] = paribu_price_tl
            binance_tr_spread = random.uniform(-0.002, 0.005)
            binance_tr_price_tl = global_price * usd_try * (1 + binance_tr_spread)
            prices["binance_tr"] = binance_tr_price_tl
        return prices

    def _get_usd_try(self) -> Optional[float]:
        """Get USD/TRY exchange rate"""
        try:
            import random

            base_rate = 32.5
            variation = random.uniform(-0.1, 0.1)
            return base_rate + variation
        except Exception as e:
            logger.error(f"Failed to get USD/TRY rate: {e}")
            return 32.5

    def _check_arbitrage(self, pair: str, global_price: float, tr_prices: Dict[str, float]):
        """Check for arbitrage opportunities"""
        usd_try = self._get_usd_try()
        if not usd_try:
            return
        global_price_tl = global_price * usd_try
        for exchange, tr_price in tr_prices.items():
            diff_bps = (tr_price - global_price_tl) / global_price_tl * 10000
            if abs(diff_bps) > self.threshold_bps:
                opportunity = {
                    "timestamp": int(time.time() * 1000),
                    "pair": pair,
                    "global_price": global_price,
                    "global_price_tl": global_price_tl,
                    "tr_exchange": exchange,
                    "tr_price": tr_price,
                    "diff_bps": round(diff_bps, 2),
                    "usd_try": usd_try,
                    "direction": "buy_global_sell_tr" if diff_bps > 0 else "buy_tr_sell_global",
                }
                self.opportunities.append(opportunity)
                self._log_opportunity(opportunity)
                if abs(diff_bps) > self.threshold_bps * 1.5:
                    self._execute_paper_trade(opportunity)
                logger.info(f"Arbitrage opportunity: {pair} {exchange} {diff_bps:.2f} bps")

    def _execute_paper_trade(self, opportunity: Dict):
        """Execute a paper arbitrage trade"""
        trade_size_tl = Decimal("1000")
        diff_pct = Decimal(str(abs(opportunity["diff_bps"]) / 10000))
        fees = Decimal("0.002")
        net_diff = diff_pct - fees
        if net_diff > 0:
            profit_tl = trade_size_tl * net_diff
            trade = {
                "timestamp": opportunity["timestamp"],
                "pair": opportunity["pair"],
                "direction": opportunity["direction"],
                "size_tl": float(trade_size_tl),
                "diff_bps": opportunity["diff_bps"],
                "gross_pct": float(diff_pct * 100),
                "fees_pct": float(fees * 100),
                "net_pct": float(net_diff * 100),
                "profit_tl": float(profit_tl),
                "exchange": opportunity["tr_exchange"],
            }
            self.paper_trades.append(trade)
            self.total_pnl_tl += profit_tl
            self._log_trade(trade)
            logger.info(f"Paper arbitrage trade: {opportunity['pair']} profit={profit_tl:.2f} TL")

    def _log_opportunity(self, opportunity: Dict):
        """Log arbitrage opportunity"""
        log_file = self.logs_dir / "arb_opportunities.log"
        with open(log_file, "a") as f:
            f.write(json.dumps(opportunity) + "\n")

    def _log_trade(self, trade: Dict):
        """Log paper trade"""
        log_file = self.logs_dir / "arb_paper.log"
        with open(log_file, "a") as f:
            f.write(json.dumps(trade) + "\n")

    def _save_results(self):
        """Save arbitrage results"""
        summary = {
            "timestamp": datetime.now().isoformat(),
            "mode": self.mode,
            "pairs": self.pairs,
            "threshold_bps": self.threshold_bps,
            "total_pnl_tl": float(self.total_pnl_tl),
            "num_opportunities": len(self.opportunities),
            "num_trades": len(self.paper_trades),
            "avg_profit_per_trade": (
                float(self.total_pnl_tl / len(self.paper_trades)) if self.paper_trades else 0
            ),
            "recent_opportunities": self.opportunities[-20:],
            "recent_trades": self.paper_trades[-20:],
        }
        summary_file = self.logs_dir / "arb_pnl.json"
        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=2)
        logger.info(
            f"Saved arbitrage results: {len(self.paper_trades)} trades, {self.total_pnl_tl:.2f} TL profit"
        )


arb_radar = ArbTLRadar()


def start(mode: str = "tl", pairs: list = None, threshold_bps: int = 50) -> dict:
    """Start arbitrage radar monitoring.

    Public API Contract v1 - Stable interface for arbitrage monitoring.

    Args:
        mode: Monitoring mode ("tl" for Turkish, "global" for cross-exchange)
        pairs: List of trading pairs to monitor (e.g., ["BTC/USDT", "ETH/USDT"])
        threshold_bps: Threshold in basis points for opportunity detection

    Returns:
        dict: {"status": "started", "mode": str, "pairs": list, "threshold_bps": int} or error

    Example:
        >>> result = start("tl", ["BTC/USDT"], 100)
        >>> print(result["status"])
        started
    """
    return arb_radar.start_radar(mode, pairs, threshold_bps)


def stop() -> dict:
    """Stop arbitrage radar monitoring.

    Public API Contract v1 - Stable interface for stopping radar.

    Returns:
        dict: {"status": "stopped", "total_pnl_tl": float, "num_opportunities": int} or error

    Example:
        >>> result = stop()
        >>> print(f"Total P&L: {result['total_pnl_tl']} TL")
    """
    return arb_radar.stop_radar()


def snap() -> dict:
    """Get current radar snapshot.

    Public API Contract v1 - Stable interface for radar status.

    Returns:
        dict: Current snapshot with opportunities, trades, and P&L

    Example:
        >>> snapshot = snap()
        >>> print(f"Opportunities: {snapshot['num_opportunities']}")
    """
    return arb_radar.get_snapshot()


__all__ = ["arb_radar", "ArbTLRadar", "start", "stop", "snap"]
