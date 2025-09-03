"""
Machine Learning Prediction Model for Sofia Trading System
Uses ensemble methods for price prediction and signal classification
"""

import warnings
from datetime import datetime
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import (
    GradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.preprocessing import StandardScaler

from src.adapters.ml.sklearn_adapter import (
    accuracy_score,
    classification_report,
    mean_squared_error,
    train_test_split,
)

warnings.filterwarnings("ignore")


class FeatureEngineering:
    """Feature engineering for ML models"""

    @staticmethod
    def create_technical_features(df: pd.DataFrame) -> pd.DataFrame:
        """Create technical indicators as features"""
        df["returns"] = df["close"].pct_change()
        df["log_returns"] = np.log(df["close"] / df["close"].shift(1))
        for period in [5, 10, 20, 50]:
            df[f"sma_{period}"] = df["close"].rolling(period).mean()
            df[f"ema_{period}"] = df["close"].ewm(span=period).mean()
        df["price_to_sma20"] = df["close"] / df["sma_20"]
        df["price_to_sma50"] = df["close"] / df["sma_50"]
        df["volatility"] = df["returns"].rolling(20).std()
        df["atr"] = FeatureEngineering.calculate_atr(df)
        df["rsi"] = FeatureEngineering.calculate_rsi(df["close"])
        exp1 = df["close"].ewm(span=12).mean()
        exp2 = df["close"].ewm(span=26).mean()
        df["macd"] = exp1 - exp2
        df["macd_signal"] = df["macd"].ewm(span=9).mean()
        df["macd_diff"] = df["macd"] - df["macd_signal"]
        df["bb_upper"] = df["sma_20"] + df["close"].rolling(20).std() * 2
        df["bb_lower"] = df["sma_20"] - df["close"].rolling(20).std() * 2
        df["bb_position"] = (df["close"] - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])
        if "volume" in df.columns:
            df["volume_sma"] = df["volume"].rolling(20).mean()
            df["volume_ratio"] = df["volume"] / df["volume_sma"]
            df["vwap"] = (df["close"] * df["volume"]).cumsum() / df["volume"].cumsum()
            df["price_to_vwap"] = df["close"] / df["vwap"]
        df["resistance"] = df["high"].rolling(20).max()
        df["support"] = df["low"].rolling(20).min()
        df["sr_position"] = (df["close"] - df["support"]) / (df["resistance"] - df["support"])
        return df

    @staticmethod
    def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI indicator"""
        delta = prices.diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss
        rsi = 100 - 100 / (1 + rs)
        return rsi

    @staticmethod
    def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range"""
        high_low = df["high"] - df["low"]
        high_close = np.abs(df["high"] - df["close"].shift())
        low_close = np.abs(df["low"] - df["close"].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        return atr

    @staticmethod
    def create_alert_features(alerts: List[Dict]) -> pd.DataFrame:
        """Create features from alert signals"""
        if not alerts:
            return pd.DataFrame()
        alert_df = pd.DataFrame(alerts)
        severity_counts = alert_df["severity"].value_counts().to_dict()
        action_counts = alert_df["action"].value_counts().to_dict()
        features = {
            "alert_count": len(alerts),
            "critical_alerts": severity_counts.get("critical", 0),
            "high_alerts": severity_counts.get("high", 0),
            "medium_alerts": severity_counts.get("medium", 0),
            "hedge_signals": action_counts.get("hedge", 0),
            "long_signals": action_counts.get("momentum_long", 0),
            "short_signals": action_counts.get("short", 0),
        }
        return pd.DataFrame([features])


class PricePredictionModel:
    """ML model for price prediction"""

    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.feature_columns = []
        self.is_trained = False

    def prepare_data(
        self, df: pd.DataFrame, target_hours: int = 1
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Prepare data for training"""
        df = FeatureEngineering.create_technical_features(df)
        df["target"] = df["close"].shift(-target_hours) / df["close"] - 1
        feature_cols = [
            col
            for col in df.columns
            if col not in ["target", "close", "open", "high", "low", "timestamp"]
        ]
        self.feature_columns = feature_cols
        df = df.dropna()
        X = df[feature_cols].values
        y = df["target"].values
        return (X, y)

    def train(self, df: pd.DataFrame, target_hours: int = 1):
        """Train the prediction model"""
        X, y = self.prepare_data(df, target_hours)
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        models = [
            RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42),
            GradientBoostingRegressor(n_estimators=100, max_depth=5, random_state=42),
        ]
        predictions = []
        for model in models:
            model.fit(X_train_scaled, y_train)
            pred = model.predict(X_test_scaled)
            predictions.append(pred)
        ensemble_pred = np.mean(predictions, axis=0)
        mse = mean_squared_error(y_test, ensemble_pred)
        rmse = np.sqrt(mse)
        print(f"Model trained - RMSE: {rmse:.6f}")
        self.model = models[0]
        self.is_trained = True
        return {"rmse": rmse, "mse": mse, "test_size": len(y_test)}

    def predict(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Make price prediction"""
        if not self.is_trained:
            raise ValueError("Model not trained yet")
        df = FeatureEngineering.create_technical_features(df)
        last_row = df[self.feature_columns].iloc[-1:].values
        last_row_scaled = self.scaler.transform(last_row)
        prediction = self.model.predict(last_row_scaled)[0]
        confidence = min(0.95, abs(prediction) * 10)
        current_price = df["close"].iloc[-1]
        predicted_price = current_price * (1 + prediction)
        return {
            "current_price": current_price,
            "predicted_price": predicted_price,
            "expected_change": prediction,
            "confidence": confidence,
            "direction": "up" if prediction > 0 else "down",
            "timestamp": datetime.now().isoformat(),
        }


class SignalClassificationModel:
    """ML model for classifying trading signals"""

    def __init__(self):
        self.model = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
        self.scaler = StandardScaler()
        self.is_trained = False

    def prepare_training_data(
        self, historical_signals: List[Dict]
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Prepare signal data for training"""
        features = []
        labels = []
        for signal in historical_signals:
            feature_vector = [
                signal.get("confidence", 0),
                signal.get("risk_level", 0),
                1 if signal.get("severity") == "high" else 0,
                1 if signal.get("action") == "buy" else -1 if signal.get("action") == "sell" else 0,
                signal.get("price_change", 0),
                signal.get("volume_ratio", 1),
                signal.get("rsi", 50),
                signal.get("macd_signal", 0),
            ]
            features.append(feature_vector)
            labels.append(1 if signal.get("outcome", 0) > 0 else 0)
        return (np.array(features), np.array(labels))

    def train(self, historical_signals: List[Dict]):
        """Train the classification model"""
        if len(historical_signals) < 100:
            print("Not enough historical data for training")
            return None
        X, y = self.prepare_training_data(historical_signals)
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        self.model.fit(X_train_scaled, y_train)
        y_pred = self.model.predict(X_test_scaled)
        accuracy = accuracy_score(y_test, y_pred)
        print(f"Signal classifier trained - Accuracy: {accuracy:.2%}")
        self.is_trained = True
        return {
            "accuracy": accuracy,
            "classification_report": classification_report(y_test, y_pred),
        }

    def classify_signal(self, signal: Dict) -> Dict[str, Any]:
        """Classify a trading signal"""
        if not self.is_trained:
            return {"classification": "neutral", "probability": 0.5, "recommendation": "hold"}
        feature_vector = [
            [
                signal.get("confidence", 0),
                signal.get("risk_level", 0),
                1 if signal.get("severity") == "high" else 0,
                1 if signal.get("action") == "buy" else -1 if signal.get("action") == "sell" else 0,
                signal.get("price_change", 0),
                signal.get("volume_ratio", 1),
                signal.get("rsi", 50),
                signal.get("macd_signal", 0),
            ]
        ]
        feature_scaled = self.scaler.transform(feature_vector)
        prediction = self.model.predict(feature_scaled)[0]
        probability = self.model.predict_proba(feature_scaled)[0]
        if prediction == 1 and probability[1] > 0.7:
            recommendation = "strong_execute"
        elif prediction == 1 and probability[1] > 0.5:
            recommendation = "execute"
        elif probability[1] < 0.3:
            recommendation = "avoid"
        else:
            recommendation = "hold"
        return {
            "classification": "positive" if prediction == 1 else "negative",
            "probability": float(probability[1]),
            "recommendation": recommendation,
            "confidence": float(max(probability)),
        }


class SentimentAnalysisModel:
    """Analyze sentiment from news and social media"""

    def __init__(self):
        self.sentiment_keywords = {
            "positive": [
                "bullish",
                "rally",
                "surge",
                "breakout",
                "moon",
                "pump",
                "adoption",
                "partnership",
                "upgrade",
                "approval",
                "etf",
            ],
            "negative": [
                "bearish",
                "crash",
                "dump",
                "selloff",
                "panic",
                "fear",
                "hack",
                "scam",
                "lawsuit",
                "ban",
                "regulation",
                "sec",
            ],
            "neutral": ["stable", "consolidation", "sideways", "range", "support"],
        }

    def analyze_text(self, text: str) -> Dict[str, Any]:
        """Analyze sentiment from text"""
        text_lower = text.lower()
        positive_count = sum(
            1 for word in self.sentiment_keywords["positive"] if word in text_lower
        )
        negative_count = sum(
            1 for word in self.sentiment_keywords["negative"] if word in text_lower
        )
        neutral_count = sum(1 for word in self.sentiment_keywords["neutral"] if word in text_lower)
        total_count = positive_count + negative_count + neutral_count
        if total_count == 0:
            return {"sentiment": "neutral", "score": 0, "confidence": 0.1}
        sentiment_score = (positive_count - negative_count) / total_count
        if sentiment_score > 0.3:
            sentiment = "positive"
        elif sentiment_score < -0.3:
            sentiment = "negative"
        else:
            sentiment = "neutral"
        confidence = min(0.95, total_count / 10)
        return {
            "sentiment": sentiment,
            "score": sentiment_score,
            "confidence": confidence,
            "positive_words": positive_count,
            "negative_words": negative_count,
        }

    def analyze_alerts(self, alerts: List[Dict]) -> Dict[str, Any]:
        """Analyze sentiment from multiple alerts"""
        if not alerts:
            return {"overall_sentiment": "neutral", "sentiment_score": 0, "confidence": 0}
        sentiments = []
        for alert in alerts:
            message = alert.get("message", "")
            sentiment = self.analyze_text(message)
            sentiments.append(sentiment)
        avg_score = np.mean([s["score"] for s in sentiments])
        avg_confidence = np.mean([s["confidence"] for s in sentiments])
        if avg_score > 0.2:
            overall = "bullish"
        elif avg_score < -0.2:
            overall = "bearish"
        else:
            overall = "neutral"
        return {
            "overall_sentiment": overall,
            "sentiment_score": float(avg_score),
            "confidence": float(avg_confidence),
            "individual_sentiments": sentiments,
        }


class MLPredictionEngine:
    """Main ML engine combining all models"""

    def __init__(self):
        self.price_model = PricePredictionModel()
        self.signal_classifier = SignalClassificationModel()
        self.sentiment_analyzer = SentimentAnalysisModel()

    def make_prediction(
        self, market_data: pd.DataFrame, alerts: List[Dict] = None
    ) -> Dict[str, Any]:
        """Make comprehensive prediction"""
        predictions = {}
        try:
            price_pred = self.price_model.predict(market_data)
            predictions["price"] = price_pred
        except:
            predictions["price"] = {"error": "Model not trained"}
        if alerts:
            sentiment = self.sentiment_analyzer.analyze_alerts(alerts)
            predictions["sentiment"] = sentiment
        confidence_score = 0
        direction_votes = []
        if "price" in predictions and "predicted_price" in predictions["price"]:
            if predictions["price"]["direction"] == "up":
                direction_votes.append(1)
            else:
                direction_votes.append(-1)
            confidence_score += predictions["price"]["confidence"]
        if "sentiment" in predictions:
            if predictions["sentiment"]["overall_sentiment"] == "bullish":
                direction_votes.append(1)
            elif predictions["sentiment"]["overall_sentiment"] == "bearish":
                direction_votes.append(-1)
            confidence_score += predictions["sentiment"]["confidence"]
        if direction_votes:
            final_direction = "bullish" if sum(direction_votes) > 0 else "bearish"
            final_confidence = confidence_score / len(direction_votes)
        else:
            final_direction = "neutral"
            final_confidence = 0
        return {
            "timestamp": datetime.now().isoformat(),
            "prediction": final_direction,
            "confidence": final_confidence,
            "details": predictions,
        }


ml_engine = MLPredictionEngine()
