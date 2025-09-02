"""
Sofia V2 - Web UI Server
Modern ve profesyonel trading stratejisi arayüzü
"""

<<<<<<< HEAD
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import asyncio
from pathlib import Path
import random
from datetime import datetime
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sofia_ui.live_data import live_data_service

# Import template resolver
from src.web.templates import render, get_templates_instance, get_resolution_report

from src.api.paper_trading import router as paper_trading_router
from src.api.canary_trading import router as canary_trading_router
from src.api.live_trading import router as live_trading_router
from src.web.middleware import OneBarMiddleware

# FastAPI uygulaması
app = FastAPI(
    title="Sofia V2 - Glass Dark Trading Platform",
    description="AI Trading Platform with Glass Dark Theme",
    version="2.0.0"
)

# Add one-bar middleware
app.add_middleware(OneBarMiddleware)

# Include trading routes
app.include_router(paper_trading_router)
app.include_router(canary_trading_router)
app.include_router(live_trading_router)

# Static dosyalar ve template'ler
static_path = Path(__file__).parent / "static"
template_path = Path(__file__).parent / "templates"

app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
templates = get_templates_instance()  # Use canonical template resolver


# Mock data functions
async def get_live_btc_data():
    """BTC için canlı veri döndürür"""
    try:
        return await live_data_service.get_live_price("BTC/USDT")
=======
import asyncio
import json
import random
from datetime import datetime
from pathlib import Path
import aiohttp
import httpx  # For calling trading status API

import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

# Import authentication and payment modules
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from src.auth.router import router as auth_router
    from src.payments.router import router as payments_router
    from src.auth.models import create_tables, init_subscription_plans, User
    from src.auth.dependencies import get_current_user, get_user_or_api_user, check_rate_limit, require_basic_subscription
    from src.data_hub.database import get_db, engine
    AUTH_ENABLED = True
    print("Authentication modules loaded successfully")
except ImportError as e:
    print(f"Warning: Authentication modules not available: {e}")
    AUTH_ENABLED = False
    
    # Mock functions when auth is not available
    def get_user_or_api_user():
        return None
    
    def get_db():
        return None
    
    User = None

try:
    from live_data import live_data_service
except:

    class MockLiveDataService:
        def get_live_price(self, symbol):
            return {
                "symbol": symbol,
                "name": "Bitcoin" if "BTC" in symbol else symbol,
                "price": 67845.32,
                "change": 2.45,
                "change_percent": 3.74,
                "volume": "28.5B",
                "market_cap": "1.34T",
                "last_updated": datetime.now().strftime("%H:%M:%S"),
            }

        def get_multiple_prices(self, symbols):
            return {s: self.get_live_price(s) for s in symbols}

        def get_crypto_prices(self):
            return {}

        def get_chart_data(self, symbol, period):
            return {}

        def get_market_summary(self):
            return {}

        def get_crypto_fear_greed_index(self):
            return {"value": 72, "value_classification": "Greed"}

    live_data_service = MockLiveDataService()

# Trading Status API URL
TRADING_API_URL = "http://localhost:8003"  # Trading status API port

async def get_real_trading_data():
    """Get real trading data from trading status API"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{TRADING_API_URL}/status")
            if response.status_code == 200:
                data = response.json()
                print(f"Successfully fetched trading data: Total balance = ${data['portfolio']['total_balance']}")
                return data
            else:
                print(f"Trading API returned status {response.status_code}")
    except Exception as e:
        print(f"Error fetching trading data: {e}")
        print(f"Failed to connect to {TRADING_API_URL}")
    
    # Fallback to default data
    return None

# FastAPI uygulaması
app = FastAPI(
    title="Sofia V2 - Trading Strategy Platform",
    description="Akıllı trading stratejileri ve backtest platformu",
    version="2.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers if authentication is enabled
if AUTH_ENABLED:
    app.include_router(auth_router)
    app.include_router(payments_router)

# Initialize database tables
@app.on_event("startup")
async def startup_event():
    """Initialize database and default data"""
    if AUTH_ENABLED:
        try:
            create_tables(engine)
            print("Database initialized successfully")
        except Exception as e:
            print(f"Database initialization failed: {e}")
    else:
        print("Running without authentication")

# Static dosyalar ve template'ler
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
static_path = os.path.join(current_dir, "static")
template_path = os.path.join(current_dir, "templates")

app.mount("/static", StaticFiles(directory=static_path), name="static")
templates = Jinja2Templates(directory=template_path)


# Mock data functions
def get_live_btc_data():
    """BTC için canlı veri döndürür"""
    try:
        return live_data_service.get_live_price("BTC-USD")
    except Exception as e:
        print(f"Live data error: {e}")
        # Fallback to mock data
        return {
            "symbol": "BTC/USDT"
            "name": "Bitcoin",
            "price": 67845.32,
            "change": 2.45,
            "change_percent": 3.74,
            "volume": "28.5B"
            "high_24h": 68500.0,
            "low_24h": 67200.0,
            "last_updated": datetime.now().strftime("%H:%M:%S")
=======
            "market_cap": "1.34T",
            "last_updated": datetime.now().strftime("%H:%M:%S"),
>>>>>>> 96de1d9
        }


def get_mock_news():
    """Mock haber verisi döndürür"""
    return [
        {
            "title": "Bitcoin ETF'ler Rekor Giriş Görüyor",
            "summary": "Kurumsal yatırımcılar Bitcoin ETF'lerine olan ilgilerini artırıyor...",
            "url": "https://www.coindesk.com/markets/2024/01/15/bitcoin-etf-inflows/",
            "source": "CoinDesk",
<<<<<<< HEAD
            "time": "2 saat önce"
=======
            "time": "2 saat önce",
>>>>>>> 96de1d9
        },
        {
            "title": "MicroStrategy Bitcoin Alımlarını Sürdürüyor",
            "summary": "Şirket hazine stratejisinin bir parçası olarak Bitcoin biriktirmeye devam ediyor...",
            "url": "https://www.bloomberg.com/news/articles/2024/01/15/microstrategy-continues-bitcoin-buying/",
            "source": "Bloomberg",
<<<<<<< HEAD
            "time": "4 saat önce"
=======
            "time": "4 saat önce",
>>>>>>> 96de1d9
        },
        {
            "title": "Fed Faiz Kararı Kripto Piyasalarını Etkiliyor",
            "summary": "Merkez bankası politikaları dijital varlık fiyatlarında dalgalanmaya neden oluyor...",
            "url": "https://www.reuters.com/business/finance/fed-decision-impacts-crypto-markets/",
            "source": "Reuters",
<<<<<<< HEAD
            "time": "6 saat önce"
        }
=======
            "time": "6 saat önce",
        },
>>>>>>> 96de1d9
    ]


def get_mock_strategies():
    """Mock strateji kartları döndürür"""
    return [
        {
            "id": 1,
            "name": "SMA Crossover",
            "symbol": "BTC-USD",
            "period": "2023-01-01 - 2024-01-01",
            "total_return": 45.6,
            "sharpe_ratio": 1.23,
            "max_drawdown": -12.4,
            "win_rate": 68.5,
            "status": "active",
<<<<<<< HEAD
            "color": "bg-emerald-500"
=======
            "color": "bg-emerald-500",
>>>>>>> 96de1d9
        },
        {
            "id": 2,
            "name": "RSI + MACD",
            "symbol": "ETH-USD",
            "period": "2023-01-01 - 2024-01-01",
            "total_return": 32.1,
            "sharpe_ratio": 0.98,
            "max_drawdown": -18.7,
            "win_rate": 61.2,
            "status": "testing",
<<<<<<< HEAD
            "color": "bg-blue-500"
=======
            "color": "bg-blue-500",
>>>>>>> 96de1d9
        },
        {
            "id": 3,
            "name": "Bollinger Bands",
            "symbol": "BTC-USD",
            "period": "2023-06-01 - 2024-01-01",
            "total_return": 28.9,
            "sharpe_ratio": 0.87,
            "max_drawdown": -15.2,
            "win_rate": 58.7,
            "status": "paused",
<<<<<<< HEAD
            "color": "bg-amber-500"
        }
    ]


# Routes
@app.get("/", response_class=HTMLResponse)
async def homepage(request: Request):
    """Ana sayfa - Sofia V2 Glass Dark UI"""
    try:
        # Always use stable Glass Dark template for production
        homepage_path = Path("templates/homepage_glass_dark_stable.html")
        if homepage_path.exists():
            content = homepage_path.read_text(encoding='utf-8')
            return HTMLResponse(content=content)
        else:
            # Fallback to regular homepage
            fallback_path = Path("templates/homepage.html")
            if fallback_path.exists():
                content = fallback_path.read_text(encoding='utf-8')
                return HTMLResponse(content=content)
            return HTMLResponse(content="<h1>No homepage template found</h1>")
    except Exception as e:
        return HTMLResponse(content=f"<h1>Error loading homepage: {str(e)}</h1>")

@app.get("/test", response_class=HTMLResponse)
async def test_page():
    """Test sayfası"""
    return HTMLResponse(content="<h1>Test Page Working! Server Updated!</h1>")


# Showcase route moved to end of file to avoid duplicates
=======
            "color": "bg-amber-500",
        },
    ]



# Routes
@app.get("/", response_class=HTMLResponse)
async def welcome_page(request: Request):
    """Welcome page - Turkish/English language selection"""
    context = {
        "request": request,
        "page_title": "Sofia V2 - AI Trading Platform",
        "current_page": "welcome",
    }
    return templates.TemplateResponse("welcome.html", context)

@app.get("/dashboard", response_class=HTMLResponse)
async def homepage(request: Request):
    """Ana sayfa - Ultimate dashboard"""
    # Get real trading data
    real_data = await get_real_trading_data()
    
    # Extract portfolio values
    total_balance = 125430.67  # Default
    daily_pnl = 2340.56
    pnl_percentage = 1.87
    
    if real_data:
        portfolio = real_data["portfolio"]
        total_balance = portfolio["total_balance"]
        daily_pnl = portfolio["daily_pnl"]
        pnl_percentage = portfolio["daily_pnl_percentage"]
    
    context = {
        "request": request,
        "page_title": "Sofia V2 - AI Trading Platform",
        "current_page": "dashboard",
        "total_balance": total_balance,
        "daily_pnl": daily_pnl,
        "pnl_percentage": pnl_percentage,
        "btc_data": get_live_btc_data(),
        "latest_news": get_mock_news()[:3],
    }
    return templates.TemplateResponse("homepage.html", context)


@app.get("/new", response_class=HTMLResponse)
async def new_dashboard(request: Request):
    """Yeni dashboard - Ultimate version"""
    context = {
        "request": request,
        "page_title": "Sofia V2 - Trading Platform",
        "current_page": "dashboard",
        "btc_data": get_live_btc_data(),
        "latest_news": get_mock_news()[:3],
    }
    return templates.TemplateResponse("dashboard_ultimate.html", context)


async def get_trading_status():
    """Get real-time trading status from backend"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:8000/health/detailed") as response:
                if response.status == 200:
                    return await response.json()
    except Exception as e:
        print(f"Failed to get trading status: {e}")
        return {
            "status": "healthy",
            "components": {
                "websocket_connections": 0,
                "enabled_exchanges": ["binance", "okx", "bybit"],
                "ingestors": {"binance": "connected", "okx": "connected", "bybit": "connected"}
            }
        }

