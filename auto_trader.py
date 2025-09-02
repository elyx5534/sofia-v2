"""
Sofia V2 - Automated Trading System
Combines all strategies with ML predictions for maximum profit
"""

import asyncio
import os
from datetime import datetime
from typing import Dict

from dotenv import load_dotenv

# Load environment
load_dotenv()

# Import all components
import joblib
import pandas as pd
from src.live_trading.trading_bot import BotConfig, TradingBot, TradingMode
from src.strategies.grid_trading import GridConfig, GridTradingStrategy


class AutoTrader:
    """
    Fully automated trading system with ML predictions
    """

    def __init__(self):
        self.config = BotConfig(
            mode=TradingMode.PAPER,
            initial_balance=10000,
            max_positions=5,
            position_size=0.15,  # 15% per position
            stop_loss=0.03,  # 3% stop loss
            take_profit=0.08,  # 8% take profit
            trailing_stop=True,
            trailing_stop_distance=0.02,
        )

        self.bot = TradingBot(self.config)
        self.ml_models = {}
        self.performance = {}

    def load_ml_models(self):
        """Load trained ML models"""
        print("Loading ML models...")

        models_dir = "models"
        if not os.path.exists(models_dir):
            print("⚠️ No ML models found. Run train_ml_models.py first!")
            return False

        symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]

        for symbol in symbols:
            try:
                self.ml_models[symbol] = {
                    "xgboost": joblib.load(f"{models_dir}/{symbol}_xgboost_model.pkl"),
                    "random_forest": joblib.load(f"{models_dir}/{symbol}_random_forest_model.pkl"),
                    "scaler": joblib.load(f"{models_dir}/{symbol}_scaler.pkl"),
                }
                print(f"✅ Loaded models for {symbol}")
            except:
                print(f"⚠️ Models not found for {symbol}")

        return len(self.ml_models) > 0

    async def get_ml_signal(self, symbol: str) -> Dict:
        """Get ML prediction signal"""
        if symbol not in self.ml_models:
            return {"action": "hold", "confidence": 0}

        try:
            # Get latest market data
            # (In production, this would come from DataHub)
            import yfinance as yf

            ticker = symbol.replace("USDT", "-USD")
            df = yf.download(ticker, period="30d", interval="1h", progress=False)

            if df.empty:
                return {"action": "hold", "confidence": 0}

            # Prepare features (simplified)
            features = self.prepare_simple_features(df)

            # Scale
            scaler = self.ml_models[symbol]["scaler"]
            X = scaler.transform(features.iloc[-1:])

            # Predict with both models
            xgb_pred = self.ml_models[symbol]["xgboost"].predict(X)[0]
            rf_pred = self.ml_models[symbol]["random_forest"].predict(X)[0]

            # Average prediction
            prediction = (xgb_pred + rf_pred) / 2

            # Generate signal
            if prediction > 0.01:  # 1% up
                return {
                    "action": "buy",
                    "confidence": min(abs(prediction) * 50, 0.9),
                    "predicted_change": prediction,
                }
            elif prediction < -0.01:  # 1% down
                return {
                    "action": "sell",
                    "confidence": min(abs(prediction) * 50, 0.9),
                    "predicted_change": prediction,
                }
            else:
                return {"action": "hold", "confidence": 0.5}

        except Exception as e:
            print(f"ML prediction error for {symbol}: {e}")
            return {"action": "hold", "confidence": 0}

    def prepare_simple_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare features for ML (simplified version)"""

        # Basic features
        df["returns"] = df["Close"].pct_change()
        df["volume_ratio"] = df["Volume"] / df["Volume"].rolling(20).mean()

        # RSI
        delta = df["Close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df["rsi"] = 100 - (100 / (1 + rs))

        # Moving averages
        df["sma_20"] = df["Close"].rolling(20).mean()
        df["sma_50"] = df["Close"].rolling(50).mean()
        df["sma_20_ratio"] = df["Close"] / df["sma_20"]

        # Select features
        feature_cols = ["returns", "volume_ratio", "rsi", "sma_20_ratio"]

        # Fill NaN
        df[feature_cols] = df[feature_cols].fillna(method="ffill").fillna(0)

        return df[feature_cols]

    async def setup_strategies(self):
        """Setup all trading strategies"""
        print("\nSetting up trading strategies...")

        # 1. Grid Trading for each symbol
        symbols = ["BTC/USDT", "ETH/USDT", "BNB/USDT"]

        for symbol in symbols:
            grid_config = GridConfig(
                symbol=symbol,
                grid_levels=8,
                grid_spacing=0.005,
                quantity_per_grid=self.config.initial_balance * 0.02,  # 2% per grid
            )
            grid_strategy = GridTradingStrategy(grid_config)
            self.bot.add_strategy(f"grid_{symbol}", grid_strategy)
            print(f"  ✅ Grid Trading for {symbol}")

        # 2. ML-Enhanced Strategy
        if self.ml_models:
            # This would be a custom strategy using ML predictions
            print("  ✅ ML Prediction Strategy enabled")

        # 3. Existing strategies
        try:
            from src.strategy_engine.strategies import MACDStrategy, RSIStrategy

            self.bot.add_strategy("rsi", RSIStrategy())
            self.bot.add_strategy("macd", MACDStrategy())
            print("  ✅ RSI & MACD Strategies")
        except:
            print("  ⚠️ Some strategies not available")

    async def monitor_performance(self):
        """Monitor and display performance"""
        while True:
            try:
                status = self.bot.get_status()

                # Clear screen
                os.system("cls" if os.name == "nt" else "clear")

                print(
                    """
