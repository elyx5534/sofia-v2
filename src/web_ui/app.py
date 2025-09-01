"""Web UI for Sofia Trading Platform."""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi import Request
import json
import asyncio
from datetime import datetime, timedelta
import random
from typing import List, Dict, Optional
import yfinance as yf
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))
from src.data_hub.news_provider import news_provider

app = FastAPI(
    title="Sofia Trading Platform",
    description="Professional Trading Dashboard",
    version="2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Setup templates
templates_path = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_path))

# WebSocket connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

# Real market data fetcher
async def fetch_real_market_data():
    """Fetch real market data from Yahoo Finance."""
    equity_symbols = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META"]
    crypto_symbols = ["BTC-USD", "ETH-USD"]
    
    market_data = []
    
    try:
        # Fetch equity data
        for symbol in equity_symbols:
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info
                current_price = info.get('currentPrice', info.get('regularMarketPrice', 0))
                prev_close = info.get('previousClose', current_price)
                change = current_price - prev_close
                change_percent = (change / prev_close * 100) if prev_close else 0
                
                market_data.append({
                    "symbol": symbol,
                    "name": info.get('shortName', symbol),
                    "price": round(current_price, 2),
                    "change": round(change, 2),
                    "changePercent": round(change_percent, 2),
                    "volume": info.get('volume', 0),
                    "high": info.get('dayHigh', current_price),
                    "low": info.get('dayLow', current_price),
                    "timestamp": datetime.utcnow().isoformat(),
                })
            except Exception as e:
                print(f"Error fetching {symbol}: {e}")
                # Use simulated data as fallback
                market_data.append(generate_simulated_quote(symbol))
        
        # Fetch crypto data
        for symbol in crypto_symbols:
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info
                current_price = info.get('currentPrice', info.get('regularMarketPrice', 0))
                prev_close = info.get('previousClose', current_price)
                change = current_price - prev_close
                change_percent = (change / prev_close * 100) if prev_close else 0
                
                display_symbol = symbol.replace('-USD', '/USDT')
                market_data.append({
                    "symbol": display_symbol,
                    "name": info.get('shortName', display_symbol),
                    "price": round(current_price, 2),
                    "change": round(change, 2),
                    "changePercent": round(change_percent, 2),
                    "volume": info.get('volume', 0),
                    "high": info.get('dayHigh', current_price),
                    "low": info.get('dayLow', current_price),
                    "timestamp": datetime.utcnow().isoformat(),
                })
            except Exception as e:
                print(f"Error fetching {symbol}: {e}")
                market_data.append(generate_simulated_quote(symbol.replace('-USD', '/USDT')))
                
    except Exception as e:
        print(f"Market data fetch error: {e}")
        # Fallback to simulated data
        return generate_simulated_market_data()
    
    return market_data

def generate_simulated_quote(symbol):
    """Generate simulated quote for a symbol."""
    base_prices = {
        "AAPL": 175.50,
        "GOOGL": 140.25,
        "MSFT": 380.75,
        "AMZN": 155.30,
        "TSLA": 240.60,
        "NVDA": 890.50,
        "META": 485.20,
        "BTC/USDT": 45000,
        "ETH/USDT": 2500,
    }
    
    base = base_prices.get(symbol, 100)
    change = random.uniform(-3, 3)
    price = base * (1 + change / 100)
    
    return {
        "symbol": symbol,
        "name": symbol,
        "price": round(price, 2),
        "change": round(price * change / 100, 2),
        "changePercent": round(change, 2),
        "volume": random.randint(1000000, 10000000),
        "high": round(price * 1.02, 2),
        "low": round(price * 0.98, 2),
        "timestamp": datetime.utcnow().isoformat(),
    }

def generate_simulated_market_data():
    """Generate simulated market data as fallback."""
    symbols = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "BTC/USDT", "ETH/USDT"]
    return [generate_simulated_quote(symbol) for symbol in symbols]

@app.get("/")
async def read_root():
    """Serve the main dashboard."""
    template_path = Path(__file__).parent / "templates" / "index.html"
    if template_path.exists():
        return FileResponse(template_path)
    return HTMLResponse(content="<h1>Sofia Trading Platform</h1>")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await manager.connect(websocket)
    
    # Send initial market data
    initial_data = await fetch_real_market_data()
    await websocket.send_json({
        "type": "market_data",
        "symbols": initial_data
    })
    
    # Start background task for this connection
    task = asyncio.create_task(send_market_updates(websocket))
    
    try:
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            # Handle any client requests here
    except WebSocketDisconnect:
        task.cancel()
        manager.disconnect(websocket)

async def send_market_updates(websocket: WebSocket):
    """Send periodic market updates to a specific websocket."""
    while True:
        try:
            await asyncio.sleep(10)  # Update every 10 seconds
            
            # Fetch real market data
            market_data = await fetch_real_market_data()
            await websocket.send_json({
                "type": "market_data",
                "symbols": market_data
            })
            
            # Simulate trading activity
            if random.random() > 0.5:
                trade = generate_random_trade()
                await websocket.send_json({
                    "type": "trade",
                    "symbol": trade["symbol"],
                    "message": trade["message"],
                    "side": trade["side"]
                })
            
        except Exception as e:
            print(f"Error sending updates: {e}")
            break

def generate_random_trade():
    """Generate random trading activity."""
    symbols = ["AAPL", "GOOGL", "MSFT", "TSLA", "BTC/USDT"]
    symbol = random.choice(symbols)
    side = random.choice(["buy", "sell"])
    quantity = random.randint(10, 500) if "/" not in symbol else round(random.uniform(0.01, 2), 4)
    price = random.uniform(100, 500) if "/" not in symbol else random.uniform(20000, 50000)
    
    return {
        "symbol": symbol,
        "side": side,
        "message": f"{side.upper()} {quantity} @ ${price:.2f}"
    }