async def get_portfolio_data():
    """Get real-time portfolio data from UNIFIED trading system"""
    try:
        # Connect to unified system
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:8889/portfolio") as response:
                if response.status == 200:
                    return await response.json()
    except:
        pass
    
    # Fallback data
    try:
        # Sofia V2 realistic portfolio data
        positions = [
            {
                "symbol": "BTCUSDT",
                "side": "long",
                "size": 0.15,
                "entry_price": 67200,
                "current_price": 67845.32,
                "unrealized_pnl": 96.75,
                "pnl_percent": 0.14,
                "value": 10176.80
            },
            {
                "symbol": "ETHUSDT", 
                "side": "long",
                "size": 2.5,
                "entry_price": 2420,
                "current_price": 2456.78,
                "unrealized_pnl": 91.95,
                "pnl_percent": 1.52,
                "value": 6141.95
            },
            {
                "symbol": "SOLUSDT",
                "side": "short", 
                "size": 8.0,
                "entry_price": 185.50,
                "current_price": 182.34,
                "unrealized_pnl": 25.28,
                "pnl_percent": 1.70,
                "value": 1458.72
            }
        ]
        
        total_value = sum(pos["value"] for pos in positions)
        daily_pnl = sum(pos["unrealized_pnl"] for pos in positions)
        
        recent_trades = [
            {"symbol": "BTCUSDT", "side": "buy", "price": 67200, "size": 0.15, "time": "10:30:45"},
            {"symbol": "ETHUSDT", "side": "buy", "price": 2420, "size": 2.5, "time": "09:15:23"},
            {"symbol": "SOLUSDT", "side": "sell", "price": 185.50, "size": 8.0, "time": "08:45:12"}
        ]
        
        return {
            "total_value": total_value,
            "daily_pnl": daily_pnl,
            "total_return_pct": (daily_pnl / (total_value - daily_pnl)) * 100 if total_value > daily_pnl else 0,
            "positions": positions,
            "recent_trades": recent_trades
        }
    except Exception as e:
        print(f"Failed to get portfolio data: {e}")
        return {
            "total_value": 100000.0,
            "daily_pnl": 0.0,
            "total_return_pct": 0.0,
            "positions": [],
            "recent_trades": []
        }

@app.get("/portfolio", response_class=HTMLResponse)
async def portfolio(request: Request):
    """Portfolio dashboard - Real-time trading data"""
    # Get real trading data from unified API
    real_data = await get_real_trading_data()
    
    # Use real data if available
    if real_data:
        portfolio_data = {
            "total_value": real_data["portfolio"]["total_balance"],
            "available_cash": real_data["portfolio"]["available_balance"],
            "positions_value": real_data["portfolio"]["in_positions"],
            "daily_pnl": real_data["portfolio"]["daily_pnl"],
            "daily_pnl_percentage": real_data["portfolio"]["daily_pnl_percentage"],
            "positions": real_data["positions"],
            "currency": "USD"
        }
        trading_status = real_data["trading_status"]
    else:
        trading_status = await get_trading_status()
        portfolio_data = await get_portfolio_data()
    
    context = {
        "request": request,
        "page_title": "Portfolio - Sofia V2",
        "current_page": "portfolio",
        "trading_status": trading_status,
        "portfolio_data": portfolio_data,
        "btc_data": get_live_btc_data(),
    }
    return templates.TemplateResponse("portfolio_realtime.html", context)


@app.get("/showcase/{symbol}", response_class=HTMLResponse)
async def showcase(request: Request, symbol: str):
    """Sembol showcase sayfası - teknik planda belirtilen"""
    try:
        symbol_data = live_data_service.get_live_price(symbol.upper())
    except:
        symbol_data = get_live_btc_data()
        symbol_data["symbol"] = symbol.upper()

    context = {
        "request": request,
        "page_title": f"{symbol.upper()} - Showcase",
        "symbol_data": symbol_data,
        "news": get_mock_news(),
        "strategies": get_mock_strategies(),
        "technical_indicators": {
            "rsi": 45.6,
            "sma_20": 66234.45,
            "sma_50": 64567.89,
            "bollinger_upper": 68500.0,
            "bollinger_lower": 65200.0,
        },
    }
    return templates.TemplateResponse("showcase.html", context)
>>>>>>> 96de1d9