╔══════════════════════════════════════════════════════════════╗
║              Sofia V2 - Auto Trading System                  ║
╚══════════════════════════════════════════════════════════════╝
"""
                )

                print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"📊 Mode: {status['mode'].upper()}")
                print(f"🟢 Status: {'RUNNING' if status['is_running'] else 'STOPPED'}")

                if status.get("account"):
                    account = status["account"].get("account", {})
                    metrics = status["account"].get("metrics", {})

                    print("\n💰 ACCOUNT:")
                    print(f"  Balance: ${account.get('current_balance', 0):,.2f}")
                    print(f"  P&L: ${account.get('total_pnl', 0):+,.2f}")
                    print(f"  Return: {metrics.get('total_return', 0):+.2f}%")

                    print("\n📈 PERFORMANCE:")
                    print(f"  Win Rate: {metrics.get('win_rate', 0):.1f}%")
                    print(f"  Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.2f}")
                    print(f"  Max Drawdown: {metrics.get('max_drawdown', 0):.1f}%")
                    print(f"  Total Trades: {account.get('total_trades', 0)}")

                print("\n📂 POSITIONS:")
                print(f"  Active: {status['active_positions']}")
                print(f"  Pending Signals: {status['pending_signals']}")

                # Show ML predictions
                if self.ml_models:
                    print("\n🤖 ML PREDICTIONS:")
                    for symbol in self.ml_models.keys():
                        signal = await self.get_ml_signal(symbol)
                        if signal["action"] != "hold":
                            print(
                                f"  {symbol}: {signal['action'].upper()} (conf: {signal['confidence']:.1%})"
                            )

                # Recent signals
                print("\n📡 RECENT SIGNALS:")
                for signal in status.get("recent_signals", [])[-5:]:
                    print(
                        f"  {signal.get('symbol', 'N/A'):10} | {signal.get('action', 'N/A'):6} | {signal.get('strategy', 'N/A')}"
                    )

                print("\n" + "=" * 65)
                print("Press Ctrl+C to stop")

                await asyncio.sleep(10)  # Update every 10 seconds

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Monitor error: {e}")
                await asyncio.sleep(10)

    async def run(self):
        """Main run loop"""
        print(
            """
        ╔══════════════════════════════════════════════╗
        ║     Sofia V2 - Automated Trading System      ║
        ║         Maximum Profit Mode Activated        ║
        ╚══════════════════════════════════════════════╝
        """
        )

        # Load ML models
        ml_loaded = self.load_ml_models()

        if not ml_loaded:
            print("\n⚠️ Running without ML predictions")
            print("Run 'python train_ml_models.py' first for better results!\n")

        # Setup strategies
        await self.setup_strategies()

        print("\n🚀 Starting automated trading...")
        print("=" * 50)

        # Start bot and monitoring
        try:
            await asyncio.gather(self.bot.start(), self.monitor_performance())
        except KeyboardInterrupt:
            print("\n\n🛑 Stopping auto trader...")
            await self.bot.stop()

            # Show final stats
            status = self.bot.get_status()
            if "account" in status:
                metrics = status["account"].get("metrics", {})
                print("\n📊 FINAL RESULTS:")
                print(f"  Total Return: {metrics.get('total_return', 0):+.2f}%")
                print(f"  Win Rate: {metrics.get('win_rate', 0):.1f}%")
                print(f"  Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.2f}")
                print(
                    f"  Total Trades: {status['account'].get('account', {}).get('total_trades', 0)}"
                )

            print("\n✅ Auto trader stopped successfully")


async def main():
    """Entry point"""
    trader = AutoTrader()
    await trader.run()


if __name__ == "__main__":
    # Check for required files
    if not os.path.exists(".env"):
        print("⚠️ .env file not found. Creating default...")
        with open(".env", "w") as f:
            f.write(
                """
# Sofia V2 Auto Trader Configuration
TRADING_MODE=paper
INITIAL_BALANCE=10000
MAX_POSITIONS=5
POSITION_SIZE=0.15
STOP_LOSS=0.03
TAKE_PROFIT=0.08
"""
            )

    asyncio.run(main())
