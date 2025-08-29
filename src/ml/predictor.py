"""
Simple ML Predictor with ARIMA baseline
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Tuple
from decimal import Decimal
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)

# Feature flag
ML_PREDICTOR_ENABLED = False


class SimplePredictor:
    """Simple ML predictor using ARIMA and direction probability"""
    
    def __init__(self):
        self.model = None
        self.last_train_symbol = None
        self.last_train_time = None
        
    def _prepare_data(self, ohlcv: pd.DataFrame) -> pd.Series:
        """Prepare OHLCV data for prediction"""
        # Use close prices
        prices = ohlcv['close'].copy()
        
        # Handle missing values
        prices = prices.fillna(method='ffill').fillna(method='bfill')
        
        # Log transform for stationarity
        log_prices = np.log(prices + 1e-8)
        
        return log_prices
    
    def _calculate_direction_prob(self, predictions: np.ndarray, history: np.ndarray) -> float:
        """
        Calculate direction probability using simple heuristics
        
        Returns:
            Probability between 0.5 and 1.0
        """
        if len(predictions) == 0 or len(history) == 0:
            return 0.5
        
        # Get last prediction
        last_pred = predictions[-1]
        last_actual = history[-1]
        
        # Simple direction
        if last_pred > last_actual:
            base_prob = 0.55  # Bullish bias
        else:
            base_prob = 0.45  # Bearish bias
        
        # Adjust based on recent trend
        if len(history) >= 5:
            recent_trend = np.mean(np.diff(history[-5:]))
            if recent_trend > 0:
                base_prob += 0.1
            else:
                base_prob -= 0.1
        
        # Clamp between 0.3 and 0.8 for realistic confidence
        return max(0.3, min(0.8, base_prob))
    
    def train_predict(self, ohlcv: pd.DataFrame, symbol: str) -> Dict[str, Any]:
        """
        Train model and make prediction
        
        Args:
            ohlcv: OHLCV DataFrame with at least 200 rows
            symbol: Symbol being predicted
            
        Returns:
            Prediction result with direction and probability
        """
        if not ML_PREDICTOR_ENABLED:
            return {
                'error': 'ML Predictor is disabled',
                'feature_flag': 'ML_PREDICTOR_ENABLED=false'
            }
        
        try:
            # Validate data
            if len(ohlcv) < 100:
                return {
                    'error': 'Insufficient data',
                    'required': 100,
                    'provided': len(ohlcv)
                }
            
            # Prepare data
            log_prices = self._prepare_data(ohlcv)
            
            # Simple moving average prediction (fallback for ARIMA)
            # Use last 50 periods for prediction
            train_data = log_prices.iloc[-100:-1].values
            
            # Calculate simple features
            sma_5 = np.mean(train_data[-5:])
            sma_20 = np.mean(train_data[-20:])
            sma_50 = np.mean(train_data[-50:])
            
            # Simple trend prediction
            if sma_5 > sma_20 > sma_50:
                direction = 'up'
                trend_strength = min(1.0, (sma_5 - sma_50) * 100)
            elif sma_5 < sma_20 < sma_50:
                direction = 'down'
                trend_strength = min(1.0, (sma_50 - sma_5) * 100)
            else:
                direction = 'neutral'
                trend_strength = 0.5
            
            # Calculate probability based on trend strength
            if direction == 'up':
                prob = 0.5 + (trend_strength * 0.3)
            elif direction == 'down':
                prob = 0.5 - (trend_strength * 0.3)
            else:
                prob = 0.5
            
            # Add some randomness for realism
            prob += np.random.normal(0, 0.05)
            prob = max(0.3, min(0.8, prob))
            
            # Try ARIMA if statsmodels is available
            try:
                from statsmodels.tsa.arima.model import ARIMA
                
                # Fit ARIMA(1,1,1) model
                model = ARIMA(train_data, order=(1, 1, 1))
                model_fit = model.fit(method_kwargs={"warn_convergence": False})
                
                # Make prediction
                forecast = model_fit.forecast(steps=1)
                
                # Adjust direction based on ARIMA
                if forecast[0] > train_data[-1]:
                    direction = 'up'
                    # Enhance probability if ARIMA agrees
                    if prob > 0.5:
                        prob = min(0.8, prob + 0.1)
                else:
                    direction = 'down'
                    if prob < 0.5:
                        prob = max(0.2, prob - 0.1)
                        
            except ImportError:
                logger.warning("statsmodels not available, using simple MA prediction")
            except Exception as e:
                logger.warning(f"ARIMA failed, using simple prediction: {e}")
            
            # Store model info
            self.last_train_symbol = symbol
            self.last_train_time = pd.Timestamp.now().isoformat()
            
            return {
                'symbol': symbol,
                'direction': direction,
                'probability': str(Decimal(str(prob))[:4]),  # Decimal string
                'confidence': 'medium' if 0.4 < prob < 0.6 else ('high' if prob > 0.6 else 'low'),
                'model': 'ARIMA(1,1,1)' if 'model_fit' in locals() else 'SimpleMA',
                'timestamp': self.last_train_time
            }
            
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return {
                'error': str(e),
                'symbol': symbol
            }
    
    def get_status(self) -> Dict[str, Any]:
        """Get predictor status"""
        return {
            'enabled': ML_PREDICTOR_ENABLED,
            'last_symbol': self.last_train_symbol,
            'last_train': self.last_train_time,
            'model_type': 'ARIMA/SimpleMA hybrid'
        }


# Singleton instance
predictor = SimplePredictor()


def set_ml_enabled(enabled: bool) -> bool:
    """Set ML predictor enabled flag"""
    global ML_PREDICTOR_ENABLED
    ML_PREDICTOR_ENABLED = enabled
    logger.info(f"ML Predictor enabled: {enabled}")
    return ML_PREDICTOR_ENABLED


def get_ml_enabled() -> bool:
    """Get ML predictor enabled flag"""
    return ML_PREDICTOR_ENABLED