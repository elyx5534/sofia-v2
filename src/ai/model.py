"""
AI Model system with LightGBM/LogReg baseline and IsotonicCalibration
Target P95 < 150ms response time with feature extraction and prediction
"""

import asyncio
import logging
import os
import time
import pickle
import numpy as np
import pandas as pd
from dataclasses import dataclass, asdict
from typing import Dict, Optional, Any, List, Tuple, Union
from datetime import datetime, timedelta
import redis.asyncio as redis
from prometheus_client import Counter, Histogram, Gauge
import lightgbm as lgb
from sklearn.linear_model import LogisticRegression
from sklearn.isotonic import IsotonicRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score
import joblib
import warnings
warnings.filterwarnings('ignore')

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Prometheus metrics
PREDICTIONS_MADE = Counter('ai_predictions_made_total', 'Total predictions made', ['model_type', 'symbol'])
PREDICTION_LATENCY = Histogram('ai_prediction_latency_seconds', 'Prediction latency', ['model_type'])
MODEL_ACCURACY = Gauge('ai_model_accuracy', 'Model accuracy', ['model_type', 'symbol'])
MODEL_TRAINING_TIME = Histogram('ai_model_training_seconds', 'Model training time', ['model_type'])
FEATURE_IMPORTANCE = Gauge('ai_feature_importance', 'Feature importance', ['model_type', 'feature_name'])
MODEL_ERRORS = Counter('ai_model_errors_total', 'Model errors', ['model_type', 'error_type'])


@dataclass
class ModelPrediction:
    """Model prediction result"""
    symbol: str
    timestamp: float
    model_type: str
    raw_score: float
    calibrated_score: float
    prediction_class: int  # 0 = down, 1 = up
    confidence: float
    features_used: List[str]
    prediction_horizon: str  # '1m', '5m', '1h'
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ModelMetrics:
    """Model performance metrics"""
    model_type: str
    symbol: str
    accuracy: float
    precision: float
    recall: float
    auc: float
    feature_count: int
    training_samples: int
    last_updated: float