@app.get("/cards", response_class=HTMLResponse)
async def strategy_cards(request: Request):
    """Strateji kartları sayfası - teknik planda belirtilen"""
    context = {
        "request": request,
        "page_title": "Strategy Cards",
<<<<<<< HEAD
        "strategies": get_mock_strategies()
    }
    return render(request, "cards.html", context)
=======
        "strategies": get_mock_strategies(),
    }
    return templates.TemplateResponse("cards.html", context)
>>>>>>> 96de1d9


@app.get("/analysis/{symbol}", response_class=HTMLResponse)
async def analysis(request: Request, symbol: str):
    """Detaylı analiz sayfası - orta vadeli hedef"""
    btc_data = get_mock_btc_data()
    btc_data["symbol"] = symbol.upper()
<<<<<<< HEAD
    
=======

>>>>>>> 96de1d9
    context = {
        "request": request,
        "page_title": f"{symbol.upper()} - Detailed Analysis",
        "symbol_data": btc_data,
        "news": get_mock_news(),
        "technical_indicators": {
            "rsi": 45.6,
            "macd": 234.5,
            "sma_20": 66234.45,
            "sma_50": 64567.89,
            "volume_sma": 1250000,
            "bollinger_upper": 68500.0,
<<<<<<< HEAD
            "bollinger_lower": 65200.0
=======
            "bollinger_lower": 65200.0,
>>>>>>> 96de1d9
        },
        "fundamental_data": {
            "market_cap": "1.34T",
            "volume_24h": "28.5B",
            "circulating_supply": "19.8M",
            "max_supply": "21M",
<<<<<<< HEAD
            "fear_greed_index": 72
=======
            "fear_greed_index": 72,
>>>>>>> 96de1d9
        },
        "prediction": {
            "direction": "up",
            "confidence": 0.73,
            "target_1w": 71000,
<<<<<<< HEAD
            "target_1m": 75000
        }
    }
    return render(request, "analysis.html", context)
=======
            "target_1m": 75000,
        },
    }
    return templates.TemplateResponse("analysis.html", context)
>>>>>>> 96de1d9


# API Endpoints
@app.get("/api/quote/{symbol}")
async def get_quote(symbol: str):
    """Fiyat bilgisi API"""
    try:
        return live_data_service.get_live_price(symbol.upper())
    except:
        data = get_live_btc_data()
        data["symbol"] = symbol.upper()
        return data


@app.get("/api/news/{symbol}")
async def get_news(symbol: str):
    """Haber API"""
<<<<<<< HEAD
    return {
        "symbol": symbol.upper(),
        "news": get_mock_news()
    }
=======
    return {"symbol": symbol.upper(), "news": get_mock_news()}
>>>>>>> 96de1d9


@app.get("/api/quotes")
async def get_multiple_quotes(symbols: str = "BTC-USD,ETH-USD,AAPL"):
    """Çoklu fiyat bilgisi API"""
    try:
<<<<<<< HEAD
        symbol_list = [s.strip() for s in symbols.split(',')]
        return live_data_service.get_multiple_prices(symbol_list)
    except Exception as e:
        # Fallback
        symbol_list = [s.strip() for s in symbols.split(',')]
        return {symbol: get_live_btc_data() for symbol in symbol_list}


