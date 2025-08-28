"""
Updated Sofia V2 server with new Data Reliability Pack integration
"""

import sys
import asyncio
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sofia_ui.live_data_adapter import live_data_service
from src.services.price_service_real import price_service

# FastAPI app
app = FastAPI(
    title="Sofia V2 - Enhanced Trading Platform",
    description="Trading platform with reliable data feeds",
    version="2.1.0"
)

# Templates
template_path = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(template_path))

# Static files (if exists)
static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


@app.get("/", response_class=HTMLResponse)
async def homepage(request: Request):
    """Main homepage"""
    btc_data = await live_data_service.get_live_price("BTC/USDT")
    return templates.TemplateResponse("homepage.html", {
        "request": request,
        "btc_price": btc_data.get('price', 0),
        "btc_change": btc_data.get('change_percent', 0)
    })


@app.get("/analysis/{symbol}", response_class=HTMLResponse)
async def analysis_page(request: Request, symbol: str):
    """Analysis page for a specific symbol"""
    # Get price data
    price_data = await price_service.get_price(symbol)
    
    # Get metrics
    metrics = price_service.get_metrics()
    
    # Mock news data
    news = [
        {
            "title": f"{symbol} Shows Strong Momentum",
            "source": "CryptoNews",
            "time": "2 hours ago"
        },
        {
            "title": f"Institutional Interest in {symbol} Growing",
            "source": "Bloomberg",
            "time": "5 hours ago"
        }
    ]
    
    return templates.TemplateResponse("analysis.html", {
        "request": request,
        "symbol": symbol,
        "price": price_data['price'] if price_data else 0,
        "source": price_data['source'] if price_data else 'N/A',
        "freshness": price_data['freshness'] if price_data else 'N/A',
        "ws_connected": metrics.get('websocket_connected', False),
        "news": news,
        "rsi": 55.2,
        "sma_20": price_data['price'] * 0.98 if price_data else 0
    })


@app.get("/showcase/{symbol}", response_class=HTMLResponse)
async def showcase_page(request: Request, symbol: str):
    """Showcase page for a symbol"""
    # Get price data
    price_data = await live_data_service.get_live_price(symbol)
    
    return templates.TemplateResponse("showcase.html", {
        "request": request,
        "symbol": symbol,
        "price": price_data.get('price', 0),
        "change": price_data.get('change_percent', 0),
        "volume": price_data.get('volume', '0')
    })


@app.get("/backtest", response_class=HTMLResponse)
async def backtest_page(request: Request):
    """Backtest page"""
    return templates.TemplateResponse("backtest.html", {
        "request": request
    })


@app.get("/strategies", response_class=HTMLResponse)
async def strategies_page(request: Request):
    """Strategies page"""
    return templates.TemplateResponse("strategies.html", {
        "request": request
    })


@app.get("/cards", response_class=HTMLResponse)
async def cards_page(request: Request):
    """Cards page"""
    return templates.TemplateResponse("cards.html", {
        "request": request
    })


@app.get("/api/live/{symbol}")
async def get_live_data(symbol: str):
    """API endpoint for live data"""
    return await live_data_service.get_live_price(symbol)


@app.get("/api/metrics")
async def get_metrics():
    """Get system metrics"""
    return live_data_service.get_metrics()


# Proxy endpoints to new data service
@app.get("/price/{symbol}")
async def get_price(symbol: str):
    """Get price for a symbol"""
    return await price_service.get_price(symbol)


@app.get("/metrics")
async def metrics():
    """System metrics"""
    return price_service.get_metrics()


@app.get("/health")
async def health():
    """Health check"""
    metrics = price_service.get_metrics()
    return {
        "status": "healthy" if metrics.get('websocket_connected') or not metrics.get('rest_failures') else "degraded",
        "websocket_connected": metrics.get('websocket_connected', False)
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)