#!/usr/bin/env python3
"""
Machine Learning Optimizer for Trading Strategies
Tracks performance, predicts movements, and optimizes parameters
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import xgboost as xgb
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from scipy.optimize import differential_evolution
from skopt import gp_minimize
from skopt.space import Real, Integer
import joblib
import json
from collections import deque
import schedule
import time

logger = logging.getLogger(__name__)

@dataclass
class StrategyMetrics:
    """Performance metrics for a strategy"""
    strategy_name: str
    timestamp: datetime
    total_trades: int
    win_rate: float
    profit_factor: float
    sharpe_ratio: float
    max_drawdown: float
    avg_profit: float
    avg_loss: float
    total_pnl: float
    market_condition: str
    volatility: float
    trend_strength: float
    volume: float
    parameters: Dict[str, Any]

@dataclass
class MarketCondition:
    """Market condition labels"""
    timestamp: datetime
    condition: str  # "trending_up", "trending_down", "ranging", "volatile"
    volatility: float
    volume: float
    trend_strength: float
    dominant_session: str  # "asian", "european", "us"
    major_news: bool
    risk_level: str  # "low", "medium", "high"

@dataclass
class PredictionResult:
    """ML prediction result"""
    model_type: str
    prediction: Any
    confidence: float
    features_importance: Dict[str, float]
    timestamp: datetime

@dataclass
class OptimizationResult:
    """Optimization result"""
    strategy: str
    old_params: Dict[str, Any]
    new_params: Dict[str, Any]
    expected_improvement: float
    optimization_method: str
    timestamp: datetime

class PerformanceTracker:
    """Track and analyze strategy performance"""
    
    def __init__(self):
        self.metrics_history: List[StrategyMetrics] = []
        self.market_conditions: List[MarketCondition] = []
        self.pattern_cache: Dict[str, List[Dict]] = {}
        self.session_patterns = {
            "asian": {"start": 0, "end": 8},
            "european": {"start": 8, "end": 16},
            "us": {"start": 14, "end": 22}
        }
    
    def record_metrics(self, strategy: str, metrics: Dict[str, Any]):
        """Record strategy performance metrics"""
        market_condition = self._label_market_condition(metrics)
        
        strategy_metrics = StrategyMetrics(
            strategy_name=strategy,
            timestamp=datetime.now(),
            total_trades=metrics.get("total_trades", 0),
            win_rate=metrics.get("win_rate", 0),
            profit_factor=metrics.get("profit_factor", 0),
            sharpe_ratio=metrics.get("sharpe_ratio", 0),
            max_drawdown=metrics.get("max_drawdown", 0),
            avg_profit=metrics.get("avg_profit", 0),
            avg_loss=metrics.get("avg_loss", 0),
            total_pnl=metrics.get("total_pnl", 0),
            market_condition=market_condition.condition,
            volatility=market_condition.volatility,
            trend_strength=market_condition.trend_strength,
            volume=market_condition.volume,
            parameters=metrics.get("parameters", {})
        )
        
        self.metrics_history.append(strategy_metrics)
        self.market_conditions.append(market_condition)
        
        # Update pattern cache
        self._update_patterns(strategy, strategy_metrics)
    
    def _label_market_condition(self, metrics: Dict) -> MarketCondition:
        """Label current market condition"""
        volatility = metrics.get("volatility", 0)
        volume = metrics.get("volume", 0)
        trend_strength = metrics.get("trend_strength", 0)
        
        # Determine condition
        if trend_strength > 0.7:
            condition = "trending_up" if metrics.get("direction", 1) > 0 else "trending_down"
        elif volatility > 0.02:
            condition = "volatile"
        else:
            condition = "ranging"
        
        # Determine session
        hour = datetime.now().hour
        if 0 <= hour < 8:
            session = "asian"
        elif 8 <= hour < 16:
            session = "european"
        else:
            session = "us"
        
        # Risk level
        if volatility > 0.03 or trend_strength > 0.8:
            risk = "high"
        elif volatility > 0.015 or trend_strength > 0.5:
            risk = "medium"
        else:
            risk = "low"
        
        return MarketCondition(
            timestamp=datetime.now(),
            condition=condition,
            volatility=volatility,
            volume=volume,
            trend_strength=trend_strength,
            dominant_session=session,
            major_news=metrics.get("major_news", False),
            risk_level=risk
        )
    
    def _update_patterns(self, strategy: str, metrics: StrategyMetrics):
        """Update time-based patterns"""
        if strategy not in self.pattern_cache:
            self.pattern_cache[strategy] = []
        
        pattern = {
            "hour": metrics.timestamp.hour,
            "day_of_week": metrics.timestamp.weekday(),
            "win_rate": metrics.win_rate,
            "profit_factor": metrics.profit_factor,
            "market_condition": metrics.market_condition
        }
        
        self.pattern_cache[strategy].append(pattern)
        
        # Keep only last 1000 patterns
        if len(self.pattern_cache[strategy]) > 1000:
            self.pattern_cache[strategy] = self.pattern_cache[strategy][-1000:]
    
    def get_best_conditions(self, strategy: str) -> Dict[str, Any]:
        """Get best performing conditions for a strategy"""
        strategy_metrics = [m for m in self.metrics_history if m.strategy_name == strategy]
        
        if not strategy_metrics:
            return {}
        
        # Group by market condition
        conditions_performance = {}
        for metric in strategy_metrics:
            condition = metric.market_condition
            if condition not in conditions_performance:
                conditions_performance[condition] = []
            conditions_performance[condition].append(metric.profit_factor)
        
        # Calculate average performance
        best_conditions = {}
        for condition, performances in conditions_performance.items():
            best_conditions[condition] = {
                "avg_profit_factor": np.mean(performances),
                "win_rate": len([p for p in performances if p > 1]) / len(performances),
                "sample_size": len(performances)
            }
        
        return best_conditions
    
    def get_time_patterns(self, strategy: str) -> Dict[str, Any]:
        """Get time-based performance patterns"""
        if strategy not in self.pattern_cache:
            return {}
        
        patterns = self.pattern_cache[strategy]
        df = pd.DataFrame(patterns)
        
        # Hour patterns
        hour_performance = df.groupby('hour').agg({
            'win_rate': 'mean',
            'profit_factor': 'mean'
        }).to_dict()
        
        # Day of week patterns
        dow_performance = df.groupby('day_of_week').agg({
            'win_rate': 'mean',
            'profit_factor': 'mean'
        }).to_dict()
        
        return {
            "hourly": hour_performance,
            "daily": dow_performance,
            "best_hours": df.nlargest(3, 'profit_factor')['hour'].tolist(),
            "worst_hours": df.nsmallest(3, 'profit_factor')['hour'].tolist()
        }

class PredictionEngine:
    """ML models for market prediction"""
    
    def __init__(self):
        self.xgb_price_model = None
        self.lstm_volatility_model = None
        self.rf_signal_model = None
        self.scaler = StandardScaler()
        self.sequence_length = 60
        self.models_trained = False
    
    def prepare_features(self, data: pd.DataFrame) -> np.ndarray:
        """Prepare features for ML models"""
        features = []
        
        # Price features
        features.append(data['close'].pct_change().fillna(0))
        features.append(data['volume'])
        
        # Technical indicators
        features.append(data['close'].rolling(20).mean())
        features.append(data['close'].rolling(20).std())
        features.append((data['close'] - data['close'].rolling(20).mean()) / data['close'].rolling(20).std())
        
        # RSI
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        features.append(100 - (100 / (1 + rs)))
        
        # MACD
        exp1 = data['close'].ewm(span=12, adjust=False).mean()
        exp2 = data['close'].ewm(span=26, adjust=False).mean()
        features.append(exp1 - exp2)
        
        # Volume indicators
        features.append(data['volume'].rolling(20).mean())
        features.append(data['volume'] / data['volume'].rolling(20).mean())
        
        # Combine features
        feature_matrix = np.column_stack(features).astype(np.float32)
        
        # Handle NaN and inf
        feature_matrix = np.nan_to_num(feature_matrix, nan=0, posinf=1, neginf=-1)
        
        return feature_matrix
    
    def train_xgboost_price(self, data: pd.DataFrame):
        """Train XGBoost for price movement prediction"""
        logger.info("Training XGBoost price prediction model...")
        
        # Prepare features
        X = self.prepare_features(data)
        
        # Create target (next hour price movement)
        y = (data['close'].shift(-1) > data['close']).astype(int)
        
        # Remove last row (no target)
        X = X[:-1]
        y = y[:-1]
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # Scale features
        X_train = self.scaler.fit_transform(X_train)
        X_test = self.scaler.transform(X_test)
        
        # Train model
        self.xgb_price_model = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.01,
            objective='binary:logistic',
            use_label_encoder=False
        )
        
        self.xgb_price_model.fit(X_train, y_train)
        
        # Evaluate
        accuracy = self.xgb_price_model.score(X_test, y_test)
        logger.info(f"XGBoost accuracy: {accuracy:.2f}")
    
    def train_lstm_volatility(self, data: pd.DataFrame):
        """Train LSTM for volatility prediction"""
        logger.info("Training LSTM volatility prediction model...")
        
        # Calculate volatility
        data['returns'] = data['close'].pct_change()
        data['volatility'] = data['returns'].rolling(20).std()
        
        # Prepare sequences
        X, y = [], []
        values = data['volatility'].values
        
        for i in range(self.sequence_length, len(values) - 1):
            X.append(values[i-self.sequence_length:i])
            y.append(values[i])
        
        X = np.array(X).reshape(-1, self.sequence_length, 1)
        y = np.array(y)
        
        # Split data
        split = int(0.8 * len(X))
        X_train, X_test = X[:split], X[split:]
        y_train, y_test = y[:split], y[split:]
        
        # Build LSTM model
        self.lstm_volatility_model = Sequential([
            LSTM(50, return_sequences=True, input_shape=(self.sequence_length, 1)),
            Dropout(0.2),
            LSTM(50, return_sequences=False),
            Dropout(0.2),
            Dense(25),
            Dense(1)
        ])
        
        self.lstm_volatility_model.compile(
            optimizer='adam',
            loss='mean_squared_error'
        )
        
        # Train model
        self.lstm_volatility_model.fit(
            X_train, y_train,
            batch_size=32,
            epochs=10,
            validation_data=(X_test, y_test),
            verbose=0
        )
        
        # Evaluate
        loss = self.lstm_volatility_model.evaluate(X_test, y_test, verbose=0)
        logger.info(f"LSTM volatility loss: {loss:.4f}")
    
    def train_random_forest_signals(self, data: pd.DataFrame, signals: pd.Series):
        """Train Random Forest for signal generation"""
        logger.info("Training Random Forest signal model...")
        
        # Prepare features
        X = self.prepare_features(data)
        y = signals.values
        
        # Ensure same length
        min_len = min(len(X), len(y))
        X = X[:min_len]
        y = y[:min_len]
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # Train model
        self.rf_signal_model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42
        )
        
        self.rf_signal_model.fit(X_train, y_train)
        
        # Evaluate
        accuracy = self.rf_signal_model.score(X_test, y_test)
        logger.info(f"Random Forest signal accuracy: {accuracy:.2f}")
    
    def predict_price_movement(self, current_features: np.ndarray) -> PredictionResult:
        """Predict next price movement"""
        if self.xgb_price_model is None:
            return None
        
        # Scale features
        features_scaled = self.scaler.transform(current_features.reshape(1, -1))
        
        # Predict
        prediction = self.xgb_price_model.predict(features_scaled)[0]
        probability = self.xgb_price_model.predict_proba(features_scaled)[0]
        
        # Get feature importance
        importance = self.xgb_price_model.feature_importances_
        feature_names = [f"feature_{i}" for i in range(len(importance))]
        importance_dict = dict(zip(feature_names, importance))
        
        return PredictionResult(
            model_type="xgboost_price",
            prediction="up" if prediction == 1 else "down",
            confidence=max(probability),
            features_importance=importance_dict,
            timestamp=datetime.now()
        )
    
    def predict_volatility(self, recent_volatility: np.ndarray) -> PredictionResult:
        """Predict future volatility"""
        if self.lstm_volatility_model is None:
            return None
        
        # Reshape for LSTM
        input_data = recent_volatility.reshape(1, self.sequence_length, 1)
        
        # Predict
        prediction = self.lstm_volatility_model.predict(input_data, verbose=0)[0][0]
        
        return PredictionResult(
            model_type="lstm_volatility",
            prediction=float(prediction),
            confidence=0.0,  # LSTM doesn't provide confidence
            features_importance={},
            timestamp=datetime.now()
        )
    
    def predict_signal(self, current_features: np.ndarray) -> PredictionResult:
        """Predict trading signal"""
        if self.rf_signal_model is None:
            return None
        
        # Predict
        prediction = self.rf_signal_model.predict(current_features.reshape(1, -1))[0]
        probability = self.rf_signal_model.predict_proba(current_features.reshape(1, -1))[0]
        
        # Get feature importance
        importance = self.rf_signal_model.feature_importances_
        feature_names = [f"feature_{i}" for i in range(len(importance))]
        importance_dict = dict(zip(feature_names, importance))
        
        return PredictionResult(
            model_type="random_forest_signal",
            prediction=prediction,
            confidence=max(probability),
            features_importance=importance_dict,
            timestamp=datetime.now()
        )

class OptimizationEngine:
    """Optimization algorithms for strategy parameters"""
    
    def __init__(self):
        self.optimization_history: List[OptimizationResult] = []
        self.best_params: Dict[str, Dict] = {}
        self.performance_cache: Dict[str, List[float]] = {}
    
    def genetic_algorithm_optimize(
        self,
        strategy: str,
        param_bounds: Dict[str, Tuple[float, float]],
        fitness_function,
        population_size: int = 50,
        generations: int = 100
    ) -> OptimizationResult:
        """Optimize parameters using genetic algorithm"""
        logger.info(f"Running genetic algorithm optimization for {strategy}")
        
        # Convert bounds to list format for differential_evolution
        bounds = list(param_bounds.values())
        param_names = list(param_bounds.keys())
        
        # Define objective function
        def objective(params):
            param_dict = dict(zip(param_names, params))
            return -fitness_function(param_dict)  # Negative for minimization
        
        # Run optimization
        result = differential_evolution(
            objective,
            bounds,
            popsize=population_size,
            maxiter=generations,
            workers=-1,
            disp=False
        )
        
        # Extract optimized parameters
        optimized_params = dict(zip(param_names, result.x))
        
        # Create result
        optimization_result = OptimizationResult(
            strategy=strategy,
            old_params=self.best_params.get(strategy, {}),
            new_params=optimized_params,
            expected_improvement=-result.fun,  # Convert back to positive
            optimization_method="genetic_algorithm",
            timestamp=datetime.now()
        )
        
        # Update best params
        self.best_params[strategy] = optimized_params
        self.optimization_history.append(optimization_result)
        
        return optimization_result
    
    def bayesian_optimize(
        self,
        strategy: str,
        param_space: List,
        objective_function,
        n_calls: int = 50
    ) -> OptimizationResult:
        """Optimize using Bayesian optimization"""
        logger.info(f"Running Bayesian optimization for {strategy}")
        
        # Run optimization
        result = gp_minimize(
            func=lambda params: -objective_function(dict(zip([p.name for p in param_space], params))),
            dimensions=param_space,
            n_calls=n_calls,
            n_initial_points=10,
            acq_func='EI'
        )
        
        # Extract optimized parameters
        param_names = [p.name for p in param_space]
        optimized_params = dict(zip(param_names, result.x))
        
        # Create result
        optimization_result = OptimizationResult(
            strategy=strategy,
            old_params=self.best_params.get(strategy, {}),
            new_params=optimized_params,
            expected_improvement=-result.fun,
            optimization_method="bayesian",
            timestamp=datetime.now()
        )
        
        # Update best params
        self.best_params[strategy] = optimized_params
        self.optimization_history.append(optimization_result)
        
        return optimization_result
    
    def reinforcement_learning_allocate(
        self,
        strategies: List[str],
        performance_history: Dict[str, List[float]],
        total_capital: float
    ) -> Dict[str, float]:
        """Use RL to optimize capital allocation"""
        logger.info("Running RL-based allocation optimization")
        
        # Simple epsilon-greedy approach
        epsilon = 0.1
        
        if np.random.random() < epsilon:
            # Exploration: random allocation
            allocations = np.random.dirichlet(np.ones(len(strategies)))
        else:
            # Exploitation: allocate based on performance
            scores = []
            for strategy in strategies:
                if strategy in performance_history:
                    # Calculate score based on recent performance
                    recent_perf = performance_history[strategy][-20:]
                    score = np.mean(recent_perf) * (1 / (np.std(recent_perf) + 0.001))
                else:
                    score = 0
                scores.append(max(score, 0))
            
            # Normalize scores to allocations
            total_score = sum(scores)
            if total_score > 0:
                allocations = [s / total_score for s in scores]
            else:
                allocations = [1 / len(strategies)] * len(strategies)
        
        # Create allocation dictionary
        allocation_dict = {}
        for strategy, allocation in zip(strategies, allocations):
            allocation_dict[strategy] = allocation * total_capital
        
        return allocation_dict
    
    def optimize_thresholds(
        self,
        strategy: str,
        threshold_ranges: Dict[str, Tuple[float, float]],
        performance_function
    ) -> Dict[str, float]:
        """Optimize strategy thresholds"""
        logger.info(f"Optimizing thresholds for {strategy}")
        
        best_thresholds = {}
        best_performance = -float('inf')
        
        # Grid search with refinement
        for threshold_name, (min_val, max_val) in threshold_ranges.items():
            test_values = np.linspace(min_val, max_val, 20)
            
            for value in test_values:
                test_thresholds = best_thresholds.copy()
                test_thresholds[threshold_name] = value
                
                performance = performance_function(test_thresholds)
                
                if performance > best_performance:
                    best_performance = performance
                    best_thresholds[threshold_name] = value
        
        return best_thresholds

class MLOptimizer:
    """Main ML Optimizer that coordinates everything"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tracker = PerformanceTracker()
        self.predictor = PredictionEngine()
        self.optimizer = OptimizationEngine()
        
        self.strategies = config.get("strategies", [])
        self.optimization_interval = config.get("optimization_interval", 3600)
        self.min_data_points = config.get("min_data_points", 100)
        
        self.running = False
        self.last_optimization = {}
        self.daily_schedule_enabled = config.get("daily_schedule", True)
    
    async def initialize(self):
        """Initialize the ML optimizer"""
        logger.info("Initializing ML Optimizer...")
        
        # Load historical data if available
        await self._load_historical_data()
        
        # Setup daily schedule if enabled
        if self.daily_schedule_enabled:
            self._setup_daily_schedule()
        
        self.running = True
        logger.info("ML Optimizer initialized")
    
    async def _load_historical_data(self):
        """Load historical performance data"""
        try:
            # Load from database or file
            # Mock implementation
            logger.info("Loading historical data...")
            await asyncio.sleep(0.5)
            logger.info("Historical data loaded")
        except Exception as e:
            logger.error(f"Error loading historical data: {e}")
    
    def _setup_daily_schedule(self):
        """Setup daily optimization schedule"""
        # 00:00 - Analyze yesterday
        schedule.every().day.at("00:00").do(self.analyze_yesterday)
        
        # 06:00 - Optimize parameters
        schedule.every().day.at("06:00").do(self.optimize_all_parameters)
        
        # 12:00 - Rebalance allocation
        schedule.every().day.at("12:00").do(self.rebalance_allocation)
        
        # 18:00 - Prepare for US session
        schedule.every().day.at("18:00").do(self.prepare_us_session)
        
        logger.info("Daily schedule configured")
    
    def analyze_yesterday(self):
        """Analyze yesterday's performance"""
        asyncio.create_task(self._analyze_yesterday())
    
    async def _analyze_yesterday(self):
        """Async analyze yesterday's performance"""
        logger.info("Analyzing yesterday's performance...")
        
        # Get yesterday's metrics
        yesterday = datetime.now() - timedelta(days=1)
        yesterday_metrics = [
            m for m in self.tracker.metrics_history
            if m.timestamp.date() == yesterday.date()
        ]
        
        # Analyze by strategy
        for strategy in self.strategies:
            strategy_metrics = [m for m in yesterday_metrics if m.strategy_name == strategy]
            
            if strategy_metrics:
                avg_win_rate = np.mean([m.win_rate for m in strategy_metrics])
                avg_profit_factor = np.mean([m.profit_factor for m in strategy_metrics])
                total_pnl = sum([m.total_pnl for m in strategy_metrics])
                
                logger.info(f"{strategy} yesterday: WR={avg_win_rate:.2f}, PF={avg_profit_factor:.2f}, PnL={total_pnl:.2f}")
                
                # Update performance cache
                if strategy not in self.optimizer.performance_cache:
                    self.optimizer.performance_cache[strategy] = []
                self.optimizer.performance_cache[strategy].append(avg_profit_factor)
    
    def optimize_all_parameters(self):
        """Optimize all strategy parameters"""
        asyncio.create_task(self._optimize_all_parameters())
    
    async def _optimize_all_parameters(self):
        """Async optimize all parameters"""
        logger.info("Optimizing all strategy parameters...")
        
        for strategy in self.strategies:
            # Get strategy performance
            best_conditions = self.tracker.get_best_conditions(strategy)
            time_patterns = self.tracker.get_time_patterns(strategy)
            
            # Define parameter bounds based on strategy
            param_bounds = self._get_param_bounds(strategy)
            
            # Define fitness function
            def fitness_function(params):
                # Simulate strategy with params
                # Mock implementation
                return np.random.random() * 2
            
            # Run optimization
            result = self.optimizer.genetic_algorithm_optimize(
                strategy,
                param_bounds,
                fitness_function,
                population_size=30,
                generations=50
            )
            
            logger.info(f"Optimized {strategy}: improvement={result.expected_improvement:.2f}")
            
            # Apply new parameters
            await self._apply_parameters(strategy, result.new_params)
    
    def rebalance_allocation(self):
        """Rebalance capital allocation"""
        asyncio.create_task(self._rebalance_allocation())
    
    async def _rebalance_allocation(self):
        """Async rebalance allocation"""
        logger.info("Rebalancing capital allocation...")
        
        # Get total capital
        total_capital = 100000  # Mock value
        
        # Get performance history
        performance_history = self.optimizer.performance_cache
        
        # Calculate new allocation
        new_allocation = self.optimizer.reinforcement_learning_allocate(
            self.strategies,
            performance_history,
            total_capital
        )
        
        logger.info(f"New allocation: {new_allocation}")
        
        # Apply allocation
        await self._apply_allocation(new_allocation)
    
    def prepare_us_session(self):
        """Prepare for US trading session"""
        asyncio.create_task(self._prepare_us_session())
    
    async def _prepare_us_session(self):
        """Async prepare for US session"""
        logger.info("Preparing for US trading session...")
        
        # Adjust parameters for US volatility
        us_adjustments = {
            "volatility_multiplier": 1.2,
            "position_size_reduction": 0.8,
            "stop_loss_tightening": 0.9
        }
        
        for strategy in self.strategies:
            await self._apply_session_adjustments(strategy, us_adjustments)
        
        logger.info("US session preparation complete")
    
    def _get_param_bounds(self, strategy: str) -> Dict[str, Tuple[float, float]]:
        """Get parameter bounds for a strategy"""
        # Default bounds (customize per strategy)
        return {
            "stop_loss": (0.005, 0.02),
            "take_profit": (0.01, 0.05),
            "position_size": (0.01, 0.1),
            "entry_threshold": (0.6, 0.9),
            "exit_threshold": (0.4, 0.7)
        }
    
    async def _apply_parameters(self, strategy: str, params: Dict[str, Any]):
        """Apply optimized parameters to strategy"""
        logger.info(f"Applying parameters to {strategy}: {params}")
        # Implementation would update actual strategy parameters
        await asyncio.sleep(0.1)
    
    async def _apply_allocation(self, allocation: Dict[str, float]):
        """Apply capital allocation"""
        logger.info(f"Applying allocation: {allocation}")
        # Implementation would update actual allocations
        await asyncio.sleep(0.1)
    
    async def _apply_session_adjustments(self, strategy: str, adjustments: Dict[str, float]):
        """Apply session-specific adjustments"""
        logger.info(f"Applying session adjustments to {strategy}: {adjustments}")
        # Implementation would update strategy settings
        await asyncio.sleep(0.1)
    
    async def train_models(self, market_data: pd.DataFrame, signals: pd.Series = None):
        """Train all ML models"""
        logger.info("Training ML models...")
        
        # Train price prediction
        self.predictor.train_xgboost_price(market_data)
        
        # Train volatility prediction
        self.predictor.train_lstm_volatility(market_data)
        
        # Train signal model if signals provided
        if signals is not None:
            self.predictor.train_random_forest_signals(market_data, signals)
        
        self.predictor.models_trained = True
        logger.info("ML models trained successfully")
    
    async def get_predictions(self, current_data: pd.DataFrame) -> Dict[str, PredictionResult]:
        """Get all predictions"""
        if not self.predictor.models_trained:
            logger.warning("Models not trained yet")
            return {}
        
        # Prepare current features
        features = self.predictor.prepare_features(current_data)
        
        predictions = {}
        
        # Price movement prediction
        price_pred = self.predictor.predict_price_movement(features[-1])
        if price_pred:
            predictions["price_movement"] = price_pred
        
        # Volatility prediction
        if len(current_data) >= self.predictor.sequence_length:
            recent_vol = current_data['close'].pct_change().rolling(20).std().values[-self.predictor.sequence_length:]
            vol_pred = self.predictor.predict_volatility(recent_vol)
            if vol_pred:
                predictions["volatility"] = vol_pred
        
        # Signal prediction
        signal_pred = self.predictor.predict_signal(features[-1])
        if signal_pred:
            predictions["signal"] = signal_pred
        
        return predictions
    
    async def auto_adjust(self):
        """Auto-adjust based on performance"""
        logger.info("Running auto-adjustment...")
        
        for strategy in self.strategies:
            # Get recent performance
            recent_metrics = [
                m for m in self.tracker.metrics_history
                if m.strategy_name == strategy and
                (datetime.now() - m.timestamp).total_seconds() < 3600
            ]
            
            if not recent_metrics:
                continue
            
            # Calculate performance score
            avg_win_rate = np.mean([m.win_rate for m in recent_metrics])
            avg_profit_factor = np.mean([m.profit_factor for m in recent_metrics])
            
            # Adjust based on performance
            if avg_profit_factor < 1.0:
                # Poor performance - reduce risk
                adjustments = {
                    "position_size": 0.5,
                    "stop_loss": 0.8,
                    "max_positions": 0.7
                }
                await self._apply_session_adjustments(strategy, adjustments)
                logger.info(f"Reduced risk for {strategy} due to poor performance")
            
            elif avg_profit_factor > 1.5 and avg_win_rate > 0.6:
                # Good performance - increase position size slightly
                adjustments = {
                    "position_size": 1.2,
                    "max_positions": 1.1
                }
                await self._apply_session_adjustments(strategy, adjustments)
                logger.info(f"Increased position size for {strategy} due to good performance")
    
    async def run_scheduler(self):
        """Run the schedule checker"""
        while self.running:
            schedule.run_pending()
            await asyncio.sleep(60)  # Check every minute
    
    def get_optimization_report(self) -> Dict[str, Any]:
        """Get optimization report"""
        return {
            "total_optimizations": len(self.optimizer.optimization_history),
            "best_parameters": self.optimizer.best_params,
            "recent_optimizations": [
                {
                    "strategy": opt.strategy,
                    "improvement": opt.expected_improvement,
                    "method": opt.optimization_method,
                    "timestamp": opt.timestamp.isoformat()
                }
                for opt in self.optimizer.optimization_history[-10:]
            ],
            "performance_summary": {
                strategy: {
                    "avg_performance": np.mean(perf) if perf else 0,
                    "trend": "improving" if len(perf) > 1 and perf[-1] > perf[-2] else "declining"
                }
                for strategy, perf in self.optimizer.performance_cache.items()
            }
        }
    
    async def shutdown(self):
        """Shutdown the optimizer"""
        logger.info("Shutting down ML Optimizer...")
        self.running = False
        
        # Save models
        if self.predictor.xgb_price_model:
            joblib.dump(self.predictor.xgb_price_model, "models/xgb_price.pkl")
        if self.predictor.lstm_volatility_model:
            self.predictor.lstm_volatility_model.save("models/lstm_volatility.h5")
        if self.predictor.rf_signal_model:
            joblib.dump(self.predictor.rf_signal_model, "models/rf_signal.pkl")
        
        logger.info("ML Optimizer shutdown complete")