"""
Advanced Market Scanner with Real-Time Analysis
Scans crypto markets for trading opportunities using multiple strategies
"""

import asyncio
import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ..data.real_time_fetcher import fetcher

logger = logging.getLogger(__name__)


class SignalType(Enum):
    BUY = "buy"
    SELL = "sell"
    STRONG_BUY = "strong_buy"
    STRONG_SELL = "strong_sell"
    NEUTRAL = "neutral"


class ScannerStrategy(Enum):
    BREAKOUT = "breakout"
    MOMENTUM = "momentum"
    VOLUME_SURGE = "volume_surge"
    RSI_OVERSOLD = "rsi_oversold"
    RSI_OVERBOUGHT = "rsi_overbought"
    GOLDEN_CROSS = "golden_cross"
    DEATH_CROSS = "death_cross"
    SUPPORT_BOUNCE = "support_bounce"
    RESISTANCE_BREAK = "resistance_break"
    HAMMER_PATTERN = "hammer_pattern"
    DOJI_PATTERN = "doji_pattern"
    BOLLINGER_SQUEEZE = "bollinger_squeeze"


@dataclass
class MarketSignal:
    id: str
    symbol: str
    signal_type: SignalType
    strategy: ScannerStrategy
    strength: float
    price: float
    timestamp: datetime
    message: str
    confidence: float
    timeframe: str
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    risk_reward_ratio: Optional[float] = None

    def to_dict(self):
        return {
            **asdict(self),
            "signal_type": self.signal_type.value,
            "strategy": self.strategy.value,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class MarketAnalysis:
    symbol: str
    current_price: float
    volume_24h: float
    price_change_24h: float
    rsi: float
    macd: float
    macd_signal: float
    bb_position: float
    sma_20: float
    sma_50: float
    ema_12: float
    ema_26: float
    volume_ratio: float
    volume_trend: str
    support_level: float
    resistance_level: float
    sentiment_score: float
    volatility: float
    timestamp: datetime

    def to_dict(self):
        return {**asdict(self), "timestamp": self.timestamp.isoformat()}


class TechnicalAnalyzer:
    """Performs technical analysis on crypto data"""

    @staticmethod
    def calculate_rsi(prices: pd.Series, period: int = 14) -> float:
        """Calculate RSI"""
        try:
            delta = prices.diff()
            gain = delta.where(delta > 0, 0).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - 100 / (1 + rs)
            return float(rsi.iloc[-1]) if not rsi.empty else 50.0
        except:
            return 50.0

    @staticmethod
    def calculate_macd(
        prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> Tuple[float, float]:
        """Calculate MACD and signal line"""
        try:
            ema_fast = prices.ewm(span=fast).mean()
            ema_slow = prices.ewm(span=slow).mean()
            macd = ema_fast - ema_slow
            macd_signal = macd.ewm(span=signal).mean()
            return (float(macd.iloc[-1]), float(macd_signal.iloc[-1]))
        except:
            return (0.0, 0.0)

    @staticmethod
    def calculate_bollinger_bands(
        prices: pd.Series, period: int = 20, std_dev: int = 2
    ) -> Tuple[float, float, float]:
        """Calculate Bollinger Bands"""
        try:
            middle = prices.rolling(period).mean()
            std = prices.rolling(period).std()
            upper = middle + std * std_dev
            lower = middle - std * std_dev
            return (float(upper.iloc[-1]), float(middle.iloc[-1]), float(lower.iloc[-1]))
        except:
            current_price = float(prices.iloc[-1]) if not prices.empty else 0.0
            return (current_price * 1.02, current_price, current_price * 0.98)

    @staticmethod
    def calculate_support_resistance(prices: pd.Series, window: int = 20) -> Tuple[float, float]:
        """Calculate support and resistance levels"""
        try:
            recent_prices = prices.tail(window)
            support = float(recent_prices.min()) * 0.99
            resistance = float(recent_prices.max()) * 1.01
            return (support, resistance)
        except:
            current_price = float(prices.iloc[-1]) if not prices.empty else 0.0
            return (current_price * 0.95, current_price * 1.05)


class AdvancedMarketScanner:
    """Advanced market scanner for crypto opportunities"""

    def __init__(self):
        self.is_running = False
        self.symbols = [
            "bitcoin",
            "ethereum",
            "solana",
            "binancecoin",
            "cardano",
            "polkadot",
            "chainlink",
            "litecoin",
            "polygon",
            "avalanche-2",
            "uniswap",
            "aave",
            "compound",
            "maker",
            "sushi",
        ]
        self.price_history: Dict[str, List[Dict]] = {}
        self.analysis_cache: Dict[str, MarketAnalysis] = {}
        self.signals: List[MarketSignal] = []
        self.rsi_oversold = 30
        self.rsi_overbought = 70
        self.volume_surge_threshold = 2.0
        self.breakout_threshold = 0.02

    async def start(self):
        """Start the market scanner"""
        if self.is_running:
            return
        self.is_running = True
        await fetcher.start()
        asyncio.create_task(self._data_collection_loop())
        asyncio.create_task(self._analysis_loop())
        asyncio.create_task(self._signal_scanning_loop())
        logger.info(f"Advanced Market Scanner started with {len(self.symbols)} symbols")

    async def stop(self):
        """Stop the market scanner"""
        self.is_running = False
        await fetcher.stop()
        logger.info("Advanced Market Scanner stopped")

    async def get_market_overview(self) -> Dict:
        """Get complete market overview"""
        try:
            gainers_losers = await fetcher.get_top_gainers_losers(10)
            recent_signals = [s.to_dict() for s in self.signals[-20:]]
            analysis_data = {
                symbol: analysis.to_dict() for symbol, analysis in self.analysis_cache.items()
            }
            sentiment_scores = [a.sentiment_score for a in self.analysis_cache.values()]
            avg_sentiment = np.mean(sentiment_scores) if sentiment_scores else 0.0
            volatilities = [a.volatility for a in self.analysis_cache.values()]
            avg_volatility = np.mean(volatilities) if volatilities else 0.0
            return {
                "market_sentiment": {
                    "overall_sentiment": avg_sentiment,
                    "sentiment_label": self._get_sentiment_label(avg_sentiment),
                    "average_volatility": avg_volatility,
                    "active_signals": len(
                        [
                            s
                            for s in self.signals
                            if (datetime.now(timezone.utc) - s.timestamp).seconds < 3600
                        ]
                    ),
                },
                "top_opportunities": self._get_top_opportunities(),
                "gainers_losers": gainers_losers,
                "recent_signals": recent_signals,
                "technical_analysis": analysis_data,
                "scanner_stats": {
                    "symbols_monitored": len(self.symbols),
                    "signals_generated": len(self.signals),
                    "last_update": datetime.now(timezone.utc).isoformat(),
                },
            }
        except Exception as e:
            logger.error(f"Error getting market overview: {e}")
            return {"error": str(e)}

    def get_symbol_signals(self, symbol: str, limit: int = 10) -> List[Dict]:
        """Get recent signals for a specific symbol"""
        symbol_signals = [s.to_dict() for s in self.signals if s.symbol.upper() == symbol.upper()]
        return sorted(symbol_signals, key=lambda x: x["timestamp"], reverse=True)[:limit]

    def get_signals_by_strategy(self, strategy: ScannerStrategy, limit: int = 20) -> List[Dict]:
        """Get signals by strategy type"""
        strategy_signals = [s.to_dict() for s in self.signals if s.strategy == strategy]
        return sorted(strategy_signals, key=lambda x: x["timestamp"], reverse=True)[:limit]

    async def _data_collection_loop(self):
        """Collect price and volume data"""
        while self.is_running:
            try:
                market_data = await fetcher.get_market_data(self.symbols)
                if market_data:
                    timestamp = datetime.now(timezone.utc)
                    for symbol, data in market_data.items():
                        symbol = symbol.upper()
                        if symbol not in self.price_history:
                            self.price_history[symbol] = []
                        self.price_history[symbol].append(
                            {
                                "timestamp": timestamp,
                                "price": data["price"],
                                "volume": data.get("volume_24h", 0),
                                "high_24h": data.get("high_24h", data["price"]),
                                "low_24h": data.get("low_24h", data["price"]),
                                "change_24h": data.get("change_24h", 0),
                            }
                        )
                        if len(self.price_history[symbol]) > 200:
                            self.price_history[symbol] = self.price_history[symbol][-200:]
                await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"Error in data collection loop: {e}")
                await asyncio.sleep(30)

    async def _analysis_loop(self):
        """Perform technical analysis"""
        while self.is_running:
            try:
                for symbol in self.symbols:
                    symbol_upper = symbol.upper()
                    if (
                        symbol_upper in self.price_history
                        and len(self.price_history[symbol_upper]) >= 20
                    ):
                        analysis = await self._analyze_symbol(symbol_upper)
                        if analysis:
                            self.analysis_cache[symbol_upper] = analysis
                await asyncio.sleep(120)
            except Exception as e:
                logger.error(f"Error in analysis loop: {e}")
                await asyncio.sleep(60)

    async def _signal_scanning_loop(self):
        """Scan for trading signals"""
        while self.is_running:
            try:
                for symbol in self.symbols:
                    symbol_upper = symbol.upper()
                    if symbol_upper in self.analysis_cache:
                        signals = await self._scan_for_signals(symbol_upper)
                        self.signals.extend(signals)
                        for signal in signals:
                            logger.info(
                                f"Signal: {signal.symbol} {signal.strategy.value} - {signal.signal_type.value} (Strength: {signal.strength:.1f})"
                            )
                if len(self.signals) > 1000:
                    self.signals = self.signals[-1000:]
                await asyncio.sleep(180)
            except Exception as e:
                logger.error(f"Error in signal scanning loop: {e}")
                await asyncio.sleep(90)

    async def _analyze_symbol(self, symbol: str) -> Optional[MarketAnalysis]:
        """Perform comprehensive technical analysis for a symbol"""
        try:
            history = self.price_history[symbol]
            if len(history) < 20:
                return None
            df = pd.DataFrame(history)
            prices = df["price"]
            volumes = df["volume"]
            current_price = float(prices.iloc[-1])
            current_volume = float(volumes.iloc[-1])
            rsi = TechnicalAnalyzer.calculate_rsi(prices)
            macd, macd_signal = TechnicalAnalyzer.calculate_macd(prices)
            bb_upper, bb_middle, bb_lower = TechnicalAnalyzer.calculate_bollinger_bands(prices)
            support, resistance = TechnicalAnalyzer.calculate_support_resistance(prices)
            sma_20 = float(prices.rolling(20).mean().iloc[-1])
            sma_50 = float(prices.rolling(min(50, len(prices))).mean().iloc[-1])
            ema_12 = float(prices.ewm(span=12).mean().iloc[-1])
            ema_26 = float(prices.ewm(span=26).mean().iloc[-1])
            bb_position = (
                (current_price - bb_lower) / (bb_upper - bb_lower) if bb_upper != bb_lower else 0.5
            )
            avg_volume = float(volumes.rolling(20).mean().iloc[-1])
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
            recent_volumes = volumes.tail(5)
            if len(recent_volumes) >= 3:
                if recent_volumes.is_monotonic_increasing:
                    volume_trend = "increasing"
                elif recent_volumes.is_monotonic_decreasing:
                    volume_trend = "decreasing"
                else:
                    volume_trend = "stable"
            else:
                volume_trend = "stable"
            price_change_24h = df["change_24h"].iloc[-1] if "change_24h" in df.columns else 0.0
            sentiment_factors = []
            if rsi < 30:
                sentiment_factors.append(20)
            elif rsi > 70:
                sentiment_factors.append(-20)
            else:
                sentiment_factors.append((50 - rsi) * 0.4)
            if macd > macd_signal:
                sentiment_factors.append(15)
            else:
                sentiment_factors.append(-15)
            if current_price > sma_20:
                sentiment_factors.append(10)
            else:
                sentiment_factors.append(-10)
            if volume_ratio > 1.5:
                sentiment_factors.append(10)
            elif volume_ratio < 0.5:
                sentiment_factors.append(-5)
            sentiment_score = np.clip(sum(sentiment_factors), -100, 100)
            returns = prices.pct_change().dropna()
            volatility = float(returns.std() * np.sqrt(24 * 365)) if len(returns) > 1 else 0.15
            return MarketAnalysis(
                symbol=symbol,
                current_price=current_price,
                volume_24h=current_volume,
                price_change_24h=price_change_24h,
                rsi=rsi,
                macd=macd,
                macd_signal=macd_signal,
                bb_position=bb_position,
                sma_20=sma_20,
                sma_50=sma_50,
                ema_12=ema_12,
                ema_26=ema_26,
                volume_ratio=volume_ratio,
                volume_trend=volume_trend,
                support_level=support,
                resistance_level=resistance,
                sentiment_score=sentiment_score,
                volatility=volatility,
                timestamp=datetime.now(timezone.utc),
            )
        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}")
            return None

    async def _scan_for_signals(self, symbol: str) -> List[MarketSignal]:
        """Scan for various trading signals"""
        signals = []
        analysis = self.analysis_cache[symbol]
        try:
            if analysis.rsi < self.rsi_oversold:
                signals.append(
                    self._create_signal(
                        symbol=symbol,
                        signal_type=SignalType.BUY,
                        strategy=ScannerStrategy.RSI_OVERSOLD,
                        strength=min(95, (self.rsi_oversold - analysis.rsi) * 2),
                        price=analysis.current_price,
                        message=f"RSI oversold at {analysis.rsi:.1f}",
                        confidence=80,
                    )
                )
            elif analysis.rsi > self.rsi_overbought:
                signals.append(
                    self._create_signal(
                        symbol=symbol,
                        signal_type=SignalType.SELL,
                        strategy=ScannerStrategy.RSI_OVERBOUGHT,
                        strength=min(95, (analysis.rsi - self.rsi_overbought) * 2),
                        price=analysis.current_price,
                        message=f"RSI overbought at {analysis.rsi:.1f}",
                        confidence=80,
                    )
                )
            if analysis.volume_ratio > self.volume_surge_threshold:
                signal_type = SignalType.BUY if analysis.price_change_24h > 0 else SignalType.SELL
                signals.append(
                    self._create_signal(
                        symbol=symbol,
                        signal_type=signal_type,
                        strategy=ScannerStrategy.VOLUME_SURGE,
                        strength=min(95, (analysis.volume_ratio - 1) * 30),
                        price=analysis.current_price,
                        message=f"Volume surge: {analysis.volume_ratio:.1f}x average",
                        confidence=70,
                    )
                )
            if analysis.macd > analysis.macd_signal and analysis.macd > 0:
                signals.append(
                    self._create_signal(
                        symbol=symbol,
                        signal_type=SignalType.BUY,
                        strategy=ScannerStrategy.GOLDEN_CROSS,
                        strength=60,
                        price=analysis.current_price,
                        message="MACD bullish crossover",
                        confidence=65,
                    )
                )
            elif analysis.macd < analysis.macd_signal and analysis.macd < 0:
                signals.append(
                    self._create_signal(
                        symbol=symbol,
                        signal_type=SignalType.SELL,
                        strategy=ScannerStrategy.DEATH_CROSS,
                        strength=60,
                        price=analysis.current_price,
                        message="MACD bearish crossover",
                        confidence=65,
                    )
                )
            if analysis.current_price > analysis.resistance_level:
                signals.append(
                    self._create_signal(
                        symbol=symbol,
                        signal_type=SignalType.STRONG_BUY,
                        strategy=ScannerStrategy.RESISTANCE_BREAK,
                        strength=85,
                        price=analysis.current_price,
                        message=f"Resistance breakout at ${analysis.resistance_level:.4f}",
                        confidence=75,
                        take_profit=analysis.current_price * 1.05,
                        stop_loss=analysis.resistance_level * 0.98,
                    )
                )
            elif analysis.current_price < analysis.support_level:
                signals.append(
                    self._create_signal(
                        symbol=symbol,
                        signal_type=SignalType.STRONG_SELL,
                        strategy=ScannerStrategy.SUPPORT_BOUNCE,
                        strength=85,
                        price=analysis.current_price,
                        message=f"Support breakdown at ${analysis.support_level:.4f}",
                        confidence=75,
                        take_profit=analysis.current_price * 0.95,
                        stop_loss=analysis.support_level * 1.02,
                    )
                )
            if 0.4 < analysis.bb_position < 0.6:
                band_width = (
                    analysis.resistance_level - analysis.support_level
                ) / analysis.current_price
                if band_width < 0.02:
                    signals.append(
                        self._create_signal(
                            symbol=symbol,
                            signal_type=SignalType.NEUTRAL,
                            strategy=ScannerStrategy.BOLLINGER_SQUEEZE,
                            strength=70,
                            price=analysis.current_price,
                            message="Bollinger Band squeeze - breakout expected",
                            confidence=60,
                        )
                    )
            recent_signals = [
                s
                for s in self.signals
                if s.symbol == symbol and (datetime.now(timezone.utc) - s.timestamp).seconds < 1800
            ]
            filtered_signals = []
            for signal in signals:
                duplicate = any(
                    rs.strategy == signal.strategy and rs.signal_type == signal.signal_type
                    for rs in recent_signals
                )
                if not duplicate and signal.strength >= 50:
                    filtered_signals.append(signal)
            return filtered_signals
        except Exception as e:
            logger.error(f"Error scanning signals for {symbol}: {e}")
            return []

    def _create_signal(
        self,
        symbol: str,
        signal_type: SignalType,
        strategy: ScannerStrategy,
        strength: float,
        price: float,
        message: str,
        confidence: float,
        take_profit: Optional[float] = None,
        stop_loss: Optional[float] = None,
    ) -> MarketSignal:
        """Create a market signal"""
        risk_reward = None
        if take_profit and stop_loss:
            if signal_type in [SignalType.BUY, SignalType.STRONG_BUY]:
                risk = abs(price - stop_loss)
                reward = abs(take_profit - price)
            else:
                risk = abs(stop_loss - price)
                reward = abs(price - take_profit)
            risk_reward = reward / risk if risk > 0 else None
        return MarketSignal(
            id=str(uuid.uuid4()),
            symbol=symbol,
            signal_type=signal_type,
            strategy=strategy,
            strength=strength,
            price=price,
            timestamp=datetime.now(timezone.utc),
            message=message,
            confidence=confidence,
            timeframe="1h",
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_reward_ratio=risk_reward,
        )

    def _get_sentiment_label(self, score: float) -> str:
        """Convert sentiment score to label"""
        if score > 50:
            return "Very Bullish"
        elif score > 20:
            return "Bullish"
        elif score > -20:
            return "Neutral"
        elif score > -50:
            return "Bearish"
        else:
            return "Very Bearish"

    def _get_top_opportunities(self, limit: int = 5) -> List[Dict]:
        """Get top trading opportunities"""
        try:
            recent_signals = [
                s
                for s in self.signals
                if (datetime.now(timezone.utc) - s.timestamp).seconds < 3600
                and s.strength >= 70
                and (
                    s.signal_type
                    in [
                        SignalType.BUY,
                        SignalType.STRONG_BUY,
                        SignalType.SELL,
                        SignalType.STRONG_SELL,
                    ]
                )
            ]
            opportunities = sorted(
                recent_signals, key=lambda x: x.strength * x.confidence, reverse=True
            )[:limit]
            return [opp.to_dict() for opp in opportunities]
        except Exception as e:
            logger.error(f"Error getting top opportunities: {e}")
            return []


market_scanner = AdvancedMarketScanner()