@app.get("/api/crypto-prices")
async def get_crypto_prices():
    """Tüm desteklenen crypto coinlerin fiyatları"""
    try:
        return await live_data_service.get_all_crypto_prices()
    except Exception as e:
        # Fallback - sadece BTC ve ETH
        return {
            "BTC/USDT": get_live_btc_data(),
            "ETH/USDT": {
                "symbol": "ETH/USDT",
=======
        symbol_list = [s.strip() for s in symbols.split(",")]
        return live_data_service.get_multiple_prices(symbol_list)
    except Exception:
        # Fallback
        symbol_list = [s.strip() for s in symbols.split(",")]
        return {symbol: get_live_btc_data() for symbol in symbol_list}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.get("/test", response_class=HTMLResponse)
async def test_page(request: Request):
    """Basit test sayfası"""
    context = {
        "request": request,
        "page_title": "Test Page",
        "btc_data": get_live_btc_data(),
    }
    return templates.TemplateResponse("test.html", context)


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                pass


manager = ConnectionManager()


@app.websocket("/ws/portfolio")
async def websocket_portfolio(websocket: WebSocket):
    """WebSocket endpoint for portfolio updates"""
    await manager.connect(websocket)
    try:
        while True:
            # Get actual portfolio data and add some realistic variation
            base_portfolio_data = await get_portfolio_data()
            
            # Add small variations for real-time effect
            portfolio_data = {
                "balance": base_portfolio_data["total_value"] + random.uniform(-50, 50),
                "daily_pnl": base_portfolio_data["daily_pnl"] + random.uniform(-10, 10),
                "positions": base_portfolio_data["positions"],
                "new_trade": (
                    {
                        "time": datetime.now().isoformat(),
                        "symbol": random.choice(["BTCUSDT", "ETHUSDT", "SOLUSDT"]),
                        "type": random.choice(["BUY", "SELL"]),
                        "price": random.uniform(100, 70000),
                        "amount": random.uniform(0.01, 5),
                        "pnl": random.uniform(-100, 100),
                    }
                    if random.random() > 0.8
                    else None
                ),
            }

            await websocket.send_text(json.dumps(portfolio_data))
            await asyncio.sleep(3)

    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/api/crypto-prices")
async def get_crypto_prices():
    """Tüm desteklenen crypto coinlerin fiyatları - 100+ coin"""
    try:
        # Top 100 kripto listesi
        top_cryptos = [
            {"symbol": "BTC", "name": "Bitcoin", "icon": "fab fa-bitcoin", "color": "orange"},
            {"symbol": "ETH", "name": "Ethereum", "icon": "fab fa-ethereum", "color": "purple"},
            {"symbol": "BNB", "name": "Binance Coin", "color": "yellow"},
            {"symbol": "SOL", "name": "Solana", "color": "purple"},
            {"symbol": "XRP", "name": "Ripple", "color": "blue"},
            {"symbol": "ADA", "name": "Cardano", "color": "blue"},
            {"symbol": "AVAX", "name": "Avalanche", "color": "red"},
            {"symbol": "DOGE", "name": "Dogecoin", "color": "yellow"},
            {"symbol": "TRX", "name": "TRON", "color": "red"},
            {"symbol": "DOT", "name": "Polkadot", "color": "pink"},
            {"symbol": "MATIC", "name": "Polygon", "color": "purple"},
            {"symbol": "LINK", "name": "Chainlink", "color": "blue"},
            {"symbol": "SHIB", "name": "Shiba Inu", "color": "orange"},
            {"symbol": "UNI", "name": "Uniswap", "color": "pink"},
            {"symbol": "LTC", "name": "Litecoin", "color": "gray"},
            {"symbol": "ATOM", "name": "Cosmos", "color": "purple"},
            {"symbol": "XLM", "name": "Stellar", "color": "black"},
            {"symbol": "ETC", "name": "Ethereum Classic", "color": "green"},
            {"symbol": "FIL", "name": "Filecoin", "color": "cyan"},
            {"symbol": "APT", "name": "Aptos", "color": "teal"},
            {"symbol": "ARB", "name": "Arbitrum", "color": "blue"},
            {"symbol": "OP", "name": "Optimism", "color": "red"},
            {"symbol": "NEAR", "name": "NEAR Protocol", "color": "green"},
            {"symbol": "VET", "name": "VeChain", "color": "blue"},
            {"symbol": "ALGO", "name": "Algorand", "color": "black"},
            {"symbol": "FTM", "name": "Fantom", "color": "blue"},
            {"symbol": "GRT", "name": "The Graph", "color": "purple"},
            {"symbol": "SAND", "name": "The Sandbox", "color": "cyan"},
            {"symbol": "MANA", "name": "Decentraland", "color": "orange"},
            {"symbol": "AXS", "name": "Axie Infinity", "color": "blue"},
            {"symbol": "THETA", "name": "Theta", "color": "orange"},
            {"symbol": "EGLD", "name": "MultiversX", "color": "black"},
            {"symbol": "CHZ", "name": "Chiliz", "color": "red"},
            {"symbol": "ENJ", "name": "Enjin", "color": "purple"},
            {"symbol": "ZIL", "name": "Zilliqa", "color": "teal"},
            {"symbol": "1INCH", "name": "1inch", "color": "red"},
            {"symbol": "SUSHI", "name": "SushiSwap", "color": "pink"},
            {"symbol": "CRV", "name": "Curve", "color": "blue"},
            {"symbol": "LDO", "name": "Lido DAO", "color": "cyan"},
            {"symbol": "SNX", "name": "Synthetix", "color": "purple"},
        ]

        result = {}
        base_price = 50000  # Base for calculations

        for i, crypto in enumerate(top_cryptos[:40]):  # First 40 for now
            # Generate realistic mock prices
            if crypto["symbol"] == "BTC":
                price = 67845.32
            elif crypto["symbol"] == "ETH":
                price = 3456.78
            elif crypto["symbol"] == "BNB":
                price = 542.45
            elif crypto["symbol"] == "SOL":
                price = 142.50
            elif crypto["symbol"] == "XRP":
                price = 0.6234
            elif crypto["symbol"] == "ADA":
                price = 0.5867
            elif crypto["symbol"] == "DOGE":
                price = 0.1234
            elif crypto["symbol"] == "SHIB":
                price = 0.00002345
            else:
                # Generate price based on position
                price = base_price / ((i + 1) * random.uniform(10, 100))

            # Generate random change
            change_percent = random.uniform(-15, 15)
            change = price * (change_percent / 100)

            # Generate volume based on rank
            volume_base = 1000000000 / (i + 1)
            volume = volume_base * random.uniform(0.5, 2)

            result[f"{crypto['symbol']}-USD"] = {
                "symbol": f"{crypto['symbol']}-USD",
                "name": crypto["name"],
                "price": round(price, 4 if price < 1 else 2),
                "change": round(change, 4 if abs(change) < 1 else 2),
                "change_percent": round(change_percent, 2),
                "volume": (
                    f"{volume/1000000000:.1f}B" if volume > 1000000000 else f"{volume/1000000:.1f}M"
                ),
                "market_cap": f"{(price * volume / 100):.0f}",
                "last_updated": datetime.now().strftime("%H:%M:%S"),
                "icon": crypto.get("icon", ""),
                "color": crypto.get("color", "gray"),
                "rank": i + 1,
            }

        return result
    except Exception as e:
        print(f"Error getting crypto prices: {e}")
        # Fallback
        return {
            "BTC-USD": get_live_btc_data(),
            "ETH-USD": {
                "symbol": "ETH-USD",
>>>>>>> 96de1d9
                "name": "Ethereum",
                "price": 3456.78,
                "change": 45.67,
                "change_percent": 1.34,
                "volume": "15.2B",
                "last_updated": datetime.now().strftime("%H:%M:%S"),
<<<<<<< HEAD
                "icon": "fab fa-ethereum"
            }
        }


@app.get("/api/ohlcv/{symbol}")
async def get_ohlcv_data(symbol: str, timeframe: str = "1h", limit: int = 100):
    """OHLCV verisi API (TradingView uyumlu)"""
    try:
        return await live_data_service.get_ohlcv(symbol.upper(), timeframe, limit)
    except Exception as e:
        return {
            "error": f"OHLCV data unavailable for {symbol}",
            "symbol": symbol.upper(),
            "timeframe": timeframe
        }


@app.get("/api/indicators/{symbol}")
async def get_indicators(symbol: str, timeframe: str = "1h"):
    """Trading indicators API (RSI, MACD, Bollinger Bands)"""
    try:
        return await live_data_service.get_indicators(symbol.upper(), timeframe)
    except Exception as e:
        return {
            "error": f"Indicators unavailable for {symbol}",
            "symbol": symbol.upper(),
            "timeframe": timeframe
        }


@app.websocket("/ws/price/{symbol}")
async def websocket_price_stream(websocket, symbol: str):
    """WebSocket price stream"""
    try:
        # WebSocket connection'ı kaydet
        if symbol not in live_data_service.websocket_connections:
            live_data_service.websocket_connections[symbol] = []
        live_data_service.websocket_connections[symbol].append(websocket)
        
        # Price stream'i başlat
        await live_data_service.start_price_stream(symbol)
        
        try:
            while True:
                # Keep connection alive
                await websocket.ping()
                await asyncio.sleep(1)
        except:
            # Connection kapandığında temizle
            if symbol in live_data_service.websocket_connections:
                live_data_service.websocket_connections[symbol].remove(websocket)
                
    except Exception as e:
        logger.error(f"WebSocket error for {symbol}: {e}")


@app.post("/api/trade")
async def save_trade(request: Request):
    """Trade kaydet"""
    try:
        data = await request.json()
        await live_data_service.save_trade(
            symbol=data['symbol'],
            side=data['side'],
            amount=data['amount'],
            price=data['price'],
            strategy=data.get('strategy'),
            pnl=data.get('pnl')
        )
        return {"status": "success", "message": "Trade saved"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


=======
                "icon": "fab fa-ethereum",
            },
        }


@app.get("/api/chart/{symbol}")
async def get_chart_data(symbol: str, period: str = "1mo"):
    """Grafik verisi API"""
    try:
        return live_data_service.get_chart_data(symbol.upper(), period)
    except Exception:
        return {
            "error": f"Chart data unavailable for {symbol}",
            "symbol": symbol.upper(),
            "period": period,
        }


>>>>>>> 96de1d9
@app.get("/api/market-summary")
async def get_market_summary():
    """Piyasa özeti API"""
    try:
        return live_data_service.get_market_summary()
    except:
        return {"error": "Market data unavailable"}


@app.get("/api/fear-greed")
async def get_fear_greed():
    """Fear & Greed Index API"""
    try:
        return live_data_service.get_crypto_fear_greed_index()
    except:
        return {"value": 72, "value_classification": "Greed"}


<<<<<<< HEAD
@app.get("/ai/news/sentiment")
async def get_news_sentiment(symbol: str = "BTC/USDT"):
    """Get news sentiment for symbol"""
    try:
        # Import here to avoid circular dependencies
        from src.ai.news_sentiment import NewsSentimentAnalyzer
        
        analyzer = NewsSentimentAnalyzer()
        if not analyzer.enabled:
            return {"error": "News sentiment analysis disabled"}
        
        # Get sentiment summary
        sentiment_data = await analyzer.get_sentiment_summary(symbol)
        
        if sentiment_data:
            return sentiment_data
        else:
            return {
                "symbol": symbol,
                "sentiment_1h": 0.0,
                "sentiment_24h": 0.0,
                "volume_1h": 0,
                "volume_24h": 0,
                "confidence_1h": 0.0,
                "confidence_24h": 0.0,
                "last_update": datetime.now().isoformat(),
                "strategy_overlay": {
                    "k_factor_adjustment": 0.0,
                    "strategy_bias": "neutral"
                },
                "recent_news": []
            }
    except Exception as e:
        logger.error(f"News sentiment API error: {e}")
        return {"error": "Failed to get news sentiment"}


@app.get("/ai/news/features")
async def get_news_features(symbol: str = "BTC/USDT"):
    """Get news features for symbol"""
    try:
        from src.ai.news_sentiment import NewsSentimentAnalyzer
        from src.ai.news_features import NewsFeatureEngine
        
        analyzer = NewsSentimentAnalyzer()
        feature_engine = NewsFeatureEngine()
        
        if not analyzer.enabled:
            return {"error": "News analysis disabled"}
        
        # Update sentiment first
        await analyzer.update_news_sentiment([symbol])
        
        # Get news items and sentiment
        news_items = analyzer.news_cache.get(symbol, [])
        sentiment_score = analyzer.sentiment_cache.get(symbol)
        
        # Extract features
        features = feature_engine.extract_features(symbol, news_items, sentiment_score)
        
        # Get trading signals
        signals = feature_engine.get_trading_signals(features)
        
        return {
            "symbol": symbol,
            "features": features,
            "trading_signals": signals,
            "news_count": len(news_items),
            "last_update": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"News features API error: {e}")
        return {"error": "Failed to get news features"}


@app.get("/assets/{symbol}", response_class=HTMLResponse)
async def assets_detail(request: Request, symbol: str):
    """Asset detay sayfası - UI planında belirtilen"""
=======
@app.get("/assets/{symbol}", response_class=HTMLResponse)
async def assets_detail(request: Request, symbol: str):
    """Asset detay sayfası - Ultra modern version"""
>>>>>>> 96de1d9
    try:
        symbol_data = live_data_service.get_live_price(symbol.upper())
    except:
        symbol_data = get_live_btc_data()
        symbol_data["symbol"] = symbol.upper()
<<<<<<< HEAD
    
    context = {
        "request": request,
        "page_title": f"{symbol.upper()} - Asset Details",
=======

    context = {
        "request": request,
        "page_title": f"{symbol.upper()} - Asset Details",
        "current_page": "assets",
>>>>>>> 96de1d9
        "symbol_data": symbol_data,
        "news": get_mock_news(),
        "technical_indicators": {
            "rsi": 45.6,
            "macd": 234.5,
            "sma_20": 66234.45,
            "sma_50": 64567.89,
            "bollinger_upper": 68500.0,
<<<<<<< HEAD
            "bollinger_lower": 65200.0
        },
        "fundamental_data": {
            "market_cap": "1.34T",
            "volume_24h": "28.5B",
            "fear_greed_index": 72
        }
    }
    return render(request, "assets_detail.html", context)
=======
            "bollinger_lower": 65200.0,
        },
        "fundamental_data": {"market_cap": "1.34T", "volume_24h": "28.5B", "fear_greed_index": 72},
    }
    return templates.TemplateResponse("assets_ultra.html", context)
