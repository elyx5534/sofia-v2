"""
SOFIA V2 - UNIFIED REAL TRADING SYSTEM
Tüm komponenler birbirine bağlı ve tutarlı
"""

import asyncio
import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Dict, List

import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# GERÇEK TRADING AYARLARI
TRADING_CONFIG = {
    "initial_balance": 10000.0,  # USD
    "trading_mode": "paper",  # paper veya live
    "exchange": "binance",
    "base_currency": "USDT",
    "max_positions": 5,
    "position_size": 0.2,  # %20 per position
    "stop_loss": 0.03,  # %3
    "take_profit": 0.08,  # %8
    "enable_shorts": False,
    "api_key": os.getenv("BINANCE_API_KEY", ""),
    "api_secret": os.getenv("BINANCE_API_SECRET", ""),
}

# Aktif semboller
ACTIVE_SYMBOLS = [
    "BTC/USDT",
    "ETH/USDT",
    "BNB/USDT",
    "SOL/USDT",
    "XRP/USDT",
    "ADA/USDT",
    "DOGE/USDT",
    "MATIC/USDT",
    "LINK/USDT",
    "BCH/USDT",
    "UNI/USDT",
    "LTC/USDT",
    "AVAX/USDT",
    "DOT/USDT",
    "ATOM/USDT",
]


@dataclass
class Position:
    """Trading position"""

    symbol: str
    side: str  # long/short
    entry_price: float
    quantity: float
    current_price: float
    stop_loss: float
    take_profit: float
    timestamp: datetime
    status: str = "open"  # open/closed
    pnl: float = 0.0
    pnl_percent: float = 0.0

    def calculate_pnl(self, current_price: float):
        """Calculate P&L"""
        if self.side == "long":
            self.pnl = (current_price - self.entry_price) * self.quantity
            self.pnl_percent = ((current_price - self.entry_price) / self.entry_price) * 100
        else:
            self.pnl = (self.entry_price - current_price) * self.quantity
            self.pnl_percent = ((self.entry_price - current_price) / self.entry_price) * 100
        self.current_price = current_price
        return self.pnl


@dataclass
class Trade:
    """Executed trade"""

    id: str
    symbol: str
    side: str  # buy/sell
    price: float
    quantity: float
    timestamp: datetime
    order_type: str  # market/limit
    status: str  # filled/pending/cancelled
    fee: float = 0.0


