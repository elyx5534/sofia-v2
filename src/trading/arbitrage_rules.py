"""
Arbitrage Micro-Rules Engine
Advanced rules for volume analysis, latency optimization, and execution timing
"""

import logging
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


@dataclass
class LatencyMetrics:
    """Network latency tracking"""

    exchange: str
    ping_times_ms: List[float] = field(default_factory=list)
    order_latency_ms: List[float] = field(default_factory=list)
    last_update: datetime = field(default_factory=datetime.now)

    @property
    def avg_ping(self) -> float:
        return statistics.mean(self.ping_times_ms) if self.ping_times_ms else 0

    @property
    def avg_order_latency(self) -> float:
        return statistics.mean(self.order_latency_ms) if self.order_latency_ms else 0

    @property
    def p95_latency(self) -> float:
        if not self.order_latency_ms:
            return 0
        sorted_latencies = sorted(self.order_latency_ms)
        idx = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[idx] if idx < len(sorted_latencies) else sorted_latencies[-1]


@dataclass
class VolumeProfile:
    """Volume analysis for optimal execution"""

    symbol: str
    hourly_volumes: List[float] = field(default_factory=list)
    minute_volumes: List[float] = field(default_factory=list)
    bid_volumes: List[float] = field(default_factory=list)
    ask_volumes: List[float] = field(default_factory=list)
    spread_history: List[float] = field(default_factory=list)

    @property
    def avg_hourly_volume(self) -> float:
        return statistics.mean(self.hourly_volumes) if self.hourly_volumes else 0

    @property
    def volume_velocity(self) -> float:
        """Rate of volume change"""
        if len(self.minute_volumes) < 2:
            return 0
        recent = (
            statistics.mean(self.minute_volumes[-5:])
            if len(self.minute_volumes) >= 5
            else self.minute_volumes[-1]
        )
        older = (
            statistics.mean(self.minute_volumes[-10:-5])
            if len(self.minute_volumes) >= 10
            else self.minute_volumes[0]
        )
        return (recent - older) / older * 100 if older > 0 else 0

    @property
    def avg_spread_bps(self) -> float:
        """Average spread in basis points"""
        return statistics.mean(self.spread_history) * 10000 if self.spread_history else 0


