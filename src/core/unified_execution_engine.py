"""
Unified Trade Execution Engine
Integrates all trading components into a single powerful engine
"""

import asyncio
import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from ..data.real_time_fetcher import fetcher
from ..ml.real_time_predictor import prediction_engine
from ..portfolio.advanced_portfolio_manager import portfolio_manager
from ..scanner.advanced_market_scanner import market_scanner
from ..trading.paper_trading_engine import OrderSide, OrderStatus, OrderType, paper_engine

logger = logging.getLogger(__name__)


class ExecutionMode(Enum):
    MANUAL = "manual"
    SEMI_AUTO = "semi_auto"  # Suggestions with confirmation
    FULL_AUTO = "full_auto"  # Fully automated


class TradingStrategy(Enum):
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    BREAKOUT = "breakout"
    AI_PREDICTION = "ai_prediction"
    ARBITRAGE = "arbitrage"
    GRID_TRADING = "grid_trading"


@dataclass
class TradingDecision:
    id: str
    user_id: str
    symbol: str
    action: str  # "buy", "sell", "hold"
    quantity: float
    price: Optional[float]
    strategy: TradingStrategy
    confidence: float
    reasoning: str
    risk_score: float
    expected_return: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    timestamp: datetime = None
    executed: bool = False

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)

    def to_dict(self):
        return {
            **asdict(self),
            "strategy": self.strategy.value,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class AutoTradingConfig:
    user_id: str
    enabled: bool = False
    max_position_size: float = 0.1  # Max 10% per position
    max_daily_trades: int = 10
    risk_tolerance: float = 0.02  # Max 2% risk per trade
    strategies: List[TradingStrategy] = None
    min_confidence: float = 0.7  # Minimum confidence for auto execution
    use_ai_predictions: bool = True
    use_market_scanner: bool = True
    stop_loss_percent: float = 0.05  # 5% stop loss
    take_profit_percent: float = 0.10  # 10% take profit

    def __post_init__(self):
        if self.strategies is None:
            self.strategies = [TradingStrategy.MOMENTUM, TradingStrategy.AI_PREDICTION]


class UnifiedExecutionEngine:
    """Main trading execution engine that coordinates all components"""

    def __init__(self):
        self.is_running = False
        self.user_configs: Dict[str, AutoTradingConfig] = {}
        self.trading_decisions: Dict[str, List[TradingDecision]] = {}
        self.execution_queue: List[TradingDecision] = []
        self.daily_trade_counts: Dict[str, Dict[str, int]] = {}  # user_id -> date -> count

        # Strategy weights for ensemble decisions
        self.strategy_weights = {
            TradingStrategy.AI_PREDICTION: 0.4,
            TradingStrategy.MOMENTUM: 0.2,
            TradingStrategy.BREAKOUT: 0.2,
            TradingStrategy.MEAN_REVERSION: 0.1,
            TradingStrategy.ARBITRAGE: 0.1,
        }

    async def start(self):
        """Start the unified execution engine"""
        if self.is_running:
            return

        self.is_running = True

        # Start all dependent engines
        await paper_engine.start()
        await prediction_engine.start()
        await portfolio_manager.start()
        await market_scanner.start()

        # Start execution loops
        asyncio.create_task(self._decision_making_loop())
        asyncio.create_task(self._execution_loop())
        asyncio.create_task(self._monitoring_loop())

        logger.info("Unified Execution Engine started")

    async def stop(self):
        """Stop the execution engine"""
        self.is_running = False

        # Stop all dependent engines
        await paper_engine.stop()
        await prediction_engine.stop()
        await portfolio_manager.stop()
        await market_scanner.stop()

        logger.info("Unified Execution Engine stopped")

    def configure_auto_trading(self, user_id: str, config: AutoTradingConfig):
        """Configure auto trading for a user"""
        config.user_id = user_id
        self.user_configs[user_id] = config
        logger.info(f"Auto trading configured for user {user_id}: enabled={config.enabled}")

    def get_auto_trading_config(self, user_id: str) -> Optional[AutoTradingConfig]:
        """Get auto trading configuration"""
        return self.user_configs.get(user_id)

    async def get_trading_suggestions(
        self, user_id: str, symbol: Optional[str] = None
    ) -> List[Dict]:
        """Get trading suggestions for manual execution"""
        try:
            suggestions = await self._generate_trading_decisions(user_id, symbol)
            return [decision.to_dict() for decision in suggestions]

        except Exception as e:
            logger.error(f"Error getting trading suggestions for {user_id}: {e}")
            return []

    async def execute_manual_trade(self, user_id: str, decision_id: str) -> Dict:
        """Execute a suggested trade manually"""
        try:
            # Find the decision
            user_decisions = self.trading_decisions.get(user_id, [])
            decision = next((d for d in user_decisions if d.id == decision_id), None)

            if not decision:
                return {"success": False, "error": "Decision not found"}

            if decision.executed:
                return {"success": False, "error": "Decision already executed"}

            # Execute the trade
            result = await self._execute_decision(decision)

            if result["success"]:
                decision.executed = True

            return result

        except Exception as e:
            logger.error(f"Error executing manual trade: {e}")
            return {"success": False, "error": str(e)}

    async def _decision_making_loop(self):
        """Main decision making loop"""
        while self.is_running:
            try:
                # Generate decisions for all users with auto trading enabled
                for user_id, config in self.user_configs.items():
                    if config.enabled:
                        decisions = await self._generate_trading_decisions(user_id)

                        # Filter decisions for auto execution
                        auto_decisions = [
                            d
                            for d in decisions
                            if d.confidence >= config.min_confidence
                            and d.risk_score <= config.risk_tolerance
                        ]

                        # Check daily trade limits
                        today = datetime.now(timezone.utc).date().isoformat()
                        if user_id not in self.daily_trade_counts:
                            self.daily_trade_counts[user_id] = {}
                        if today not in self.daily_trade_counts[user_id]:
                            self.daily_trade_counts[user_id][today] = 0

                        daily_count = self.daily_trade_counts[user_id][today]

                        for decision in auto_decisions:
                            if daily_count < config.max_daily_trades:
                                self.execution_queue.append(decision)
                                daily_count += 1

                        self.daily_trade_counts[user_id][today] = daily_count

                        # Store all decisions for manual review
                        if user_id not in self.trading_decisions:
                            self.trading_decisions[user_id] = []
                        self.trading_decisions[user_id].extend(decisions)

                        # Keep only last 100 decisions per user
                        if len(self.trading_decisions[user_id]) > 100:
                            self.trading_decisions[user_id] = self.trading_decisions[user_id][-100:]

                await asyncio.sleep(300)  # Generate decisions every 5 minutes

            except Exception as e:
                logger.error(f"Error in decision making loop: {e}")
                await asyncio.sleep(60)

    async def _execution_loop(self):
        """Execute queued trading decisions"""
        while self.is_running:
            try:
                if self.execution_queue:
                    decision = self.execution_queue.pop(0)

                    # Execute the decision
                    result = await self._execute_decision(decision)

                    if result["success"]:
                        decision.executed = True
                        logger.info(
                            f"Auto executed: {decision.symbol} {decision.action} - {decision.strategy.value}"
                        )
                    else:
                        logger.error(
                            f"Failed to execute: {decision.symbol} {decision.action} - {result['error']}"
                        )

                await asyncio.sleep(1)  # Check queue every second

            except Exception as e:
                logger.error(f"Error in execution loop: {e}")
                await asyncio.sleep(10)

    async def _monitoring_loop(self):
        """Monitor positions and manage risk"""
        while self.is_running:
            try:
                # Check all user portfolios for risk management
                for user_id in self.user_configs.keys():
                    await self._check_risk_management(user_id)

                await asyncio.sleep(30)  # Monitor every 30 seconds

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(60)

    async def _generate_trading_decisions(
        self, user_id: str, specific_symbol: Optional[str] = None
    ) -> List[TradingDecision]:
        """Generate trading decisions using multiple strategies"""
        decisions = []

        try:
            config = self.user_configs.get(user_id, AutoTradingConfig(user_id))
            portfolio = paper_engine.get_portfolio_summary(user_id)

            if not portfolio:
                return decisions

            # Get symbols to analyze
            symbols = [specific_symbol] if specific_symbol else ["BTC", "ETH", "SOL", "BNB", "ADA"]

            for symbol in symbols:
                symbol_decisions = []

                # AI Prediction Strategy
                if TradingStrategy.AI_PREDICTION in config.strategies:
                    ai_decision = await self._ai_prediction_strategy(user_id, symbol, config)
                    if ai_decision:
                        symbol_decisions.append(ai_decision)

                # Market Scanner Strategy
                if config.use_market_scanner:
                    scanner_decision = await self._scanner_strategy(user_id, symbol, config)
                    if scanner_decision:
                        symbol_decisions.append(scanner_decision)

                # Momentum Strategy
                if TradingStrategy.MOMENTUM in config.strategies:
                    momentum_decision = await self._momentum_strategy(user_id, symbol, config)
                    if momentum_decision:
                        symbol_decisions.append(momentum_decision)

                # Combine decisions for this symbol
                if symbol_decisions:
                    combined_decision = await self._combine_decisions(symbol_decisions, config)
                    if combined_decision:
                        decisions.append(combined_decision)

            return decisions

        except Exception as e:
            logger.error(f"Error generating trading decisions: {e}")
            return []

    async def _ai_prediction_strategy(
        self, user_id: str, symbol: str, config: AutoTradingConfig
    ) -> Optional[TradingDecision]:
        """Generate decision based on AI predictions"""
        try:
            prediction = prediction_engine.get_prediction(symbol.lower())

            if not prediction:
                return None

            current_price = prediction.current_price
            predicted_24h = prediction.predicted_price_24h
            confidence = prediction.confidence_24h / 100.0

            # Calculate expected return
            expected_return = (predicted_24h - current_price) / current_price

            # Determine action
            if expected_return > 0.02 and prediction.trend_direction == "up":
                action = "buy"
                reasoning = f"AI predicts {expected_return*100:.1f}% gain in 24h (confidence: {prediction.confidence_24h:.1f}%)"
            elif expected_return < -0.02 and prediction.trend_direction == "down":
                action = "sell"
                reasoning = f"AI predicts {abs(expected_return)*100:.1f}% decline in 24h (confidence: {prediction.confidence_24h:.1f}%)"
            else:
                action = "hold"
                reasoning = "AI prediction shows sideways movement"

            if action == "hold":
                return None

            # Calculate position size
            portfolio = paper_engine.get_portfolio_summary(user_id)
            max_trade_value = portfolio["total_value"] * config.max_position_size
            quantity = max_trade_value / current_price

            # Calculate risk score
            risk_score = (1 - confidence) * abs(expected_return)

            return TradingDecision(
                id=str(uuid.uuid4()),
                user_id=user_id,
                symbol=symbol,
                action=action,
                quantity=quantity,
                price=current_price,
                strategy=TradingStrategy.AI_PREDICTION,
                confidence=confidence,
                reasoning=reasoning,
                risk_score=risk_score,
                expected_return=expected_return,
                stop_loss=(
                    current_price * (1 - config.stop_loss_percent)
                    if action == "buy"
                    else current_price * (1 + config.stop_loss_percent)
                ),
                take_profit=(
                    current_price * (1 + config.take_profit_percent)
                    if action == "buy"
                    else current_price * (1 - config.take_profit_percent)
                ),
            )

        except Exception as e:
            logger.error(f"Error in AI prediction strategy: {e}")
            return None

    async def _scanner_strategy(
        self, user_id: str, symbol: str, config: AutoTradingConfig
    ) -> Optional[TradingDecision]:
        """Generate decision based on market scanner signals"""
        try:
            signals = market_scanner.get_symbol_signals(symbol, 5)

            if not signals:
                return None

            # Get most recent strong signal
            strong_signals = [s for s in signals if s["strength"] >= 70]

            if not strong_signals:
                return None

            signal = strong_signals[0]

            # Convert signal type to action
            signal_type = signal["signal_type"]
            if signal_type in ["buy", "strong_buy"]:
                action = "buy"
            elif signal_type in ["sell", "strong_sell"]:
                action = "sell"
            else:
                return None

            current_price = signal["price"]
            confidence = signal["confidence"] / 100.0
            strength = signal["strength"] / 100.0

            # Calculate expected return (estimated)
            expected_return = 0.03 * strength if action == "buy" else -0.03 * strength

            # Calculate position size
            portfolio = paper_engine.get_portfolio_summary(user_id)
            max_trade_value = portfolio["total_value"] * config.max_position_size
            quantity = max_trade_value / current_price

            # Calculate risk score
            risk_score = (1 - confidence) * abs(expected_return)

            return TradingDecision(
                id=str(uuid.uuid4()),
                user_id=user_id,
                symbol=symbol,
                action=action,
                quantity=quantity,
                price=current_price,
                strategy=TradingStrategy.BREAKOUT,
                confidence=confidence,
                reasoning=f"Scanner signal: {signal['message']} (Strength: {signal['strength']:.1f}%)",
                risk_score=risk_score,
                expected_return=expected_return,
                stop_loss=signal.get("stop_loss"),
                take_profit=signal.get("take_profit"),
            )

        except Exception as e:
            logger.error(f"Error in scanner strategy: {e}")
            return None

    async def _momentum_strategy(
        self, user_id: str, symbol: str, config: AutoTradingConfig
    ) -> Optional[TradingDecision]:
        """Generate decision based on momentum analysis"""
        try:
            # Get market data
            market_data = await fetcher.get_market_data([symbol.lower()])

            if not market_data or symbol not in market_data:
                return None

            data = market_data[symbol]
            current_price = data["price"]
            change_24h = data.get("change_24h", 0)
            volume_24h = data.get("volume_24h", 0)

            # Simple momentum rules
            if change_24h > 5 and volume_24h > 1000000:  # Strong upward momentum
                action = "buy"
                expected_return = 0.02
                confidence = min(0.8, abs(change_24h) / 10)
                reasoning = f"Strong upward momentum: {change_24h:.1f}% with high volume"

            elif change_24h < -5 and volume_24h > 1000000:  # Strong downward momentum
                action = "sell"
                expected_return = -0.02
                confidence = min(0.8, abs(change_24h) / 10)
                reasoning = f"Strong downward momentum: {change_24h:.1f}% with high volume"

            else:
                return None

            # Calculate position size
            portfolio = paper_engine.get_portfolio_summary(user_id)
            max_trade_value = portfolio["total_value"] * config.max_position_size
            quantity = max_trade_value / current_price

            # Calculate risk score
            risk_score = (1 - confidence) * abs(expected_return)

            return TradingDecision(
                id=str(uuid.uuid4()),
                user_id=user_id,
                symbol=symbol,
                action=action,
                quantity=quantity,
                price=current_price,
                strategy=TradingStrategy.MOMENTUM,
                confidence=confidence,
                reasoning=reasoning,
                risk_score=risk_score,
                expected_return=expected_return,
                stop_loss=(
                    current_price * (1 - config.stop_loss_percent)
                    if action == "buy"
                    else current_price * (1 + config.stop_loss_percent)
                ),
                take_profit=(
                    current_price * (1 + config.take_profit_percent)
                    if action == "buy"
                    else current_price * (1 - config.take_profit_percent)
                ),
            )

        except Exception as e:
            logger.error(f"Error in momentum strategy: {e}")
            return None

    async def _combine_decisions(
        self, decisions: List[TradingDecision], config: AutoTradingConfig
    ) -> Optional[TradingDecision]:
        """Combine multiple strategy decisions into one"""
        if not decisions:
            return None

        if len(decisions) == 1:
            return decisions[0]

        try:
            # Group by action
            buy_decisions = [d for d in decisions if d.action == "buy"]
            sell_decisions = [d for d in decisions if d.action == "sell"]

            # Choose the action with higher weighted confidence
            buy_score = sum(
                [d.confidence * self.strategy_weights.get(d.strategy, 0.1) for d in buy_decisions]
            )
            sell_score = sum(
                [d.confidence * self.strategy_weights.get(d.strategy, 0.1) for d in sell_decisions]
            )

            if buy_score > sell_score and buy_score > 0.5:
                chosen_decisions = buy_decisions
                action = "buy"
            elif sell_score > 0.5:
                chosen_decisions = sell_decisions
                action = "sell"
            else:
                return None

            # Combine the chosen decisions
            if not chosen_decisions:
                return None

            # Weighted averages
            total_weight = sum(
                [self.strategy_weights.get(d.strategy, 0.1) for d in chosen_decisions]
            )

            combined_confidence = (
                sum(
                    [
                        d.confidence * self.strategy_weights.get(d.strategy, 0.1)
                        for d in chosen_decisions
                    ]
                )
                / total_weight
            )

            combined_expected_return = (
                sum(
                    [
                        d.expected_return * self.strategy_weights.get(d.strategy, 0.1)
                        for d in chosen_decisions
                    ]
                )
                / total_weight
            )

            combined_risk = (
                sum(
                    [
                        d.risk_score * self.strategy_weights.get(d.strategy, 0.1)
                        for d in chosen_decisions
                    ]
                )
                / total_weight
            )

            # Create combined reasoning
            reasoning = "Combined strategy: " + "; ".join(
                [f"{d.strategy.value} ({d.confidence:.1%})" for d in chosen_decisions]
            )

            # Use values from the highest confidence decision
            best_decision = max(chosen_decisions, key=lambda x: x.confidence)

            return TradingDecision(
                id=str(uuid.uuid4()),
                user_id=best_decision.user_id,
                symbol=best_decision.symbol,
                action=action,
                quantity=best_decision.quantity,
                price=best_decision.price,
                strategy=best_decision.strategy,  # Use best strategy as primary
                confidence=combined_confidence,
                reasoning=reasoning,
                risk_score=combined_risk,
                expected_return=combined_expected_return,
                stop_loss=best_decision.stop_loss,
                take_profit=best_decision.take_profit,
            )

        except Exception as e:
            logger.error(f"Error combining decisions: {e}")
            return None

    async def _execute_decision(self, decision: TradingDecision) -> Dict:
        """Execute a trading decision"""
        try:
            # Place order
            order_side = OrderSide.BUY if decision.action == "buy" else OrderSide.SELL

            order = await paper_engine.place_order(
                user_id=decision.user_id,
                symbol=decision.symbol,
                side=order_side,
                order_type=OrderType.MARKET,
                quantity=decision.quantity,
            )

            if order.status == OrderStatus.FILLED:
                # Place stop loss and take profit orders if specified
                if decision.stop_loss:
                    await paper_engine.place_order(
                        user_id=decision.user_id,
                        symbol=decision.symbol,
                        side=OrderSide.SELL if decision.action == "buy" else OrderSide.BUY,
                        order_type=OrderType.STOP_LOSS,
                        quantity=decision.quantity,
                        price=decision.stop_loss,
                    )

                if decision.take_profit:
                    await paper_engine.place_order(
                        user_id=decision.user_id,
                        symbol=decision.symbol,
                        side=OrderSide.SELL if decision.action == "buy" else OrderSide.BUY,
                        order_type=OrderType.TAKE_PROFIT,
                        quantity=decision.quantity,
                        price=decision.take_profit,
                    )

                return {
                    "success": True,
                    "order_id": order.id,
                    "message": f"Executed {decision.action} order for {decision.quantity} {decision.symbol}",
                }
            else:
                return {"success": False, "error": f"Order not filled: {order.status.value}"}

        except Exception as e:
            logger.error(f"Error executing decision: {e}")
            return {"success": False, "error": str(e)}

    async def _check_risk_management(self, user_id: str):
        """Check and enforce risk management rules"""
        try:
            config = self.user_configs.get(user_id)
            if not config or not config.enabled:
                return

            portfolio = paper_engine.get_portfolio_summary(user_id)
            if not portfolio:
                return

            # Check overall portfolio risk
            if portfolio["total_pnl_percent"] < -10:  # 10% drawdown
                # Disable auto trading temporarily
                config.enabled = False
                logger.warning(f"Auto trading disabled for {user_id} due to high drawdown")

            # Check individual positions for stop losses
            for position in portfolio.get("positions", []):
                symbol = position["symbol"]
                current_price = position["current_price"]
                entry_price = position["avg_price"]
                unrealized_pnl_percent = ((current_price - entry_price) / entry_price) * 100

                # Emergency stop loss at 20%
                if unrealized_pnl_percent < -20:
                    await paper_engine.place_order(
                        user_id=user_id,
                        symbol=symbol,
                        side=OrderSide.SELL,
                        order_type=OrderType.MARKET,
                        quantity=position["quantity"],
                    )
                    logger.warning(f"Emergency stop loss triggered for {user_id} - {symbol}")

        except Exception as e:
            logger.error(f"Error in risk management for {user_id}: {e}")


# Global execution engine instance
execution_engine = UnifiedExecutionEngine()