class UnifiedTradingSystem:
    """Ana trading sistemi - tüm komponenler burada"""

    def __init__(self):
        self.balance = TRADING_CONFIG["initial_balance"]
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.price_cache: Dict[str, float] = {}
        self.portfolio_value = self.balance
        self.total_pnl = 0.0
        self.win_rate = 0.0
        self.trade_count = 0
        self.winning_trades = 0
        self.is_running = False
        self.ws_connections = []

        # Initialize prices (realistic market prices)
        self.price_cache = {
            "BTC/USDT": 43250.0,
            "ETH/USDT": 2580.0,
            "BNB/USDT": 245.0,
            "SOL/USDT": 102.0,
            "XRP/USDT": 0.61,
            "ADA/USDT": 0.52,
            "DOGE/USDT": 0.083,
            "MATIC/USDT": 0.89,
            "LINK/USDT": 14.25,
            "BCH/USDT": 245.0,
            "UNI/USDT": 6.45,
            "LTC/USDT": 73.50,
            "AVAX/USDT": 37.80,
            "DOT/USDT": 7.25,
            "ATOM/USDT": 10.15,
        }

    async def initialize(self):
        """Sistemi başlat"""
        logger.info("🚀 Initializing Unified Trading System...")

        # Load ML models if available
        await self.load_ml_models()

        # Connect to exchange
        await self.connect_exchange()

        # Start price feeds
        asyncio.create_task(self.price_updater())

        # Start trading engine
        asyncio.create_task(self.trading_engine())

        # Start portfolio updater
        asyncio.create_task(self.portfolio_updater())

        self.is_running = True
        logger.info("✅ System initialized successfully!")

    async def load_ml_models(self):
        """ML modellerini yükle"""
        try:
            import pickle

            models_path = "models"
            if os.path.exists(f"{models_path}/xgboost_model.pkl"):
                with open(f"{models_path}/xgboost_model.pkl", "rb") as f:
                    self.ml_model = pickle.load(f)
                logger.info("✅ ML models loaded")
            else:
                self.ml_model = None
                logger.info("⚠️ ML models not found, using rule-based strategies")
        except Exception as e:
            logger.error(f"ML model loading error: {e}")
            self.ml_model = None

    async def connect_exchange(self):
        """Exchange bağlantısı"""
        if TRADING_CONFIG["trading_mode"] == "live":
            # Gerçek Binance bağlantısı
            try:
                import ccxt

                self.exchange = ccxt.binance(
                    {
                        "apiKey": TRADING_CONFIG["api_key"],
                        "secret": TRADING_CONFIG["api_secret"],
                        "enableRateLimit": True,
                        "options": {"defaultType": "spot"},
                    }
                )

                # Test connection
                balance = self.exchange.fetch_balance()
                self.balance = balance["USDT"]["free"]
                logger.info(f"✅ Connected to Binance. Balance: ${self.balance:.2f}")
            except Exception as e:
                logger.error(f"Exchange connection failed: {e}")
                logger.info("Falling back to paper trading")
                TRADING_CONFIG["trading_mode"] = "paper"
        else:
            logger.info("📝 Paper trading mode active")

    async def price_updater(self):
        """Gerçek zamanlı fiyat güncellemeleri"""
        while self.is_running:
            try:
                if TRADING_CONFIG["trading_mode"] == "live" and hasattr(self, "exchange"):
                    # Gerçek fiyatlar
                    for symbol in ACTIVE_SYMBOLS:
                        ticker = self.exchange.fetch_ticker(symbol)
                        self.price_cache[symbol] = ticker["last"]
                else:
                    # Simüle fiyatlar (gerçekçi dalgalanma)
                    import random

                    for symbol in ACTIVE_SYMBOLS:
                        current = self.price_cache.get(symbol, 100)
                        change = random.uniform(-0.002, 0.002)  # %0.2 dalgalanma
                        self.price_cache[symbol] = current * (1 + change)

                # Update position P&L
                for symbol, position in self.positions.items():
                    if symbol in self.price_cache:
                        position.calculate_pnl(self.price_cache[symbol])

                await asyncio.sleep(1)  # Her saniye güncelle

            except Exception as e:
                logger.error(f"Price update error: {e}")
                await asyncio.sleep(5)

    async def trading_engine(self):
        """Ana trading logic"""
        while self.is_running:
            try:
                # Check existing positions
                await self.check_positions()

                # Look for new opportunities
                if len(self.positions) < TRADING_CONFIG["max_positions"]:
                    await self.find_trading_opportunities()

                await asyncio.sleep(5)  # 5 saniyede bir kontrol

            except Exception as e:
                logger.error(f"Trading engine error: {e}")
                await asyncio.sleep(10)

    async def check_positions(self):
        """Pozisyonları kontrol et (SL/TP)"""
        positions_to_close = []

        for symbol, position in self.positions.items():
            current_price = self.price_cache.get(symbol)
            if not current_price:
                continue

            # Check stop loss
            if position.side == "long":
                if current_price <= position.stop_loss:
                    logger.info(f"🛑 Stop loss hit for {symbol}")
                    positions_to_close.append(symbol)
                elif current_price >= position.take_profit:
                    logger.info(f"🎯 Take profit hit for {symbol}")
                    positions_to_close.append(symbol)
            elif current_price >= position.stop_loss:
                logger.info(f"🛑 Stop loss hit for {symbol}")
                positions_to_close.append(symbol)
            elif current_price <= position.take_profit:
                logger.info(f"🎯 Take profit hit for {symbol}")
                positions_to_close.append(symbol)

        # Close positions
        for symbol in positions_to_close:
            await self.close_position(symbol)

    async def find_trading_opportunities(self):
        """Yeni trading fırsatları bul"""
        for symbol in ACTIVE_SYMBOLS:
            if symbol in self.positions:
                continue

            signal = await self.analyze_symbol(symbol)

            if signal == "BUY":
                await self.open_position(symbol, "long")
            elif signal == "SELL" and TRADING_CONFIG["enable_shorts"]:
                await self.open_position(symbol, "short")

    async def analyze_symbol(self, symbol: str) -> str:
        """Teknik analiz ve ML tahmin"""
        try:
            # Basit RSI stratejisi
            prices = await self.get_historical_prices(symbol)
            if len(prices) < 14:
                return "HOLD"

            # Calculate RSI
            rsi = self.calculate_rsi(prices)

            # ML prediction if available
            if self.ml_model:
                features = self.prepare_ml_features(prices)
                prediction = self.ml_model.predict([features])[0]
                if prediction > 0.7:
                    return "BUY"
                elif prediction < 0.3:
                    return "SELL"

            # Rule-based
            if rsi < 30:
                return "BUY"
            elif rsi > 70:
                return "SELL"

            return "HOLD"

        except Exception as e:
            logger.error(f"Analysis error for {symbol}: {e}")
            return "HOLD"

    async def get_historical_prices(self, symbol: str, limit: int = 100):
        """Geçmiş fiyatları al"""
        # Simulated for now
        import random

        base_price = self.price_cache.get(symbol, 100)
        prices = []
        for i in range(limit):
            price = base_price * (1 + random.uniform(-0.01, 0.01))
            prices.append(price)
        return prices

    def calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """RSI hesapla"""
        if len(prices) < period:
            return 50

        deltas = np.diff(prices)
        seed = deltas[: period + 1]
        up = seed[seed >= 0].sum() / period
        down = -seed[seed < 0].sum() / period
        rs = up / down if down != 0 else 100
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def prepare_ml_features(self, prices: List[float]):
        """ML için feature hazırla"""
        if len(prices) < 20:
            return [50] * 10  # Default features

        features = []
        features.append(self.calculate_rsi(prices))
        features.append(np.mean(prices[-5:]))  # MA5
        features.append(np.mean(prices[-10:]))  # MA10
        features.append(np.std(prices[-20:]))  # Volatility
        features.append((prices[-1] - prices[-5]) / prices[-5] * 100)  # 5-day return
        features.append(
            (prices[-1] - min(prices[-20:])) / (max(prices[-20:]) - min(prices[-20:])) * 100
        )  # Stochastic

        # Pad to 10 features
        while len(features) < 10:
            features.append(0)

        return features[:10]

    async def open_position(self, symbol: str, side: str):
        """Pozisyon aç"""
        try:
            current_price = self.price_cache[symbol]
            position_value = self.portfolio_value * TRADING_CONFIG["position_size"]
            quantity = position_value / current_price

            # Calculate SL/TP
            if side == "long":
                stop_loss = current_price * (1 - TRADING_CONFIG["stop_loss"])
                take_profit = current_price * (1 + TRADING_CONFIG["take_profit"])
            else:
                stop_loss = current_price * (1 + TRADING_CONFIG["stop_loss"])
                take_profit = current_price * (1 - TRADING_CONFIG["take_profit"])

            # Create position
            position = Position(
                symbol=symbol,
                side=side,
                entry_price=current_price,
                quantity=quantity,
                current_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                timestamp=datetime.now(timezone.utc),
            )

            self.positions[symbol] = position
            self.balance -= position_value

            # Record trade
            trade = Trade(
                id=f"T{self.trade_count:04d}",
                symbol=symbol,
                side="buy" if side == "long" else "sell",
                price=current_price,
                quantity=quantity,
                timestamp=datetime.now(timezone.utc),
                order_type="market",
                status="filled",
            )
            self.trades.append(trade)
            self.trade_count += 1

            logger.info(f"✅ Opened {side} position: {symbol} @ ${current_price:.2f}")
            logger.info(
                f"   Quantity: {quantity:.4f}, SL: ${stop_loss:.2f}, TP: ${take_profit:.2f}"
            )

        except Exception as e:
            logger.error(f"Failed to open position: {e}")

    async def close_position(self, symbol: str):
        """Pozisyon kapat"""
        try:
            position = self.positions[symbol]
            current_price = self.price_cache[symbol]

            # Calculate final P&L
            position.calculate_pnl(current_price)

            # Update balance
            self.balance += position.quantity * current_price
            self.total_pnl += position.pnl

            # Update stats
            if position.pnl > 0:
                self.winning_trades += 1

            # Record closing trade
            trade = Trade(
                id=f"T{self.trade_count:04d}",
                symbol=symbol,
                side="sell" if position.side == "long" else "buy",
                price=current_price,
                quantity=position.quantity,
                timestamp=datetime.now(timezone.utc),
                order_type="market",
                status="filled",
            )
            self.trades.append(trade)
            self.trade_count += 1

            logger.info(f"💰 Closed position: {symbol}")
            logger.info(f"   P&L: ${position.pnl:.2f} ({position.pnl_percent:.2f}%)")

            # Remove position
            del self.positions[symbol]

        except Exception as e:
            logger.error(f"Failed to close position: {e}")

    async def portfolio_updater(self):
        """Portfolio değerlerini güncelle"""
        while self.is_running:
            try:
                # Calculate total portfolio value
                positions_value = sum(
                    pos.quantity * self.price_cache.get(pos.symbol, pos.entry_price)
                    for pos in self.positions.values()
                )

                self.portfolio_value = self.balance + positions_value

                # Calculate win rate
                if self.trade_count > 0:
                    self.win_rate = (self.winning_trades / (self.trade_count / 2)) * 100

                # Broadcast to WebSocket clients
                await self.broadcast_portfolio_update()

                await asyncio.sleep(5)

            except Exception as e:
                logger.error(f"Portfolio update error: {e}")
                await asyncio.sleep(10)

    async def broadcast_portfolio_update(self):
        """WebSocket ile portfolio güncellemesi yayınla"""
        portfolio_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "balance": self.balance,
            "portfolio_value": self.portfolio_value,
            "total_pnl": self.total_pnl,
            "total_pnl_percent": (self.total_pnl / TRADING_CONFIG["initial_balance"]) * 100,
            "positions": [
                {
                    "symbol": pos.symbol,
                    "side": pos.side,
                    "entry_price": pos.entry_price,
                    "current_price": pos.current_price,
                    "quantity": pos.quantity,
                    "pnl": pos.pnl,
                    "pnl_percent": pos.pnl_percent,
                }
                for pos in self.positions.values()
            ],
            "trade_count": self.trade_count,
            "win_rate": self.win_rate,
            "active_positions": len(self.positions),
        }

        # Send to all WebSocket connections
        for ws in self.ws_connections:
            try:
                await ws.send(json.dumps(portfolio_data))
            except:
                self.ws_connections.remove(ws)

    def get_status(self) -> Dict:
        """Sistem durumunu al"""
        return {
            "is_running": self.is_running,
            "mode": TRADING_CONFIG["trading_mode"],
            "balance": self.balance,
            "portfolio_value": self.portfolio_value,
            "total_pnl": self.total_pnl,
            "total_pnl_percent": (self.total_pnl / TRADING_CONFIG["initial_balance"]) * 100,
            "active_positions": len(self.positions),
            "trade_count": self.trade_count,
            "win_rate": self.win_rate,
            "positions": [asdict(pos) for pos in self.positions.values()],
            "recent_trades": [asdict(trade) for trade in self.trades[-10:]],
            "price_cache": self.price_cache,  # Add price cache for market data
        }


