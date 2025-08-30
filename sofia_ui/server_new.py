"""
Sofia V2 Glass Dark UI Server
FastAPI application with all routes
"""

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import route modules
try:
    from src.routes.ui_dashboard import router as dashboard_router
    from src.routes.ui_portfolio import router as portfolio_router
    from src.routes.ui_markets import router as markets_router
    from src.routes.bot_api import router as bot_router
    from src.routes.ultimate_api import router as ultimate_router
except ImportError as e:
    print(f"Warning: Could not import route modules: {e}")
    dashboard_router = None
    portfolio_router = None
    markets_router = None
    bot_router = None
    ultimate_router = None

app = FastAPI(
    title="Sofia V2 - Glass Dark UI",
    description="Beautiful AI Trading Platform Interface",
    version="2.0.0"
)

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates  
templates = Jinja2Templates(directory="templates")

# Include routers if available
if dashboard_router:
    app.include_router(dashboard_router)
if portfolio_router:
    app.include_router(portfolio_router)
if markets_router:
    app.include_router(markets_router)
if bot_router:
    app.include_router(bot_router)
if ultimate_router:
    app.include_router(ultimate_router)

# Quick route implementations for remaining pages
@app.get("/backtest", response_class=HTMLResponse)
async def backtest(request: Request):
    """Backtest page"""
    return templates.TemplateResponse("clean_dashboard.html", {
        "request": request,
        "current_page": "backtest",
        "page_title": "Backtest - Sofia V2"
    })

@app.get("/strategies", response_class=HTMLResponse)
async def strategies(request: Request):
    """Strategies page"""
    return templates.TemplateResponse("clean_dashboard.html", {
        "request": request,
        "current_page": "strategies",
        "page_title": "Strategies - Sofia V2"
    })

@app.get("/trade/ai", response_class=HTMLResponse)
async def trade_ai(request: Request):
    """AI Trading page"""
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "current_page": "ai_trading",
        "page_title": "AI Trading - Sofia V2"
    })

@app.get("/trade/manual", response_class=HTMLResponse)
async def trade_manual(request: Request):
    """Manual Trading page"""
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "current_page": "manual_trading",
        "page_title": "Manual Trading - Sofia V2"
    })

@app.get("/reliability", response_class=HTMLResponse)
async def reliability(request: Request):
    """Reliability page"""
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "current_page": "reliability",
        "page_title": "Reliability - Sofia V2"
    })

@app.get("/settings", response_class=HTMLResponse)
async def settings(request: Request):
    """Settings page"""
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "current_page": "settings",
        "page_title": "Settings - Sofia V2"
    })

@app.get("/showcase/{symbol}", response_class=HTMLResponse)
async def showcase(request: Request, symbol: str):
    """Showcase page for specific symbols"""
    tv_symbol_map = {
        "BTC": "BINANCE:BTCUSDT",
        "ETH": "BINANCE:ETHUSDT", 
        "AAPL": "NASDAQ:AAPL"
    }
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "current_page": "showcase",
        "page_title": f"{symbol} Showcase - Sofia V2",
        "symbol": symbol,
        "tv_symbol": tv_symbol_map.get(symbol, f"BINANCE:{symbol}USDT")
    })

@app.get("/bist", response_class=HTMLResponse)
async def bist(request: Request):
    """BIST page - skeleton"""
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "current_page": "bist",
        "page_title": "BIST - Sofia V2"
    })

@app.get("/bist/analysis", response_class=HTMLResponse)
async def bist_analysis(request: Request):
    """BIST Analysis page - skeleton"""
    return templates.TemplateResponse("clean_dashboard.html", {
        "request": request,
        "current_page": "bist_analysis",
        "page_title": "BIST Analysis - Sofia V2"
    })

@app.get("/trading-bot", response_class=HTMLResponse)
async def trading_bot(request: Request):
    """Trading Bot page"""
    return templates.TemplateResponse("trading_bot.html", {
        "request": request,
        "current_page": "trading_bot",
        "page_title": "Trading Bot - Sofia V2"
    })

@app.get("/live-trading", response_class=HTMLResponse)
async def live_trading(request: Request):
    """Live Trading page"""
    return templates.TemplateResponse("live_trading.html", {
        "request": request,
        "current_page": "live_trading",
        "page_title": "Live Trading - Sofia V2"
    })

@app.get("/ultimate", response_class=HTMLResponse)
async def ultimate_trading(request: Request):
    """Ultimate Trading System page"""
    return templates.TemplateResponse("ultimate_trading.html", {
        "request": request,
        "current_page": "ultimate",
        "page_title": "Ultimate Trading - Sofia V2"
    })

# Health check
@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "version": "2.0.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8090)