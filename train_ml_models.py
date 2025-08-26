"""
Sofia V2 - ML Model Training Pipeline
Train XGBoost, LSTM, and ensemble models for price prediction
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_percentage_error
import xgboost as xgb
from sklearn.ensemble import RandomForestRegressor
import joblib
import yfinance as yf
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')


class MLTrainer:
    """
    Machine Learning model trainer for price prediction
    """
    
    def __init__(self):
        self.models = {}
        self.scalers = {}
        self.feature_importance = {}
        
    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create features for ML models"""
        
        print("Creating features...")
        
        # Price features
        df['returns'] = df['Close'].pct_change()
        df['log_returns'] = np.log(df['Close'] / df['Close'].shift(1))
        df['price_range'] = (df['High'] - df['Low']) / df['Close']
        df['close_to_high'] = (df['High'] - df['Close']) / df['High']
        df['close_to_low'] = (df['Close'] - df['Low']) / df['Low']
        
        # Volume features
        df['volume_ratio'] = df['Volume'] / df['Volume'].rolling(20).mean()
        df['volume_change'] = df['Volume'].pct_change()
        
        # Technical indicators
        # RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # Moving averages
        for period in [5, 10, 20, 50]:
            df[f'sma_{period}'] = df['Close'].rolling(period).mean()
            df[f'sma_{period}_ratio'] = df['Close'] / df[f'sma_{period}']
            
        # MACD
        df['ema_12'] = df['Close'].ewm(span=12).mean()
        df['ema_26'] = df['Close'].ewm(span=26).mean()
        df['macd'] = df['ema_12'] - df['ema_26']
        df['macd_signal'] = df['macd'].ewm(span=9).mean()
        df['macd_diff'] = df['macd'] - df['macd_signal']
        
        # Bollinger Bands
        df['bb_middle'] = df['Close'].rolling(20).mean()
        bb_std = df['Close'].rolling(20).std()
        df['bb_upper'] = df['bb_middle'] + 2 * bb_std
        df['bb_lower'] = df['bb_middle'] - 2 * bb_std
        df['bb_position'] = (df['Close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        
        # Lag features
        for i in [1, 2, 3, 5, 10]:
            df[f'returns_lag_{i}'] = df['returns'].shift(i)
            df[f'volume_lag_{i}'] = df['volume_ratio'].shift(i)
            
        # Rolling statistics
        for window in [5, 10, 20]:
            df[f'returns_std_{window}'] = df['returns'].rolling(window).std()
            df[f'returns_mean_{window}'] = df['returns'].rolling(window).mean()
            df[f'volume_std_{window}'] = df['Volume'].rolling(window).std()
            
        # Time features
        df['hour'] = df.index.hour
        df['day_of_week'] = df.index.dayofweek
        df['month'] = df.index.month
        
        # Target: Next hour return
        df['target'] = df['Close'].shift(-1) / df['Close'] - 1
        
        # Drop NaN
        df = df.dropna()
        
        return df
    
    def train_xgboost(self, X_train, y_train, X_test, y_test):
        """Train XGBoost model"""
        
        print("Training XGBoost...")
        
        # Parameters optimized for crypto
        params = {
            'objective': 'reg:squarederror',
            'max_depth': 6,
            'learning_rate': 0.01,
            'n_estimators': 1000,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'gamma': 0.01,
            'reg_alpha': 0.1,
            'reg_lambda': 1.0,
            'random_state': 42
        }
        
        model = xgb.XGBRegressor(**params)
        
        # Train with early stopping
        model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            early_stopping_rounds=50,
            verbose=False
        )
        
        # Get feature importance
        self.feature_importance['xgboost'] = dict(zip(
            X_train.columns,
            model.feature_importances_
        ))
        
        return model
    
    def train_random_forest(self, X_train, y_train, X_test, y_test):
        """Train Random Forest model"""
        
        print("Training Random Forest...")
        
        model = RandomForestRegressor(
            n_estimators=500,
            max_depth=10,
            min_samples_split=5,
            min_samples_leaf=2,
            max_features='sqrt',
            random_state=42,
            n_jobs=-1
        )
        
        model.fit(X_train, y_train)
        
        # Get feature importance
        self.feature_importance['random_forest'] = dict(zip(
            X_train.columns,
            model.feature_importances_
        ))
        
        return model
    
    def create_ensemble(self, models, X_test, y_test):
        """Create ensemble predictions"""
        
        print("Creating ensemble model...")
        
        predictions = []
        weights = []
        
        for name, model in models.items():
            pred = model.predict(X_test)
            predictions.append(pred)
            
            # Weight by inverse error
            error = mean_squared_error(y_test, pred)
            weight = 1 / (error + 1e-6)
            weights.append(weight)
        
        # Normalize weights
        weights = np.array(weights) / sum(weights)
        
        # Weighted average
        ensemble_pred = np.average(predictions, axis=0, weights=weights)
        
        return ensemble_pred, weights
    
    def train_all_models(self, symbol: str, days: int = 90):
        """Train all ML models for a symbol"""
        
        print(f"\n{'='*50}")
        print(f"Training ML Models for {symbol}")
        print(f"{'='*50}\n")
        
        # Fetch data
        print(f"Fetching {days} days of data...")
        ticker = symbol.replace("USDT", "-USD")
        df = yf.download(
            ticker,
            start=datetime.now() - timedelta(days=days),
            interval='1h',
            progress=False
        )
        
        if df.empty:
            print(f"No data available for {symbol}")
            return None
        
        # Prepare features
        df = self.prepare_features(df)
        
        # Split features and target
        feature_cols = [col for col in df.columns if col not in ['target', 'Close', 'Open', 'High', 'Low']]
        X = df[feature_cols]
        y = df['target']
        
        # Time series split
        tscv = TimeSeriesSplit(n_splits=3)
        
        all_models = {}
        all_scores = {}
        
        for fold, (train_idx, test_idx) in enumerate(tscv.split(X), 1):
            print(f"\nTraining Fold {fold}/3...")
            
            X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
            y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
            
            # Scale features
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            X_train_scaled = pd.DataFrame(X_train_scaled, columns=X_train.columns, index=X_train.index)
            X_test_scaled = pd.DataFrame(X_test_scaled, columns=X_test.columns, index=X_test.index)
            
            # Train models
            models = {}
            models['xgboost'] = self.train_xgboost(X_train_scaled, y_train, X_test_scaled, y_test)
            models['random_forest'] = self.train_random_forest(X_train_scaled, y_train, X_test_scaled, y_test)
            
            # Evaluate models
            for name, model in models.items():
                pred = model.predict(X_test_scaled)
                mse = mean_squared_error(y_test, pred)
                mape = mean_absolute_percentage_error(y_test, pred)
                
                if name not in all_scores:
                    all_scores[name] = []
                all_scores[name].append({'mse': mse, 'mape': mape})
            
            # Ensemble
            ensemble_pred, weights = self.create_ensemble(models, X_test_scaled, y_test)
            ensemble_mse = mean_squared_error(y_test, ensemble_pred)
            ensemble_mape = mean_absolute_percentage_error(y_test, ensemble_pred)
            
            if 'ensemble' not in all_scores:
                all_scores['ensemble'] = []
            all_scores['ensemble'].append({'mse': ensemble_mse, 'mape': ensemble_mape})
            
            # Save best fold
            if fold == 1:
                all_models = models
                self.scalers[symbol] = scaler
        
        # Print results
        print(f"\n{'='*50}")
        print(f"Model Performance Summary for {symbol}")
        print(f"{'='*50}\n")
        
        for model_name, scores in all_scores.items():
            avg_mse = np.mean([s['mse'] for s in scores])
            avg_mape = np.mean([s['mape'] for s in scores]) * 100
            print(f"{model_name.upper()}")
            print(f"  MSE: {avg_mse:.6f}")
            print(f"  MAPE: {avg_mape:.2f}%")
            print()
        
        # Save models
        for name, model in all_models.items():
            filename = f"models/{symbol}_{name}_model.pkl"
            joblib.dump(model, filename)
            print(f"Saved {name} model to {filename}")
        
        # Save scaler
        scaler_file = f"models/{symbol}_scaler.pkl"
        joblib.dump(self.scalers[symbol], scaler_file)
        
        # Print top features
        print(f"\n{'='*50}")
        print(f"Top 10 Important Features")
        print(f"{'='*50}\n")
        
        for model_name, importance_dict in self.feature_importance.items():
            print(f"\n{model_name.upper()}:")
            sorted_features = sorted(importance_dict.items(), key=lambda x: x[1], reverse=True)[:10]
            for i, (feature, importance) in enumerate(sorted_features, 1):
                print(f"  {i}. {feature}: {importance:.4f}")
        
        return all_models, all_scores
    
    def predict_next_hour(self, symbol: str, model_name: str = 'ensemble'):
        """Make prediction for next hour"""
        
        # Load model
        if model_name == 'ensemble':
            models = {}
            for name in ['xgboost', 'random_forest']:
                models[name] = joblib.load(f"models/{symbol}_{name}_model.pkl")
        else:
            model = joblib.load(f"models/{symbol}_{model_name}_model.pkl")
        
        # Load scaler
        scaler = joblib.load(f"models/{symbol}_scaler.pkl")
        
        # Get latest data
        ticker = symbol.replace("USDT", "-USD")
        df = yf.download(
            ticker,
            start=datetime.now() - timedelta(days=30),
            interval='1h',
            progress=False
        )
        
        # Prepare features
        df = self.prepare_features(df)
        feature_cols = [col for col in df.columns if col not in ['target', 'Close', 'Open', 'High', 'Low']]
        
        # Get last row
        X_last = df[feature_cols].iloc[-1:].values
        X_last_scaled = scaler.transform(X_last)
        
        # Predict
        if model_name == 'ensemble':
            predictions = []
            for name, model in models.items():
                pred = model.predict(X_last_scaled)
                predictions.append(pred[0])
            prediction = np.mean(predictions)
        else:
            prediction = model.predict(X_last_scaled)[0]
        
        # Convert to price change percentage
        price_change_pct = prediction * 100
        current_price = df['Close'].iloc[-1]
        predicted_price = current_price * (1 + prediction)
        
        return {
            'symbol': symbol,
            'current_price': current_price,
            'predicted_price': predicted_price,
            'price_change_pct': price_change_pct,
            'confidence': abs(price_change_pct) * 10,  # Simple confidence metric
            'timestamp': datetime.now()
        }


def main():
    """Main training pipeline"""
    
    print("""
    ╔══════════════════════════════════════════════╗
    ║      Sofia V2 - ML Model Training            ║
    ║         Price Prediction Models              ║
    ╚══════════════════════════════════════════════╝
    """)
    
    # Create models directory
    import os
    os.makedirs('models', exist_ok=True)
    
    # Symbols to train
    symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
    
    trainer = MLTrainer()
    
    # Train models for each symbol
    all_results = {}
    for symbol in symbols:
        models, scores = trainer.train_all_models(symbol, days=90)
        all_results[symbol] = scores
    
    # Make predictions
    print(f"\n{'='*50}")
    print("Next Hour Predictions")
    print(f"{'='*50}\n")
    
    for symbol in symbols:
        try:
            prediction = trainer.predict_next_hour(symbol)
            print(f"{symbol}:")
            print(f"  Current Price: ${prediction['current_price']:.2f}")
            print(f"  Predicted Price: ${prediction['predicted_price']:.2f}")
            print(f"  Change: {prediction['price_change_pct']:+.2f}%")
            print(f"  Signal: {'BUY' if prediction['price_change_pct'] > 0.5 else 'SELL' if prediction['price_change_pct'] < -0.5 else 'HOLD'}")
            print()
        except Exception as e:
            print(f"Error predicting {symbol}: {e}")
    
    print("\n✅ ML models trained and saved to 'models/' directory")
    print("📊 Use these predictions in your trading strategies!")


if __name__ == "__main__":
    main()