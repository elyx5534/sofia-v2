"""
Advanced Data Fetching Module with Multiple Provider Support
Supports: yfinance, Binance, CoinGecko, Alpha Vantage
"""

import os
import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import json

import yfinance as yf
import pandas as pd
import requests
from functools import lru_cache
import aiohttp

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataProvider(Enum):
    YFINANCE = "yfinance"
    BINANCE = "binance"
    COINGECKO = "coingecko"
    ALPHAVANTAGE = "alphavantage"
    CACHE = "cache"

class DataFetcher:
    """
    Robust data fetching with multiple fallback providers
    """
    
    def __init__(self):
        self.cache = {}
        self.cache_duration = 60  # seconds
        self.binance_base = "https://api.binance.com/api/v3"
        self.coingecko_base = "https://api.coingecko.com/api/v3"
        self.providers_tried = []
        
    def _is_cache_valid(self, symbol: str) -> bool:
        """Check if cached data is still valid"""
        if symbol not in self.cache:
            return False
        
        cache_time = self.cache[symbol].get('timestamp')
        if not cache_time:
            return False
            
        return (datetime.now() - cache_time).seconds < self.cache_duration
    
    def _get_from_cache(self, symbol: str) -> Optional[Dict]:
        """Get data from cache if valid"""
        if self._is_cache_valid(symbol):
            logger.info(f"Cache hit for {symbol}")
            data = self.cache[symbol].copy()
            data['provider'] = DataProvider.CACHE.value
            return data
        return None
    
    def _save_to_cache(self, symbol: str, data: Dict):
        """Save data to cache"""
        data['timestamp'] = datetime.now()
        self.cache[symbol] = data
        
    async def fetch_yfinance(self, symbol: str) -> Optional[Dict]:
        """Fetch data from Yahoo Finance"""
        try:
            logger.info(f"Fetching {symbol} from yfinance")
            ticker = yf.Ticker(symbol)
            
            # Get historical data
            hist = ticker.history(period="1mo", interval="1d")
            if hist.empty:
                raise ValueError(f"No data returned for {symbol}")
            
            # Get current info
            info = ticker.info
            
            result = {
                "symbol": symbol,
                "provider": DataProvider.YFINANCE.value,
                "last_price": float(hist['Close'].iloc[-1]),
                "prices": hist['Close'].tolist()[-30:],
                "volumes": hist['Volume'].tolist()[-30:],
                "high_24h": float(hist['High'].tail(1).values[0]),
                "low_24h": float(hist['Low'].tail(1).values[0]),
                "change_24h": float(hist['Close'].iloc[-1] - hist['Close'].iloc[-2]),
                "change_percent_24h": float((hist['Close'].iloc[-1] / hist['Close'].iloc[-2] - 1) * 100),
                "market_cap": info.get('marketCap', 0),
                "volume_24h": float(hist['Volume'].iloc[-1]),
                "timestamp": datetime.now().isoformat()
            }
            
            self._save_to_cache(symbol, result)
            return result
            
        except Exception as e:
            logger.error(f"yfinance error for {symbol}: {str(e)}")
            return None
    
    async def fetch_binance(self, symbol: str) -> Optional[Dict]:
        """Fetch crypto data from Binance"""
        try:
            # Convert symbol format (BTC-USD -> BTCUSDT)
            binance_symbol = symbol.replace('-', '').replace('USD', 'USDT')
            
            logger.info(f"Fetching {binance_symbol} from Binance")
            
            async with aiohttp.ClientSession() as session:
                # Get ticker data
                ticker_url = f"{self.binance_base}/ticker/24hr?symbol={binance_symbol}"
                async with session.get(ticker_url) as response:
                    if response.status != 200:
                        raise ValueError(f"Binance API error: {response.status}")
                    ticker = await response.json()
                
                # Get klines (candlestick data)
                klines_url = f"{self.binance_base}/klines?symbol={binance_symbol}&interval=1d&limit=30"
                async with session.get(klines_url) as response:
                    if response.status != 200:
                        raise ValueError(f"Binance klines error: {response.status}")
                    klines = await response.json()
            
            prices = [float(k[4]) for k in klines]  # Close prices
            volumes = [float(k[5]) for k in klines]  # Volumes
            
            result = {
                "symbol": symbol,
                "provider": DataProvider.BINANCE.value,
                "last_price": float(ticker['lastPrice']),
                "prices": prices,
                "volumes": volumes,
                "high_24h": float(ticker['highPrice']),
                "low_24h": float(ticker['lowPrice']),
                "change_24h": float(ticker['priceChange']),
                "change_percent_24h": float(ticker['priceChangePercent']),
                "volume_24h": float(ticker['volume']),
                "timestamp": datetime.now().isoformat()
            }
            
            self._save_to_cache(symbol, result)
            return result
            
        except Exception as e:
            logger.error(f"Binance error for {symbol}: {str(e)}")
            return None
    
    async def fetch_coingecko(self, symbol: str) -> Optional[Dict]:
        """Fetch data from CoinGecko"""
        try:
            # Map common symbols to CoinGecko IDs
            symbol_map = {
                'BTC-USD': 'bitcoin',
                'ETH-USD': 'ethereum',
                'BNB-USD': 'binancecoin',
                'SOL-USD': 'solana',
                'ADA-USD': 'cardano'
            }
            
            coin_id = symbol_map.get(symbol)
            if not coin_id:
                return None
                
            logger.info(f"Fetching {coin_id} from CoinGecko")
            
            async with aiohttp.ClientSession() as session:
                # Get market data
                url = f"{self.coingecko_base}/coins/{coin_id}/market_chart?vs_currency=usd&days=30"
                async with session.get(url) as response:
                    if response.status != 200:
                        raise ValueError(f"CoinGecko API error: {response.status}")
                    data = await response.json()
                
                # Get current price
                price_url = f"{self.coingecko_base}/simple/price?ids={coin_id}&vs_currencies=usd&include_24hr_change=true&include_24hr_vol=true"
                async with session.get(price_url) as response:
                    current = await response.json()
            
            prices = [p[1] for p in data['prices'][-30:]]
            volumes = [v[1] for v in data['total_volumes'][-30:]]
            
            result = {
                "symbol": symbol,
                "provider": DataProvider.COINGECKO.value,
                "last_price": prices[-1],
                "prices": prices,
                "volumes": volumes,
                "high_24h": max(prices[-24:]) if len(prices) >= 24 else max(prices),
                "low_24h": min(prices[-24:]) if len(prices) >= 24 else min(prices),
                "change_percent_24h": current[coin_id]['usd_24h_change'],
                "volume_24h": current[coin_id]['usd_24h_vol'],
                "timestamp": datetime.now().isoformat()
            }
            
            result['change_24h'] = result['last_price'] * result['change_percent_24h'] / 100
            
            self._save_to_cache(symbol, result)
            return result
            
        except Exception as e:
            logger.error(f"CoinGecko error for {symbol}: {str(e)}")
            return None
    
    async def fetch_with_fallback(self, symbol: str) -> Dict:
        """
        Fetch data with automatic fallback mechanism
        Try: Cache -> yfinance -> Binance -> CoinGecko
        """
        self.providers_tried = []
        
        # Check cache first
        cached = self._get_from_cache(symbol)
        if cached:
            return cached
        
        # Try providers in order
        providers = [
            (DataProvider.YFINANCE, self.fetch_yfinance),
            (DataProvider.BINANCE, self.fetch_binance),
            (DataProvider.COINGECKO, self.fetch_coingecko)
        ]
        
        for provider_name, fetch_func in providers:
            self.providers_tried.append(provider_name.value)
            try:
                result = await fetch_func(symbol)
                if result:
                    result['providers_tried'] = self.providers_tried
                    logger.info(f"Successfully fetched {symbol} from {provider_name.value}")
                    return result
            except Exception as e:
                logger.error(f"Provider {provider_name.value} failed: {str(e)}")
                continue
        
        # If all fail, return error response
        return {
            "symbol": symbol,
            "error": "All data providers failed",
            "providers_tried": self.providers_tried,
            "last_price": 0,
            "prices": [],
            "timestamp": datetime.now().isoformat()
        }
    
    async def fetch_multiple(self, symbols: List[str]) -> Dict[str, Dict]:
        """Fetch data for multiple symbols concurrently"""
        tasks = [self.fetch_with_fallback(symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks)
        return {symbol: result for symbol, result in zip(symbols, results)}

# Singleton instance
data_fetcher = DataFetcher()

async def get_market_data(symbol: str) -> Dict:
    """Main function to get market data"""
    return await data_fetcher.fetch_with_fallback(symbol)

async def get_portfolio_data(symbols: List[str]) -> Dict[str, Dict]:
    """Get data for multiple symbols"""
    return await data_fetcher.fetch_multiple(symbols)