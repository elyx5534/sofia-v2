"""
Binance Funding Rate Farming Strategy
Delta-neutral positions to harvest funding rates
"""

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from statistics import mean
from typing import Any, Dict, List, Optional, Set

import numpy as np

logger = logging.getLogger(__name__)


class MarketType(Enum):
    PERPETUAL = "perpetual"
    SPOT = "spot"
    MARGIN = "margin"


class PositionSide(Enum):
    LONG = "long"
    SHORT = "short"


class FarmStatus(Enum):
    SCANNING = "scanning"
    ENTERING = "entering"
    FARMING = "farming"
    REBALANCING = "rebalancing"
    CLOSING = "closing"
    CLOSED = "closed"


@dataclass
class FundingData:
    """Funding rate data for a symbol"""

    symbol: str
    funding_rate: Decimal
    funding_time: datetime
    mark_price: Decimal
    index_price: Decimal
    volume_24h: Decimal
    open_interest: Decimal
    predicted_rate: Optional[Decimal] = None
    timestamp: float = field(default_factory=time.time)

    @property
    def hours_until_funding(self) -> float:
        """Hours until next funding payment"""
        now = datetime.now()
        time_diff = self.funding_time - now
        return time_diff.total_seconds() / 3600

    @property
    def is_negative(self) -> bool:
        """Check if funding rate is negative (favorable for longs)"""
        return self.funding_rate < 0

    @property
    def annualized_rate(self) -> Decimal:
        """Calculate annualized funding rate (3 payments per day)"""
        return self.funding_rate * 3 * 365


@dataclass
class DeltaNeutralPosition:
    """Delta-neutral position for funding farming"""

    symbol: str
    perp_side: PositionSide  # Always LONG for negative funding
    spot_side: PositionSide  # Always SHORT for hedging
    perp_size: Decimal
    spot_size: Decimal
    perp_entry: Decimal
    spot_entry: Decimal
    current_perp_price: Decimal
    current_spot_price: Decimal
    funding_rate: Decimal
    entry_time: datetime
    status: FarmStatus
    total_funding_collected: Decimal = Decimal(0)
    rebalance_count: int = 0

    @property
    def position_value(self) -> Decimal:
        """Total position value in USD"""
        return self.perp_size * self.current_perp_price

    @property
    def delta(self) -> Decimal:
        """Calculate position delta (should be close to 0)"""
        perp_value = self.perp_size * self.current_perp_price
        spot_value = self.spot_size * self.current_spot_price
        return perp_value - spot_value

    @property
    def delta_percentage(self) -> Decimal:
        """Delta as percentage of position"""
        if self.position_value > 0:
            return (self.delta / self.position_value) * 100
        return Decimal(0)

    @property
    def funding_per_payment(self) -> Decimal:
        """Expected funding per 8-hour payment"""
        return abs(self.funding_rate) * self.position_value

    @property
    def daily_funding(self) -> Decimal:
        """Expected daily funding (3 payments)"""
        return self.funding_per_payment * 3

    @property
    def apy(self) -> Decimal:
        """Annual percentage yield from funding"""
        return abs(self.funding_rate) * 3 * 365 * 100


@dataclass
class FarmingOpportunity:
    """Funding farming opportunity"""

    symbol: str
    funding_rate: Decimal
    predicted_rate: Decimal
    volume_24h: Decimal
    open_interest: Decimal
    mark_price: Decimal
    spot_price: Decimal
    spread: Decimal  # Mark vs Spot
    score: Decimal  # Opportunity score
    estimated_daily_return: Decimal
    risk_level: str  # LOW, MEDIUM, HIGH


