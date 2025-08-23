from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import yfinance as yf
from pathlib import Path
import asyncio
import json
import logging
from typing import List, Dict
from datetime import datetime

# Import our advanced data fetcher
from data import get_market_data, get_portfolio_data

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Sofia V2 Professional Trading Platform")

# CORS middleware for API access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Templates setup
BASE_DIR = Path(__file__).parent
templates_dir = BASE_DIR / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Client connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"Client disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                pass

manager = ConnectionManager()

@app.get("/health")
def health():
    """Health check endpoint"""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0"
    }

@app.get("/status")
def status():
    """System status endpoint"""
    return {
        "status": "operational",
        "active_connections": len(manager.active_connections),
        "timestamp": datetime.now().isoformat(),
        "services": {
            "data_fetcher": "active",
            "websocket": "active",
            "api": "active"
        }
    }

@app.get("/data")
async def data(symbol: str = Query("BTC-USD")):
    """
    Get market data with automatic fallback
    Uses: yfinance -> Binance -> CoinGecko
    """
    try:
        result = await get_market_data(symbol)
        
        if "error" in result:
            return JSONResponse(
                status_code=503,
                content={
                    "error": result["error"],
                    "providers_tried": result.get("providers_tried", []),
                    "symbol": symbol
                }
            )
        
        return result
        
    except Exception as e:
        logger.error(f"Data endpoint error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "symbol": symbol}
        )

@app.get("/portfolio")
async def portfolio(symbols: str = Query("BTC-USD,ETH-USD,BNB-USD")):
    """
    Get data for multiple symbols
    """
    try:
        symbol_list = [s.strip() for s in symbols.split(",")]
        result = await get_portfolio_data(symbol_list)
        
        # Calculate portfolio metrics
        total_value = 0
        total_change = 0
        
        for symbol, data in result.items():
            if "error" not in data:
                # Simulate holding 1 unit of each
                total_value += data.get("last_price", 0)
                total_change += data.get("change_24h", 0)
        
        return {
            "portfolio": result,
            "summary": {
                "total_value": total_value,
                "total_change_24h": total_change,
                "total_change_percent": (total_change / total_value * 100) if total_value > 0 else 0,
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Portfolio endpoint error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

@app.get("/strategy")
async def strategy(
    symbol: str = Query("BTC-USD"),
    short: int = 5,
    long: int = 20
):
    """
    Enhanced strategy with real-time data
    """
    try:
        # Get market data
        data = await get_market_data(symbol)
        
        if "error" in data or not data.get("prices"):
            return JSONResponse(
                status_code=503,
                content={"error": "Cannot calculate strategy without price data"}
            )
        
        prices = data["prices"]
        
        if len(prices) < max(short, long):
            return {
                "symbol": symbol,
                "signal": "insufficient_data",
                "message": f"Need at least {max(short, long)} data points"
            }
        
        # Calculate SMAs
        prices_series = pd.Series(prices)
        sma_short = prices_series.rolling(short).mean()
        sma_long = prices_series.rolling(long).mean()
        
        # Generate signal
        signal = "hold"
        if len(prices) >= max(short, long):
            if sma_short.iloc[-1] > sma_long.iloc[-1] and sma_short.iloc[-2] <= sma_long.iloc[-2]:
                signal = "buy"
            elif sma_short.iloc[-1] < sma_long.iloc[-1] and sma_short.iloc[-2] >= sma_long.iloc[-2]:
                signal = "sell"
        
        # Calculate additional metrics
        rsi = calculate_rsi(prices)
        support_resistance = calculate_support_resistance(prices)
        
        return {
            "symbol": symbol,
            "signal": signal,
            "indicators": {
                "sma_short": float(sma_short.iloc[-1]),
                "sma_long": float(sma_long.iloc[-1]),
                "rsi": rsi,
                "support": support_resistance["support"],
                "resistance": support_resistance["resistance"]
            },
            "current_price": data["last_price"],
            "provider": data.get("provider"),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Strategy endpoint error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

def calculate_rsi(prices: List[float], period: int = 14) -> float:
    """Calculate RSI indicator"""
    if len(prices) < period + 1:
        return 50.0  # Neutral
    
    prices_series = pd.Series(prices)
    delta = prices_series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    return float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0

def calculate_support_resistance(prices: List[float]) -> Dict[str, float]:
    """Calculate support and resistance levels"""
    if not prices:
        return {"support": 0, "resistance": 0}
    
    recent_prices = prices[-20:] if len(prices) > 20 else prices
    support = min(recent_prices)
    resistance = max(recent_prices)
    
    return {
        "support": float(support),
        "resistance": float(resistance)
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket for real-time price updates
    """
    await manager.connect(websocket)
    
    try:
        # Send initial message
        await websocket.send_text(json.dumps({
            "type": "connected",
            "message": "WebSocket connected successfully",
            "timestamp": datetime.now().isoformat()
        }))
        
        # Price update loop
        symbols = ["BTC-USD", "ETH-USD", "BNB-USD"]
        
        while True:
            # Fetch latest prices
            for symbol in symbols:
                try:
                    data = await get_market_data(symbol)
                    
                    if "error" not in data:
                        update = {
                            "type": "price_update",
                            "symbol": symbol,
                            "price": data["last_price"],
                            "change_24h": data.get("change_24h", 0),
                            "change_percent_24h": data.get("change_percent_24h", 0),
                            "provider": data.get("provider"),
                            "timestamp": datetime.now().isoformat()
                        }
                        
                        await websocket.send_text(json.dumps(update))
                        
                except Exception as e:
                    logger.error(f"WebSocket update error for {symbol}: {str(e)}")
            
            # Wait before next update
            await asyncio.sleep(10)  # Update every 10 seconds
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        manager.disconnect(websocket)

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, symbol: str = "BTC-USD"):
    """Enhanced dashboard with real-time features"""
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "symbol": symbol,
            "ws_url": "ws://localhost:8000/ws"
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)