"""
Trading Status API - Connects trading bot to UI
Provides real-time trading data to the frontend
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional

from src.adapters.web.fastapi_adapter import FastAPI, WebSocket, WebSocketDisconnect
from src.live_trading.trading_bot import BotConfig, TradingBot, TradingMode
from src.paper_trading.paper_engine import PaperTradingEngine


class TradingStatusManager:
    """Manages trading bot status and provides data to UI"""

    def __init__(self):
        self.bot: Optional[TradingBot] = None
        self.paper_engine: Optional[PaperTradingEngine] = None
        self.is_running = False
        self.mode = "paper"
        self.base_currency = "USD"

    def initialize_bot(self, mode: str = "paper"):
        """Initialize trading bot"""
        config = BotConfig(
            mode=TradingMode.PAPER if mode == "paper" else TradingMode.LIVE,
            initial_balance=100000,
            max_positions=5,
            position_size=0.15,
            stop_loss=0.03,
            take_profit=0.08,
            trailing_stop=True,
            trailing_stop_distance=0.02,
        )
        self.bot = TradingBot(config)
        self.mode = mode
        self.is_running = True
        if mode == "paper":
            self.paper_engine = PaperTradingEngine(initial_balance=100000)

    def get_portfolio_status(self) -> Dict:
        """Get current portfolio status"""
        if not self.bot:
            return {
                "total_value": 100000,
                "available_balance": 100000,
                "used_balance": 0,
                "positions": [],
                "pnl": 0,
                "pnl_percentage": 0,
                "currency": "USD",
            }
        if self.mode == "paper" and self.paper_engine:
            summary = self.paper_engine.get_account_summary()
            account = summary["account"]
            positions = summary["positions"]
            total_value = account["balance"]
            for pos in positions:
                total_value += pos.get("unrealized_pnl", 0)
            return {
                "total_value": total_value,
                "available_balance": account["available_balance"],
                "used_balance": account["balance"] - account["available_balance"],
                "positions": self._format_positions(positions),
                "pnl": account.get("total_pnl", 0),
                "pnl_percentage": account.get("total_pnl", 0) / 100000 * 100,
                "currency": "USD",
            }
        else:
            return {
                "total_value": 100000,
                "available_balance": 100000,
                "used_balance": 0,
                "positions": [],
                "pnl": 0,
                "pnl_percentage": 0,
                "currency": "USD",
            }

    def _format_positions(self, positions: List[Dict]) -> List[Dict]:
        """Format positions for UI display"""
        formatted = []
        for pos in positions:
            formatted.append(
                {
                    "symbol": pos["symbol"],
                    "side": pos["side"],
                    "quantity": pos["quantity"],
                    "entry_price": pos["entry_price"],
                    "current_price": pos.get("current_price", pos["entry_price"]),
                    "pnl": pos.get("unrealized_pnl", 0),
                    "pnl_percentage": pos.get("pnl_percentage", 0),
                    "value": pos["quantity"] * pos.get("current_price", pos["entry_price"]),
                }
            )
        return formatted

    def get_market_data(self) -> Dict:
        """Get current market data"""
        return {
            "BTC/USDT": {"price": 95432.5, "change_24h": 2.15, "volume_24h": 28500000000},
            "ETH/USDT": {"price": 3342.75, "change_24h": 3.28, "volume_24h": 15200000000},
            "BNB/USDT": {"price": 690.25, "change_24h": -0.45, "volume_24h": 1850000000},
            "SOL/USDT": {"price": 178.9, "change_24h": 5.12, "volume_24h": 3200000000},
        }

    def get_dashboard_data(self) -> Dict:
        """Get dashboard data for UI"""
        portfolio = self.get_portfolio_status()
        market = self.get_market_data()
        return {
            "portfolio": {
                "total_balance": portfolio["total_value"],
                "available_balance": portfolio["available_balance"],
                "used_balance": portfolio["used_balance"],
                "currency": "USD",
                "pnl": portfolio["pnl"],
                "pnl_percentage": portfolio["pnl_percentage"],
            },
            "positions": portfolio["positions"],
            "market_data": market,
            "trading_status": {
                "is_active": self.is_running,
                "mode": self.mode,
                "last_update": datetime.utcnow().isoformat(),
            },
        }

    async def start_trading(self, mode: str = "paper", strategy: str = "grid"):
        """Start trading bot"""
        if not self.bot:
            self.initialize_bot(mode)
        if self.bot and (not self.is_running):
            asyncio.create_task(self.bot.start())
            self.is_running = True
            return {"status": "started", "mode": mode, "strategy": strategy}
        return {"status": "already_running"}

    async def stop_trading(self):
        """Stop trading bot"""
        if self.bot and self.is_running:
            await self.bot.stop()
            self.is_running = False
            return {"status": "stopped"}
        return {"status": "not_running"}


trading_manager = TradingStatusManager()
app = FastAPI(title="Trading Status API")


@app.get("/status")
async def get_status():
    """Get current trading status"""
    return trading_manager.get_dashboard_data()


@app.get("/portfolio")
async def get_portfolio():
    """Get portfolio details"""
    return trading_manager.get_portfolio_status()


@app.post("/start")
async def start_trading(mode: str = "paper", strategy: str = "grid"):
    """Start trading bot"""
    result = await trading_manager.start_trading(mode, strategy)
    return result


@app.post("/stop")
async def stop_trading():
    """Stop trading bot"""
    result = await trading_manager.stop_trading()
    return result


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time updates"""
    await websocket.accept()
    try:
        while True:
            data = trading_manager.get_dashboard_data()
            await websocket.send_json(data)
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")
        await websocket.close()