>>>>>>> 96de1d9


@app.get("/backtest", response_class=HTMLResponse)
async def backtest_page(request: Request, symbol: str = None, strategy: str = None):
    """Backtest sayfası - UI planında belirtilen"""
    context = {
        "request": request,
        "page_title": "Backtest Strategy",
        "preselected_symbol": symbol,
<<<<<<< HEAD
        "preselected_strategy": strategy
    }
    return render(request, "backtest.html", context)
=======
        "preselected_strategy": strategy,
    }
    return templates.TemplateResponse("backtest.html", context)
>>>>>>> 96de1d9


@app.get("/strategies", response_class=HTMLResponse)
async def strategies_page(request: Request):
    """Stratejiler sayfası - UI planında belirtilen"""
<<<<<<< HEAD
    context = {
        "request": request,
        "page_title": "Trading Strategies"
    }
    return render(request, "strategies.html", context)


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Settings page - ROUTES ALWAYS OPEN"""
    context = {
        "request": request,
        "page_title": "Settings - Paper Trading Control"
    }
    
    # Try main template first, fallback to stub
    try:
        return render(request, "settings.html", context)
    except:
        return render(request, "settings_stub.html", context)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """Paper trading dashboard with live metrics"""
    # Mock total balance - in production would come from database/API
    total_balance = 12500.75  # Example balance
    
    context = {
        "request": request,
        "page_title": "Trading Dashboard",
        "total_balance": total_balance
    }
    return render(request, "dashboard.html", context)


@app.get("/live", response_class=HTMLResponse)
async def live_trading_grid(request: Request):
    """Live trading grid with 200+ assets"""
    context = {
        "request": request,
        "page_title": "Live Trading Grid"
    }
    return render(request, "live.html", context)


@app.get("/trade/manual", response_class=HTMLResponse)
async def trade_manual(request: Request):
    """Manual trading interface"""
    context = {
        "request": request,
        "page_title": "Manual Trading - Sofia V2"
    }
    return render(request, "trade_manual.html", context)


@app.get("/trade/ai", response_class=HTMLResponse)
async def trade_ai(request: Request):
    """AI trading interface"""
    context = {
        "request": request,
        "page_title": "AI Trading - Sofia V2"
    }
    return render(request, "trade_ai.html", context)
=======
    context = {"request": request, "page_title": "Trading Strategies"}
    return templates.TemplateResponse("strategies.html", context)


@app.get("/markets", response_class=HTMLResponse)
async def markets_page(request: Request):
    """Markets sayfası - 100+ kripto listesi"""
    # Sample crypto data for markets page
    cryptos = [
        {"symbol": "BTCUSDT", "name": "Bitcoin", "price": 67845.32, "change": 2.45, "volume": "1.2B"},
        {"symbol": "ETHUSDT", "name": "Ethereum", "price": 2456.78, "change": -1.23, "volume": "865M"},
        {"symbol": "SOLUSDT", "name": "Solana", "price": 156.43, "change": 5.67, "volume": "432M"},
        {"symbol": "BNBUSDT", "name": "BNB", "price": 612.34, "change": 1.89, "volume": "298M"},
        {"symbol": "ADAUSDT", "name": "Cardano", "price": 0.4567, "change": -2.34, "volume": "187M"},
        {"symbol": "XRPUSDT", "name": "XRP", "price": 0.5432, "change": 3.21, "volume": "654M"},
        {"symbol": "DOGEUSDT", "name": "Dogecoin", "price": 0.0876, "change": 8.45, "volume": "234M"},
        {"symbol": "AVAXUSDT", "name": "Avalanche", "price": 32.45, "change": -0.87, "volume": "156M"},
    ]
    
    context = {
        "request": request,
        "page_title": "Crypto Markets - Sofia V2",
        "current_page": "markets",
        "cryptos": cryptos,
    }
    return templates.TemplateResponse("markets.html", context)


@app.get("/trading", response_class=HTMLResponse)
async def trading_page(request: Request):
    """Trading sayfası - AI önerileri"""
    context = {
        "request": request,
        "page_title": "Trading Recommendations - Sofia V2",
        "current_page": "trading",
    }
    return templates.TemplateResponse("trading_recommendations.html", context)


@app.get("/manual-trading", response_class=HTMLResponse)
async def manual_trading_page(request: Request):
    """Manuel trading sayfası"""
    # Mock coin data for manual trading
    top_coins = [
        {"id": "bitcoin", "name": "Bitcoin", "symbol": "btc", "current_price": 67845.32, "image": "/static/btc.png", "market_cap_rank": 1, "price_change_percentage_24h": 2.45, "total_volume": 25600000000},
        {"id": "ethereum", "name": "Ethereum", "symbol": "eth", "current_price": 2456.78, "image": "/static/eth.png", "market_cap_rank": 2, "price_change_percentage_24h": -1.23, "total_volume": 18400000000},
        {"id": "solana", "name": "Solana", "symbol": "sol", "current_price": 156.43, "image": "/static/sol.png", "market_cap_rank": 3, "price_change_percentage_24h": 5.67, "total_volume": 12300000000},
        {"id": "bnb", "name": "BNB", "symbol": "bnb", "current_price": 612.34, "image": "/static/bnb.png", "market_cap_rank": 4, "price_change_percentage_24h": 1.89, "total_volume": 8900000000},
        {"id": "cardano", "name": "Cardano", "symbol": "ada", "current_price": 0.4567, "image": "/static/ada.png", "market_cap_rank": 5, "price_change_percentage_24h": -2.34, "total_volume": 6700000000},
        {"id": "xrp", "name": "XRP", "symbol": "xrp", "current_price": 0.5432, "image": "/static/xrp.png", "market_cap_rank": 6, "price_change_percentage_24h": 3.21, "total_volume": 15600000000},
        {"id": "dogecoin", "name": "Dogecoin", "symbol": "doge", "current_price": 0.0876, "image": "/static/doge.png", "market_cap_rank": 7, "price_change_percentage_24h": 8.45, "total_volume": 4500000000},
        {"id": "avalanche", "name": "Avalanche", "symbol": "avax", "current_price": 32.45, "image": "/static/avax.png", "market_cap_rank": 8, "price_change_percentage_24h": -0.87, "total_volume": 3200000000},
    ]
    
    total_volume = 156800000000  # $156.8B
    avg_change = 2.3  # +2.3%
    
    context = {
        "request": request,
        "page_title": "Manual Trading - Sofia V2", 
        "current_page": "manual-trading",
        "top_coins": top_coins,
        "total_volume": total_volume,
        "avg_change": avg_change,
    }
    return templates.TemplateResponse("manual_trading_simple.html", context)


@app.get("/reliability", response_class=HTMLResponse)
async def reliability_page(request: Request):
    """Güvenilirlik analizi sayfası"""
    context = {
        "request": request,
        "page_title": "AI Reliability Analysis - Sofia V2",
        "current_page": "reliability",
    }
    return templates.TemplateResponse("reliability.html", context)
>>>>>>> 96de1d9


# Backtest API endpoint - arkadaşının kullanacağı
@app.post("/api/backtest")
async def run_backtest(request: Request):
<<<<<<< HEAD
    """Backtest API endpoint - backend arkadaşının implement edeceği"""
    # Bu endpoint arkadaşının implement edeceği kısım
    # Şimdilik mock response dönüyoruz
    import random
    import time
    
    # Simulate processing time
    await asyncio.sleep(2)
    
    return {
        "status": "completed",
        "results": {
            "total_return": round(random.uniform(-10, 50), 1),
            "sharpe_ratio": round(random.uniform(0.5, 2.5), 2),
            "max_drawdown": round(random.uniform(-25, -5), 1),
            "win_rate": round(random.uniform(50, 80), 1),
            "total_trades": random.randint(10, 100),
            "equity_curve": [{"date": "2023-01-01", "value": 10000}] # Placeholder
        }
    }


# Missing main pages
@app.get("/portfolio", response_class=HTMLResponse)
async def portfolio_page(request: Request):
    """Portfolio sayfası - ROUTES ALWAYS OPEN guarantee"""
    total_balance = 12500.75  # Mock data
    
    context = {
        "request": request,
        "page_title": "Portfolio",
        "total_balance": total_balance
    }
    
    # Try main template first, fallback to stub
    try:
        return render(request, "portfolio.html", context)
    except:
        return render(request, "portfolio_stub.html", context)

@app.get("/markets", response_class=HTMLResponse) 
async def markets_page(request: Request):
    """Markets sayfası - ROUTES ALWAYS OPEN guarantee"""
    context = {
        "request": request,
        "page_title": "Crypto Markets"
    }
    
    # Try main template first, fallback to stub
    try:
        return render(request, "markets.html", context)
    except:
        return render(request, "markets_stub.html", context)

@app.get("/bist", response_class=HTMLResponse)
async def bist_page(request: Request):
    """BIST sayfası - ROUTES ALWAYS OPEN guarantee"""
    context = {
        "request": request,
        "page_title": "BIST Markets"
    }
    
    # Try main template first, fallback to stub
    try:
        return render(request, "bist_markets.html", context)
    except:
        return render(request, "bist_stub.html", context)

@app.get("/bist/analysis", response_class=HTMLResponse)
async def bist_analysis_page(request: Request):
    """BIST analiz sayfası"""
    try:
        template_path = Path("templates/bist_analysis.html")
        if template_path.exists():
            content = template_path.read_text(encoding='utf-8')
            return HTMLResponse(content=content)
        else:
            return HTMLResponse(content="<h1>BIST Analysis template not found</h1>")
    except Exception as e:
        return HTMLResponse(content=f"<h1>Error loading BIST Analysis: {str(e)}</h1>")

@app.get("/data-collection", response_class=HTMLResponse)
async def data_collection_page(request: Request):
    """Data collection sayfası"""
    try:
        template_path = Path("templates/data_collection.html")
        if template_path.exists():
            content = template_path.read_text(encoding='utf-8')
            return HTMLResponse(content=content)
        else:
            return HTMLResponse(content="<h1>Data Collection template not found</h1>")
    except Exception as e:
        return HTMLResponse(content=f"<h1>Error loading Data Collection: {str(e)}</h1>")

@app.get("/trading", response_class=HTMLResponse)
async def ai_trading_page(request: Request):
    """AI Trading sayfası"""
    try:
        template_path = Path("templates/ai_trading.html")
        if template_path.exists():
            content = template_path.read_text(encoding='utf-8')
            return HTMLResponse(content=content)
        else:
            return HTMLResponse(content="<h1>AI Trading template not found</h1>")
    except Exception as e:
        return HTMLResponse(content=f"<h1>Error loading AI Trading: {str(e)}</h1>")

@app.get("/manual-trading", response_class=HTMLResponse)
async def manual_trading_page(request: Request):
    """Manuel trading sayfası"""
    try:
        template_path = Path("templates/manual_trading.html")
        if template_path.exists():
            content = template_path.read_text(encoding='utf-8')
            return HTMLResponse(content=content)
        else:
            return HTMLResponse(content="<h1>Manual Trading template not found</h1>")
    except Exception as e:
        return HTMLResponse(content=f"<h1>Error loading Manual Trading: {str(e)}</h1>")

@app.get("/reliability", response_class=HTMLResponse)
async def reliability_page(request: Request):
    """Güvenilirlik sayfası"""
    try:
        template_path = Path("templates/reliability.html")
        if template_path.exists():
            content = template_path.read_text(encoding='utf-8')
            return HTMLResponse(content=content)
        else:
            return HTMLResponse(content="<h1>Reliability template not found</h1>")
    except Exception as e:
        return HTMLResponse(content=f"<h1>Error loading Reliability: {str(e)}</h1>")

# Compat redirects (307)
@app.get("/manual-trading")
async def compat_manual_trading():
    """Redirect old manual-trading URL"""
    return RedirectResponse(url="/trade/manual", status_code=307)

@app.get("/trading") 
async def compat_trading():
    """Redirect old trading URL"""
    return RedirectResponse(url="/trade/ai", status_code=307)

@app.get("/bist/analiz")
async def compat_bist_analiz():
    """Redirect Turkish analysis URL"""
    return RedirectResponse(url="/bist/analysis", status_code=307)

# Missing routes
@app.get("/ai-strategies", response_class=HTMLResponse)
async def ai_strategies_page(request: Request):
    """AI Strategies page - ROUTES ALWAYS OPEN"""
    context = {
        "request": request,
        "page_title": "AI Strategies"
    }
    return render(request, "ai_strategies.html", context)

@app.get("/showcase/{symbol}", response_class=HTMLResponse)
async def showcase_page(request: Request, symbol: str):
    """Showcase page for any symbol - ROUTES ALWAYS OPEN"""
    # Mock symbol data
    symbol_data = {
        "symbol": f"{symbol}/USDT",
        "name": symbol.upper(),
        "price": 67845.32 if symbol.upper() == "BTC" else 3456.78,
        "change": 2.45,
        "change_percent": 3.74,
        "volume": "28.5B"
    }
    
    context = {
        "request": request,
        "page_title": f"{symbol.upper()} Showcase",
        "symbol": symbol.upper(),
        "symbol_data": symbol_data,
        "news": get_mock_news(),
        "strategies": get_mock_strategies()
    }
    
    # Try main template first, fallback to stub
    try:
        return render(request, "showcase.html", context)
    except:
        return render(request, "showcase_stub.html", context)

@app.get("/api/template-resolution")
async def get_template_resolution():
    """Get template resolution report for debugging"""
    return get_resolution_report()
=======
    """Backtest API endpoint - gerçek backtester entegrasyonu"""
    try:
        # Parse request body
        body = await request.json()

        # Import backtester modules
        from datetime import datetime

        import pandas as pd

        from src.backtester.engine import BacktestEngine
        from src.backtester.metrics import calculate_metrics
        from src.backtester.strategies.bollinger_strategy import BollingerBandsStrategy
        from src.backtester.strategies.macd_strategy import MACDStrategy
        from src.backtester.strategies.rsi_strategy import RSIStrategy
        from src.backtester.strategies.sma import SMAStrategy
        from src.data_hub.data_fetcher import DataFetcher
        from src.data_hub.models import AssetType

        # Extract parameters
        symbol = body.get("symbol", "BTC-USD")
        strategy_name = body.get("strategy", "sma_cross")
        start_date = body.get("start_date", "2023-01-01")
        end_date = body.get("end_date", "2024-01-01")
        initial_capital = body.get("initial_capital", 10000)

        # Strategy-specific parameters
        strategy_params = {}
        if strategy_name == "sma_cross":
            strategy_params = {
                "fast_period": body.get("fast_sma", 20),
                "slow_period": body.get("slow_sma", 50),
            }
            strategy_instance = SMAStrategy()
        elif strategy_name == "rsi_mean_reversion":
            strategy_params = {
                "period": body.get("rsi_period", 14),
                "oversold": body.get("rsi_oversold", 30),
                "overbought": body.get("rsi_overbought", 70),
            }
            strategy_instance = RSIStrategy()
        elif strategy_name == "bollinger_bands":
            strategy_params = {
                "period": body.get("bb_period", 20),
                "std_dev": body.get("bb_std", 2),
            }
            strategy_instance = BollingerBandsStrategy()
        elif strategy_name == "macd_momentum":
            strategy_params = {
                "fast_period": body.get("macd_fast", 12),
                "slow_period": body.get("macd_slow", 26),
                "signal_period": body.get("macd_signal", 9),
            }
            strategy_instance = MACDStrategy()
        else:
            # Default to SMA
            strategy_instance = SMAStrategy()

        # Fetch historical data
        fetcher = DataFetcher()

        # Determine asset type from symbol
        if symbol in ["BTC-USD", "ETH-USD"]:
            asset_type = AssetType.CRYPTO
        else:
            asset_type = AssetType.STOCK

        # Get historical data
        try:
            data = fetcher.fetch_historical(
                symbol=symbol,
                asset_type=asset_type,
                start_date=datetime.strptime(start_date, "%Y-%m-%d"),
                end_date=datetime.strptime(end_date, "%Y-%m-%d"),
                interval="1d",
            )
        except:
            # Fallback to mock data if fetch fails
            dates = pd.date_range(start=start_date, end=end_date, freq="D")
            prices = [random.uniform(40000, 70000) for _ in range(len(dates))]
            data = pd.DataFrame(
                {
                    "open": prices,
                    "high": [p * 1.02 for p in prices],
                    "low": [p * 0.98 for p in prices],
                    "close": prices,
                    "volume": [random.uniform(1000000, 5000000) for _ in range(len(dates))],
                },
                index=dates,
            )

        # Run backtest
        engine = BacktestEngine(
            initial_capital=initial_capital,
            commission=body.get("commission", 0.001),
            slippage=body.get("slippage", 0.0001),
        )

        results = engine.run(data, strategy_instance, **strategy_params)

        # Calculate metrics
        metrics = calculate_metrics(
            equity_curve=results["equity_curve"],
            trades=results["trades"],
            initial_capital=initial_capital,
        )

        # Format equity curve for chart
        equity_curve_data = []
        for date, value in zip(data.index, results["equity_curve"], strict=False):
            equity_curve_data.append({"date": date.strftime("%Y-%m-%d"), "value": round(value, 2)})

        # Format trades for table
        formatted_trades = []
        for trade in results["trades"][:20]:  # Limit to 20 recent trades
            formatted_trades.append(
                {
                    "date": (
                        trade["timestamp"].strftime("%Y-%m-%d")
                        if hasattr(trade["timestamp"], "strftime")
                        else str(trade["timestamp"])
                    ),
                    "action": trade["type"],
                    "price": round(trade["price"], 2),
                    "quantity": round(trade["quantity"], 4),
                    "pnl": round(trade.get("pnl", 0), 2),
                }
            )

        return {
            "status": "completed",
            "results": {
                "total_return": round(metrics["total_return"], 1),
                "sharpe_ratio": round(metrics["sharpe_ratio"], 2),
                "max_drawdown": round(metrics["max_drawdown"], 1),
                "win_rate": round(metrics.get("win_rate", 50), 1),
                "total_trades": len(results["trades"]),
                "equity_curve": equity_curve_data,
                "trades": formatted_trades,
                "final_value": round(results["final_equity"], 2),
            },
        }
    except Exception as e:
        print(f"Backtest error: {e}")
        # Fallback to mock data on error
        import random

        await asyncio.sleep(2)

        return {
            "status": "completed",
            "results": {
                "total_return": round(random.uniform(-10, 50), 1),
                "sharpe_ratio": round(random.uniform(0.5, 2.5), 2),
                "max_drawdown": round(random.uniform(-25, -5), 1),
                "win_rate": round(random.uniform(50, 80), 1),
                "total_trades": random.randint(10, 100),
                "equity_curve": [{"date": "2023-01-01", "value": 10000}],
                "trades": [],
            },
        }


# Authentication routes (simple versions)
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page"""
    context = {"request": request}
    return templates.TemplateResponse("login.html", context)

