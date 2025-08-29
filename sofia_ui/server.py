"""
Sofia V2 - Web UI Server
Modern ve profesyonel trading stratejisi arayüzü
"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import asyncio
from pathlib import Path
import random
from datetime import datetime
import os
import sys
from sofia_ui.live_data import live_data_service
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.api.paper_trading import router as paper_trading_router

# FastAPI uygulaması
app = FastAPI(
    title="Sofia V2 - Trading Strategy Platform",
    description="Akıllı trading stratejileri ve backtest platformu",
    version="2.0.0"
)

# Include paper trading routes
app.include_router(paper_trading_router)

# Static dosyalar ve template'ler
static_path = Path(__file__).parent / "static"
template_path = Path(__file__).parent / "templates"

app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
templates = Jinja2Templates(directory=str(template_path))


# Mock data functions
async def get_live_btc_data():
    """BTC için canlı veri döndürür"""
    try:
        return await live_data_service.get_live_price("BTC/USDT")
    except Exception as e:
        print(f"Live data error: {e}")
        # Fallback to mock data
        return {
            "symbol": "BTC/USDT",
            "name": "Bitcoin",
            "price": 67845.32,
            "change": 2.45,
            "change_percent": 3.74,
            "volume": "28.5B",
            "high_24h": 68500.0,
            "low_24h": 67200.0,
            "last_updated": datetime.now().strftime("%H:%M:%S")
        }


def get_mock_news():
    """Mock haber verisi döndürür"""
    return [
        {
            "title": "Bitcoin ETF'ler Rekor Giriş Görüyor",
            "summary": "Kurumsal yatırımcılar Bitcoin ETF'lerine olan ilgilerini artırıyor...",
            "url": "https://www.coindesk.com/markets/2024/01/15/bitcoin-etf-inflows/",
            "source": "CoinDesk",
            "time": "2 saat önce"
        },
        {
            "title": "MicroStrategy Bitcoin Alımlarını Sürdürüyor",
            "summary": "Şirket hazine stratejisinin bir parçası olarak Bitcoin biriktirmeye devam ediyor...",
            "url": "https://www.bloomberg.com/news/articles/2024/01/15/microstrategy-continues-bitcoin-buying/",
            "source": "Bloomberg",
            "time": "4 saat önce"
        },
        {
            "title": "Fed Faiz Kararı Kripto Piyasalarını Etkiliyor",
            "summary": "Merkez bankası politikaları dijital varlık fiyatlarında dalgalanmaya neden oluyor...",
            "url": "https://www.reuters.com/business/finance/fed-decision-impacts-crypto-markets/",
            "source": "Reuters",
            "time": "6 saat önce"
        }
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
            "color": "bg-emerald-500"
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
            "color": "bg-blue-500"
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
            "color": "bg-amber-500"
        }
    ]


# Routes
@app.get("/", response_class=HTMLResponse)
async def homepage(request: Request):
    """Ana sayfa"""
    try:
        btc_data = await get_live_btc_data()
    except:
        btc_data = {
            "symbol": "BTC/USDT",
            "name": "Bitcoin",
            "price": 67845.32,
            "change": 2.45,
            "change_percent": 3.74,
            "volume": "28.5B",
            "last_updated": datetime.now().strftime("%H:%M:%S")
        }
    
    context = {
        "request": request,
        "page_title": "Sofia V2 - Trading Platform",
        "btc_data": btc_data,
        "featured_strategies": get_mock_strategies()[:2],
        "latest_news": get_mock_news()[:3]
    }
    return templates.TemplateResponse("homepage.html", context)


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
            "bollinger_lower": 65200.0
        }
    }
    return templates.TemplateResponse("showcase.html", context)


@app.get("/cards", response_class=HTMLResponse)
async def strategy_cards(request: Request):
    """Strateji kartları sayfası - teknik planda belirtilen"""
    context = {
        "request": request,
        "page_title": "Strategy Cards",
        "strategies": get_mock_strategies()
    }
    return templates.TemplateResponse("cards.html", context)


@app.get("/analysis/{symbol}", response_class=HTMLResponse)
async def analysis(request: Request, symbol: str):
    """Detaylı analiz sayfası - orta vadeli hedef"""
    btc_data = get_mock_btc_data()
    btc_data["symbol"] = symbol.upper()
    
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
            "bollinger_lower": 65200.0
        },
        "fundamental_data": {
            "market_cap": "1.34T",
            "volume_24h": "28.5B",
            "circulating_supply": "19.8M",
            "max_supply": "21M",
            "fear_greed_index": 72
        },
        "prediction": {
            "direction": "up",
            "confidence": 0.73,
            "target_1w": 71000,
            "target_1m": 75000
        }
    }
    return templates.TemplateResponse("analysis.html", context)


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
    return {
        "symbol": symbol.upper(),
        "news": get_mock_news()
    }


@app.get("/api/quotes")
async def get_multiple_quotes(symbols: str = "BTC-USD,ETH-USD,AAPL"):
    """Çoklu fiyat bilgisi API"""
    try:
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
                "name": "Ethereum",
                "price": 3456.78,
                "change": 45.67,
                "change_percent": 1.34,
                "volume": "15.2B",
                "last_updated": datetime.now().strftime("%H:%M:%S"),
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
    try:
        symbol_data = live_data_service.get_live_price(symbol.upper())
    except:
        symbol_data = get_live_btc_data()
        symbol_data["symbol"] = symbol.upper()
    
    context = {
        "request": request,
        "page_title": f"{symbol.upper()} - Asset Details",
        "symbol_data": symbol_data,
        "news": get_mock_news(),
        "technical_indicators": {
            "rsi": 45.6,
            "macd": 234.5,
            "sma_20": 66234.45,
            "sma_50": 64567.89,
            "bollinger_upper": 68500.0,
            "bollinger_lower": 65200.0
        },
        "fundamental_data": {
            "market_cap": "1.34T",
            "volume_24h": "28.5B",
            "fear_greed_index": 72
        }
    }
    return templates.TemplateResponse("assets_detail.html", context)


@app.get("/backtest", response_class=HTMLResponse)
async def backtest_page(request: Request, symbol: str = None, strategy: str = None):
    """Backtest sayfası - UI planında belirtilen"""
    context = {
        "request": request,
        "page_title": "Backtest Strategy",
        "preselected_symbol": symbol,
        "preselected_strategy": strategy
    }
    return templates.TemplateResponse("backtest.html", context)


@app.get("/strategies", response_class=HTMLResponse)
async def strategies_page(request: Request):
    """Stratejiler sayfası - UI planında belirtilen"""
    context = {
        "request": request,
        "page_title": "Trading Strategies"
    }
    return templates.TemplateResponse("strategies.html", context)


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Settings page with paper trading control"""
    context = {
        "request": request,
        "page_title": "Settings - Paper Trading Control"
    }
    return templates.TemplateResponse("settings.html", context)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """Paper trading dashboard with live metrics"""
    context = {
        "request": request,
        "page_title": "Paper Trading Dashboard"
    }
    return templates.TemplateResponse("dashboard.html", context)


# Backtest API endpoint - arkadaşının kullanacağı
@app.post("/api/backtest")
async def run_backtest(request: Request):
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


if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
