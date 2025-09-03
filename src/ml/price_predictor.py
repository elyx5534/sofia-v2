"""Machine Learning models for price prediction."""

import logging
import pickle
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.preprocessing import StandardScaler

from src.adapters.ml.sklearn_adapter import (
    accuracy_score,
    cross_val_score,
    f1_score,
    precision_score,
    recall_score,
    train_test_split,
)
from src.adapters.ml.xgboost_adapter import *

logger = logging.getLogger(__name__)


class PricePredictor:
    """
    ML model for predicting price movements.
    Supports both classification (up/down) and regression (price value).
    """

    def __init__(self, model_type: str = "classification", algorithm: str = "xgboost"):
        """
        Initialize price predictor.

        Args:
            model_type: 'classification' for direction, 'regression' for price
            algorithm: 'xgboost', 'random_forest'
        """
        self.model_type = model_type
        self.algorithm = algorithm
        self.model = None
        self.scaler = StandardScaler()
        self.feature_importance = None
        self.is_trained = False
        self._init_model()

    def _init_model(self):
        """Initialize the ML model based on configuration."""
        if self.model_type == "classification":
            if self.algorithm == "xgboost":
                self.model = xgb.XGBClassifier(
                    n_estimators=100,
                    max_depth=5,
                    learning_rate=0.1,
                    objective="binary:logistic",
                    use_label_encoder=False,
                    eval_metric="logloss",
                )
            else:
                self.model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
        elif self.algorithm == "xgboost":
            self.model = xgb.XGBRegressor(
                n_estimators=100, max_depth=5, learning_rate=0.1, objective="reg:squarederror"
            )
        else:
            self.model = RandomForestRegressor(n_estimators=100, max_depth=5, random_state=42)

    def create_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Create technical features from OHLCV data.

        Args:
            data: DataFrame with OHLCV columns

        Returns:
            DataFrame with features
        """
        features = pd.DataFrame(index=data.index)
        features["returns"] = data["Close"].pct_change()
        features["log_returns"] = np.log(data["Close"] / data["Close"].shift(1))
        features["high_low_ratio"] = data["High"] / data["Low"]
        features["close_open_ratio"] = data["Close"] / data["Open"]
        for period in [5, 10, 20, 50]:
            features[f"sma_{period}"] = data["Close"].rolling(period).mean()
            features[f"sma_{period}_ratio"] = data["Close"] / features[f"sma_{period}"]
        for period in [12, 26]:
            features[f"ema_{period}"] = data["Close"].ewm(span=period).mean()
            features[f"ema_{period}_ratio"] = data["Close"] / features[f"ema_{period}"]
        delta = data["Close"].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        features["rsi"] = 100 - 100 / (1 + rs)
        ema_12 = data["Close"].ewm(span=12).mean()
        ema_26 = data["Close"].ewm(span=26).mean()
        features["macd"] = ema_12 - ema_26
        features["macd_signal"] = features["macd"].ewm(span=9).mean()
        features["macd_histogram"] = features["macd"] - features["macd_signal"]
        sma_20 = data["Close"].rolling(20).mean()
        std_20 = data["Close"].rolling(20).std()
        features["bb_upper"] = sma_20 + 2 * std_20
        features["bb_lower"] = sma_20 - 2 * std_20
        features["bb_width"] = features["bb_upper"] - features["bb_lower"]
        features["bb_position"] = (data["Close"] - features["bb_lower"]) / features["bb_width"]
        if "Volume" in data.columns:
            features["volume_ratio"] = data["Volume"] / data["Volume"].rolling(20).mean()
            features["volume_change"] = data["Volume"].pct_change()
            obv = (np.sign(data["Close"].diff()) * data["Volume"]).fillna(0).cumsum()
            features["obv"] = obv
            features["obv_ema"] = obv.ewm(span=20).mean()
        features["volatility"] = data["Close"].rolling(20).std()
        features["volatility_ratio"] = (
            features["volatility"] / features["volatility"].rolling(50).mean()
        )
        high_low = data["High"] - data["Low"]
        high_close = np.abs(data["High"] - data["Close"].shift())
        low_close = np.abs(data["Low"] - data["Close"].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        features["atr"] = true_range.rolling(14).mean()
        low_14 = data["Low"].rolling(14).min()
        high_14 = data["High"].rolling(14).max()
        features["stoch_k"] = 100 * ((data["Close"] - low_14) / (high_14 - low_14))
        features["stoch_d"] = features["stoch_k"].rolling(3).mean()
        for lag in [1, 2, 3, 5, 10]:
            features[f"returns_lag_{lag}"] = features["returns"].shift(lag)
            features[f"volume_ratio_lag_{lag}"] = features.get("volume_ratio", 0).shift(lag)
        if isinstance(data.index, pd.DatetimeIndex):
            features["day_of_week"] = data.index.dayofweek
            features["day_of_month"] = data.index.day
            features["month"] = data.index.month
            features["quarter"] = data.index.quarter
        features = features.fillna(method="ffill").dropna()
        return features

    def create_labels(self, data: pd.DataFrame, prediction_horizon: int = 1) -> pd.Series:
        """
        Create labels for training.

        Args:
            data: DataFrame with OHLCV columns
            prediction_horizon: Number of periods ahead to predict

        Returns:
            Series with labels
        """
        if self.model_type == "classification":
            future_returns = data["Close"].shift(-prediction_horizon) / data["Close"] - 1
            labels = (future_returns > 0).astype(int)
        else:
            labels = data["Close"].shift(-prediction_horizon)
        return labels

    def train(
        self,
        data: pd.DataFrame,
        prediction_horizon: int = 1,
        test_size: float = 0.2,
        validate: bool = True,
    ) -> Dict[str, Any]:
        """
        Train the ML model.

        Args:
            data: DataFrame with OHLCV columns
            prediction_horizon: Number of periods ahead to predict
            test_size: Fraction of data for testing
            validate: Whether to perform cross-validation

        Returns:
            Dictionary with training metrics
        """
        features = self.create_features(data)
        labels = self.create_labels(data, prediction_horizon)
        common_index = features.index.intersection(labels.dropna().index)
        X = features.loc[common_index]
        y = labels.loc[common_index]
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, shuffle=False
        )
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        self.model.fit(X_train_scaled, y_train)
        self.is_trained = True
        if hasattr(self.model, "feature_importances_"):
            self.feature_importance = pd.Series(
                self.model.feature_importances_, index=X.columns
            ).sort_values(ascending=False)
        train_pred = self.model.predict(X_train_scaled)
        test_pred = self.model.predict(X_test_scaled)
        metrics = {}
        if self.model_type == "classification":
            metrics["train_accuracy"] = accuracy_score(y_train, train_pred)
            metrics["test_accuracy"] = accuracy_score(y_test, test_pred)
            metrics["precision"] = precision_score(y_test, test_pred, zero_division=0)
            metrics["recall"] = recall_score(y_test, test_pred, zero_division=0)
            metrics["f1_score"] = f1_score(y_test, test_pred, zero_division=0)
            test_proba = self.model.predict_proba(X_test_scaled)[:, 1]
            metrics["avg_confidence"] = np.mean(np.abs(test_proba - 0.5) + 0.5)
        else:
            from src.adapters.ml.sklearn_adapter import (
                mean_absolute_error,
                mean_squared_error,
                r2_score,
            )

            metrics["train_mse"] = mean_squared_error(y_train, train_pred)
            metrics["test_mse"] = mean_squared_error(y_test, test_pred)
            metrics["train_mae"] = mean_absolute_error(y_train, train_pred)
            metrics["test_mae"] = mean_absolute_error(y_test, test_pred)
            metrics["train_r2"] = r2_score(y_train, train_pred)
            metrics["test_r2"] = r2_score(y_test, test_pred)
        if validate and len(X) > 50:
            if self.model_type == "classification":
                cv_scores = cross_val_score(
                    self.model, X_train_scaled, y_train, cv=5, scoring="accuracy"
                )
                metrics["cv_accuracy_mean"] = np.mean(cv_scores)
                metrics["cv_accuracy_std"] = np.std(cv_scores)
            else:
                cv_scores = cross_val_score(
                    self.model, X_train_scaled, y_train, cv=5, scoring="neg_mean_squared_error"
                )
                metrics["cv_mse_mean"] = -np.mean(cv_scores)
                metrics["cv_mse_std"] = np.std(cv_scores)
        metrics["n_features"] = X.shape[1]
        metrics["n_train_samples"] = len(X_train)
        metrics["n_test_samples"] = len(X_test)
        return metrics

    def predict(self, data: pd.DataFrame, return_confidence: bool = False) -> pd.DataFrame:
        """
        Make predictions on new data.

        Args:
            data: DataFrame with OHLCV columns
            return_confidence: Return confidence scores for classification

        Returns:
            DataFrame with predictions
        """
        if not self.is_trained:
            raise ValueError("Model must be trained before prediction")
        features = self.create_features(data)
        features_scaled = self.scaler.transform(features)
        predictions = self.model.predict(features_scaled)
        result = pd.DataFrame(index=features.index)
        if self.model_type == "classification":
            result["prediction"] = predictions
            result["direction"] = result["prediction"].map({1: "UP", 0: "DOWN"})
            if return_confidence:
                proba = self.model.predict_proba(features_scaled)
                result["confidence"] = np.max(proba, axis=1)
                result["prob_up"] = proba[:, 1]
                result["prob_down"] = proba[:, 0]
        else:
            result["predicted_price"] = predictions
            result["current_price"] = data.loc[features.index, "Close"]
            result["predicted_return"] = (
                result["predicted_price"] / result["current_price"] - 1
            ) * 100
        return result

    def backtest_predictions(
        self,
        data: pd.DataFrame,
        prediction_horizon: int = 1,
        training_window: int = 252,
        retrain_frequency: int = 20,
    ) -> pd.DataFrame:
        """
        Backtest the model with walk-forward analysis.

        Args:
            data: DataFrame with OHLCV columns
            prediction_horizon: Number of periods ahead to predict
            training_window: Size of training window
            retrain_frequency: How often to retrain the model

        Returns:
            DataFrame with backtest results
        """
        results = []
        for i in range(training_window, len(data) - prediction_horizon, retrain_frequency):
            train_data = data.iloc[i - training_window : i]
            test_end = min(i + retrain_frequency, len(data) - prediction_horizon)
            test_data = data.iloc[i:test_end]
            self.train(train_data, prediction_horizon, test_size=0.0, validate=False)
            predictions = self.predict(test_data, return_confidence=True)
            for j, (idx, pred) in enumerate(predictions.iterrows()):
                actual_idx = i + j + prediction_horizon
                if actual_idx < len(data):
                    actual_return = (
                        data.iloc[actual_idx]["Close"] / data.iloc[i + j]["Close"] - 1
                    ) * 100
                    result = {
                        "date": idx,
                        "predicted": pred.get("direction", pred.get("predicted_return")),
                        "actual_return": actual_return,
                        "correct": (
                            pred.get("direction") == "UP"
                            and actual_return > 0
                            or (pred.get("direction") == "DOWN" and actual_return <= 0)
                            if self.model_type == "classification"
                            else None
                        ),
                        "confidence": pred.get("confidence", None),
                    }
                    results.append(result)
        backtest_df = pd.DataFrame(results)
        if self.model_type == "classification":
            backtest_df["accuracy"] = backtest_df["correct"].rolling(50).mean()
        return backtest_df

    def save_model(self, path: Path):
        """Save trained model to disk."""
        if not self.is_trained:
            raise ValueError("Model must be trained before saving")
        model_data = {
            "model": self.model,
            "scaler": self.scaler,
            "model_type": self.model_type,
            "algorithm": self.algorithm,
            "feature_importance": self.feature_importance,
        }
        with open(path, "wb") as f:
            pickle.dump(model_data, f)
        logger.info(f"Model saved to {path}")

    def load_model(self, path: Path):
        """Load trained model from disk."""
        with open(path, "rb") as f:
            model_data = pickle.load(f)
        self.model = model_data["model"]
        self.scaler = model_data["scaler"]
        self.model_type = model_data["model_type"]
        self.algorithm = model_data["algorithm"]
        self.feature_importance = model_data["feature_importance"]
        self.is_trained = True
        logger.info(f"Model loaded from {path}")

    def get_top_features(self, n: int = 10) -> pd.Series:
        """Get top n most important features."""
        if self.feature_importance is None:
            return pd.Series()
        return self.feature_importance.head(n)
