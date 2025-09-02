"""
Parallel Paper Trading Runner with K-factor Ramp and Auto-Gates
"""

import asyncio
import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.paper.signal_hub import SignalHub
from src.risk.engine import RiskEngine

logger = logging.getLogger(__name__)


@dataclass
class StrategyLedger:
    """Per-strategy trading ledger"""

    strategy_name: str
    balance: Decimal
    total_pnl: Decimal
    daily_pnl: Decimal
    unrealized_pnl: Decimal
    positions: Dict[str, Any]
    orders: List[Any]
    trade_count: int
    win_count: int
    win_rate: float
    max_drawdown: float
    k_factor: Decimal
    running: bool
    last_update: datetime


class ParallelPaperRunner:
    """Run multiple strategies in parallel with individual ledgers"""

    def __init__(self):
        self.config = {
            "PAPER_INITIAL_BALANCE": Decimal(os.getenv("PAPER_INITIAL_BALANCE", "10000")),
            "MAX_DAILY_LOSS": Decimal(os.getenv("MAX_DAILY_LOSS", "200")),
            "MAX_POSITION_USD": Decimal(os.getenv("MAX_POSITION_USD", "1000")),
            "SLIPPAGE_BPS": int(os.getenv("SLIPPAGE_BPS", "50")),
            "PAPER_FEE_RATE": Decimal(os.getenv("PAPER_FEE_RATE", "0.001")),
        }

        # Strategy configurations from optimization results
        self.strategy_configs = self._load_strategy_configs()

        # Per-strategy ledgers
        self.ledgers: Dict[str, StrategyLedger] = {}

        # Initialize ledgers
        self._initialize_ledgers()

        # Shared components
        self.signal_hub = SignalHub()
        self.risk_engine = RiskEngine()

        # K-factor ramping
        self.start_date = date.today()
        self.k_factor_schedule = {
            0: Decimal("0.25"),  # Day 1
            1: Decimal("0.50"),  # Day 2
            2: Decimal("1.00"),  # Day 3+
        }

        # Auto-gates
        self.gate_violations: Dict[str, List[str]] = {}
        self.kill_switch_active = False

        # Control
        self.running = False
        self.tasks: List[asyncio.Task] = []

        # Reporting
        self.last_replay_check = datetime.now()
        self.replay_interval = timedelta(hours=1)

    def _load_strategy_configs(self) -> Dict[str, Dict[str, Any]]:
        """Load optimized strategy configurations"""
        # Try to load from latest optimization results
        try:
            results_dir = "reports/optimizer"
            if os.path.exists(results_dir):
                # Find latest results
                subdirs = [
                    d
                    for d in os.listdir(results_dir)
                    if os.path.isdir(os.path.join(results_dir, d))
                ]
                if subdirs:
                    latest_dir = sorted(subdirs)[-1]
                    results_file = os.path.join(
                        results_dir, latest_dir, "optimization_results.json"
                    )

                    if os.path.exists(results_file):
                        with open(results_file) as f:
                            results = json.load(f)

                        configs = {}
                        for symbol, symbol_results in results.items():
                            for result in symbol_results[:3]:  # Top 3 per symbol
                                strategy_key = f"{result['strategy_name']}_{symbol}"
                                configs[strategy_key] = {
                                    "strategy_name": result["strategy_name"],
                                    "symbol": symbol,
                                    "parameters": result["parameters"],
                                    "oos_metrics": result["oos_metrics"],
                                }

                        logger.info(f"Loaded {len(configs)} optimized strategy configurations")
                        return configs
        except Exception as e:
            logger.warning(f"Failed to load optimization results: {e}")

        # Fallback to default configurations
        return self._get_default_configs()

    def _get_default_configs(self) -> Dict[str, Dict[str, Any]]:
        """Default strategy configurations"""
        symbols = ["BTC/USDT", "ETH/USDT", "AAPL", "MSFT"]
        strategies = {
            "sma_cross": {"fast_period": 12, "slow_period": 26},
            "ema_breakout": {"ema_period": 21, "breakout_threshold": 2.0},
            "supertrend": {"atr_length": 14, "factor": 2.5},
            "bollinger_revert": {"bb_period": 20, "bb_std": 2.0},
        }

        configs = {}
        for symbol in symbols:
            for strategy_name, params in strategies.items():
                strategy_key = f"{strategy_name}_{symbol}"
                configs[strategy_key] = {
                    "strategy_name": strategy_name,
                    "symbol": symbol,
                    "parameters": params,
                    "oos_metrics": {"sharpe": 0.5, "mar": 0.3},  # Default expectations
                }

        return configs

    def _initialize_ledgers(self):
        """Initialize per-strategy ledgers"""
        initial_balance = self.config["PAPER_INITIAL_BALANCE"]

        for strategy_key, config in self.strategy_configs.items():
            self.ledgers[strategy_key] = StrategyLedger(
                strategy_name=config["strategy_name"],
                balance=initial_balance,
                total_pnl=Decimal("0"),
                daily_pnl=Decimal("0"),
                unrealized_pnl=Decimal("0"),
                positions={},
                orders=[],
                trade_count=0,
                win_count=0,
                win_rate=0.0,
                max_drawdown=0.0,
                k_factor=self.k_factor_schedule[0],
                running=True,
                last_update=datetime.now(),
            )

    async def start(self):
        """Start parallel paper trading"""
        if self.running:
            return

        self.running = True
        logger.info("Starting parallel paper trading runners...")

        # Initialize components
        await self.signal_hub.initialize()

        # Start tasks for each strategy
        for strategy_key in self.ledgers.keys():
            task = asyncio.create_task(self._strategy_runner(strategy_key))
            self.tasks.append(task)

        # Start monitoring tasks
        self.tasks.append(asyncio.create_task(self._k_factor_ramp_monitor()))
        self.tasks.append(asyncio.create_task(self._auto_gates_monitor()))
        self.tasks.append(asyncio.create_task(self._hourly_replay_monitor()))

        logger.info(f"Started {len(self.tasks)} parallel tasks")

    async def stop(self):
        """Stop all runners"""
        self.running = False

        # Cancel all tasks
        for task in self.tasks:
            task.cancel()

        # Wait for tasks to finish
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)

        self.tasks.clear()
        logger.info("Parallel paper trading stopped")

    async def _strategy_runner(self, strategy_key: str):
        """Run individual strategy"""
        config = self.strategy_configs[strategy_key]
        ledger = self.ledgers[strategy_key]

        logger.info(f"Starting runner for {strategy_key}")

        while self.running and ledger.running and not self.kill_switch_active:
            try:
                # Update K-factor
                ledger.k_factor = self._get_current_k_factor()

                # Get signal for this strategy's symbol
                symbol = config["symbol"]
                current_price = await self._get_current_price(symbol)

                if current_price is None:
                    await asyncio.sleep(10)
                    continue

                # Get signal from strategy
                signal = await self._get_strategy_signal(config, symbol, current_price)

                if signal and signal.get("strength", 0) > 0.1:
                    await self._process_strategy_signal(strategy_key, signal, current_price)

                # Update positions and P&L
                await self._update_strategy_pnl(strategy_key, current_price)

                # Check exit conditions
                await self._check_strategy_exits(strategy_key, current_price)

                ledger.last_update = datetime.now()
                await asyncio.sleep(15)  # 15 second cycle

            except Exception as e:
                logger.error(f"Error in strategy runner {strategy_key}: {e}")
                await asyncio.sleep(30)

    async def _get_current_price(self, symbol: str) -> Optional[Decimal]:
        """Get current market price"""
        try:
            # Mock price fetching - in production would fetch from data feeds
            import random

            base_prices = {"BTC/USDT": 67000, "ETH/USDT": 3400, "AAPL": 185, "MSFT": 420}

            base_price = base_prices.get(symbol, 100)
            # Add some random variation
            variation = random.uniform(-0.005, 0.005)  # ±0.5%
            price = base_price * (1 + variation)

            return Decimal(str(price))
        except Exception as e:
            logger.error(f"Failed to get price for {symbol}: {e}")
            return None

    async def _get_strategy_signal(
        self, config: Dict[str, Any], symbol: str, current_price: Decimal
    ) -> Optional[Dict[str, Any]]:
        """Get signal from specific strategy"""
        try:
            # Get signal from signal hub (would be filtered by strategy)
            signal = self.signal_hub.get_signal(symbol, current_price)

            if signal:
                # Filter by strategy name if needed
                strategy_name = config["strategy_name"]
                if signal.get("strategy") == strategy_name or signal.get("strategies"):
                    return signal

            return None
        except Exception as e:
            logger.error(f"Failed to get signal for {config['strategy_name']}/{symbol}: {e}")
            return None

    async def _process_strategy_signal(
        self, strategy_key: str, signal: Dict[str, Any], current_price: Decimal
    ):
        """Process trading signal for strategy"""
        config = self.strategy_configs[strategy_key]
        ledger = self.ledgers[strategy_key]
        symbol = config["symbol"]

        # Calculate position size
        position_size = self._calculate_position_size(ledger, signal["strength"])

        if position_size == Decimal("0"):
            return

        # Risk checks
        risk_check = await self._check_strategy_risk(
            strategy_key, symbol, position_size, current_price
        )
        if not risk_check["approved"]:
            logger.warning(f"Risk check failed for {strategy_key}: {risk_check}")
            return

        # Create order
        side = "buy" if signal["direction"] > 0 else "sell"
        await self._create_strategy_order(strategy_key, symbol, side, position_size, current_price)

    def _calculate_position_size(self, ledger: StrategyLedger, signal_strength: float) -> Decimal:
        """Calculate position size for strategy"""
        # Use Kelly-inspired sizing
        risk_amount = ledger.balance * ledger.k_factor * Decimal(str(abs(signal_strength)))

        # For simplicity, assume 2% stop distance
        stop_distance_pct = Decimal("0.02")
        position_size = risk_amount / stop_distance_pct

        # Apply limits
        max_position = self.config["MAX_POSITION_USD"]
        position_size = min(position_size, max_position)

        return position_size

    async def _check_strategy_risk(
        self, strategy_key: str, symbol: str, position_size: Decimal, price: Decimal
    ) -> Dict[str, Any]:
        """Check risk for strategy trade"""
        ledger = self.ledgers[strategy_key]

        # Daily loss check
        max_daily_loss = self.config["MAX_DAILY_LOSS"]
        if ledger.daily_pnl < -max_daily_loss:
            return {"approved": False, "reason": "daily_loss_limit"}

        # Position size check
        position_value = position_size * price
        if position_value > self.config["MAX_POSITION_USD"]:
            return {"approved": False, "reason": "position_size_limit"}

        # Balance check
        if ledger.balance < position_value:
            return {"approved": False, "reason": "insufficient_balance"}

        return {"approved": True}

    async def _create_strategy_order(
        self, strategy_key: str, symbol: str, side: str, quantity: Decimal, price: Decimal
    ):
        """Create order for strategy"""
        ledger = self.ledgers[strategy_key]

        # Simulate order execution
        slippage_bps = self.config["SLIPPAGE_BPS"]
        slippage_factor = Decimal(str(slippage_bps / 10000))

        if side == "buy":
            filled_price = price * (Decimal("1") + slippage_factor)
        else:
            filled_price = price * (Decimal("1") - slippage_factor)

        fee_rate = self.config["PAPER_FEE_RATE"]
        fees = quantity * filled_price * fee_rate

        # Create order record
        order = {
            "timestamp": datetime.now(),
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "filled_price": filled_price,
            "fees": fees,
            "status": "filled",
        }

        ledger.orders.append(order)
        ledger.trade_count += 1

        # Update positions
        if side == "buy":
            if symbol in ledger.positions:
                # Add to existing position
                old_pos = ledger.positions[symbol]
                old_qty = old_pos["quantity"]
                old_price = old_pos["entry_price"]

                new_qty = old_qty + quantity
                new_avg_price = ((old_qty * old_price) + (quantity * filled_price)) / new_qty

                ledger.positions[symbol].update({"quantity": new_qty, "entry_price": new_avg_price})
            else:
                # New position
                ledger.positions[symbol] = {
                    "quantity": quantity,
                    "entry_price": filled_price,
                    "side": "long",
                    "entry_time": datetime.now(),
                }

            ledger.balance -= quantity * filled_price + fees

        elif symbol in ledger.positions:
            pos = ledger.positions[symbol]

            # Calculate P&L
            pnl = (filled_price - pos["entry_price"]) * min(quantity, pos["quantity"])
            ledger.total_pnl += pnl
            ledger.daily_pnl += pnl

            if pnl > 0:
                ledger.win_count += 1

            # Update win rate
            ledger.win_rate = ledger.win_count / ledger.trade_count * 100

            # Reduce or close position
            if quantity >= pos["quantity"]:
                # Close position
                ledger.balance += pos["quantity"] * filled_price - fees
                del ledger.positions[symbol]
            else:
                # Reduce position
                pos["quantity"] -= quantity
                ledger.balance += quantity * filled_price - fees

        logger.info(
            f"Order executed for {strategy_key}: {side} {quantity} {symbol} @ {filled_price}"
        )

    async def _update_strategy_pnl(self, strategy_key: str, current_price: Decimal):
        """Update strategy P&L"""
        ledger = self.ledgers[strategy_key]
        config = self.strategy_configs[strategy_key]
        symbol = config["symbol"]

        if symbol in ledger.positions:
            pos = ledger.positions[symbol]
            unrealized_pnl = (current_price - pos["entry_price"]) * pos["quantity"]
            ledger.unrealized_pnl = unrealized_pnl

    async def _check_strategy_exits(self, strategy_key: str, current_price: Decimal):
        """Check exit conditions for strategy positions"""
        ledger = self.ledgers[strategy_key]
        config = self.strategy_configs[strategy_key]
        symbol = config["symbol"]

        if symbol not in ledger.positions:
            return

        pos = ledger.positions[symbol]

        # Simple stop-loss and take-profit (2% and 4%)
        entry_price = pos["entry_price"]

        if pos["side"] == "long":
            stop_price = entry_price * Decimal("0.98")  # 2% stop
            target_price = entry_price * Decimal("1.04")  # 4% target

            if current_price <= stop_price or current_price >= target_price:
                await self._create_strategy_order(
                    strategy_key, symbol, "sell", pos["quantity"], current_price
                )

    def _get_current_k_factor(self) -> Decimal:
        """Get current K-factor based on ramp schedule"""
        days_since_start = (date.today() - self.start_date).days

        if days_since_start >= 2:
            return self.k_factor_schedule[2]
        elif days_since_start >= 1:
            return self.k_factor_schedule[1]
        else:
            return self.k_factor_schedule[0]

    async def _k_factor_ramp_monitor(self):
        """Monitor K-factor ramping"""
        while self.running:
            current_k = self._get_current_k_factor()

            # Update all ledgers
            for ledger in self.ledgers.values():
                if ledger.k_factor != current_k:
                    ledger.k_factor = current_k
                    logger.info(f"K-factor updated to {current_k} for all strategies")

            await asyncio.sleep(3600)  # Check hourly

    async def _auto_gates_monitor(self):
        """Monitor auto-gates and downgrade/kill switch"""
        while self.running:
            violated_strategies = []

            for strategy_key, ledger in self.ledgers.items():
                violations = []

                # Check error rate (mock - would check actual error metrics)
                error_rate = 0.005  # 0.5% mock error rate
                if error_rate > 0.01:  # > 1%
                    violations.append("high_error_rate")

                # Check slippage (mock)
                avg_slippage_bps = 45  # Mock
                if avg_slippage_bps > 50:
                    violations.append("high_slippage")

                # Check max drawdown
                if ledger.max_drawdown < -15:  # > 15% DD
                    violations.append("excessive_drawdown")

                # Check daily loss
                max_daily_loss = self.config["MAX_DAILY_LOSS"]
                if ledger.daily_pnl < -max_daily_loss:
                    violations.append("daily_loss_limit")

                if violations:
                    self.gate_violations[strategy_key] = violations

                    # Auto-downgrade: reduce K-factor by half
                    ledger.k_factor *= Decimal("0.5")
                    logger.warning(
                        f"Auto-downgrade for {strategy_key}: K-factor -> {ledger.k_factor}, violations: {violations}"
                    )

                    # If still violating, stop strategy
                    if len(violations) >= 2:
                        ledger.running = False
                        violated_strategies.append(strategy_key)
                        logger.error(
                            f"Strategy {strategy_key} stopped due to violations: {violations}"
                        )

            # Kill switch if too many strategies failed
            if len(violated_strategies) >= len(self.ledgers) * 0.5:  # 50% failure rate
                self.kill_switch_active = True
                logger.critical("KILL SWITCH ACTIVATED - 50% strategy failure rate")

                for ledger in self.ledgers.values():
                    ledger.running = False

            await asyncio.sleep(300)  # Check every 5 minutes

    async def _hourly_replay_monitor(self):
        """Run hourly replay simulations"""
        while self.running:
            if datetime.now() - self.last_replay_check >= self.replay_interval:
                logger.info("Running hourly replay simulation...")

                try:
                    await self._run_quick_replay()
                    self.last_replay_check = datetime.now()
                except Exception as e:
                    logger.error(f"Hourly replay failed: {e}")

            await asyncio.sleep(600)  # Check every 10 minutes

    async def _run_quick_replay(self):
        """Run quick replay simulation"""
        from scripts.paper_replay import PaperReplay

        # Run 6-hour replay
        replay = PaperReplay(hours=6)
        report = await replay.run_replay()

        if report:
            expected_pnl = report["results"]["total_pnl"]

            # Compare with actual performance
            total_actual_pnl = sum(ledger.total_pnl for ledger in self.ledgers.values())

            divergence = abs(float(total_actual_pnl) - expected_pnl)
            divergence_pct = divergence / abs(expected_pnl) * 100 if expected_pnl != 0 else 0

            logger.info(
                f"Replay vs Actual: Expected=${expected_pnl:.2f}, Actual=${total_actual_pnl:.2f}, "
                f"Divergence={divergence_pct:.1f}%"
            )

            # Save divergence report
            divergence_report = {
                "timestamp": datetime.now().isoformat(),
                "expected_pnl": expected_pnl,
                "actual_pnl": float(total_actual_pnl),
                "divergence_pct": divergence_pct,
                "replay_hours": 6,
                "strategy_breakdown": {
                    key: {
                        "total_pnl": float(ledger.total_pnl),
                        "daily_pnl": float(ledger.daily_pnl),
                        "trade_count": ledger.trade_count,
                        "win_rate": ledger.win_rate,
                        "k_factor": float(ledger.k_factor),
                        "running": ledger.running,
                    }
                    for key, ledger in self.ledgers.items()
                },
            }

            os.makedirs("reports/paper/divergence", exist_ok=True)
            divergence_file = f"reports/paper/divergence/divergence_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

            with open(divergence_file, "w") as f:
                json.dump(divergence_report, f, indent=2)

    def get_combined_state(self) -> Dict[str, Any]:
        """Get combined state of all strategies"""
        total_balance = sum(ledger.balance for ledger in self.ledgers.values())
        total_pnl = sum(ledger.total_pnl for ledger in self.ledgers.values())
        total_daily_pnl = sum(ledger.daily_pnl for ledger in self.ledgers.values())
        total_trades = sum(ledger.trade_count for ledger in self.ledgers.values())
        total_positions = sum(len(ledger.positions) for ledger in self.ledgers.values())

        # Calculate combined win rate
        total_wins = sum(ledger.win_count for ledger in self.ledgers.values())
        combined_win_rate = total_wins / total_trades * 100 if total_trades > 0 else 0

        return {
            "total_balance": float(total_balance),
            "total_pnl": float(total_pnl),
            "daily_pnl": float(total_daily_pnl),
            "trade_count": total_trades,
            "positions_count": total_positions,
            "win_rate": combined_win_rate,
            "strategies_running": sum(1 for ledger in self.ledgers.values() if ledger.running),
            "total_strategies": len(self.ledgers),
            "k_factor": float(self._get_current_k_factor()),
            "kill_switch_active": self.kill_switch_active,
            "running": self.running,
            "gate_violations": len(self.gate_violations),
            "strategy_breakdown": {key: asdict(ledger) for key, ledger in self.ledgers.items()},
        }
