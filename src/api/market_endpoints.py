"""
Multi-asset market endpoints for crypto and equity trading
"""
from fastapi import APIRouter, HTTPException, Query
from decimal import Decimal
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

# External market data libraries
try:
    import ccxt
    CCXT_AVAILABLE = True
except ImportError:
    CCXT_AVAILABLE = False
    
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/market", tags=["market"])

# Initialize exchanges
binance = ccxt.binance() if CCXT_AVAILABLE else None

@router.get("/quotes")
async def get_quotes(symbols: str = Query(..., description="Comma-separated symbols like BTC/USDT,ETH/USDT,AAPL")):
    """
    Get real-time quotes for multiple assets (crypto and equity)
    """
    output = {}
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    
    for symbol in symbol_list:
        try:
            if "/" in symbol:  # Crypto pair
                if not CCXT_AVAILABLE or not binance:
                    output[symbol] = {
                        "price": "67500.00",  # Mock data
                        "type": "crypto",
                        "source": "mock"
                    }
                else:
                    ticker = binance.fetch_ticker(symbol)
                    output[symbol] = {
                        "price": str(Decimal(str(ticker["last"]))),
                        "type": "crypto",
                        "source": "binance",
                        "volume": str(Decimal(str(ticker.get("quoteVolume", 0)))),
                        "change_24h": str(Decimal(str(ticker.get("percentage", 0))))
                    }
            else:  # Equity symbol
                if not YFINANCE_AVAILABLE:
                    # Mock data for equities
                    mock_prices = {
                        "AAPL": "175.50",
                        "MSFT": "420.75",
                        "NVDA": "850.00",
                        "TSLA": "245.50"
                    }
                    output[symbol] = {
                        "price": mock_prices.get(symbol, "100.00"),
                        "type": "equity",
                        "source": "mock"
                    }
                else:
                    ticker = yf.Ticker(symbol)
                    info = ticker.info
                    price = info.get("regularMarketPrice") or info.get("currentPrice") or info.get("previousClose")
                    if price:
                        output[symbol] = {
                            "price": str(Decimal(str(price))),
                            "type": "equity",
                            "source": "yfinance",
                            "volume": str(info.get("regularMarketVolume", 0)),
                            "change_24h": str(info.get("regularMarketChangePercent", 0))
                        }
                    else:
                        output[symbol] = {"error": "Price not available", "type": "equity"}
        except Exception as e:
            logger.error(f"Error fetching {symbol}: {e}")
            output[symbol] = {"error": str(e)}
    
    return output

@router.get("/ohlcv")
async def get_ohlcv(
    symbol: str,
    timeframe: str = "1m",
    limit: int = 100
):
    """
    Get OHLCV data for a symbol
    """
    try:
        if "/" in symbol:  # Crypto
            if not CCXT_AVAILABLE or not binance:
                # Return mock OHLCV data
                return {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "data": [
                        [1234567890000, 67000, 67500, 66800, 67300, 1000],
                        [1234567950000, 67300, 67400, 67100, 67200, 900]
                    ]
                }
            else:
                ohlcv = binance.fetch_ohlcv(symbol, timeframe, limit=limit)
                return {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "data": ohlcv
                }
        else:  # Equity
            if not YFINANCE_AVAILABLE:
                return {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "data": []
                }
            else:
                ticker = yf.Ticker(symbol)
                period_map = {
                    "1m": "1d",
                    "5m": "5d",
                    "15m": "5d",
                    "1h": "1mo",
                    "1d": "1y"
                }
                period = period_map.get(timeframe, "1mo")
                hist = ticker.history(period=period)
                
                data = []
                for idx, row in hist.iterrows():
                    data.append([
                        int(idx.timestamp() * 1000),
                        float(row["Open"]),
                        float(row["High"]),
                        float(row["Low"]),
                        float(row["Close"]),
                        float(row["Volume"])
                    ])
                
                return {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "data": data
                }
    except Exception as e:
        logger.error(f"Error fetching OHLCV for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/assets/list")
async def list_assets(
    type: Optional[str] = Query(None, description="Filter by type: crypto or equity")
):
    """
    List available assets
    """
    assets = []
    
    # Crypto assets
    crypto_symbols = [
        {"symbol": "BTC/USDT", "name": "Bitcoin", "type": "crypto"},
        {"symbol": "ETH/USDT", "name": "Ethereum", "type": "crypto"},
        {"symbol": "BNB/USDT", "name": "Binance Coin", "type": "crypto"},
        {"symbol": "SOL/USDT", "name": "Solana", "type": "crypto"},
        {"symbol": "ADA/USDT", "name": "Cardano", "type": "crypto"},
        {"symbol": "AVAX/USDT", "name": "Avalanche", "type": "crypto"},
        {"symbol": "DOT/USDT", "name": "Polkadot", "type": "crypto"},
        {"symbol": "MATIC/USDT", "name": "Polygon", "type": "crypto"},
    ]
    
    # Equity assets
    equity_symbols = [
        {"symbol": "AAPL", "name": "Apple Inc.", "type": "equity"},
        {"symbol": "MSFT", "name": "Microsoft Corp.", "type": "equity"},
        {"symbol": "NVDA", "name": "NVIDIA Corp.", "type": "equity"},
        {"symbol": "TSLA", "name": "Tesla Inc.", "type": "equity"},
        {"symbol": "AMZN", "name": "Amazon.com Inc.", "type": "equity"},
        {"symbol": "GOOGL", "name": "Alphabet Inc.", "type": "equity"},
        {"symbol": "META", "name": "Meta Platforms Inc.", "type": "equity"},
        # BIST 30 samples
        {"symbol": "THYAO.IS", "name": "Turkish Airlines", "type": "equity"},
        {"symbol": "GARAN.IS", "name": "Garanti Bank", "type": "equity"},
        {"symbol": "AKBNK.IS", "name": "Akbank", "type": "equity"},
    ]
    
    if type == "crypto":
        assets = crypto_symbols
    elif type == "equity":
        assets = equity_symbols
    else:
        assets = crypto_symbols + equity_symbols
    
    return {"assets": assets, "total": len(assets)}

@router.get("/fx")
async def get_fx_rates():
    """
    Get foreign exchange rates
    """
    return {
        "rates": {
            "USDTRY": "34.50",
            "EURUSD": "1.08",
            "GBPUSD": "1.27",
            "USDEUR": "0.926",
            "TRYUSD": "0.029",
            "USDTUSD": "1.00"
        },
        "timestamp": datetime.utcnow().isoformat()
    }