@app.on_event("startup")
async def startup_event():
    """Start background tasks on startup."""
    # Market data will be sent per connection now
    pass

@app.get("/api/portfolio")
async def get_portfolio():
    """Get current portfolio status."""
    return {
        "total_value": 125342.67 + random.uniform(-1000, 1000),
        "cash_balance": 80112.67,
        "positions_value": 45230.00,
        "daily_pnl": 2341.50 + random.uniform(-200, 200),
        "daily_pnl_percent": 1.87,
        "total_return": 25.34,
        "positions": [
            {"symbol": "AAPL", "quantity": 100, "value": 17823.00, "pnl": 273.00},
            {"symbol": "GOOGL", "quantity": 50, "value": 7128.00, "pnl": -122.00},
            {"symbol": "BTC/USDT", "quantity": 0.5, "value": 21783.95, "pnl": 783.95},
        ]
    }

@app.get("/api/metrics")
async def get_metrics():
    """Get trading metrics."""
    return {
        "win_rate": 73.5,
        "total_trades": 200,
        "winning_trades": 147,
        "sharpe_ratio": 2.34,
        "max_drawdown": -8.5,
        "avg_win": 125.50,
        "avg_loss": -45.30,
        "profit_factor": 2.77
    }

@app.get("/analysis/{symbol}")
async def analysis_page(request: Request, symbol: str):
    """Render detailed analysis page for a symbol."""
    try:
        # Simple import without reload
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from core.indicators import calculate_rsi, calculate_sma
        
        # Fetch current data
        ticker = yf.Ticker(symbol)
        info = ticker.info
        hist = ticker.history(period="1mo")
        
        # Calculate indicators
        indicators_list = []
        if not hist.empty:
            current_price = hist['Close'].iloc[-1]
            # Convert to pandas Series before passing to indicators
            close_prices = hist['Close']
            rsi = calculate_rsi(close_prices)
            sma_20 = calculate_sma(close_prices, 20)
            
            # Determine signals
            rsi_signal = "bullish" if rsi < 30 else "bearish" if rsi > 70 else "neutral"
            sma_signal = "bullish" if current_price > sma_20 else "bearish"
            
            indicators_list = [
                {"name": "RSI(14)", "value": f"{float(rsi):.2f}", "signal": rsi_signal},
                {"name": "SMA(20)", "value": f"${float(sma_20):.2f}", "signal": sma_signal},
                {"name": "Volume", "value": f"{hist['Volume'].iloc[-1]:,.0f}", "signal": "neutral"}
            ]
        
        # Fetch news
        news_items = await news_provider.fetch_news(symbol, 5)
        
        # Prepare template data
        context = {
            "request": request,
            "symbol": symbol,
            "company_name": info.get('longName', symbol),
            "current_price": f"{info.get('currentPrice', 0):.2f}",
            "price_change": round(info.get('currentPrice', 0) - info.get('previousClose', 0), 2),
            "price_change_pct": f"{((info.get('currentPrice', 0) / info.get('previousClose', 1) - 1) * 100):.2f}",
            "indicators": indicators_list,
            "metrics": [
                {"name": "Market Cap", "value": f"${info.get('marketCap', 0)/1e9:.2f}B" if info.get('marketCap') else "N/A"},
                {"name": "P/E Ratio", "value": f"{info.get('trailingPE', 0):.2f}" if info.get('trailingPE') else "N/A"},
                {"name": "52W High", "value": f"${info.get('fiftyTwoWeekHigh', 0):.2f}"},
                {"name": "52W Low", "value": f"${info.get('fiftyTwoWeekLow', 0):.2f}"},
                {"name": "Avg Volume", "value": f"{info.get('averageVolume', 0)/1e6:.2f}M" if info.get('averageVolume') else "N/A"}
            ],
            "news": [n.to_dict() for n in news_items],
            "best_strategy": {
                "name": "SMA Crossover",
                "return": "32.5",
                "sharpe": "1.85",
                "win_rate": "68",
                "total_trades": "42"
            }
        }
        
        return templates.TemplateResponse("analysis.html", context)
        
    except Exception as e:
        print(f"Analysis page error: {e}")
        return HTMLResponse(content=f"<h1>Error loading analysis for {symbol}</h1><p>{str(e)}</p>", status_code=500)

@app.get("/api/news/{symbol}")
async def get_news(symbol: str, limit: int = 5):
    """Get latest news for a symbol."""
    try:
        # Handle general market news request
        if symbol == "MARKET":
            symbol = "SPY"  # Use SPY as proxy for market news
        news_items = await news_provider.fetch_news(symbol, limit)
        return {
            "symbol": symbol,
            "news": [item.to_dict() for item in news_items],
            "count": len(news_items)
        }
    except Exception as e:
        return {
            "symbol": symbol,
            "news": [],
            "error": str(e)
        }

@app.get("/api/backtest/latest")
async def get_latest_backtest():
    """Get latest backtest results."""
    # Mock data for now - will be replaced with actual backtest service
    return {
        "strategy": "SMA Crossover",
        "symbol": "BTC/USDT",
        "period": "2024-01-01 to 2024-08-24",
        "initial_capital": 100000,
        "final_value": 128500,
        "total_return": 28.5,
        "sharpe_ratio": 1.85,
        "max_drawdown": -12.3,
        "win_rate": 67,
        "total_trades": 45,
        "winning_trades": 30,
        "losing_trades": 15,
        "avg_win": 1250,
        "avg_loss": -450,
        "profit_factor": 1.86,
        "timestamp": datetime.utcnow().isoformat()
    }