"""
Equity Market Endpoints for Sofia V2
Support for BIST30 and US equities using yfinance
"""

import json
import logging
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
import yfinance as yf
from pathlib import Path
import asyncio
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/assets", tags=["equities"])

# Load equity symbols
EQUITY_DATA_PATH = Path(__file__).parent.parent.parent / "data" / "symbols_equity.json"

def load_equity_symbols() -> Dict[str, List[Dict[str, str]]]:
    """Load equity symbols from JSON file"""
    try:
        with open(EQUITY_DATA_PATH, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load equity symbols: {e}")
        return {}

EQUITY_SYMBOLS = load_equity_symbols()

# Flatten all symbols for quick lookup
ALL_EQUITY_SYMBOLS = {}
for category, symbols in EQUITY_SYMBOLS.items():
    for symbol_data in symbols:
        ALL_EQUITY_SYMBOLS[symbol_data["symbol"]] = {
            **symbol_data,
            "category": category
        }

# Thread pool for yfinance calls
executor = ThreadPoolExecutor(max_workers=10)


class EquityInfo(BaseModel):
    symbol: str
    name: str
    sector: str
    category: str
    price: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None
    volume: Optional[int] = None
    market_cap: Optional[float] = None
    
class MarketQuote(BaseModel):
    symbol: str
    price: float
    timestamp: str
    source: str = "yfinance"


def fetch_yfinance_price(symbol: str) -> Optional[Dict[str, Any]]:
    """Fetch price data from yfinance"""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        
        # Get last price
        last_price = info.last_price if hasattr(info, 'last_price') else None
        
        # Try to get from history if fast_info fails
        if last_price is None or last_price == 0:
            hist = ticker.history(period="1d", interval="1m")
            if not hist.empty:
                last_price = float(hist['Close'].iloc[-1])
        
        if last_price and last_price > 0:
            # Get additional info if available
            prev_close = info.previous_close if hasattr(info, 'previous_close') else None
            volume = info.last_volume if hasattr(info, 'last_volume') else None
            market_cap = info.market_cap if hasattr(info, 'market_cap') else None
            
            change = None
            change_pct = None
            if prev_close and prev_close > 0:
                change = last_price - prev_close
                change_pct = (change / prev_close) * 100
            
            return {
                "price": last_price,
                "change": change,
                "change_pct": change_pct,
                "volume": volume,
                "market_cap": market_cap,
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        logger.warning(f"Failed to fetch price for {symbol}: {e}")
    
    return None


async def fetch_price_async(symbol: str) -> Optional[Dict[str, Any]]:
    """Async wrapper for yfinance price fetch"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, fetch_yfinance_price, symbol)


@router.get("/list")
async def list_assets(
    type: str = Query("all", description="Asset type: equity, crypto, or all"),
    category: Optional[str] = Query(None, description="Category filter (e.g., BIST30, US_MEGA_TECH)")
) -> Dict[str, List[EquityInfo]]:
    """List available assets with optional filtering"""
    
    if type == "crypto":
        # Return empty for now, crypto handled elsewhere
        return {"assets": []}
    
    result = []
    
    if category:
        # Filter by specific category
        if category in EQUITY_SYMBOLS:
            for symbol_data in EQUITY_SYMBOLS[category]:
                result.append(EquityInfo(
                    symbol=symbol_data["symbol"],
                    name=symbol_data["name"],
                    sector=symbol_data["sector"],
                    category=category
                ))
    else:
        # Return all equities
        for symbol, data in ALL_EQUITY_SYMBOLS.items():
            result.append(EquityInfo(
                symbol=symbol,
                name=data["name"],
                sector=data["sector"],
                category=data["category"]
            ))
    
    return {"assets": result}


@router.get("/categories")
async def list_categories() -> Dict[str, List[str]]:
    """List available equity categories"""
    return {
        "categories": list(EQUITY_SYMBOLS.keys()),
        "descriptions": {
            "BIST30": "Turkish Stock Exchange Top 30",
            "US_MEGA_TECH": "US Technology Giants",
            "US_FINANCE": "US Financial Sector",
            "US_HEALTHCARE": "US Healthcare & Pharma",
            "US_ENERGY": "US Energy Sector",
            "US_CONSUMER": "US Consumer Goods & Services",
            "US_INDUSTRIAL": "US Industrial Sector"
        }
    }


@router.get("/quote/{symbol}")
async def get_quote(symbol: str) -> MarketQuote:
    """Get real-time quote for a specific symbol"""
    
    # Validate symbol exists
    if symbol not in ALL_EQUITY_SYMBOLS:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")
    
    # Fetch price
    price_data = await fetch_price_async(symbol)
    
    if not price_data or not price_data.get("price"):
        raise HTTPException(status_code=503, detail=f"Unable to fetch price for {symbol}")
    
    return MarketQuote(
        symbol=symbol,
        price=price_data["price"],
        timestamp=price_data["timestamp"]
    )


@router.post("/quotes")
async def get_bulk_quotes(symbols: List[str]) -> Dict[str, List[MarketQuote]]:
    """Get quotes for multiple symbols"""
    
    # Limit to 50 symbols per request
    if len(symbols) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 symbols per request")
    
    # Filter valid symbols
    valid_symbols = [s for s in symbols if s in ALL_EQUITY_SYMBOLS]
    
    if not valid_symbols:
        return {"quotes": []}
    
    # Fetch prices concurrently
    tasks = [fetch_price_async(symbol) for symbol in valid_symbols]
    results = await asyncio.gather(*tasks)
    
    quotes = []
    for symbol, price_data in zip(valid_symbols, results):
        if price_data and price_data.get("price"):
            quotes.append(MarketQuote(
                symbol=symbol,
                price=price_data["price"],
                timestamp=price_data["timestamp"]
            ))
    
    return {"quotes": quotes}


@router.get("/search")
async def search_assets(
    q: str = Query(..., description="Search query"),
    limit: int = Query(20, description="Maximum results")
) -> Dict[str, List[EquityInfo]]:
    """Search for assets by symbol or name"""
    
    query = q.upper()
    results = []
    
    for symbol, data in ALL_EQUITY_SYMBOLS.items():
        # Search in symbol and name
        if query in symbol.upper() or query in data["name"].upper():
            results.append(EquityInfo(
                symbol=symbol,
                name=data["name"],
                sector=data["sector"],
                category=data["category"]
            ))
            
            if len(results) >= limit:
                break
    
    return {"results": results}


@router.get("/market/overview")
async def market_overview() -> Dict[str, Any]:
    """Get market overview with major indices"""
    
    # Define major indices to track
    indices = {
        "^GSPC": "S&P 500",
        "^DJI": "Dow Jones",
        "^IXIC": "NASDAQ",
        "^VIX": "VIX",
        "XU100.IS": "BIST 100",
        "^FTSE": "FTSE 100",
        "^GDAXI": "DAX",
        "^N225": "Nikkei 225"
    }
    
    # Fetch index prices
    tasks = [fetch_price_async(symbol) for symbol in indices.keys()]
    results = await asyncio.gather(*tasks)
    
    overview = {}
    for (symbol, name), price_data in zip(indices.items(), results):
        if price_data:
            overview[symbol] = {
                "name": name,
                "price": price_data.get("price"),
                "change": price_data.get("change"),
                "change_pct": price_data.get("change_pct")
            }
    
    return {
        "indices": overview,
        "timestamp": datetime.now().isoformat()
    }