@app.get("/pricing", response_class=HTMLResponse)  
async def pricing_page(request: Request):
    """Pricing page"""
    context = {"request": request}
    return templates.TemplateResponse("pricing.html", context)

@app.get("/subscription/success")
async def subscription_success(request: Request, session_id: str = None):
    """Subscription success page"""
    return RedirectResponse(url="/?success=subscription")

@app.get("/subscription/cancel")
async def subscription_cancel(request: Request):
    """Subscription cancel page"""
    return RedirectResponse(url="/pricing?cancelled=1")


# Trading API endpoints for dashboard and portfolio
@app.get("/api/trading/positions")
async def get_trading_positions():
    """Get current trading positions"""
    # Sofia V2 demo positions with realistic data
    positions = {
        "BTCUSDT": {
            "symbol": "BTCUSDT",
            "side": "long",
            "size": 0.15,
            "entry_price": 67200,
            "current_price": 67845.32,
            "unrealized_pnl": 96.75,
            "pnl_percent": 0.14,
            "timestamp": datetime.now().isoformat()
        },
        "ETHUSDT": {
            "symbol": "ETHUSDT", 
            "side": "long",
            "size": 2.5,
            "entry_price": 2420,
            "current_price": 2456.78,
            "unrealized_pnl": 91.95,
            "pnl_percent": 1.52,
            "timestamp": datetime.now().isoformat()
        },
        "SOLUSDT": {
            "symbol": "SOLUSDT",
            "side": "short", 
            "size": 8.0,
            "entry_price": 185.50,
            "current_price": 182.34,
            "unrealized_pnl": 25.28,
            "pnl_percent": 1.70,
            "timestamp": datetime.now().isoformat()
        }
    }
    
    return {
        "positions": positions,
        "total_pnl": sum(pos["unrealized_pnl"] for pos in positions.values()),
        "total_value": sum(pos["size"] * pos["current_price"] for pos in positions.values()),
        "active_trades": len(positions)
    }