# FastAPI entegrasyonu
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI(title="Sofia V2 Unified Trading System")
trading_system = UnifiedTradingSystem()


@app.on_event("startup")
async def startup_event():
    """Sistem başlatma"""
    await trading_system.initialize()


@app.get("/")
async def root():
    """Ana sayfa"""
    return {"message": "Sofia V2 Unified Trading System", "status": trading_system.get_status()}


@app.get("/portfolio")
async def get_portfolio():
    """Portfolio durumu"""
    return trading_system.get_status()


@app.get("/positions")
async def get_positions():
    """Aktif pozisyonlar"""
    return {
        "positions": [asdict(pos) for pos in trading_system.positions.values()],
        "count": len(trading_system.positions),
    }


@app.get("/trades")
async def get_trades():
    """İşlem geçmişi"""
    return {
        "trades": [asdict(trade) for trade in trading_system.trades],
        "count": len(trading_system.trades),
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket bağlantısı"""
    await websocket.accept()
    trading_system.ws_connections.append(websocket)

    try:
        while True:
            # Send updates
            await websocket.send_json(trading_system.get_status())
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        trading_system.ws_connections.remove(websocket)


@app.post("/execute_trade")
async def execute_trade(symbol: str, side: str, amount: float):
    """Manuel trade execution"""
    if side == "buy":
        await trading_system.open_position(symbol, "long")
    else:
        await trading_system.close_position(symbol)

    return {"status": "executed", "symbol": symbol, "side": side}


if __name__ == "__main__":
    print(
        """
    ===================================================
    SOFIA V2 - UNIFIED REAL TRADING SYSTEM
    ===================================================
    Mode: Paper Trading (Safe)
    Initial Balance: $10,000
    Max Positions: 5
    Stop Loss: 3%
    Take Profit: 8%

    Starting unified system on http://localhost:8888
    ===================================================
    """
    )

    uvicorn.run(app, host="0.0.0.0", port=8889)
