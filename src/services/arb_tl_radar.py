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
        self.threshold_bps = 50  # Basis points
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

        # Start monitoring thread
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

        # Wait for thread
        if self.thread:
            self.thread.join(timeout=5)

        # Save final results
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
            "opportunities": self.opportunities[-10:],  # Last 10
            "paper_trades": self.paper_trades[-10:],  # Last 10
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
                    # Get prices from different sources
                    global_price = self._get_global_price(pair)
                    tr_prices = self._get_tr_prices(pair)

                    if global_price and tr_prices:
                        # Check for arbitrage opportunities
                        self._check_arbitrage(pair, global_price, tr_prices)

                # Rate limit
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

        # Get USD/TRY rate first
        usd_try = self._get_usd_try()
        if not usd_try:
            return prices

        # Simulated Turkish exchange prices (in real implementation, use actual APIs)
        # For demo, we'll add some spread to global price
        global_price = self._get_global_price(pair)
        if global_price:
            # Simulate price differences
            import random

            # BtcTurk simulation
            btcturk_spread = random.uniform(-0.005, 0.01)  # -0.5% to +1%
            btcturk_price_tl = global_price * usd_try * (1 + btcturk_spread)
            prices["btcturk"] = btcturk_price_tl

            # Paribu simulation
            paribu_spread = random.uniform(-0.003, 0.008)
            paribu_price_tl = global_price * usd_try * (1 + paribu_spread)
            prices["paribu"] = paribu_price_tl

            # Binance TR simulation
            binance_tr_spread = random.uniform(-0.002, 0.005)
            binance_tr_price_tl = global_price * usd_try * (1 + binance_tr_spread)
            prices["binance_tr"] = binance_tr_price_tl

        return prices

    def _get_usd_try(self) -> Optional[float]:
        """Get USD/TRY exchange rate"""
        try:
            # Try to get from forex API or fallback to fixed rate
            # For demo, using a simulated rate
            import random

            base_rate = 32.5  # Approximate rate
            variation = random.uniform(-0.1, 0.1)
            return base_rate + variation

        except Exception as e:
            logger.error(f"Failed to get USD/TRY rate: {e}")
            return 32.5  # Fallback rate

    def _check_arbitrage(self, pair: str, global_price: float, tr_prices: Dict[str, float]):
        """Check for arbitrage opportunities"""
        usd_try = self._get_usd_try()
        if not usd_try:
            return

        global_price_tl = global_price * usd_try

        for exchange, tr_price in tr_prices.items():
            # Calculate price difference in basis points
            diff_bps = ((tr_price - global_price_tl) / global_price_tl) * 10000

            # Check if opportunity exists
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

                # Execute paper trade if significant opportunity
                if abs(diff_bps) > self.threshold_bps * 1.5:
                    self._execute_paper_trade(opportunity)

                logger.info(f"Arbitrage opportunity: {pair} {exchange} {diff_bps:.2f} bps")

    def _execute_paper_trade(self, opportunity: Dict):
        """Execute a paper arbitrage trade"""
        # Simulate trade execution
        trade_size_tl = Decimal("1000")  # 1000 TL per trade

        # Calculate profit based on price difference
        diff_pct = Decimal(str(abs(opportunity["diff_bps"]) / 10000))

        # Account for fees (0.1% each side = 0.2% total)
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


# Global instance
arb_radar = ArbTLRadar()