class FundingRateFarmer:
    """Farms funding rates using delta-neutral positions"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

        # Scanner parameters
        self.min_negative_funding = Decimal(
            str(config.get("min_negative_funding", -0.0001))
        )  # -0.01%
        self.min_volume = Decimal(str(config.get("min_volume", 10000000)))  # $10M
        self.min_open_interest = Decimal(str(config.get("min_open_interest", 5000000)))  # $5M

        # Position parameters
        self.max_concurrent_positions = config.get("max_concurrent_positions", 5)
        self.max_capital_percentage = Decimal(str(config.get("max_capital_percentage", 0.3)))  # 30%
        self.position_size_per_farm = Decimal(
            str(config.get("position_size_per_farm", 10000))
        )  # $10K
        self.delta_threshold = Decimal(
            str(config.get("delta_threshold", 0.02))
        )  # 2% delta tolerance

        # Rebalancing parameters
        self.rebalance_interval_hours = config.get("rebalance_interval_hours", 4)
        self.max_rebalance_cost = Decimal(str(config.get("max_rebalance_cost", 0.001)))  # 0.1%

        # Risk parameters
        self.max_spread = Decimal(str(config.get("max_spread", 0.002)))  # 0.2% mark vs spot
        self.min_time_until_funding = config.get("min_time_until_funding", 0.5)  # 30 minutes
        self.compound_earnings = config.get("compound_earnings", True)

        # API configuration
        self.api_key = config.get("api_key", "")
        self.api_secret = config.get("api_secret", "")
        self.testnet = config.get("testnet", True)

        # State tracking
        self.funding_data: Dict[str, FundingData] = {}
        self.positions: Dict[str, DeltaNeutralPosition] = {}
        self.opportunities: List[FarmingOpportunity] = []
        self.total_funding_collected = Decimal(0)
        self.total_capital_deployed = Decimal(0)
        self.available_capital = Decimal(str(config.get("initial_capital", 100000)))

        # Historical data for prediction
        self.funding_history: Dict[str, deque] = {}
        self.prediction_model_data: Dict[str, List] = {}

        # Blacklist for problematic symbols
        self.blacklist: Set[str] = set()

        # Tasks
        self.scanner_task = None
        self.rebalance_task = None
        self.collector_task = None
        self.predictor_task = None

    async def initialize(self):
        """Initialize funding rate farmer"""
        logger.info("Initializing Funding Rate Farmer")

        # Start tasks
        self.scanner_task = asyncio.create_task(self._scan_funding_rates())
        self.rebalance_task = asyncio.create_task(self._rebalance_positions())
        self.collector_task = asyncio.create_task(self._collect_funding())
        self.predictor_task = asyncio.create_task(self._predict_funding_rates())

        # Load historical data
        await self._load_historical_data()

        logger.info("Funding Rate Farmer initialized")

    async def shutdown(self):
        """Shutdown the farmer"""
        # Cancel tasks
        for task in [
            self.scanner_task,
            self.rebalance_task,
            self.collector_task,
            self.predictor_task,
        ]:
            if task:
                task.cancel()

        # Close all positions
        for position in list(self.positions.values()):
            await self._close_position(position, "Shutdown")

    async def _scan_funding_rates(self):
        """Continuously scan for funding opportunities"""
        while True:
            try:
                # Get all perpetual contracts
                symbols = await self._get_perpetual_symbols()

                opportunities = []

                for symbol in symbols:
                    # Skip if blacklisted
                    if symbol in self.blacklist:
                        continue

                    # Get funding data
                    funding_data = await self._get_funding_data(symbol)

                    if not funding_data:
                        continue

                    # Store funding data
                    self.funding_data[symbol] = funding_data

                    # Check if opportunity
                    if self._is_opportunity(funding_data):
                        opportunity = await self._evaluate_opportunity(funding_data)
                        if opportunity:
                            opportunities.append(opportunity)

                # Sort opportunities by score
                opportunities.sort(key=lambda x: x.score, reverse=True)
                self.opportunities = opportunities

                # Execute top opportunities
                await self._execute_opportunities(opportunities[: self.max_concurrent_positions])

                # Log summary
                if opportunities:
                    logger.info(f"Found {len(opportunities)} funding opportunities")
                    top_opp = opportunities[0]
                    logger.info(
                        f"Best: {top_opp.symbol} "
                        f"Rate: {top_opp.funding_rate:.4%} "
                        f"Daily: ${top_opp.estimated_daily_return:.2f}"
                    )

                await asyncio.sleep(60)  # Scan every minute

            except Exception as e:
                logger.error(f"Funding scanner error: {e}")
                await asyncio.sleep(30)

    async def _get_perpetual_symbols(self) -> List[str]:
        """Get all perpetual contract symbols"""
        try:
            # In production, fetch from Binance API
            # For now, return common perpetuals
            return [
                "BTCUSDT",
                "ETHUSDT",
                "BNBUSDT",
                "SOLUSDT",
                "ADAUSDT",
                "DOTUSDT",
                "AVAXUSDT",
                "MATICUSDT",
                "LINKUSDT",
                "UNIUSDT",
                "ATOMUSDT",
                "NEARUSDT",
                "FTMUSDT",
                "ALGOUSDT",
                "VETUSDT",
                "ICPUSDT",
            ]
        except Exception as e:
            logger.error(f"Error getting symbols: {e}")
            return []

    async def _get_funding_data(self, symbol: str) -> Optional[FundingData]:
        """Get funding rate data for symbol"""
        try:
            # In production, fetch from Binance API
            # For now, return mock data

            # Simulate various funding rates
            base_rate = np.random.uniform(-0.02, 0.01)  # -2% to 1%

            # Make some symbols consistently negative
            if symbol in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]:
                base_rate = np.random.uniform(-0.02, -0.005)

            return FundingData(
                symbol=symbol,
                funding_rate=Decimal(str(base_rate / 100)),  # Convert to decimal percentage
                funding_time=datetime.now() + timedelta(hours=np.random.uniform(0.5, 8)),
                mark_price=Decimal(str(np.random.uniform(100, 50000))),
                index_price=Decimal(str(np.random.uniform(100, 50000))),
                volume_24h=Decimal(str(np.random.uniform(5000000, 100000000))),
                open_interest=Decimal(str(np.random.uniform(1000000, 50000000))),
            )

        except Exception as e:
            logger.error(f"Error getting funding data for {symbol}: {e}")
            return None

    def _is_opportunity(self, funding_data: FundingData) -> bool:
        """Check if funding data represents an opportunity"""
        return (
            funding_data.funding_rate <= self.min_negative_funding
            and funding_data.volume_24h >= self.min_volume
            and funding_data.open_interest >= self.min_open_interest
            and funding_data.hours_until_funding >= self.min_time_until_funding
        )

    async def _evaluate_opportunity(
        self, funding_data: FundingData
    ) -> Optional[FarmingOpportunity]:
        """Evaluate and score a funding opportunity"""
        try:
            # Get spot price
            spot_price = await self._get_spot_price(
                funding_data.symbol.replace("USDT", "") + "USDT"
            )

            if not spot_price:
                return None

            # Calculate spread
            spread = abs(funding_data.mark_price - spot_price) / spot_price

            # Skip if spread too wide
            if spread > self.max_spread:
                return None

            # Predict next funding rate
            predicted_rate = await self._predict_single_rate(funding_data.symbol)

            # Calculate score
            score = self._calculate_opportunity_score(funding_data, predicted_rate, spread)

            # Calculate estimated returns
            position_value = self.position_size_per_farm
            funding_per_payment = abs(funding_data.funding_rate) * position_value
            daily_return = funding_per_payment * 3  # 3 payments per day

            # Determine risk level
            risk_level = self._assess_risk_level(funding_data, spread, predicted_rate)

            return FarmingOpportunity(
                symbol=funding_data.symbol,
                funding_rate=funding_data.funding_rate,
                predicted_rate=predicted_rate,
                volume_24h=funding_data.volume_24h,
                open_interest=funding_data.open_interest,
                mark_price=funding_data.mark_price,
                spot_price=spot_price,
                spread=spread,
                score=score,
                estimated_daily_return=daily_return,
                risk_level=risk_level,
            )

        except Exception as e:
            logger.error(f"Error evaluating opportunity: {e}")
            return None

    async def _get_spot_price(self, symbol: str) -> Optional[Decimal]:
        """Get spot price for symbol"""
        try:
            # In production, fetch from API
            # For now, return mock price close to mark
            mark_price = self.funding_data.get(
                symbol,
                FundingData(
                    symbol=symbol,
                    funding_rate=Decimal(0),
                    funding_time=datetime.now(),
                    mark_price=Decimal("1000"),
                    index_price=Decimal("1000"),
                    volume_24h=Decimal(0),
                    open_interest=Decimal(0),
                ),
            ).mark_price

            # Add small spread
            spread_factor = Decimal(str(1 + np.random.uniform(-0.002, 0.002)))
            return mark_price * spread_factor

        except Exception as e:
            logger.error(f"Error getting spot price: {e}")
            return None

    def _calculate_opportunity_score(
        self, funding_data: FundingData, predicted_rate: Decimal, spread: Decimal
    ) -> Decimal:
        """Calculate opportunity score (0-100)"""
        score = Decimal(0)

        # Funding rate component (40 points max)
        funding_score = min(40, abs(funding_data.funding_rate) * 2000)
        score += funding_score

        # Predicted rate component (20 points max)
        if predicted_rate < 0:
            predicted_score = min(20, abs(predicted_rate) * 1000)
            score += predicted_score

        # Volume component (15 points max)
        volume_score = min(15, funding_data.volume_24h / Decimal("10000000"))
        score += volume_score

        # Open interest component (15 points max)
        oi_score = min(15, funding_data.open_interest / Decimal("5000000"))
        score += oi_score

        # Spread penalty (10 points max penalty)
        spread_penalty = min(10, spread * 500)
        score -= spread_penalty

        # Time until funding bonus (up to 10 points)
        if funding_data.hours_until_funding < 2:
            time_bonus = Decimal(10)
        else:
            time_bonus = max(0, 10 - funding_data.hours_until_funding)
        score += time_bonus

        return max(0, min(100, score))

    def _assess_risk_level(
        self, funding_data: FundingData, spread: Decimal, predicted_rate: Decimal
    ) -> str:
        """Assess risk level of opportunity"""
        risk_score = 0

        # Check funding stability
        if predicted_rate >= 0:
            risk_score += 3  # High risk if funding might flip

        # Check spread
        if spread > Decimal("0.001"):
            risk_score += 2

        # Check volume
        if funding_data.volume_24h < Decimal("20000000"):
            risk_score += 1

        # Check time until funding
        if funding_data.hours_until_funding < 1:
            risk_score += 1

        if risk_score <= 2:
            return "LOW"
        elif risk_score <= 4:
            return "MEDIUM"
        else:
            return "HIGH"

    async def _execute_opportunities(self, opportunities: List[FarmingOpportunity]):
        """Execute top funding opportunities"""
        for opportunity in opportunities:
            # Check if already have position
            if opportunity.symbol in self.positions:
                continue

            # Check position limits
            if len(self.positions) >= self.max_concurrent_positions:
                break

            # Check capital limits
            required_capital = self.position_size_per_farm * 2  # Need capital for both legs
            if required_capital > self.available_capital:
                break

            if (
                self.total_capital_deployed + required_capital
                > self.available_capital * self.max_capital_percentage
            ):
                break

            # Execute position
            success = await self._open_delta_neutral_position(opportunity)

            if success:
                logger.info(
                    f"Opened funding farm: {opportunity.symbol} "
                    f"Rate: {opportunity.funding_rate:.4%} "
                    f"Daily: ${opportunity.estimated_daily_return:.2f}"
                )

    async def _open_delta_neutral_position(self, opportunity: FarmingOpportunity) -> bool:
        """Open a delta-neutral position"""
        try:
            symbol = opportunity.symbol
            position_size = self.position_size_per_farm

            # Calculate sizes
            perp_size = position_size / opportunity.mark_price
            spot_size = position_size / opportunity.spot_price

            # In production, place actual orders
            # For now, simulate position opening

            position = DeltaNeutralPosition(
                symbol=symbol,
                perp_side=PositionSide.LONG,  # Long perp for negative funding
                spot_side=PositionSide.SHORT,  # Short spot for hedge
                perp_size=perp_size,
                spot_size=spot_size,
                perp_entry=opportunity.mark_price,
                spot_entry=opportunity.spot_price,
                current_perp_price=opportunity.mark_price,
                current_spot_price=opportunity.spot_price,
                funding_rate=opportunity.funding_rate,
                entry_time=datetime.now(),
                status=FarmStatus.FARMING,
            )

            # Update state
            self.positions[symbol] = position
            self.total_capital_deployed += position_size * 2
            self.available_capital -= position_size * 2

            return True

        except Exception as e:
            logger.error(f"Error opening position: {e}")
            return False

    async def _rebalance_positions(self):
        """Rebalance delta-neutral positions periodically"""
        while True:
            try:
                await asyncio.sleep(self.rebalance_interval_hours * 3600)

                for position in list(self.positions.values()):
                    if position.status != FarmStatus.FARMING:
                        continue

                    # Update prices
                    await self._update_position_prices(position)

                    # Check delta
                    if abs(position.delta_percentage) > self.delta_threshold * 100:
                        logger.info(
                            f"Rebalancing {position.symbol}: "
                            f"Delta {position.delta_percentage:.2f}%"
                        )

                        await self._rebalance_position(position)

                    # Check if funding turned positive
                    current_funding = self.funding_data.get(position.symbol)
                    if current_funding and current_funding.funding_rate > 0:
                        logger.warning(
                            f"Funding turned positive for {position.symbol}: "
                            f"{current_funding.funding_rate:.4%}"
                        )
                        await self._close_position(position, "Positive funding")

            except Exception as e:
                logger.error(f"Rebalancing error: {e}")

    async def _update_position_prices(self, position: DeltaNeutralPosition):
        """Update current prices for position"""
        try:
            # Get current mark price
            funding_data = self.funding_data.get(position.symbol)
            if funding_data:
                position.current_perp_price = funding_data.mark_price

            # Get current spot price
            spot_price = await self._get_spot_price(position.symbol)
            if spot_price:
                position.current_spot_price = spot_price

        except Exception as e:
            logger.error(f"Error updating prices: {e}")

    async def _rebalance_position(self, position: DeltaNeutralPosition):
        """Rebalance a position to maintain delta neutrality"""
        try:
            position.status = FarmStatus.REBALANCING

            # Calculate rebalance amounts
            target_value = position.position_value
            current_spot_value = position.spot_size * position.current_spot_price

            if position.delta > 0:
                # Perp value > Spot value, need more spot short
                additional_spot = (target_value - current_spot_value) / position.current_spot_price
                position.spot_size += additional_spot
            else:
                # Spot value > Perp value, need more perp long
                additional_perp = (current_spot_value - target_value) / position.current_perp_price
                position.perp_size += additional_perp

            position.rebalance_count += 1
            position.status = FarmStatus.FARMING

            logger.info(f"Rebalanced {position.symbol}: Delta now {position.delta_percentage:.2f}%")

        except Exception as e:
            logger.error(f"Rebalancing error: {e}")
            position.status = FarmStatus.FARMING

    async def _collect_funding(self):
        """Collect funding payments every 8 hours"""
        while True:
            try:
                # Wait until next funding time (every 8 hours at 00:00, 08:00, 16:00 UTC)
                await self._wait_until_next_funding()

                total_collected = Decimal(0)

                for position in self.positions.values():
                    if position.status != FarmStatus.FARMING:
                        continue

                    # Calculate funding payment
                    funding_payment = position.funding_per_payment

                    # Update position
                    position.total_funding_collected += funding_payment
                    total_collected += funding_payment

                    # Update global stats
                    self.total_funding_collected += funding_payment

                    logger.info(
                        f"Collected funding for {position.symbol}: "
                        f"${funding_payment:.2f} "
                        f"(Total: ${position.total_funding_collected:.2f})"
                    )

                # Compound earnings if enabled
                if self.compound_earnings and total_collected > 0:
                    self.available_capital += total_collected
                    logger.info(f"Compounded ${total_collected:.2f} in earnings")

                logger.info(f"Total funding collected this round: ${total_collected:.2f}")

            except Exception as e:
                logger.error(f"Funding collection error: {e}")
                await asyncio.sleep(60)

    async def _wait_until_next_funding(self):
        """Wait until next funding time"""
        now = datetime.now()
        hour = now.hour

        # Funding times: 00:00, 08:00, 16:00 UTC
        funding_hours = [0, 8, 16]
        next_funding_hour = min(h for h in funding_hours if h > hour % 24)

        if next_funding_hour == hour:
            next_funding_hour = funding_hours[0]
            next_funding = now.replace(hour=next_funding_hour, minute=0, second=0) + timedelta(
                days=1
            )
        else:
            next_funding = now.replace(hour=next_funding_hour, minute=0, second=0)

        wait_seconds = (next_funding - now).total_seconds()
        logger.info(f"Waiting {wait_seconds/60:.1f} minutes until next funding")

        await asyncio.sleep(wait_seconds)

    async def _predict_funding_rates(self):
        """Predict future funding rates"""
        while True:
            try:
                await asyncio.sleep(300)  # Update predictions every 5 minutes

                for symbol in self.funding_data.keys():
                    predicted_rate = await self._predict_single_rate(symbol)

                    if symbol in self.funding_data:
                        self.funding_data[symbol].predicted_rate = predicted_rate

            except Exception as e:
                logger.error(f"Prediction error: {e}")

    async def _predict_single_rate(self, symbol: str) -> Decimal:
        """Predict next funding rate for a symbol"""
        try:
            # Simple prediction based on historical trend
            if symbol not in self.funding_history:
                self.funding_history[symbol] = deque(maxlen=100)

            # Add current rate to history
            current_data = self.funding_data.get(symbol)
            if current_data:
                self.funding_history[symbol].append(float(current_data.funding_rate))

            # Need at least 3 data points
            if len(self.funding_history[symbol]) < 3:
                return current_data.funding_rate if current_data else Decimal(0)

            # Calculate trend
            rates = list(self.funding_history[symbol])

            # Simple moving average prediction
            recent_avg = mean(rates[-3:])
            longer_avg = mean(rates[-10:]) if len(rates) >= 10 else recent_avg

            # Trend direction
            trend = recent_avg - longer_avg

            # Predict next rate
            predicted = Decimal(str(recent_avg + trend * 0.5))

            return predicted

        except Exception as e:
            logger.error(f"Prediction error for {symbol}: {e}")
            return Decimal(0)

    async def _close_position(self, position: DeltaNeutralPosition, reason: str):
        """Close a delta-neutral position"""
        try:
            position.status = FarmStatus.CLOSING

            # In production, close actual positions
            # For now, simulate closing

            # Return capital
            position_value = position.position_value * 2  # Both legs
            self.available_capital += position_value
            self.total_capital_deployed -= position_value

            # Remove from active positions
            if position.symbol in self.positions:
                del self.positions[position.symbol]

            logger.info(
                f"Closed position {position.symbol} ({reason}): "
                f"Total funding collected: ${position.total_funding_collected:.2f} "
                f"APY: {position.apy:.2f}%"
            )

        except Exception as e:
            logger.error(f"Error closing position: {e}")

    async def _load_historical_data(self):
        """Load historical funding data for predictions"""
        # In production, load from database or API
        # For now, generate some mock history
        for symbol in ["BTCUSDT", "ETHUSDT", "BNBUSDT"]:
            self.funding_history[symbol] = deque(maxlen=100)

            # Generate mock historical rates
            for _ in range(50):
                rate = np.random.uniform(-0.02, 0.01) / 100
                self.funding_history[symbol].append(rate)

    def get_statistics(self) -> Dict[str, Any]:
        """Get farming statistics"""
        active_positions = []
        total_daily_income = Decimal(0)

        for position in self.positions.values():
            active_positions.append(
                {
                    "symbol": position.symbol,
                    "funding_rate": float(position.funding_rate * 100),
                    "position_value": float(position.position_value),
                    "delta": float(position.delta_percentage),
                    "daily_funding": float(position.daily_funding),
                    "total_collected": float(position.total_funding_collected),
                    "apy": float(position.apy),
                    "rebalances": position.rebalance_count,
                }
            )
            total_daily_income += position.daily_funding

        return {
            "active_positions": len(self.positions),
            "total_capital_deployed": float(self.total_capital_deployed),
            "available_capital": float(self.available_capital),
            "total_funding_collected": float(self.total_funding_collected),
            "daily_income": float(total_daily_income),
            "positions": active_positions,
            "top_opportunities": [
                {
                    "symbol": opp.symbol,
                    "funding_rate": float(opp.funding_rate * 100),
                    "score": float(opp.score),
                    "daily_return": float(opp.estimated_daily_return),
                    "risk": opp.risk_level,
                }
                for opp in self.opportunities[:5]
            ],
        }
