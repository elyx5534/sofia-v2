"""
News Feature Engineering for Trading Strategies
"""

import logging
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np

from .news_sentiment import NewsItem, SentimentScore

logger = logging.getLogger(__name__)


class NewsFeatureEngine:
    """Extract trading-relevant features from news"""

    def __init__(self):
        # High-impact keywords and their weights
        self.impact_keywords = {
            "high_impact": {
                "keywords": [
                    "earnings",
                    "revenue",
                    "profit",
                    "loss",
                    "guidance",
                    "outlook",
                    "merger",
                    "acquisition",
                    "ipo",
                    "dividend",
                    "split",
                    "buyback",
                    "sec",
                    "regulatory",
                    "approval",
                    "ban",
                    "investigation",
                    "partnership",
                    "deal",
                    "contract",
                    "launch",
                    "release",
                    "hack",
                    "breach",
                    "crash",
                    "rally",
                    "surge",
                    "plunge",
                ],
                "weight": 2.0,
            },
            "medium_impact": {
                "keywords": [
                    "growth",
                    "decline",
                    "increase",
                    "decrease",
                    "expansion",
                    "upgrade",
                    "downgrade",
                    "target",
                    "recommendation",
                    "market",
                    "trading",
                    "volume",
                    "volatility",
                    "innovation",
                    "technology",
                    "development",
                ],
                "weight": 1.5,
            },
            "sentiment_modifiers": {
                "keywords": [
                    "strong",
                    "weak",
                    "bullish",
                    "bearish",
                    "optimistic",
                    "pessimistic",
                    "confident",
                    "uncertain",
                    "positive",
                    "negative",
                    "outperform",
                    "underperform",
                    "beat",
                    "miss",
                    "exceed",
                ],
                "weight": 1.3,
            },
        }

        # Event type classification
        self.event_types = {
            "earnings": ["earnings", "revenue", "profit", "ebitda", "guidance"],
            "corporate_action": ["merger", "acquisition", "dividend", "split", "buyback"],
            "regulatory": ["sec", "fda", "regulatory", "approval", "ban", "compliance"],
            "product": ["launch", "release", "product", "service", "innovation"],
            "partnership": ["partnership", "deal", "contract", "agreement", "alliance"],
            "market_structure": ["listing", "delisting", "index", "etf", "futures"],
            "macroeconomic": ["fed", "interest", "inflation", "gdp", "employment"],
            "security": ["hack", "breach", "security", "cyber", "attack"],
        }

        # Urgency indicators
        self.urgency_keywords = [
            "breaking",
            "urgent",
            "alert",
            "emergency",
            "immediate",
            "now",
            "today",
            "just",
            "announced",
            "confirms",
        ]

        # Historical feature tracking
        self.feature_history: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.history_window = 100  # Keep last 100 feature sets per symbol

    def extract_features(
        self,
        symbol: str,
        news_items: List[NewsItem],
        sentiment_score: Optional[SentimentScore] = None,
    ) -> Dict[str, Any]:
        """Extract comprehensive features from news"""

        if not news_items:
            return self._get_empty_features(symbol)

        # Time windows
        now = datetime.now()
        windows = {
            "1h": now - timedelta(hours=1),
            "6h": now - timedelta(hours=6),
            "24h": now - timedelta(hours=24),
        }

        features = {
            "symbol": symbol,
            "timestamp": now.isoformat(),
            "total_news_count": len(news_items),
        }

        # Time-windowed features
        for window_name, window_start in windows.items():
            window_news = [item for item in news_items if item.timestamp >= window_start]
            features.update(self._extract_window_features(window_news, window_name))

        # Keyword impact analysis
        features.update(self._analyze_keyword_impact(news_items))

        # Event type classification
        features.update(self._classify_event_types(news_items))

        # Urgency and timing features
        features.update(self._extract_timing_features(news_items))

        # Source credibility and diversity
        features.update(self._analyze_source_features(news_items))

        # Sentiment features
        if sentiment_score:
            features.update(self._extract_sentiment_features(sentiment_score))

        # Anomaly and surprise features
        features.update(self._detect_news_anomalies(symbol, features))

        # Store in history
        self._update_feature_history(symbol, features)

        return features

    def _extract_window_features(
        self, window_news: List[NewsItem], window_name: str
    ) -> Dict[str, Any]:
        """Extract features for specific time window"""
        if not window_news:
            return {
                f"news_count_{window_name}": 0,
                f"avg_sentiment_{window_name}": 0.0,
                f"sentiment_volatility_{window_name}": 0.0,
                f"source_diversity_{window_name}": 0,
            }

        # Basic counts
        news_count = len(window_news)

        # Sentiment statistics
        sentiments = [
            item.sentiment_score for item in window_news if item.sentiment_score is not None
        ]
        avg_sentiment = np.mean(sentiments) if sentiments else 0.0
        sentiment_volatility = np.std(sentiments) if len(sentiments) > 1 else 0.0

        # Source diversity
        sources = set(item.source for item in window_news)
        source_diversity = len(sources)

        # Confidence statistics
        confidences = [item.confidence for item in window_news if item.confidence is not None]
        avg_confidence = np.mean(confidences) if confidences else 0.0

        return {
            f"news_count_{window_name}": news_count,
            f"avg_sentiment_{window_name}": avg_sentiment,
            f"sentiment_volatility_{window_name}": sentiment_volatility,
            f"source_diversity_{window_name}": source_diversity,
            f"avg_confidence_{window_name}": avg_confidence,
        }

    def _analyze_keyword_impact(self, news_items: List[NewsItem]) -> Dict[str, Any]:
        """Analyze impact keywords in news"""
        impact_scores = defaultdict(float)
        keyword_counts = defaultdict(int)

        for item in news_items:
            text = (item.title + " " + item.summary).lower()

            for impact_level, config in self.impact_keywords.items():
                for keyword in config["keywords"]:
                    count = len(re.findall(r"\b" + keyword + r"\b", text))
                    if count > 0:
                        weight = config["weight"]

                        # Apply sentiment modifier
                        sentiment_modifier = 1.0
                        if item.sentiment_score is not None:
                            sentiment_modifier = 1.0 + abs(item.sentiment_score) * 0.5

                        # Time decay (more recent = higher impact)
                        hours_ago = (datetime.now() - item.timestamp).total_seconds() / 3600
                        time_weight = np.exp(-hours_ago / 6)  # 6-hour half-life

                        final_weight = weight * sentiment_modifier * time_weight
                        impact_scores[impact_level] += count * final_weight
                        keyword_counts[keyword] += count

        # Get top keywords
        top_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "high_impact_score": impact_scores["high_impact"],
            "medium_impact_score": impact_scores["medium_impact"],
            "sentiment_modifier_score": impact_scores["sentiment_modifiers"],
            "total_impact_score": sum(impact_scores.values()),
            "top_keywords": [{"keyword": k, "count": c} for k, c in top_keywords],
        }

    def _classify_event_types(self, news_items: List[NewsItem]) -> Dict[str, Any]:
        """Classify news by event types"""
        event_scores = defaultdict(float)
        event_counts = defaultdict(int)

        for item in news_items:
            text = (item.title + " " + item.summary).lower()

            for event_type, keywords in self.event_types.items():
                score = 0
                for keyword in keywords:
                    count = len(re.findall(r"\b" + keyword + r"\b", text))
                    score += count

                if score > 0:
                    # Weight by sentiment and recency
                    sentiment_weight = 1.0 + abs(item.sentiment_score or 0) * 0.3
                    hours_ago = (datetime.now() - item.timestamp).total_seconds() / 3600
                    time_weight = np.exp(-hours_ago / 12)  # 12-hour half-life

                    weighted_score = score * sentiment_weight * time_weight
                    event_scores[event_type] += weighted_score
                    event_counts[event_type] += 1

        # Identify dominant event type
        dominant_event = (
            max(event_scores.items(), key=lambda x: x[1])[0] if event_scores else "none"
        )

        return {
            "dominant_event_type": dominant_event,
            "event_type_scores": dict(event_scores),
            "event_type_counts": dict(event_counts),
            "event_diversity": len([score for score in event_scores.values() if score > 0]),
        }

    def _extract_timing_features(self, news_items: List[NewsItem]) -> Dict[str, Any]:
        """Extract timing and urgency features"""
        urgency_score = 0
        recent_burst_count = 0

        # Check for urgency keywords
        for item in news_items:
            text = (item.title + " " + item.summary).lower()

            for urgency_keyword in self.urgency_keywords:
                if urgency_keyword in text:
                    urgency_score += 1

        # Detect news bursts (many articles in short time)
        now = datetime.now()
        last_2h = now - timedelta(hours=2)
        recent_news = [item for item in news_items if item.timestamp >= last_2h]

        if len(recent_news) >= 3:  # 3+ articles in 2 hours
            recent_burst_count = len(recent_news)

        # Time distribution analysis
        if news_items:
            timestamps = [item.timestamp for item in news_items]
            time_span = (max(timestamps) - min(timestamps)).total_seconds() / 3600  # hours
            news_frequency = len(news_items) / max(time_span, 1)  # news per hour
        else:
            news_frequency = 0

        # Market hours analysis (assuming UTC)
        market_hours_count = 0
        after_hours_count = 0

        for item in news_items:
            hour = item.timestamp.hour
            # US market hours: 14:30-21:00 UTC (9:30-4:00 EST)
            if 14 <= hour <= 21:
                market_hours_count += 1
            else:
                after_hours_count += 1

        return {
            "urgency_score": urgency_score,
            "recent_burst_count": recent_burst_count,
            "news_frequency": news_frequency,
            "market_hours_ratio": market_hours_count / len(news_items) if news_items else 0,
            "after_hours_ratio": after_hours_count / len(news_items) if news_items else 0,
        }

    def _analyze_source_features(self, news_items: List[NewsItem]) -> Dict[str, Any]:
        """Analyze news source characteristics"""
        source_counts = Counter(item.source for item in news_items)

        # Source credibility scores (mock - would be based on historical accuracy)
        credibility_scores = {
            "Reuters": 0.95,
            "Bloomberg": 0.93,
            "Wall Street Journal": 0.90,
            "CoinDesk": 0.85,
            "Yahoo Finance": 0.75,
            "Unknown": 0.50,
        }

        weighted_credibility = 0
        total_weight = 0

        for source, count in source_counts.items():
            credibility = credibility_scores.get(source, 0.50)
            weighted_credibility += credibility * count
            total_weight += count

        avg_credibility = weighted_credibility / total_weight if total_weight > 0 else 0.5

        # Source concentration (are all news from one source?)
        source_concentration = max(source_counts.values()) / len(news_items) if news_items else 0

        return {
            "source_diversity": len(source_counts),
            "avg_source_credibility": avg_credibility,
            "source_concentration": source_concentration,
            "top_source": max(source_counts, key=source_counts.get) if source_counts else "none",
            "source_breakdown": dict(source_counts),
        }

    def _extract_sentiment_features(self, sentiment_score: SentimentScore) -> Dict[str, Any]:
        """Extract advanced sentiment features"""
        # Sentiment momentum (change over time)
        sentiment_momentum = sentiment_score.score_1h - sentiment_score.score_24h

        # Sentiment-volume correlation
        volume_weighted_sentiment_1h = sentiment_score.score_1h * (sentiment_score.volume_1h / 10)
        volume_weighted_sentiment_24h = sentiment_score.score_24h * (
            sentiment_score.volume_24h / 50
        )

        # Confidence trends
        confidence_trend = sentiment_score.confidence_1h - sentiment_score.confidence_24h

        return {
            "sentiment_momentum": sentiment_momentum,
            "volume_weighted_sentiment_1h": volume_weighted_sentiment_1h,
            "volume_weighted_sentiment_24h": volume_weighted_sentiment_24h,
            "confidence_trend": confidence_trend,
            "sentiment_volatility": abs(sentiment_momentum),
            "high_confidence_sentiment": 1 if sentiment_score.confidence_1h > 0.7 else 0,
        }

    def _detect_news_anomalies(
        self, symbol: str, current_features: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Detect anomalous news patterns"""
        if symbol not in self.feature_history or len(self.feature_history[symbol]) < 10:
            return {
                "news_volume_anomaly": False,
                "sentiment_anomaly": False,
                "impact_anomaly": False,
                "anomaly_score": 0.0,
            }

        history = self.feature_history[symbol]

        # News volume anomaly
        historical_volumes = [h.get("news_count_24h", 0) for h in history[-20:]]
        current_volume = current_features.get("news_count_24h", 0)

        if historical_volumes:
            avg_volume = np.mean(historical_volumes)
            std_volume = np.std(historical_volumes)
            volume_z_score = (current_volume - avg_volume) / (std_volume + 1e-6)
            volume_anomaly = abs(volume_z_score) > 2.0
        else:
            volume_anomaly = False
            volume_z_score = 0

        # Sentiment anomaly
        historical_sentiments = [h.get("avg_sentiment_24h", 0) for h in history[-20:]]
        current_sentiment = current_features.get("avg_sentiment_24h", 0)

        if historical_sentiments:
            avg_sentiment = np.mean(historical_sentiments)
            std_sentiment = np.std(historical_sentiments)
            sentiment_z_score = (current_sentiment - avg_sentiment) / (std_sentiment + 1e-6)
            sentiment_anomaly = abs(sentiment_z_score) > 2.0
        else:
            sentiment_anomaly = False
            sentiment_z_score = 0

        # Impact anomaly
        historical_impacts = [h.get("total_impact_score", 0) for h in history[-20:]]
        current_impact = current_features.get("total_impact_score", 0)

        if historical_impacts:
            avg_impact = np.mean(historical_impacts)
            std_impact = np.std(historical_impacts)
            impact_z_score = (current_impact - avg_impact) / (std_impact + 1e-6)
            impact_anomaly = abs(impact_z_score) > 2.0
        else:
            impact_anomaly = False
            impact_z_score = 0

        # Overall anomaly score
        anomaly_score = (abs(volume_z_score) + abs(sentiment_z_score) + abs(impact_z_score)) / 3

        return {
            "news_volume_anomaly": volume_anomaly,
            "sentiment_anomaly": sentiment_anomaly,
            "impact_anomaly": impact_anomaly,
            "anomaly_score": anomaly_score,
            "volume_z_score": volume_z_score,
            "sentiment_z_score": sentiment_z_score,
            "impact_z_score": impact_z_score,
        }

    def _update_feature_history(self, symbol: str, features: Dict[str, Any]):
        """Update feature history for symbol"""
        self.feature_history[symbol].append(features.copy())

        # Keep only recent history
        if len(self.feature_history[symbol]) > self.history_window:
            self.feature_history[symbol] = self.feature_history[symbol][-self.history_window :]

    def _get_empty_features(self, symbol: str) -> Dict[str, Any]:
        """Get empty feature set when no news available"""
        return {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "total_news_count": 0,
            "news_count_1h": 0,
            "news_count_6h": 0,
            "news_count_24h": 0,
            "avg_sentiment_1h": 0.0,
            "avg_sentiment_6h": 0.0,
            "avg_sentiment_24h": 0.0,
            "total_impact_score": 0.0,
            "dominant_event_type": "none",
            "urgency_score": 0,
            "source_diversity": 0,
            "anomaly_score": 0.0,
        }

    def get_trading_signals(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Generate trading signals from news features"""
        signals = {
            "news_momentum_signal": 0.0,
            "event_impact_signal": 0.0,
            "anomaly_signal": 0.0,
            "composite_signal": 0.0,
            "confidence": 0.0,
        }

        # News momentum signal
        volume_1h = features.get("news_count_1h", 0)
        volume_24h = features.get("news_count_24h", 0)

        if volume_24h > 0:
            momentum = (volume_1h * 24 - volume_24h) / volume_24h
            signals["news_momentum_signal"] = np.tanh(momentum)  # Bound to [-1, 1]

        # Event impact signal
        total_impact = features.get("total_impact_score", 0)
        sentiment_1h = features.get("avg_sentiment_1h", 0)

        if total_impact > 0:
            # Combine impact with sentiment direction
            impact_signal = min(total_impact / 10, 1.0) * np.sign(sentiment_1h)
            signals["event_impact_signal"] = impact_signal

        # Anomaly signal
        anomaly_score = features.get("anomaly_score", 0)
        if anomaly_score > 1.0:  # Significant anomaly
            # Anomalies can be opportunities or risks
            anomaly_direction = np.sign(sentiment_1h) if sentiment_1h != 0 else 1
            signals["anomaly_signal"] = min(anomaly_score / 3, 1.0) * anomaly_direction

        # Composite signal
        weights = [0.4, 0.4, 0.2]  # momentum, impact, anomaly
        signal_values = [
            signals["news_momentum_signal"],
            signals["event_impact_signal"],
            signals["anomaly_signal"],
        ]

        composite = sum(w * s for w, s in zip(weights, signal_values))
        signals["composite_signal"] = np.tanh(composite)  # Bound to [-1, 1]

        # Confidence based on various factors
        confidence_factors = [
            min(features.get("source_diversity", 0) / 3, 1.0),  # More sources = higher confidence
            min(features.get("avg_confidence_1h", 0), 1.0),  # Sentiment confidence
            min(total_impact / 5, 1.0),  # Impact strength
            1.0 - min(anomaly_score / 3, 0.5),  # Lower confidence for anomalies
        ]

        signals["confidence"] = np.mean(confidence_factors)

        return signals
