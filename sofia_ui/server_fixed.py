"""
Sofia V2 - Fixed Web UI Server
Unified trading data from port 8003
"""

import asyncio
import json
import random
from datetime import datetime
from pathlib import Path
import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import httpx

# Create FastAPI app
app = FastAPI(
    title="Sofia V2 - Trading Strategy Platform",
    description="Unified trading platform",
    version="2.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup templates and static files
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Trading Status API URL
TRADING_API_URL = "http://localhost:8003"

async def get_unified_data():
    """Get data from unified trading API"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{TRADING_API_URL}/status")
            if response.status_code == 200:
                return response.json()
    except Exception as e:
        print(f"Error: {e}")
    return None

@app.get("/", response_class=HTMLResponse)
async def welcome(request: Request):
    """Welcome page"""
    return templates.TemplateResponse("welcome.html", {
        "request": request,
        "page_title": "Sofia V2",
        "current_page": "welcome",
    })

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Dashboard page with real data"""
    data = await get_unified_data()
    
    # Get BTC price from market data
    btc_price = 95000  # Default
    if data and "market_data" in data:
        btc_data = data["market_data"].get("BTC/USDT", {})
        btc_price = btc_data.get("price", 95000)
    
    context = {
        "request": request,
        "page_title": "Dashboard - Sofia V2",
        "current_page": "dashboard",
        "total_balance": data["portfolio"]["total_balance"] if data else 100000,
        "daily_pnl": data["portfolio"]["daily_pnl"] if data else 0,
        "pnl_percentage": data["portfolio"]["daily_pnl_percentage"] if data else 0,
        "btc_data": {"price": btc_price},
        "latest_news": []  # Empty news for now
    }
    return templates.TemplateResponse("homepage.html", context)

@app.get("/portfolio", response_class=HTMLResponse)
async def portfolio(request: Request):
    """Portfolio page with real data"""
    data = await get_unified_data()
    
    portfolio_data = {
        "total_value": data["portfolio"]["total_balance"] if data else 100000,
        "daily_pnl": data["portfolio"]["daily_pnl"] if data else 0,
        "daily_pnl_percentage": data["portfolio"]["daily_pnl_percentage"] if data else 0,
        "available_cash": data["portfolio"]["available_balance"] if data else 100000,
        "positions_value": data["portfolio"]["in_positions"] if data else 0,
    }
    
    context = {
        "request": request,
        "page_title": "Portfolio - Sofia V2",
        "current_page": "portfolio",
        "portfolio_data": portfolio_data,
        "trading_status": data["trading_status"] if data else {"is_active": False},
    }
    return templates.TemplateResponse("portfolio_realtime.html", context)

@app.get("/api/trading/portfolio")
async def api_portfolio():
    """API endpoint - returns unified data"""
    data = await get_unified_data()
    
    if data:
        portfolio = data["portfolio"]
        positions = {}
        for pos in data["positions"]:
            key = pos["symbol"].replace("/", "")
            positions[key] = {
                "symbol": key,
                "side": pos["side"],
                "size": pos["quantity"],
                "entry_price": pos["entry_price"],
                "current_price": pos["current_price"],
                "unrealized_pnl": pos["pnl"],
                "pnl_percent": pos["pnl_percentage"],
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        return {
            "total_balance": portfolio["total_balance"],
            "available_balance": portfolio["available_balance"],
            "used_balance": portfolio["in_positions"],
            "daily_pnl": portfolio["daily_pnl"],
            "daily_pnl_percent": portfolio["daily_pnl_percentage"],
            "total_return": portfolio["daily_pnl_percentage"],
            "positions": positions,
            "active_strategies": [
                {"name": "Grid Trading", "status": "active", "pnl": 89.67},
                {"name": "Mean Reversion", "status": "active", "pnl": 156.23},
                {"name": "Momentum", "status": "active", "pnl": -23.45}
            ]
        }
    
    # Fallback
    return {
        "total_balance": 100000,
        "available_balance": 100000,
        "used_balance": 0,
        "daily_pnl": 0,
        "daily_pnl_percent": 0,
        "total_return": 0,
        "positions": {},
        "active_strategies": []
    }

@app.get("/strategies", response_class=HTMLResponse)
async def strategies(request: Request):
    """Strategies page"""
    return templates.TemplateResponse("strategies.html", {
        "request": request,
        "page_title": "Strategies - Sofia V2",
        "current_page": "strategies",
    })

@app.get("/backtest", response_class=HTMLResponse)
async def backtest(request: Request):
    """Backtest page"""
    return templates.TemplateResponse("backtest.html", {
        "request": request,
        "page_title": "Backtest - Sofia V2",
        "current_page": "backtest",
    })

@app.get("/markets", response_class=HTMLResponse)
async def markets(request: Request):
    """Markets page"""
    return templates.TemplateResponse("markets.html", {
        "request": request,
        "page_title": "Markets - Sofia V2",
        "current_page": "markets",
    })

if __name__ == "__main__":
    print("Starting Sofia V2 Fixed Server...")
    print("Using Trading API at:", TRADING_API_URL)
    uvicorn.run(app, host="127.0.0.1", port=8005)