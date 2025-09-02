"""
Real-Time AI Prediction Engine
Uses real crypto data to predict price movements with multiple ML models
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler, StandardScaler

from ..data.real_time_fetcher import fetcher

logger = logging.getLogger(__name__)


@dataclass
class PredictionResult:
    symbol: str
    current_price: float
    predicted_price_1h: float
    predicted_price_24h: float
    predicted_price_7d: float
    confidence_1h: float
    confidence_24h: float
    confidence_7d: float
    trend_direction: str  # "up", "down", "sideways"
    signal_strength: float  # 0-100
    model_consensus: float  # Agreement between models
    timestamp: datetime

    def to_dict(self):
        return {
            "symbol": self.symbol,
            "current_price": self.current_price,
            "predictions": {
                "1h": {"price": self.predicted_price_1h, "confidence": self.confidence_1h},
                "24h": {"price": self.predicted_price_24h, "confidence": self.confidence_24h},
                "7d": {"price": self.predicted_price_7d, "confidence": self.confidence_7d},
            },
            "trend_direction": self.trend_direction,
            "signal_strength": self.signal_strength,
            "model_consensus": self.model_consensus,
            "timestamp": self.timestamp.isoformat(),
        }


class FeatureEngineer:
    """Creates features for ML models from crypto data"""

    def __init__(self):
        self.price_scaler = StandardScaler()
        self.volume_scaler = StandardScaler()
        self.fitted = False

    def create_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create technical indicators and features from OHLCV data"""
        features = df.copy()

        # Price-based features
        features["sma_5"] = features["close"].rolling(5).mean()
        features["sma_10"] = features["close"].rolling(10).mean()
        features["sma_20"] = features["close"].rolling(20).mean()
        features["ema_5"] = features["close"].ewm(span=5).mean()
        features["ema_10"] = features["close"].ewm(span=10).mean()

        # Momentum indicators
        features["rsi"] = self._calculate_rsi(features["close"], 14)
        features["macd"], features["macd_signal"], features["macd_histogram"] = (
            self._calculate_macd(features["close"])
        )

        # Bollinger Bands
        features["bb_upper"], features["bb_middle"], features["bb_lower"] = (
            self._calculate_bollinger_bands(features["close"])
        )
        features["bb_width"] = features["bb_upper"] - features["bb_lower"]
        features["bb_position"] = (features["close"] - features["bb_lower"]) / (
            features["bb_upper"] - features["bb_lower"]
        )

        # Volume indicators
        features["volume_sma"] = features["volume"].rolling(10).mean()
        features["volume_ratio"] = features["volume"] / features["volume_sma"]
        features["price_volume"] = features["close"] * features["volume"]

        # Price action features
        features["body_size"] = abs(features["close"] - features["open"])
        features["upper_shadow"] = features["high"] - np.maximum(
            features["open"], features["close"]
        )
        features["lower_shadow"] = np.minimum(features["open"], features["close"]) - features["low"]
        features["hl_ratio"] = (features["high"] - features["low"]) / features["close"]

        # Returns and volatility
        features["returns_1h"] = features["close"].pct_change(1)
        features["returns_4h"] = features["close"].pct_change(4)
        features["returns_24h"] = features["close"].pct_change(24)
        features["volatility_5"] = features["returns_1h"].rolling(5).std()
        features["volatility_10"] = features["returns_1h"].rolling(10).std()

        # Time-based features
        features["hour"] = pd.to_datetime(features.index).hour
        features["day_of_week"] = pd.to_datetime(features.index).dayofweek

        # Lag features
        for lag in [1, 2, 3, 6, 12, 24]:
            features[f"close_lag_{lag}"] = features["close"].shift(lag)
            features[f"volume_lag_{lag}"] = features["volume"].shift(lag)

        return features.dropna()

    def _calculate_rsi(self, prices, period=14):
        """Calculate Relative Strength Index"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _calculate_macd(self, prices, fast=12, slow=26, signal=9):
        """Calculate MACD"""
        ema_fast = prices.ewm(span=fast).mean()
        ema_slow = prices.ewm(span=slow).mean()
        macd = ema_fast - ema_slow
        macd_signal = macd.ewm(span=signal).mean()
        macd_histogram = macd - macd_signal
        return macd, macd_signal, macd_histogram

    def _calculate_bollinger_bands(self, prices, period=20, std_dev=2):
        """Calculate Bollinger Bands"""
        middle = prices.rolling(period).mean()
        std = prices.rolling(period).std()
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        return upper, middle, lower


class MultiModelPredictor:
    """Ensemble of multiple ML models for crypto price prediction"""

    def __init__(self):
        self.models = {
            "rf": RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1),
            "gb": GradientBoostingRegressor(n_estimators=100, random_state=42),
            "lr": LinearRegression(),
        }

        self.feature_engineer = FeatureEngineer()
        self.is_trained = False
        self.feature_columns = None
        self.target_scaler = MinMaxScaler()

    async def prepare_data(self, symbol: str, hours: int = 168) -> Optional[pd.DataFrame]:
        """Fetch and prepare data for training"""
        try:
            # Fetch hourly data
            klines = await fetcher.get_klines(symbol.lower(), "1h", hours)

            if not klines:
                logger.error(f"No data received for {symbol}")
                return None

            # Convert to DataFrame
            df = pd.DataFrame(klines)
            df["time"] = pd.to_datetime(df["time"])
            df.set_index("time", inplace=True)

            # Sort by time
            df = df.sort_index()

            logger.info(f"Prepared {len(df)} hours of data for {symbol}")
            return df

        except Exception as e:
            logger.error(f"Error preparing data for {symbol}: {e}")
            return None

    def train_models(self, df: pd.DataFrame, target_horizons: List[int] = [1, 24, 168]):
        """Train models for different prediction horizons"""
        try:
            # Create features
            features_df = self.feature_engineer.create_features(df)

            if len(features_df) < 50:
                logger.error("Not enough data for training")
                return False

            # Select feature columns (exclude price columns)
            exclude_cols = ["open", "high", "low", "close", "volume"]
            self.feature_columns = [col for col in features_df.columns if col not in exclude_cols]

            X = features_df[self.feature_columns]

            # Train for each horizon
            self.trained_models = {}
            self.model_scores = {}

            for horizon in target_horizons:
                logger.info(f"Training models for {horizon}h horizon")

                # Create target variable (future price)
                y = features_df["close"].shift(-horizon).dropna()
                X_horizon = X[:-horizon] if horizon > 0 else X

                if len(X_horizon) != len(y):
                    X_horizon = X_horizon.iloc[: len(y)]

                # Scale target
                y_scaled = self.target_scaler.fit_transform(y.values.reshape(-1, 1)).ravel()

                # Split data
                X_train, X_test, y_train, y_test = train_test_split(
                    X_horizon, y_scaled, test_size=0.2, random_state=42, shuffle=False
                )

                # Train each model
                horizon_models = {}
                horizon_scores = {}

                for name, model in self.models.items():
                    try:
                        # Train model
                        model.fit(X_train, y_train)

                        # Predict
                        y_pred = model.predict(X_test)

                        # Calculate scores
                        mse = mean_squared_error(y_test, y_pred)
                        r2 = r2_score(y_test, y_pred)

                        horizon_models[name] = model
                        horizon_scores[name] = {"mse": mse, "r2": r2}

                        logger.info(f"Model {name} - {horizon}h: R² = {r2:.3f}, MSE = {mse:.6f}")

                    except Exception as e:
                        logger.error(f"Error training {name} model for {horizon}h: {e}")

                self.trained_models[horizon] = horizon_models
                self.model_scores[horizon] = horizon_scores

            self.is_trained = True
            logger.info("Model training completed successfully")
            return True

        except Exception as e:
            logger.error(f"Error in model training: {e}")
            return False

    async def predict(self, symbol: str, current_data: pd.DataFrame) -> Optional[PredictionResult]:
        """Make predictions using ensemble of models"""
        if not self.is_trained:
            logger.error("Models not trained yet")
            return None

        try:
            # Create features for current data
            features_df = self.feature_engineer.create_features(current_data)

            if features_df.empty:
                logger.error("No features created from current data")
                return None

            # Get latest feature values
            X_current = features_df[self.feature_columns].iloc[-1:].fillna(0)
            current_price = current_data["close"].iloc[-1]

            # Make predictions for each horizon
            predictions = {}
            confidences = {}

            for horizon in [1, 24, 168]:
                if horizon not in self.trained_models:
                    continue

                horizon_predictions = []
                horizon_weights = []

                for name, model in self.trained_models[horizon].items():
                    try:
                        # Make prediction
                        pred_scaled = model.predict(X_current)[0]
                        pred_price = self.target_scaler.inverse_transform([[pred_scaled]])[0][0]

                        # Calculate weight based on model performance
                        r2_score = self.model_scores[horizon][name]["r2"]
                        weight = max(0, r2_score)  # Use R² as weight

                        horizon_predictions.append(pred_price)
                        horizon_weights.append(weight)

                    except Exception as e:
                        logger.error(f"Error in prediction with {name}: {e}")

                if horizon_predictions:
                    # Weighted average prediction
                    if sum(horizon_weights) > 0:
                        weighted_pred = np.average(horizon_predictions, weights=horizon_weights)
                        confidence = np.mean(horizon_weights) * 100  # Convert to percentage
                    else:
                        weighted_pred = np.mean(horizon_predictions)
                        confidence = 50.0  # Default confidence

                    predictions[horizon] = weighted_pred
                    confidences[horizon] = min(95, max(10, confidence))  # Clamp between 10-95%

            # Calculate trend direction and signal strength
            if 1 in predictions and 24 in predictions:
                short_term_change = (predictions[1] - current_price) / current_price * 100
                medium_term_change = (predictions[24] - current_price) / current_price * 100

                if medium_term_change > 2:
                    trend_direction = "up"
                    signal_strength = min(100, abs(medium_term_change) * 10)
                elif medium_term_change < -2:
                    trend_direction = "down"
                    signal_strength = min(100, abs(medium_term_change) * 10)
                else:
                    trend_direction = "sideways"
                    signal_strength = 30
            else:
                trend_direction = "sideways"
                signal_strength = 50

            # Calculate model consensus (agreement between models)
            if len(predictions) >= 2:
                pred_values = list(predictions.values())
                relative_changes = [(p - current_price) / current_price for p in pred_values]
                consensus = 100 - (np.std(relative_changes) * 1000)  # Lower std = higher consensus
                model_consensus = max(0, min(100, consensus))
            else:
                model_consensus = 50

            # Create prediction result
            result = PredictionResult(
                symbol=symbol,
                current_price=current_price,
                predicted_price_1h=predictions.get(1, current_price),
                predicted_price_24h=predictions.get(24, current_price),
                predicted_price_7d=predictions.get(168, current_price),
                confidence_1h=confidences.get(1, 50),
                confidence_24h=confidences.get(24, 50),
                confidence_7d=confidences.get(168, 50),
                trend_direction=trend_direction,
                signal_strength=signal_strength,
                model_consensus=model_consensus,
                timestamp=datetime.now(timezone.utc),
            )

            logger.info(
                f"Prediction for {symbol}: {trend_direction} trend, {signal_strength:.1f}% strength"
            )
            return result

        except Exception as e:
            logger.error(f"Error making prediction for {symbol}: {e}")
            return None


class RealTimePredictionEngine:
    """Main engine for real-time crypto predictions"""

    def __init__(self):
        self.predictors: Dict[str, MultiModelPredictor] = {}
        self.prediction_cache: Dict[str, PredictionResult] = {}
        self.is_running = False

        # Symbols to predict
        self.symbols = ["bitcoin", "ethereum", "solana", "binancecoin", "cardano"]

    async def start(self):
        """Start the prediction engine"""
        if self.is_running:
            return

        self.is_running = True
        await fetcher.start()

        # Initialize predictors for each symbol
        logger.info("Initializing AI prediction models...")

        for symbol in self.symbols:
            logger.info(f"Training models for {symbol}...")
            predictor = MultiModelPredictor()

            # Prepare training data (last 7 days)
            df = await predictor.prepare_data(symbol, hours=168)

            if df is not None and len(df) >= 50:
                success = predictor.train_models(df)
                if success:
                    self.predictors[symbol] = predictor
                    logger.info(f"Models trained successfully for {symbol}")
                else:
                    logger.error(f"Failed to train models for {symbol}")
            else:
                logger.error(f"Insufficient data for {symbol}")

        # Start prediction loop
        asyncio.create_task(self._prediction_loop())
        logger.info(f"AI Prediction Engine started with {len(self.predictors)} symbols")

    async def stop(self):
        """Stop the prediction engine"""
        self.is_running = False
        await fetcher.stop()
        logger.info("AI Prediction Engine stopped")

    async def _prediction_loop(self):
        """Main prediction loop"""
        while self.is_running:
            try:
                for symbol in self.symbols:
                    if symbol not in self.predictors:
                        continue

                    # Get recent data for prediction
                    df = await self.predictors[symbol].prepare_data(symbol, hours=48)

                    if df is not None and len(df) >= 24:
                        # Make prediction
                        prediction = await self.predictors[symbol].predict(symbol, df)

                        if prediction:
                            self.prediction_cache[symbol] = prediction

                await asyncio.sleep(600)  # Update every 10 minutes

            except Exception as e:
                logger.error(f"Error in prediction loop: {e}")
                await asyncio.sleep(60)

    def get_prediction(self, symbol: str) -> Optional[PredictionResult]:
        """Get latest prediction for a symbol"""
        return self.prediction_cache.get(symbol)

    def get_all_predictions(self) -> Dict[str, Dict]:
        """Get all current predictions"""
        return {symbol: pred.to_dict() for symbol, pred in self.prediction_cache.items()}

    async def retrain_model(self, symbol: str, hours: int = 168):
        """Retrain model for a specific symbol with fresh data"""
        try:
            logger.info(f"Retraining model for {symbol}...")

            predictor = MultiModelPredictor()
            df = await predictor.prepare_data(symbol, hours=hours)

            if df is not None and len(df) >= 50:
                success = predictor.train_models(df)
                if success:
                    self.predictors[symbol] = predictor
                    logger.info(f"Model retrained successfully for {symbol}")
                    return True

        except Exception as e:
            logger.error(f"Error retraining model for {symbol}: {e}")

        return False


# Global prediction engine instance
prediction_engine = RealTimePredictionEngine()