@app.get("/api/trading/portfolio")
async def get_portfolio_data():
    """Get portfolio summary data - from unified API"""
    print("get_portfolio_data called")
    # Get real data from trading status API
    real_data = await get_real_trading_data()
    print(f"real_data = {real_data is not None}")
    
    if real_data:
        portfolio = real_data["portfolio"]
        positions = {
            pos["symbol"].replace("/", ""): {
                "symbol": pos["symbol"].replace("/", ""),
                "side": pos["side"],
                "size": pos["quantity"],
                "entry_price": pos["entry_price"],
                "current_price": pos["current_price"],
                "unrealized_pnl": pos["pnl"],
                "pnl_percent": pos["pnl_percentage"],
                "timestamp": datetime.now().isoformat()
            }
            for pos in real_data["positions"]
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
                {"name": "Mean Reversion", "status": "active", "pnl": 156.23},
                {"name": "Momentum Breakout", "status": "active", "pnl": -23.45}, 
                {"name": "Grid Trading", "status": "active", "pnl": 89.67}
            ]
        }
    
    # Fallback to mock data if API not available
    positions_data = await get_trading_positions()
    positions = positions_data["positions"]
    total_value = positions_data["total_value"]
    total_pnl = positions_data["total_pnl"]
    initial_value = total_value - total_pnl
    
    return {
        "total_balance": total_value,
        "available_balance": total_value * 0.3,
        "used_balance": total_value * 0.7,
        "daily_pnl": total_pnl,
        "daily_pnl_percent": (total_pnl / initial_value * 100) if initial_value > 0 else 0,
        "total_return": 12.5,
        "positions": positions,
        "active_strategies": [
            {"name": "Mean Reversion", "status": "active", "pnl": 156.23},
            {"name": "Momentum Breakout", "status": "active", "pnl": -23.45}, 
            {"name": "Grid Trading", "status": "active", "pnl": 89.67}
        ]
    }

