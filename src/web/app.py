"""
FastAPI web application for Sofia V2 Global Crypto Scanner
"""
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import json
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import pandas as pd
from loguru import logger

from ..data.pipeline import data_pipeline
from ..scan.scanner import scanner
from ..news.aggregator import news_aggregator
from ..metrics.indicators import add_all_indicators


# Create FastAPI app
app = FastAPI(
    title="Sofia V2 - Global Crypto Scanner",
    description="Real-time cryptocurrency signal scanning and analysis",
    version="1.0.0"
)

# Mount static files
static_dir = Path(__file__).parent.parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Setup templates
templates_dir = Path(__file__).parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

# Outputs directory
outputs_dir = Path(__file__).parent.parent.parent / "outputs"


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page redirect to signals"""
    return templates.TemplateResponse("signals.html", {
        "request": request,
        "title": "Sofia V2 - Crypto Scanner"
    })


@app.get("/signals", response_class=HTMLResponse)
async def signals_page(request: Request):
    """Signals page with filtering and sorting"""
    return templates.TemplateResponse("signals.html", {
        "request": request,
        "title": "Crypto Signals"
    })


@app.get("/heatmap", response_class=HTMLResponse)
async def heatmap_page(request: Request):
    """Heatmap visualization page"""
    return templates.TemplateResponse("heatmap.html", {
        "request": request,
        "title": "Signal Heatmap"
    })


@app.get("/chart/{symbol}", response_class=HTMLResponse)
async def chart_page(request: Request, symbol: str):
    """Interactive chart page for a symbol"""
    return templates.TemplateResponse("chart.html", {
        "request": request,
        "title": f"{symbol} Chart",
        "symbol": symbol
    })


@app.get("/news", response_class=HTMLResponse)
async def news_page(request: Request):
    """News aggregation page"""
    return templates.TemplateResponse("news.html", {
        "request": request,
        "title": "Crypto News"
    })


# API Endpoints

@app.get("/api/signals")
async def api_signals():
    """Get current signals data"""
    try:
        signals_file = outputs_dir / "signals.json"
        
        if not signals_file.exists():
            return {"signals": [], "last_updated": None}
            
        with open(signals_file, 'r') as f:
            data = json.load(f)
            
        # Add last modified timestamp
        last_updated = datetime.fromtimestamp(signals_file.stat().st_mtime).isoformat()
        
        return {
            "signals": data if isinstance(data, list) else [],
            "last_updated": last_updated,
            "total_count": len(data) if isinstance(data, list) else 0
        }
        
    except Exception as e:
        logger.error(f"Error loading signals: {e}")
        raise HTTPException(status_code=500, detail="Failed to load signals data")


@app.get("/api/heatmap")
async def api_heatmap():
    """Get heatmap data with scores"""
    try:
        signals_file = outputs_dir / "signals.json"
        
        if not signals_file.exists():
            return {"heatmap_data": []}
            
        with open(signals_file, 'r') as f:
            signals = json.load(f)
            
        # Create heatmap data
        heatmap_data = []
        
        for signal in signals[:100]:  # Limit to top 100
            symbol = signal.get('symbol', '')
            score = signal.get('score', 0)
            
            if score > 0:
                heatmap_data.append({
                    'symbol': symbol,
                    'score': score,
                    'color_intensity': min(score / 5.0, 1.0),  # Normalize for color
                    'price': signal.get('indicators', {}).get('close', 0),
                    'change_24h': signal.get('indicators', {}).get('price_change_24h', 0)
                })
                
        return {"heatmap_data": heatmap_data}
        
    except Exception as e:
        logger.error(f"Error creating heatmap: {e}")
        raise HTTPException(status_code=500, detail="Failed to create heatmap data")


@app.get("/api/ohlcv")
async def api_ohlcv(symbol: str = Query(...), timeframe: str = Query("1h", regex="^(1h|1d)$")):
    """Get OHLCV data for a symbol"""
    try:
        df = data_pipeline.get_symbol_data(symbol, timeframe)
        
        if df.empty:
            raise HTTPException(status_code=404, detail=f"No data found for {symbol}")
            
        # Add indicators
        df_with_indicators = add_all_indicators(df)
        
        # Convert to format suitable for lightweight-charts
        chart_data = []
        
        for idx, row in df_with_indicators.iterrows():
            chart_data.append({
                'time': int(idx.timestamp()),
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': float(row['volume']),
                # Indicators
                'rsi': float(row.get('rsi', 50)),
                'sma_20': float(row.get('sma_20', row['close'])),
                'sma_50': float(row.get('sma_50', row['close'])),
                'bb_upper': float(row.get('bb_upper', row['close'])),
                'bb_middle': float(row.get('bb_middle', row['close'])),
                'bb_lower': float(row.get('bb_lower', row['close'])),
                'macd': float(row.get('macd', 0)),
                'macd_signal': float(row.get('macd_signal', 0))
            })
            
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "data": chart_data,
            "total_records": len(chart_data)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching OHLCV for {symbol}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch chart data")


@app.get("/api/news")
async def api_news(symbol: Optional[str] = Query(None), limit: int = Query(20, ge=1, le=100)):
    """Get news data"""
    try:
        if symbol:
            # Symbol-specific news
            news_data = news_aggregator.get_symbol_news(symbol)
        else:
            # Global news
            news_data = news_aggregator.get_latest_news(limit)
            
        return {
            "news": news_data,
            "symbol": symbol,
            "total_count": len(news_data)
        }
        
    except Exception as e:
        logger.error(f"Error fetching news: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch news data")


@app.get("/api/status")
async def api_status():
    """Get system status"""
    try:
        # Check available symbols
        available_symbols = data_pipeline.get_available_symbols()
        
        # Check signals file age
        signals_file = outputs_dir / "signals.json"
        signals_age = None
        
        if signals_file.exists():
            signals_age = (datetime.now() - 
                         datetime.fromtimestamp(signals_file.stat().st_mtime)).total_seconds()
                         
        # Check news file age
        news_file = outputs_dir / "news" / "global.json"
        news_age = None
        
        if news_file.exists():
            news_age = (datetime.now() - 
                       datetime.fromtimestamp(news_file.stat().st_mtime)).total_seconds()
                       
        return {
            "status": "healthy",
            "available_symbols": len(available_symbols),
            "signals_age_seconds": signals_age,
            "news_age_seconds": news_age,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@app.get("/api/search")
async def api_search(q: str = Query(..., min_length=2), limit: int = Query(10)):
    """Search symbols"""
    try:
        available_symbols = data_pipeline.get_available_symbols()
        query = q.upper()
        
        # Search symbols
        matching_symbols = [
            symbol for symbol in available_symbols 
            if query in symbol or query in symbol.replace('/', '')
        ][:limit]
        
        return {
            "query": q,
            "results": matching_symbols,
            "total_count": len(matching_symbols)
        }
        
    except Exception as e:
        logger.error(f"Error searching symbols: {e}")
        raise HTTPException(status_code=500, detail="Search failed")


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Custom 404 handler"""
    return templates.TemplateResponse("404.html", {
        "request": request,
        "title": "Page Not Found"
    }, status_code=404)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)