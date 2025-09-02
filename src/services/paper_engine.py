"""
Paper Trading Engine Service
Simulates trading without real money
"""

import json
import logging
import threading
import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)


class PaperEngine:
    """Paper trading engine for simulated trading"""

    def __init__(self):
        self.running = False
        self.session_type = None
        self.symbol = None
        self.position = Decimal("0")
        self.cash = Decimal("10000")  # Starting cash
        self.initial_cash = Decimal("10000")
        self.trades = []
        self.pnl = Decimal("0")
        self.thread = None
        self.logs_dir = Path("logs")
        self.logs_dir.mkdir(exist_ok=True)

    def start_session(self, session_type: str, symbol: str, params: Dict = None) -> Dict:
        """Start a paper trading session"""
        if self.running:
            return {"error": "Session already running"}

        self.running = True
        self.session_type = session_type
        self.symbol = symbol
        self.params = params or {}
        self.position = Decimal("0")
        self.cash = self.initial_cash
        self.trades = []
        self.pnl = Decimal("0")

        # Start trading thread
        self.thread = threading.Thread(target=self._run_session)
        self.thread.daemon = True
        self.thread.start()

        logger.info(f"Started {session_type} paper session for {symbol}")

        return {"status": "started", "session": session_type, "symbol": symbol}

    def stop_session(self) -> Dict:
        """Stop the current paper trading session"""
        if not self.running:
            return {"error": "No session running"}

        self.running = False

        # Wait for thread to finish
        if self.thread:
            self.thread.join(timeout=5)

        # Save final results
        self._save_results()

        logger.info(f"Stopped paper session. Final P&L: {self.pnl}")

        return {"status": "stopped", "final_pnl": float(self.pnl), "num_trades": len(self.trades)}

    def get_status(self) -> Dict:
        """Get current session status"""
        if not self.running:
            return {
                "running": False,
                "session": None,
                "symbol": None,
                "pnl": 0,
                "position": 0,
                "cash": float(self.initial_cash),
                "num_trades": 0,
            }

        current_value = self.cash
        if self.position != 0:
            # Get current price
            from src.services.datahub import datahub

            price_data = datahub.get_latest_price(self.symbol)
            current_price = Decimal(str(price_data.get("price", 0)))
            current_value = self.cash + self.position * current_price

        self.pnl = current_value - self.initial_cash

        return {
            "running": True,
            "session": self.session_type,
            "symbol": self.symbol,
            "pnl": float(self.pnl),
            "position": float(self.position),
            "cash": float(self.cash),
            "num_trades": len(self.trades),
            "current_value": float(current_value),
        }

    def _run_session(self):
        """Main trading loop"""
        logger.info(f"Paper trading loop started for {self.symbol}")

        if self.session_type == "grid":
            self._run_grid_strategy()
        elif self.session_type == "mean_revert":
            self._run_mean_revert_strategy()
        else:
            self._run_simple_strategy()

    def _run_grid_strategy(self):
        """Run grid trading strategy"""
        # Get initial price
        from src.services.datahub import datahub

        price_data = datahub.get_latest_price(self.symbol)
        if not price_data or price_data["price"] == 0:
            logger.error(f"Failed to get price for {self.symbol}")
            return

        base_price = Decimal(str(price_data["price"]))
        grid_spacing = Decimal(str(self.params.get("grid_spacing", 0.01)))  # 1% default
        grid_levels = self.params.get("grid_levels", 5)

        # Create grid levels
        buy_levels = []
        sell_levels = []

        for i in range(1, grid_levels + 1):
            buy_price = base_price * (Decimal("1") - grid_spacing * i)
            sell_price = base_price * (Decimal("1") + grid_spacing * i)
            buy_levels.append(buy_price)
            sell_levels.append(sell_price)

        logger.info(
            f"Grid setup: Base={base_price}, Buy levels={buy_levels[:3]}, Sell levels={sell_levels[:3]}"
        )

        # Trading loop
        last_check = time.time()
        while self.running:
            try:
                # Rate limit
                if time.time() - last_check < 3:
                    time.sleep(1)
                    continue

                last_check = time.time()

                # Get current price
                price_data = datahub.get_latest_price(self.symbol)
                if not price_data or price_data["price"] == 0:
                    continue

                current_price = Decimal(str(price_data["price"]))

                # Check grid levels
                for buy_level in buy_levels:
                    if current_price <= buy_level and self.cash > 100:
                        # Execute buy
                        size = min(Decimal("100") / current_price, self.cash / current_price / 5)
                        cost = size * current_price * Decimal("1.001")  # 0.1% fee

                        if cost <= self.cash:
                            self.position += size
                            self.cash -= cost

                            trade = {
                                "timestamp": int(time.time() * 1000),
                                "side": "buy",
                                "price": float(current_price),
                                "size": float(size),
                                "cost": float(cost),
                            }
                            self.trades.append(trade)
                            self._log_trade(trade)

                            logger.info(f"Grid BUY: {size:.4f} @ {current_price:.2f}")
                            break

                for sell_level in sell_levels:
                    if current_price >= sell_level and self.position > 0:
                        # Execute sell
                        size = min(self.position / 5, self.position)
                        revenue = size * current_price * Decimal("0.999")  # 0.1% fee

                        self.position -= size
                        self.cash += revenue

                        trade = {
                            "timestamp": int(time.time() * 1000),
                            "side": "sell",
                            "price": float(current_price),
                            "size": float(size),
                            "revenue": float(revenue),
                        }
                        self.trades.append(trade)
                        self._log_trade(trade)

                        logger.info(f"Grid SELL: {size:.4f} @ {current_price:.2f}")
                        break

                # Update P&L
                current_value = self.cash + self.position * current_price
                self.pnl = current_value - self.initial_cash

                # Save interim results
                if len(self.trades) % 10 == 0:
                    self._save_results()

            except Exception as e:
                logger.error(f"Grid strategy error: {e}")

            time.sleep(2)

    def _run_mean_revert_strategy(self):
        """Run mean reversion strategy"""
        from src.services.datahub import datahub

        lookback = self.params.get("lookback", 20)
        z_threshold = self.params.get("z_threshold", 2.0)
        prices = []

        while self.running:
            try:
                # Get current price
                price_data = datahub.get_latest_price(self.symbol)
                if not price_data or price_data["price"] == 0:
                    time.sleep(3)
                    continue

                current_price = Decimal(str(price_data["price"]))
                prices.append(float(current_price))

                # Keep only lookback period
                if len(prices) > lookback:
                    prices = prices[-lookback:]

                # Need enough data
                if len(prices) < lookback:
                    time.sleep(3)
                    continue

                # Calculate z-score
                import numpy as np

                mean_price = np.mean(prices)
                std_price = np.std(prices)

                if std_price > 0:
                    z_score = (float(current_price) - mean_price) / std_price
                else:
                    z_score = 0

                # Trading logic
                position_size = Decimal("0.1")  # 10% of capital

                if z_score < -z_threshold and self.position <= 0:
                    # Buy signal (oversold)
                    size = (self.cash * position_size) / current_price
                    cost = size * current_price * Decimal("1.001")

                    if cost <= self.cash:
                        self.position += size
                        self.cash -= cost

                        trade = {
                            "timestamp": int(time.time() * 1000),
                            "side": "buy",
                            "price": float(current_price),
                            "size": float(size),
                            "z_score": z_score,
                        }
                        self.trades.append(trade)
                        self._log_trade(trade)

                        logger.info(f"Mean Revert BUY: z={z_score:.2f}, price={current_price:.2f}")

                elif z_score > z_threshold and self.position > 0:
                    # Sell signal (overbought)
                    size = self.position
                    revenue = size * current_price * Decimal("0.999")

                    self.position -= size
                    self.cash += revenue

                    trade = {
                        "timestamp": int(time.time() * 1000),
                        "side": "sell",
                        "price": float(current_price),
                        "size": float(size),
                        "z_score": z_score,
                    }
                    self.trades.append(trade)
                    self._log_trade(trade)

                    logger.info(f"Mean Revert SELL: z={z_score:.2f}, price={current_price:.2f}")

                # Update P&L
                current_value = self.cash + self.position * current_price
                self.pnl = current_value - self.initial_cash

                # Save interim results
                if len(self.trades) % 5 == 0:
                    self._save_results()

            except Exception as e:
                logger.error(f"Mean revert strategy error: {e}")

            time.sleep(3)

    def _run_simple_strategy(self):
        """Run a simple momentum strategy"""
        from src.services.datahub import datahub

        last_price = None
        momentum_threshold = Decimal("0.005")  # 0.5% move

        while self.running:
            try:
                # Get current price
                price_data = datahub.get_latest_price(self.symbol)
                if not price_data or price_data["price"] == 0:
                    time.sleep(3)
                    continue

                current_price = Decimal(str(price_data["price"]))

                if last_price:
                    price_change = (current_price - last_price) / last_price

                    # Buy on positive momentum
                    if price_change > momentum_threshold and self.position == 0:
                        size = (self.cash * Decimal("0.5")) / current_price
                        cost = size * current_price * Decimal("1.001")

                        if cost <= self.cash:
                            self.position += size
                            self.cash -= cost

                            trade = {
                                "timestamp": int(time.time() * 1000),
                                "side": "buy",
                                "price": float(current_price),
                                "size": float(size),
                            }
                            self.trades.append(trade)
                            self._log_trade(trade)

                            logger.info(f"Momentum BUY: {size:.4f} @ {current_price:.2f}")

                    # Sell on negative momentum or take profit
                    elif (
                        price_change < -momentum_threshold or price_change > momentum_threshold * 2
                    ) and self.position > 0:
                        size = self.position
                        revenue = size * current_price * Decimal("0.999")

                        self.position -= size
                        self.cash += revenue

                        trade = {
                            "timestamp": int(time.time() * 1000),
                            "side": "sell",
                            "price": float(current_price),
                            "size": float(size),
                        }
                        self.trades.append(trade)
                        self._log_trade(trade)

                        logger.info(f"Momentum SELL: {size:.4f} @ {current_price:.2f}")

                last_price = current_price

                # Update P&L
                current_value = self.cash + self.position * current_price
                self.pnl = current_value - self.initial_cash

                # Save interim results
                if len(self.trades) % 5 == 0:
                    self._save_results()

            except Exception as e:
                logger.error(f"Simple strategy error: {e}")

            time.sleep(5)

    def _log_trade(self, trade: Dict):
        """Log trade to audit file"""
        audit_file = self.logs_dir / "paper_audit.log"
        with open(audit_file, "a") as f:
            f.write(json.dumps(trade) + "\n")

    def _save_results(self):
        """Save current P&L summary"""
        summary = {
            "timestamp": datetime.now().isoformat(),
            "session": self.session_type,
            "symbol": self.symbol,
            "pnl": float(self.pnl),
            "position": float(self.position),
            "cash": float(self.cash),
            "num_trades": len(self.trades),
            "trades": self.trades[-10:] if self.trades else [],  # Last 10 trades
        }

        summary_file = self.logs_dir / "pnl_summary.json"
        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=2)


# Global instance
paper_engine = PaperEngine()