class ArbitrageMicroRules:
    """Advanced micro-rules for arbitrage execution"""

    def __init__(self):
        self.latency_metrics: Dict[str, LatencyMetrics] = {}
        self.volume_profiles: Dict[str, VolumeProfile] = {}
        self.execution_windows: List[Tuple[int, int]] = []
        self.logger = logging.getLogger(f"{__name__}.MicroRules")
        self.max_acceptable_latency_ms = 100
        self.min_volume_ratio = 0.1
        self.max_spread_bps = 10
        self.volume_surge_threshold = 50
        self.latency_spike_threshold = 2.0

    async def measure_latency(self, exchange_name: str, exchange_obj) -> float:
        """Measure current latency to exchange"""
        try:
            start = time.time()
            await exchange_obj.fetch_time()
            latency_ms = (time.time() - start) * 1000
            if exchange_name not in self.latency_metrics:
                self.latency_metrics[exchange_name] = LatencyMetrics(exchange_name)
            metrics = self.latency_metrics[exchange_name]
            metrics.ping_times_ms.append(latency_ms)
            metrics.ping_times_ms = metrics.ping_times_ms[-100:]
            metrics.last_update = datetime.now()
            return latency_ms
        except Exception as e:
            self.logger.error(f"Latency measurement failed for {exchange_name}: {e}")
            return 999

    async def analyze_volume(self, exchange_obj, symbol: str) -> VolumeProfile:
        """Analyze volume profile for a symbol"""
        try:
            if symbol not in self.volume_profiles:
                self.volume_profiles[symbol] = VolumeProfile(symbol)
            profile = self.volume_profiles[symbol]
            ticker = await exchange_obj.fetch_ticker(symbol)
            if ticker and "quoteVolume" in ticker:
                profile.hourly_volumes.append(ticker["quoteVolume"] / 24)
                profile.hourly_volumes = profile.hourly_volumes[-24:]
            orderbook = await exchange_obj.fetch_order_book(symbol, 10)
            bid_volume = sum(bid[1] * bid[0] for bid in orderbook["bids"][:5])
            ask_volume = sum(ask[1] * ask[0] for ask in orderbook["asks"][:5])
            profile.bid_volumes.append(bid_volume)
            profile.ask_volumes.append(ask_volume)
            profile.bid_volumes = profile.bid_volumes[-60:]
            profile.ask_volumes = profile.ask_volumes[-60:]
            if orderbook["bids"] and orderbook["asks"]:
                best_bid = orderbook["bids"][0][0]
                best_ask = orderbook["asks"][0][0]
                spread = (best_ask - best_bid) / best_bid
                profile.spread_history.append(spread)
                profile.spread_history = profile.spread_history[-100:]
            profile.minute_volumes.append((bid_volume + ask_volume) / 2)
            profile.minute_volumes = profile.minute_volumes[-60:]
            return profile
        except Exception as e:
            self.logger.error(f"Volume analysis failed for {symbol}: {e}")
            return self.volume_profiles.get(symbol, VolumeProfile(symbol))

    def check_execution_rules(self, opportunity: Dict) -> Tuple[bool, List[str]]:
        """Check if opportunity passes micro-rules"""
        violations = []
        symbol = opportunity["symbol"]
        for exchange in [opportunity["buy_exchange"], opportunity["sell_exchange"]]:
            if exchange in self.latency_metrics:
                metrics = self.latency_metrics[exchange]
                if metrics.avg_ping > self.max_acceptable_latency_ms:
                    violations.append(f"High latency to {exchange}: {metrics.avg_ping:.0f}ms")
                if metrics.ping_times_ms:
                    recent_latency = metrics.ping_times_ms[-1]
                    if recent_latency > metrics.avg_ping * self.latency_spike_threshold:
                        violations.append(f"Latency spike on {exchange}: {recent_latency:.0f}ms")
        if symbol in self.volume_profiles:
            profile = self.volume_profiles[symbol]
            if profile.avg_spread_bps > self.max_spread_bps:
                violations.append(f"Spread too wide: {profile.avg_spread_bps:.1f} bps")
            if abs(profile.volume_velocity) > self.volume_surge_threshold:
                violations.append(f"Volume surge detected: {profile.volume_velocity:.1f}%")
            if profile.bid_volumes and profile.ask_volumes:
                recent_bids = statistics.mean(profile.bid_volumes[-5:])
                recent_asks = statistics.mean(profile.ask_volumes[-5:])
                imbalance = abs(recent_bids - recent_asks) / max(recent_bids, recent_asks)
                if imbalance > 0.5:
                    violations.append(f"Order book imbalance: {imbalance * 100:.0f}%")
        current_hour = datetime.now().hour
        if 2 <= current_hour <= 6:
            violations.append(f"Low liquidity hour: {current_hour}:00 UTC")
        if current_hour in [14, 15, 21, 22]:
            violations.append(f"High volatility hour: {current_hour}:00 UTC")
        profit_pct = opportunity.get("profit_pct", 0)
        risk_multiplier = 1.0
        if violations:
            risk_multiplier = 1.5
        min_required_profit = 0.3 * risk_multiplier
        if profit_pct < min_required_profit:
            violations.append(
                f"Insufficient profit for risk: {profit_pct:.2f}% < {min_required_profit:.2f}%"
            )
        can_execute = len(violations) == 0
        return (can_execute, violations)

    def calculate_optimal_size(self, opportunity: Dict, max_size: float) -> float:
        """Calculate optimal trade size based on conditions"""
        base_size = max_size
        symbol = opportunity["symbol"]
        latency_factor = 1.0
        for exchange in [opportunity["buy_exchange"], opportunity["sell_exchange"]]:
            if exchange in self.latency_metrics:
                metrics = self.latency_metrics[exchange]
                if metrics.avg_ping > 50:
                    latency_factor *= 50 / metrics.avg_ping
        volume_factor = 1.0
        if symbol in self.volume_profiles:
            profile = self.volume_profiles[symbol]
            if profile.avg_spread_bps > 5:
                volume_factor *= 5 / profile.avg_spread_bps
            if abs(profile.volume_velocity) > 20:
                volume_factor *= 0.7
        profit_factor = min(opportunity.get("profit_pct", 0.3) / 0.3, 2.0)
        optimal_size = base_size * latency_factor * volume_factor * profit_factor
        optimal_size = max(optimal_size, base_size * 0.1)
        optimal_size = min(optimal_size, base_size)
        self.logger.info(
            f"Size calculation for {symbol}: Base=${base_size:.0f}, Optimal=${optimal_size:.0f} (L:{latency_factor:.2f}, V:{volume_factor:.2f}, P:{profit_factor:.2f})"
        )
        return optimal_size

    def suggest_execution_timing(self) -> Dict[str, any]:
        """Suggest optimal execution timing"""
        current_hour = datetime.now().hour
        optimal_windows = [(7, 10), (13, 16), (19, 21)]
        in_optimal_window = any((start <= current_hour < end for start, end in optimal_windows))
        next_window = None
        for start, end in optimal_windows:
            if current_hour < start:
                next_window = (start, end)
                break
        if not next_window:
            next_window = optimal_windows[0]
        if in_optimal_window:
            wait_minutes = 0
        else:
            hours_until = next_window[0] - current_hour
            if hours_until < 0:
                hours_until += 24
            wait_minutes = hours_until * 60
        return {
            "current_hour_utc": current_hour,
            "in_optimal_window": in_optimal_window,
            "next_window_utc": f"{next_window[0]:02d}:00-{next_window[1]:02d}:00",
            "wait_minutes": wait_minutes,
            "recommendation": (
                "Execute now" if in_optimal_window else f"Wait {wait_minutes} minutes"
            ),
        }

    def get_execution_score(self, opportunity: Dict) -> float:
        """Calculate execution score (0-100)"""
        score = 100.0
        symbol = opportunity["symbol"]
        for exchange in [opportunity["buy_exchange"], opportunity["sell_exchange"]]:
            if exchange in self.latency_metrics:
                metrics = self.latency_metrics[exchange]
                if metrics.avg_ping > 100:
                    score -= 15
                elif metrics.avg_ping > 50:
                    score -= 7.5
        if symbol in self.volume_profiles:
            profile = self.volume_profiles[symbol]
            if profile.avg_spread_bps > 10:
                score -= 15
            elif profile.avg_spread_bps > 5:
                score -= 7.5
            if abs(profile.volume_velocity) > 50:
                score -= 15
            elif abs(profile.volume_velocity) > 25:
                score -= 7.5
        current_hour = datetime.now().hour
        if 2 <= current_hour <= 6:
            score -= 20
        elif current_hour in [14, 15, 21, 22]:
            score -= 10
        profit_pct = opportunity.get("profit_pct", 0)
        if profit_pct > 1.0:
            score = min(score + 20, 100)
        elif profit_pct > 0.5:
            score = min(score + 10, 100)
        return max(score, 0)


arbitrage_rules = ArbitrageMicroRules()