@app.get("/api/trading/strategies")
async def get_trading_strategies():
    """Get trading strategies data"""
    strategies = [
        {
            "id": 1,
            "name": "Mean Reversion",
            "type": "mean_reversion", 
            "status": "active",
            "created_date": "2024-01-15",
            "performance": {
                "total_return": 15.8,
                "sharpe_ratio": 1.34,
                "max_drawdown": -8.2,
                "win_rate": 67.3
            },
            "parameters": {
                "rsi_period": 14,
                "oversold": 30,
                "overbought": 70,
                "stop_loss": 3.0
            },
            "description": "RSI-based mean reversion strategy for sideways markets"
        },
        {
            "id": 2,
            "name": "Momentum Breakout",
            "type": "momentum",
            "status": "active",
            "created_date": "2024-01-12", 
            "performance": {
                "total_return": 28.5,
                "sharpe_ratio": 1.89,
                "max_drawdown": -12.1,
                "win_rate": 58.2
            },
            "parameters": {
                "breakout_period": 20,
                "volume_threshold": 1.5,
                "stop_loss": 2.5
            },
            "description": "Volume-confirmed breakout strategy for trending markets"
        },
        {
            "id": 3,
            "name": "Scalping",
            "type": "scalping",
            "status": "testing",
            "created_date": "2024-01-10",
            "performance": {
                "total_return": 8.3,
                "sharpe_ratio": 0.92,
                "max_drawdown": -4.7,
                "win_rate": 71.5
            },
            "parameters": {
                "tick_size": 0.01,
                "profit_target": 0.5,
                "max_hold_time": 300
            },
            "description": "High-frequency scalping for quick profits"
        },
        {
            "id": 4,
            "name": "Grid Trading",
            "type": "grid",
            "status": "active", 
            "created_date": "2024-01-08",
            "performance": {
                "total_return": 22.1,
                "sharpe_ratio": 1.56,
                "max_drawdown": -9.8,
                "win_rate": 64.7
            },
            "parameters": {
                "grid_size": 1.0,
                "num_levels": 5,
                "order_size": 100
            },
            "description": "Grid-based strategy for ranging markets"
        },
        {
            "id": 5,
            "name": "Arbitrage",
            "type": "arbitrage",
            "status": "paused",
            "created_date": "2024-01-05",
            "performance": {
                "total_return": 5.2,
                "sharpe_ratio": 2.34,
                "max_drawdown": -1.8,
                "win_rate": 89.3
            },
            "parameters": {
                "min_spread": 0.1,
                "max_exposure": 1000,
                "timeout": 10
            },
            "description": "Cross-exchange arbitrage opportunities"
        },
        {
            "id": 6,
            "name": "ML-Enhanced Momentum", 
            "type": "ai_generated",
            "status": "active",
            "created_date": "2024-01-01",
            "performance": {
                "total_return": 31.7,
                "sharpe_ratio": 2.12,
                "max_drawdown": -7.4,
                "win_rate": 73.8
            },
            "parameters": {
                "ml_model": "random_forest",
                "features": 15,
                "lookback": 50,
                "confidence_threshold": 0.8
            },
            "description": "Machine learning enhanced momentum strategy"
        }
    ]
    
    return {"strategies": strategies}

@app.get("/api/trading/market-data")  
async def get_market_data():
    """Get market data for supported symbols"""
    # Sofia V2's supported symbols
    supported_symbols = [
        'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'ADAUSDT', 'LINKUSDT',
        'UNIUSDT', 'MATICUSDT', 'XRPUSDT', 'DOGEUSDT', 'BCHUSDT'
    ]
    
    # Get current crypto prices
    crypto_prices = await get_crypto_prices()
    
    prices = {}
    for symbol in supported_symbols:
        # Convert USDT format to -USD format for lookup
        lookup_symbol = symbol.replace('USDT', '-USD')
        if lookup_symbol in crypto_prices:
            crypto_data = crypto_prices[lookup_symbol]
            prices[symbol] = {
                "price": crypto_data["price"],
                "change_24h": crypto_data["change_percent"], 
                "volume_24h": crypto_data.get("volume", "0").replace("B", "e9").replace("M", "e6").replace("K", "e3"),
                "market_cap": crypto_data.get("market_cap", 0)
            }
    
    return {"prices": prices}


@app.get("/api/unified/portfolio")
async def get_unified_portfolio():
    """Get portfolio from unified system"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:8889/portfolio") as response:
                if response.status == 200:
                    return await response.json()
    except:
        return await get_portfolio_data()


@app.get("/api/unified/markets")
async def get_unified_markets():
    """Get market data from unified system"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:8889/portfolio") as response:
                if response.status == 200:
                    data = await response.json()
                    # Get price cache from unified system
                    return data.get("price_cache", {})
    except:
        return await get_crypto_prices()


# Missing API endpoints for frontend
@app.get("/api/alerts")
async def get_alerts(limit: int = 5):
    """Get recent alerts"""
    alerts = [
        {"id": 1, "type": "BUY", "symbol": "BTCUSDT", "price": 67845.32, "timestamp": "2024-08-26 10:30:00"},
        {"id": 2, "type": "SELL", "symbol": "ETHUSDT", "price": 2456.78, "timestamp": "2024-08-26 10:25:00"},
        {"id": 3, "type": "BUY", "symbol": "SOLUSDT", "price": 156.43, "timestamp": "2024-08-26 10:20:00"},
    ]
    return {"alerts": alerts[:limit]}


@app.get("/api/market-data-extended")
async def get_market_data_extended():
    """Extended market data for dashboard"""
    return {
        "total_market_cap": 2340000000000,
        "total_volume": 156800000000,
        "btc_dominance": 42.5,
        "eth_dominance": 18.2,
        "fear_greed_index": 67,
        "top_gainers": [
            {"symbol": "DOGE", "change": 8.45},
            {"symbol": "SOL", "change": 5.67},
            {"symbol": "XRP", "change": 3.21},
        ],
        "top_losers": [
            {"symbol": "ADA", "change": -2.34},
            {"symbol": "ETH", "change": -1.23},
            {"symbol": "AVAX", "change": -0.87},
        ]
    }
>>>>>>> 96de1d9


if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
