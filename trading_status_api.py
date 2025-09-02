"""
Trading Status API - Unified data source for UI
Provides consistent trading data to frontend
"""

import asyncio
import random
from datetime import datetime
from typing import Dict, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Trading Status API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TradingDataManager:
    """Manages unified trading data"""

    def __init__(self):
        # Initialize with realistic starting values in USD
        self.base_balance = 100000.00  # $100k USD
        self.positions = []
        self.pnl = 0
        self.is_trading = False
        self.mode = "paper"

    def get_portfolio_status(self) -> Dict:
        """Get current portfolio status in USD"""
        # Simulate some trading activity
        if self.is_trading and random.random() > 0.7:
            # Add small PnL changes
            self.pnl += random.uniform(-100, 200)

        total_value = self.base_balance + self.pnl
        positions_value = sum(p["value"] for p in self.positions)
        available = total_value - positions_value

        return {
            "total_balance": round(total_value, 2),
            "available_balance": round(available, 2),
            "in_positions": round(positions_value, 2),
            "daily_pnl": round(self.pnl, 2),
            "daily_pnl_percentage": round((self.pnl / self.base_balance) * 100, 2),
            "currency": "USD",
        }

    def get_positions(self) -> List[Dict]:
        """Get current positions"""
        if not self.positions and self.is_trading:
            # Create some demo positions
            self.positions = [
                {
                    "symbol": "BTC/USDT",
                    "side": "long",
                    "quantity": 0.5,
                    "entry_price": 94850.00,
                    "current_price": 95432.50,
                    "value": 47716.25,
                    "pnl": 291.25,
                    "pnl_percentage": 0.61,
                },
                {
                    "symbol": "ETH/USDT",
                    "side": "long",
                    "quantity": 10,
                    "entry_price": 3285.00,
                    "current_price": 3342.75,
                    "value": 33427.50,
                    "pnl": 577.50,
                    "pnl_percentage": 1.76,
                },
            ]

        # Update current prices slightly
        for pos in self.positions:
            pos["current_price"] *= random.uniform(0.998, 1.002)
            pos["value"] = pos["quantity"] * pos["current_price"]
            pos["pnl"] = (pos["current_price"] - pos["entry_price"]) * pos["quantity"]
            pos["pnl_percentage"] = (
                (pos["current_price"] - pos["entry_price"]) / pos["entry_price"]
            ) * 100

        return self.positions

    def get_market_data(self) -> Dict:
        """Get current market data"""
        base_prices = {
            "BTC/USDT": 95432.50,
            "ETH/USDT": 3342.75,
            "BNB/USDT": 690.25,
            "SOL/USDT": 178.90,
        }

        market_data = {}
        for symbol, base_price in base_prices.items():
            # Add small variations
            price = base_price * random.uniform(0.995, 1.005)
            change = random.uniform(-3, 5)

            market_data[symbol] = {
                "price": round(price, 2),
                "change_24h": round(change, 2),
                "volume_24h": random.randint(1000000000, 30000000000),
            }

        return market_data

    def start_trading(self, mode: str = "paper"):
        """Start trading simulation"""
        self.is_trading = True
        self.mode = mode
        return {"status": "started", "mode": mode}

    def stop_trading(self):
        """Stop trading simulation"""
        self.is_trading = False
        self.positions = []
        return {"status": "stopped"}


# Global manager instance
manager = TradingDataManager()


@app.get("/status")
async def get_status():
    """Get unified trading status"""
    portfolio = manager.get_portfolio_status()
    positions = manager.get_positions()
    market_data = manager.get_market_data()

    return {
        "portfolio": portfolio,
        "positions": positions,
        "market_data": market_data,
        "trading_status": {
            "is_active": manager.is_trading,
            "mode": manager.mode,
            "last_update": datetime.utcnow().isoformat(),
        },
    }


@app.get("/portfolio")
async def get_portfolio():
    """Get portfolio details"""
    return manager.get_portfolio_status()


@app.get("/positions")
async def get_positions():
    """Get current positions"""
    return {"positions": manager.get_positions()}


@app.post("/start")
async def start_trading(mode: str = "paper"):
    """Start trading"""
    return manager.start_trading(mode)


@app.post("/stop")
async def stop_trading():
    """Stop trading"""
    return manager.stop_trading()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time updates"""
    await websocket.accept()

    try:
        while True:
            # Send updates every 2 seconds
            status = await get_status()
            await websocket.send_json(status)
            await asyncio.sleep(2)

    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")
        await websocket.close()


@app.get("/")
async def root():
    """API info"""
    return {
        "name": "Trading Status API",
        "version": "1.0.0",
        "endpoints": [
            "/status - Get complete trading status",
            "/portfolio - Get portfolio details",
            "/positions - Get current positions",
            "/start - Start trading (POST)",
            "/stop - Stop trading (POST)",
            "/ws - WebSocket for real-time updates",
        ],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8003)