class BaseMLModel:
    """Base class for ML models"""
    
    def __init__(self, model_type: str, symbol: str):
        self.model_type = model_type
        self.symbol = symbol
        self.model = None
        self.calibrator = None
        self.scaler = None
        self.feature_names = []
        self.is_trained = False
        self.last_training_time = 0
        self.metrics = None
        
        # Configuration
        self.min_training_samples = int(os.getenv('AI_MIN_TRAINING_SAMPLES', '1000'))
        self.retrain_interval = int(os.getenv('AI_RETRAIN_INTERVAL_HOURS', '6')) * 3600
        self.calibration_enabled = os.getenv('AI_CALIBRATION_ENABLED', 'true').lower() == 'true'
        
    def extract_features_and_target(self, data: pd.DataFrame, target_horizon: str = '5m') -> Tuple[np.ndarray, np.ndarray]:
        """Extract features and target from dataframe"""
        # Define feature columns (excluding timestamp, symbol, and target)
        feature_cols = [col for col in data.columns if col not in ['timestamp', 'symbol'] and not col.startswith('target_')]
        
        # Filter out None/NaN features
        features_df = data[feature_cols].fillna(0)
        
        # Create target based on horizon
        target_col = f'target_{target_horizon}'
        if target_col not in data.columns:
            # Create target: 1 if price goes up in the next period, 0 otherwise
            if 'close' in data.columns:
                # Simple price direction prediction
                future_prices = data['close'].shift(-1)  # Next period price
                data[target_col] = (future_prices > data['close']).astype(int)
            else:
                # Fallback: use r_1m if available
                if 'r_1m' in data.columns:
                    data[target_col] = (data['r_1m'].shift(-1) > 0).astype(int)
                else:
                    logger.warning(f"Cannot create target for {target_horizon}")
                    return np.array([]), np.array([])
        
        # Drop rows with NaN targets
        valid_mask = ~data[target_col].isna()
        features_df = features_df[valid_mask]
        target = data[target_col][valid_mask]
        
        self.feature_names = feature_cols
        return features_df.values, target.values
    
    def train(self, X: np.ndarray, y: np.ndarray) -> bool:
        """Train the model - implemented by subclasses"""
        raise NotImplementedError
    
    def predict(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Make predictions - implemented by subclasses"""
        raise NotImplementedError
    
    def save_model(self, filepath: str):
        """Save model to file"""
        model_data = {
            'model': self.model,
            'calibrator': self.calibrator,
            'scaler': self.scaler,
            'feature_names': self.feature_names,
            'is_trained': self.is_trained,
            'last_training_time': self.last_training_time,
            'metrics': self.metrics
        }
        joblib.dump(model_data, filepath)
    
    def load_model(self, filepath: str) -> bool:
        """Load model from file"""
        try:
            model_data = joblib.load(filepath)
            self.model = model_data['model']
            self.calibrator = model_data.get('calibrator')
            self.scaler = model_data.get('scaler')
            self.feature_names = model_data['feature_names']
            self.is_trained = model_data['is_trained']
            self.last_training_time = model_data['last_training_time']
            self.metrics = model_data.get('metrics')
            return True
        except Exception as e:
            logger.error(f"Model loading error: {e}")
            return False


class LightGBMModel(BaseMLModel):
    """LightGBM model implementation"""
    
    def __init__(self, symbol: str):
        super().__init__('lightgbm', symbol)
        
        # LightGBM hyperparameters
        self.params = {
            'objective': 'binary',
            'metric': 'binary_logloss',
            'boosting_type': 'gbdt',
            'num_leaves': int(os.getenv('LGBM_NUM_LEAVES', '31')),
            'learning_rate': float(os.getenv('LGBM_LEARNING_RATE', '0.05')),
            'feature_fraction': float(os.getenv('LGBM_FEATURE_FRACTION', '0.8')),
            'bagging_fraction': float(os.getenv('LGBM_BAGGING_FRACTION', '0.8')),
            'bagging_freq': int(os.getenv('LGBM_BAGGING_FREQ', '5')),
            'min_child_samples': int(os.getenv('LGBM_MIN_CHILD_SAMPLES', '20')),
            'max_depth': int(os.getenv('LGBM_MAX_DEPTH', '8')),
            'reg_alpha': float(os.getenv('LGBM_REG_ALPHA', '0.1')),
            'reg_lambda': float(os.getenv('LGBM_REG_LAMBDA', '0.1')),
            'verbosity': -1,
            'random_state': 42
        }
        
        self.num_boost_round = int(os.getenv('LGBM_NUM_BOOST_ROUND', '100'))
        self.early_stopping_rounds = int(os.getenv('LGBM_EARLY_STOPPING', '10'))
    
    def train(self, X: np.ndarray, y: np.ndarray) -> bool:
        """Train LightGBM model"""
        try:
            start_time = time.time()
            
            if len(X) < self.min_training_samples:
                logger.warning(f"Insufficient training data: {len(X)} < {self.min_training_samples}")
                return False
            
            # Split data
            X_train, X_val, y_train, y_val = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )
            
            # Scale features
            self.scaler = StandardScaler()
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_val_scaled = self.scaler.transform(X_val)
            
            # Create datasets
            train_data = lgb.Dataset(X_train_scaled, label=y_train)
            val_data = lgb.Dataset(X_val_scaled, label=y_val, reference=train_data)
            
            # Train model
            self.model = lgb.train(
                self.params,
                train_data,
                valid_sets=[val_data],
                num_boost_round=self.num_boost_round,
                callbacks=[lgb.early_stopping(self.early_stopping_rounds), lgb.log_evaluation(0)]
            )
            
            # Calibrate predictions
            if self.calibration_enabled:
                train_pred = self.model.predict(X_train_scaled, num_iteration=self.model.best_iteration)
                self.calibrator = IsotonicRegression(out_of_bounds='clip')
                self.calibrator.fit(train_pred, y_train)
            
            # Evaluate model
            val_pred = self.model.predict(X_val_scaled, num_iteration=self.model.best_iteration)
            val_pred_binary = (val_pred > 0.5).astype(int)
            
            accuracy = accuracy_score(y_val, val_pred_binary)
            precision = precision_score(y_val, val_pred_binary, zero_division=0)
            recall = recall_score(y_val, val_pred_binary, zero_division=0)
            auc = roc_auc_score(y_val, val_pred) if len(np.unique(y_val)) > 1 else 0.5
            
            # Store metrics
            self.metrics = ModelMetrics(
                model_type=self.model_type,
                symbol=self.symbol,
                accuracy=accuracy,
                precision=precision,
                recall=recall,
                auc=auc,
                feature_count=len(self.feature_names),
                training_samples=len(X),
                last_updated=time.time()
            )
            
            # Update Prometheus metrics
            MODEL_ACCURACY.labels(model_type=self.model_type, symbol=self.symbol).set(accuracy)
            MODEL_TRAINING_TIME.labels(model_type=self.model_type).observe(time.time() - start_time)
            
            # Feature importance
            if hasattr(self.model, 'feature_importance'):
                importance = self.model.feature_importance(importance_type='gain')
                for i, imp in enumerate(importance):
                    if i < len(self.feature_names):
                        FEATURE_IMPORTANCE.labels(
                            model_type=self.model_type,
                            feature_name=self.feature_names[i]
                        ).set(imp)
            
            self.is_trained = True
            self.last_training_time = time.time()
            
            logger.info(f"LightGBM trained for {self.symbol}: accuracy={accuracy:.3f}, AUC={auc:.3f}")
            return True
            
        except Exception as e:
            logger.error(f"LightGBM training error for {self.symbol}: {e}")
            MODEL_ERRORS.labels(model_type=self.model_type, error_type=type(e).__name__).inc()
            return False
    
    def predict(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Make predictions with LightGBM"""
        if not self.is_trained or self.model is None:
            return np.array([]), np.array([])
        
        try:
            # Scale features
            X_scaled = self.scaler.transform(X) if self.scaler else X
            
            # Get raw predictions
            raw_pred = self.model.predict(X_scaled, num_iteration=self.model.best_iteration)
            
            # Calibrate predictions if calibrator is available
            if self.calibrator:
                calibrated_pred = self.calibrator.predict(raw_pred)
            else:
                calibrated_pred = raw_pred
            
            return raw_pred, calibrated_pred
            
        except Exception as e:
            logger.error(f"LightGBM prediction error: {e}")
            MODEL_ERRORS.labels(model_type=self.model_type, error_type=type(e).__name__).inc()
            return np.array([]), np.array([])


class LogisticRegressionModel(BaseMLModel):
    """Logistic Regression model implementation"""
    
    def __init__(self, symbol: str):
        super().__init__('logistic_regression', symbol)
        
        # LogReg hyperparameters
        self.C = float(os.getenv('LOGREG_C', '1.0'))
        self.max_iter = int(os.getenv('LOGREG_MAX_ITER', '1000'))
        self.solver = os.getenv('LOGREG_SOLVER', 'liblinear')
    
    def train(self, X: np.ndarray, y: np.ndarray) -> bool:
        """Train Logistic Regression model"""
        try:
            start_time = time.time()
            
            if len(X) < self.min_training_samples:
                logger.warning(f"Insufficient training data: {len(X)} < {self.min_training_samples}")
                return False
            
            # Split data
            X_train, X_val, y_train, y_val = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )
            
            # Scale features
            self.scaler = StandardScaler()
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_val_scaled = self.scaler.transform(X_val)
            
            # Train model
            self.model = LogisticRegression(
                C=self.C,
                max_iter=self.max_iter,
                solver=self.solver,
                random_state=42
            )
            self.model.fit(X_train_scaled, y_train)
            
            # Calibrate predictions
            if self.calibration_enabled:
                train_pred = self.model.predict_proba(X_train_scaled)[:, 1]
                self.calibrator = IsotonicRegression(out_of_bounds='clip')
                self.calibrator.fit(train_pred, y_train)
            
            # Evaluate model
            val_pred_proba = self.model.predict_proba(X_val_scaled)[:, 1]
            val_pred = self.model.predict(X_val_scaled)
            
            accuracy = accuracy_score(y_val, val_pred)
            precision = precision_score(y_val, val_pred, zero_division=0)
            recall = recall_score(y_val, val_pred, zero_division=0)
            auc = roc_auc_score(y_val, val_pred_proba) if len(np.unique(y_val)) > 1 else 0.5
            
            # Store metrics
            self.metrics = ModelMetrics(
                model_type=self.model_type,
                symbol=self.symbol,
                accuracy=accuracy,
                precision=precision,
                recall=recall,
                auc=auc,
                feature_count=len(self.feature_names),
                training_samples=len(X),
                last_updated=time.time()
            )
            
            # Update Prometheus metrics
            MODEL_ACCURACY.labels(model_type=self.model_type, symbol=self.symbol).set(accuracy)
            MODEL_TRAINING_TIME.labels(model_type=self.model_type).observe(time.time() - start_time)
            
            # Feature importance (coefficients)
            if hasattr(self.model, 'coef_'):
                importance = np.abs(self.model.coef_[0])
                for i, imp in enumerate(importance):
                    if i < len(self.feature_names):
                        FEATURE_IMPORTANCE.labels(
                            model_type=self.model_type,
                            feature_name=self.feature_names[i]
                        ).set(imp)
            
            self.is_trained = True
            self.last_training_time = time.time()
            
            logger.info(f"LogReg trained for {self.symbol}: accuracy={accuracy:.3f}, AUC={auc:.3f}")
            return True
            
        except Exception as e:
            logger.error(f"LogReg training error for {self.symbol}: {e}")
            MODEL_ERRORS.labels(model_type=self.model_type, error_type=type(e).__name__).inc()
            return False
    
    def predict(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Make predictions with Logistic Regression"""
        if not self.is_trained or self.model is None:
            return np.array([]), np.array([])
        
        try:
            # Scale features
            X_scaled = self.scaler.transform(X) if self.scaler else X
            
            # Get raw predictions (probabilities)
            raw_pred = self.model.predict_proba(X_scaled)[:, 1]
            
            # Calibrate predictions if calibrator is available
            if self.calibrator:
                calibrated_pred = self.calibrator.predict(raw_pred)
            else:
                calibrated_pred = raw_pred
            
            return raw_pred, calibrated_pred
            
        except Exception as e:
            logger.error(f"LogReg prediction error: {e}")
            MODEL_ERRORS.labels(model_type=self.model_type, error_type=type(e).__name__).inc()
            return np.array([]), np.array([])


class ModelEnsemble:
    """Ensemble of multiple models"""
    
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.models = {}
        self.ensemble_weights = {}
        
        # Initialize models
        model_types = os.getenv('AI_MODEL_TYPES', 'lightgbm,logistic_regression').split(',')
        
        for model_type in model_types:
            model_type = model_type.strip()
            if model_type == 'lightgbm':
                self.models[model_type] = LightGBMModel(symbol)
            elif model_type == 'logistic_regression':
                self.models[model_type] = LogisticRegressionModel(symbol)
        
        # Equal weights initially
        if self.models:
            weight = 1.0 / len(self.models)
            for model_type in self.models:
                self.ensemble_weights[model_type] = weight
    
    def train_all(self, X: np.ndarray, y: np.ndarray) -> Dict[str, bool]:
        """Train all models in ensemble"""
        results = {}
        
        for model_type, model in self.models.items():
            results[model_type] = model.train(X, y)
        
        # Update ensemble weights based on performance
        self._update_ensemble_weights()
        
        return results
    
    def _update_ensemble_weights(self):
        """Update ensemble weights based on model performance"""
        total_auc = 0
        model_aucs = {}
        
        for model_type, model in self.models.items():
            if model.is_trained and model.metrics:
                auc = model.metrics.auc
                model_aucs[model_type] = auc
                total_auc += auc
        
        if total_auc > 0:
            # Weight by AUC performance
            for model_type in model_aucs:
                self.ensemble_weights[model_type] = model_aucs[model_type] / total_auc
        
        logger.info(f"Updated ensemble weights for {self.symbol}: {self.ensemble_weights}")
    
    def predict(self, X: np.ndarray) -> Optional[ModelPrediction]:
        """Make ensemble prediction"""
        if not X.size:
            return None
        
        predictions = {}
        raw_scores = {}
        calibrated_scores = {}
        
        # Get predictions from all trained models
        for model_type, model in self.models.items():
            if model.is_trained:
                raw_pred, calibrated_pred = model.predict(X)
                if len(raw_pred) > 0:
                    predictions[model_type] = {
                        'raw': raw_pred[0] if len(raw_pred) == 1 else np.mean(raw_pred),
                        'calibrated': calibrated_pred[0] if len(calibrated_pred) == 1 else np.mean(calibrated_pred)
                    }
                    raw_scores[model_type] = predictions[model_type]['raw']
                    calibrated_scores[model_type] = predictions[model_type]['calibrated']
        
        if not predictions:
            return None
        
        # Ensemble predictions using weights
        ensemble_raw = sum(
            self.ensemble_weights.get(model_type, 0) * score 
            for model_type, score in raw_scores.items()
        )
        
        ensemble_calibrated = sum(
            self.ensemble_weights.get(model_type, 0) * score 
            for model_type, score in calibrated_scores.items()
        )
        
        # Calculate confidence as agreement between models
        if len(predictions) > 1:
            calibrated_values = list(calibrated_scores.values())
            confidence = 1.0 - np.std(calibrated_values)  # Higher agreement = higher confidence
        else:
            confidence = 0.8  # Default confidence for single model
        
        # Determine prediction class
        prediction_class = 1 if ensemble_calibrated > 0.5 else 0
        
        # Get feature names from any trained model
        feature_names = []
        for model in self.models.values():
            if model.is_trained:
                feature_names = model.feature_names
                break
        
        return ModelPrediction(
            symbol=self.symbol,
            timestamp=time.time(),
            model_type='ensemble',
            raw_score=ensemble_raw,
            calibrated_score=ensemble_calibrated,
            prediction_class=prediction_class,
            confidence=confidence,
            features_used=feature_names,
            prediction_horizon='5m'  # Default horizon
        )


class AIModelManager:
    """Main AI model management system"""
    
    def __init__(self):
        self.redis_client = None
        self.ensembles = {}  # {symbol: ModelEnsemble}
        self.training_data = {}  # {symbol: DataFrame}
        self.running = False
        
        # Configuration
        self.symbols = self._get_symbols()
        self.prediction_interval = int(os.getenv('AI_PREDICTION_INTERVAL', '60'))  # seconds
        self.training_data_window = int(os.getenv('AI_TRAINING_WINDOW_HOURS', '24')) * 3600
        self.max_training_samples = int(os.getenv('AI_MAX_TRAINING_SAMPLES', '10000'))
        self.model_save_dir = os.getenv('AI_MODEL_SAVE_DIR', 'models/ai')
        
        # Initialize ensembles
        for symbol in self.symbols:
            self.ensembles[symbol] = ModelEnsemble(symbol)
            self.training_data[symbol] = pd.DataFrame()
        
        # Create model save directory
        os.makedirs(self.model_save_dir, exist_ok=True)
    
    def _get_symbols(self) -> List[str]:
        """Get symbols from environment"""
        symbols_env = os.getenv('AI_SYMBOLS', 'BTCUSDT,ETHUSDT,SOLUSDT')
        return [s.strip() for s in symbols_env.split(',')]
    
    async def start(self):
        """Start AI model manager"""
        # Connect to Redis
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        self.redis_client = redis.from_url(redis_url)
        
        self.running = True
        logger.info(f"Starting AI model manager for {len(self.symbols)} symbols")
        
        # Load existing models
        await self.load_models()
        
        # Start tasks
        tasks = [
            asyncio.create_task(self.feature_consumer()),
            asyncio.create_task(self.prediction_loop()),
            asyncio.create_task(self.training_loop()),
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def load_models(self):
        """Load existing models from disk"""
        for symbol in self.symbols:
            for model_type in self.ensembles[symbol].models:
                model_file = os.path.join(self.model_save_dir, f"{symbol}_{model_type}.joblib")
                if os.path.exists(model_file):
                    success = self.ensembles[symbol].models[model_type].load_model(model_file)
                    if success:
                        logger.info(f"Loaded {model_type} model for {symbol}")
    
    async def feature_consumer(self):
        """Consume features from Redis streams for training"""
        logger.info("Starting feature consumer for model training")
        
        consumer_group = os.getenv('AI_CONSUMER_GROUP', 'ai_models')
        consumer_name = os.getenv('AI_CONSUMER_NAME', f'ai_model_{os.getpid()}')
        
        while self.running:
            try:
                # Discover feature streams
                feature_streams = {}
                async for key in self.redis_client.scan_iter(match="features.*"):
                    key_str = key.decode()
                    if any(symbol.lower() in key_str for symbol in self.symbols):
                        feature_streams[key_str] = '>'
                
                if not feature_streams:
                    await asyncio.sleep(5)
                    continue
                
                # Create consumer groups
                for stream_key in feature_streams.keys():
                    try:
                        await self.redis_client.xgroup_create(
                            stream_key, consumer_group, '$', mkstream=True
                        )
                    except redis.RedisError:
                        pass
                
                # Read from streams
                stream_list = [(k, '>') for k in feature_streams.keys()]
                messages = await self.redis_client.xreadgroup(
                    consumer_group,
                    consumer_name,
                    streams=dict(stream_list),
                    count=100,
                    block=1000
                )
                
                for stream, msgs in messages:
                    stream_str = stream.decode()
                    
                    for msg_id, fields in msgs:
                        try:
                            await self.process_feature_message(stream_str, fields)
                            
                            # Acknowledge message
                            await self.redis_client.xack(stream, consumer_group, msg_id)
                            
                        except Exception as e:
                            logger.error(f"Feature processing error: {e}")
                
            except Exception as e:
                logger.error(f"Feature consumer error: {e}")
                await asyncio.sleep(5)
    
    async def process_feature_message(self, stream: str, fields: Dict[bytes, bytes]):
        """Process feature message and add to training data"""
        try:
            # Parse feature data
            data = {k.decode(): v.decode() for k, v in fields.items()}
            
            # Convert string values to float
            for key, value in data.items():
                if key not in ['symbol', 'timestamp']:
                    try:
                        data[key] = float(value) if value != '' else np.nan
                    except (ValueError, TypeError):
                        data[key] = np.nan
            
            symbol = data.get('symbol', '').upper()
            if symbol not in self.symbols:
                return
            
            # Add to training data
            if symbol in self.training_data:
                new_row = pd.DataFrame([data])
                self.training_data[symbol] = pd.concat([self.training_data[symbol], new_row], ignore_index=True)
                
                # Limit training data size
                if len(self.training_data[symbol]) > self.max_training_samples:
                    self.training_data[symbol] = self.training_data[symbol].tail(self.max_training_samples)
                
        except Exception as e:
            logger.error(f"Feature message processing error: {e}")
    
    async def prediction_loop(self):
        """Generate predictions periodically"""
        logger.info("Starting prediction loop")
        
        while self.running:
            try:
                start_time = time.time()
                
                # Generate predictions for all symbols
                for symbol in self.symbols:
                    await self.generate_prediction(symbol)
                
                # Calculate sleep time to maintain P95 < 150ms target
                elapsed = time.time() - start_time
                sleep_time = max(0, self.prediction_interval - elapsed)
                
                if elapsed > 0.15:  # 150ms
                    logger.warning(f"Prediction cycle exceeded 150ms target: {elapsed:.3f}s")
                
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                    
            except Exception as e:
                logger.error(f"Prediction loop error: {e}")
                await asyncio.sleep(30)
    
    async def generate_prediction(self, symbol: str):
        """Generate prediction for a symbol"""
        try:
            start_time = time.time()
            
            ensemble = self.ensembles[symbol]
            
            # Get latest features
            if symbol in self.training_data and not self.training_data[symbol].empty:
                latest_features = self.training_data[symbol].tail(1)
                
                # Prepare feature array (exclude timestamp and symbol)
                feature_cols = [col for col in latest_features.columns if col not in ['timestamp', 'symbol']]
                X = latest_features[feature_cols].fillna(0).values
                
                if X.size > 0:
                    # Make prediction
                    prediction = ensemble.predict(X)
                    
                    if prediction:
                        # Record metrics
                        prediction_latency = time.time() - start_time
                        PREDICTION_LATENCY.labels(model_type='ensemble').observe(prediction_latency)
                        PREDICTIONS_MADE.labels(model_type='ensemble', symbol=symbol).inc()
                        
                        # Publish prediction
                        await self.publish_prediction(prediction)
                        
                        logger.debug(f"Generated prediction for {symbol}: score={prediction.calibrated_score:.3f}, latency={prediction_latency:.3f}s")
                    
        except Exception as e:
            logger.error(f"Prediction generation error for {symbol}: {e}")
    
    async def publish_prediction(self, prediction: ModelPrediction):
        """Publish prediction to Redis stream"""
        try:
            stream_key = f"predictions.{prediction.symbol.lower()}"
            prediction_data = prediction.to_dict()
            
            await self.redis_client.xadd(
                stream_key,
                prediction_data,
                maxlen=int(os.getenv('PREDICTIONS_STREAM_MAXLEN', '1000')),
                approximate=True
            )
            
            # Also publish to general predictions stream
            await self.redis_client.xadd(
                "predictions.all",
                prediction_data,
                maxlen=1000,
                approximate=True
            )
            
        except Exception as e:
            logger.error(f"Prediction publishing error: {e}")
    
    async def training_loop(self):
        """Periodic model training"""
        logger.info("Starting training loop")
        
        while self.running:
            try:
                await asyncio.sleep(3600)  # Check every hour
                
                for symbol in self.symbols:
                    await self.train_models(symbol)
                    
            except Exception as e:
                logger.error(f"Training loop error: {e}")
    
    async def train_models(self, symbol: str):
        """Train models for a symbol"""
        try:
            if symbol not in self.training_data or self.training_data[symbol].empty:
                return
            
            ensemble = self.ensembles[symbol]
            
            # Check if retraining is needed
            current_time = time.time()
            needs_training = False
            
            for model in ensemble.models.values():
                if (not model.is_trained or 
                    current_time - model.last_training_time > model.retrain_interval):
                    needs_training = True
                    break
            
            if not needs_training:
                return
            
            logger.info(f"Starting model training for {symbol}")
            
            # Prepare training data
            data = self.training_data[symbol].copy()
            
            # Extract features and targets
            X, y = ensemble.models[list(ensemble.models.keys())[0]].extract_features_and_target(data)
            
            if len(X) < 100:  # Need minimum data
                logger.warning(f"Insufficient data for training {symbol}: {len(X)} samples")
                return
            
            # Train all models in ensemble
            results = ensemble.train_all(X, y)
            
            # Save trained models
            for model_type, success in results.items():
                if success:
                    model_file = os.path.join(self.model_save_dir, f"{symbol}_{model_type}.joblib")
                    ensemble.models[model_type].save_model(model_file)
                    logger.info(f"Saved {model_type} model for {symbol}")
            
        except Exception as e:
            logger.error(f"Model training error for {symbol}: {e}")
    
    async def stop(self):
        """Stop AI model manager"""
        self.running = False
        
        if self.redis_client:
            await self.redis_client.close()
        
        logger.info("Stopped AI model manager")
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get model manager health status"""
        status = {
            'running': self.running,
            'symbols': self.symbols,
            'ensembles': {}
        }
        
        for symbol, ensemble in self.ensembles.items():
            ensemble_status = {
                'models': {},
                'training_samples': len(self.training_data.get(symbol, pd.DataFrame()))
            }
            
            for model_type, model in ensemble.models.items():
                ensemble_status['models'][model_type] = {
                    'trained': model.is_trained,
                    'last_training': model.last_training_time,
                    'metrics': asdict(model.metrics) if model.metrics else None
                }
            
            status['ensembles'][symbol] = ensemble_status
        
        return status


async def main():
    """Main entry point"""
    logger.info("Starting AI Model Manager")
    
    manager = AIModelManager()
    
    try:
        await manager.start()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        await manager.stop()


if __name__ == "__main__":
    asyncio.run(main())