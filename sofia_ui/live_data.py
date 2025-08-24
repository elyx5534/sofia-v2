"""
Sofia V2 - Live Data Service
Canlı fiyat ve piyasa verilerini çeken servis
"""

import yfinance as yf
import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import asyncio
import logging

# Logging ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LiveDataService:
    """Canlı veri servisi"""
    
    def __init__(self):
        self.cache = {}
        self.cache_duration = 60  # 60 saniye cache
        
        # Desteklenen crypto coinler
        self.supported_cryptos = [
            "BTC-USD", "ETH-USD", "SOL-USD", "LTC-USD", "ADA-USD", 
            "DOT-USD", "LINK-USD", "UNI-USD", "AVAX-USD", "MATIC-USD",
            "XRP-USD", "DOGE-USD", "SHIB-USD", "BCH-USD", "XLM-USD"
        ]
        
    def get_live_price(self, symbol: str) -> Dict:
        """
        Canlı fiyat verisi al
        
        Args:
            symbol: Ticker symbolu (örn: BTC-USD, AAPL)
            
        Returns:
            Dict: Fiyat ve değişim bilgileri
        """
        try:
            # Cache kontrolü
            cache_key = f"price_{symbol}"
            if self._is_cached(cache_key):
                return self.cache[cache_key]['data']
            
            # YFinance ile veri çek
            ticker = yf.Ticker(symbol)
            info = ticker.info
            hist = ticker.history(period="2d")
            
            if hist.empty:
                return self._get_fallback_data(symbol)
            
            current_price = hist['Close'].iloc[-1]
            previous_price = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
            
            change = current_price - previous_price
            change_percent = (change / previous_price) * 100 if previous_price != 0 else 0
            
            # Volume - son 24h
            volume = hist['Volume'].iloc[-1] if 'Volume' in hist.columns else 0
            
            data = {
                "symbol": symbol,
                "name": info.get('longName', symbol),
                "price": float(current_price),
                "change": float(change),
                "change_percent": round(float(change_percent), 2),
                "volume": self._format_volume(float(volume)),
                "market_cap": info.get('marketCap', 'N/A'),
                "last_updated": datetime.now().strftime("%H:%M:%S"),
                "currency": info.get('currency', 'USD'),
                "sector": info.get('sector', 'Unknown')
            }
            
            # Cache'e kaydet
            self._cache_data(cache_key, data)
            
            logger.info(f"Live price fetched for {symbol}: ${current_price:.2f}")
            return data
            
        except Exception as e:
            logger.error(f"Error fetching live price for {symbol}: {str(e)}")
            return self._get_fallback_data(symbol)
    
    def get_crypto_prices(self) -> Dict[str, Dict]:
        """
        Tüm desteklenen crypto coinlerin fiyatlarını al
        """
        results = {}
        
        try:
            # Paralel olarak veri çek
            tickers = yf.Tickers(' '.join(self.supported_cryptos))
            
            for symbol in self.supported_cryptos:
                try:
                    ticker = tickers.tickers[symbol]
                    hist = ticker.history(period="2d")
                    
                    if not hist.empty:
                        current_price = hist['Close'].iloc[-1]
                        previous_price = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
                        
                        change = current_price - previous_price
                        change_percent = (change / previous_price) * 100 if previous_price != 0 else 0
                        
                        # Coin adını al
                        coin_name = self._get_coin_name(symbol)
                        
                        results[symbol] = {
                            "symbol": symbol,
                            "name": coin_name,
                            "price": float(current_price),
                            "change": float(change),
                            "change_percent": round(float(change_percent), 2),
                            "volume": self._format_volume(float(hist['Volume'].iloc[-1]) if 'Volume' in hist.columns else 0),
                            "last_updated": datetime.now().strftime("%H:%M:%S"),
                            "icon": self._get_coin_icon(symbol)
                        }
                    else:
                        results[symbol] = self._get_fallback_data(symbol)
                        
                except Exception as e:
                    logger.error(f"Error fetching {symbol}: {str(e)}")
                    results[symbol] = self._get_fallback_data(symbol)
                    
            return results
            
        except Exception as e:
            logger.error(f"Error in batch crypto fetch: {str(e)}")
            return {symbol: self._get_fallback_data(symbol) for symbol in self.supported_cryptos}
    
    def get_chart_data(self, symbol: str, period: str = "1mo") -> Dict:
        """
        Grafik verisi al
        
        Args:
            symbol: Ticker symbolu
            period: Zaman periyodu (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
        """
        try:
            cache_key = f"chart_{symbol}_{period}"
            if self._is_cached(cache_key):
                return self.cache[cache_key]['data']
            
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period)
            
            if hist.empty:
                return self._get_fallback_chart_data(symbol)
            
            # Chart.js formatında veri hazırla
            chart_data = {
                "labels": [date.strftime("%Y-%m-%d") for date in hist.index],
                "datasets": [{
                    "label": f"{symbol} Price",
                    "data": hist['Close'].tolist(),
                    "borderColor": self._get_chart_color(symbol),
                    "backgroundColor": self._get_chart_color(symbol, alpha=0.1),
                    "borderWidth": 2,
                    "fill": True,
                    "tension": 0.4
                }]
            }
            
            # İstatistikler
            stats = {
                "current_price": float(hist['Close'].iloc[-1]),
                "price_change": float(hist['Close'].iloc[-1] - hist['Close'].iloc[0]),
                "price_change_percent": float(((hist['Close'].iloc[-1] - hist['Close'].iloc[0]) / hist['Close'].iloc[0]) * 100),
                "high": float(hist['High'].max()),
                "low": float(hist['Low'].min()),
                "volume": self._format_volume(float(hist['Volume'].sum())),
                "period": period
            }
            
            data = {
                "chart_data": chart_data,
                "stats": stats,
                "symbol": symbol,
                "name": self._get_coin_name(symbol)
            }
            
            # Cache'e kaydet
            self._cache_data(cache_key, data)
            
            return data
            
        except Exception as e:
            logger.error(f"Error fetching chart data for {symbol}: {str(e)}")
            return self._get_fallback_chart_data(symbol)
    
    def get_multiple_prices(self, symbols: List[str]) -> Dict[str, Dict]:
        """
        Birden fazla sembol için fiyat al
        
        Args:
            symbols: Sembol listesi
            
        Returns:
            Dict: Sembol -> fiyat bilgisi mapping
        """
        results = {}
        
        try:
            # Paralel olarak veri çek
            tickers = yf.Tickers(' '.join(symbols))
            
            for symbol in symbols:
                try:
                    ticker = tickers.tickers[symbol]
                    hist = ticker.history(period="2d")
                    
                    if not hist.empty:
                        current_price = hist['Close'].iloc[-1]
                        previous_price = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
                        
                        change = current_price - previous_price
                        change_percent = (change / previous_price) * 100 if previous_price != 0 else 0
                        
                        results[symbol] = {
                            "symbol": symbol,
                            "price": float(current_price),
                            "change": float(change),
                            "change_percent": round(float(change_percent), 2),
                            "last_updated": datetime.now().strftime("%H:%M:%S")
                        }
                    else:
                        results[symbol] = self._get_fallback_data(symbol)
                        
                except Exception as e:
                    logger.error(f"Error fetching {symbol}: {str(e)}")
                    results[symbol] = self._get_fallback_data(symbol)
                    
            return results
            
        except Exception as e:
            logger.error(f"Error in batch fetch: {str(e)}")
            return {symbol: self._get_fallback_data(symbol) for symbol in symbols}
    
    def get_crypto_fear_greed_index(self) -> Dict:
        """
        Crypto Fear & Greed Index al
        """
        try:
            # Alternative.me API
            url = "https://api.alternative.me/fng/"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                fng_data = data['data'][0]
                
                return {
                    "value": int(fng_data['value']),
                    "value_classification": fng_data['value_classification'],
                    "timestamp": fng_data['timestamp'],
                    "last_updated": datetime.now().strftime("%H:%M:%S")
                }
            else:
                return self._get_fallback_fear_greed()
                
        except Exception as e:
            logger.error(f"Error fetching Fear & Greed Index: {str(e)}")
            return self._get_fallback_fear_greed()
    
    def get_market_summary(self) -> Dict:
        """
        Genel piyasa özeti
        """
        try:
            # Önemli endeksler
            symbols = ['^GSPC', '^DJI', '^IXIC', '^VIX']  # S&P500, Dow, Nasdaq, VIX
            summary_data = self.get_multiple_prices(symbols)
            
            # Crypto market cap (CoinGecko API)
            crypto_data = self._get_crypto_market_data()
            
            return {
                "indices": summary_data,
                "crypto": crypto_data,
                "last_updated": datetime.now().strftime("%H:%M:%S")
            }
            
        except Exception as e:
            logger.error(f"Error fetching market summary: {str(e)}")
            return {"error": "Market data unavailable"}
    
    def _get_crypto_market_data(self) -> Dict:
        """CoinGecko API'den crypto market data"""
        try:
            url = "https://api.coingecko.com/api/v3/global"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()['data']
                
                return {
                    "total_market_cap": data['total_market_cap']['usd'],
                    "total_volume": data['total_volume']['usd'],
                    "btc_dominance": data['market_cap_percentage']['btc'],
                    "market_cap_change_24h": data.get('market_cap_change_percentage_24h_usd', 0)
                }
            else:
                return self._get_fallback_crypto_data()
                
        except Exception as e:
            logger.error(f"Error fetching crypto market data: {str(e)}")
            return self._get_fallback_crypto_data()
    
    def _is_cached(self, key: str) -> bool:
        """Cache kontrolü"""
        if key not in self.cache:
            return False
            
        cache_time = self.cache[key]['timestamp']
        return (datetime.now() - cache_time).seconds < self.cache_duration
    
    def _cache_data(self, key: str, data: Dict):
        """Veriyi cache'le"""
        self.cache[key] = {
            'data': data,
            'timestamp': datetime.now()
        }
    
    def _format_volume(self, volume: float) -> str:
        """Volume formatla"""
        if volume >= 1e12:
            return f"{volume/1e12:.1f}T"
        elif volume >= 1e9:
            return f"{volume/1e9:.1f}B"
        elif volume >= 1e6:
            return f"{volume/1e6:.1f}M"
        elif volume >= 1e3:
            return f"{volume/1e3:.1f}K"
        else:
            return f"{volume:.0f}"
    
    def _get_fallback_data(self, symbol: str) -> Dict:
        """Fallback veri"""
        base_prices = {
            "BTC-USD": 67845.32,
            "ETH-USD": 3456.78,
            "AAPL": 178.25,
            "GOOGL": 142.33,
            "TSLA": 248.50,
            "MSFT": 378.85
        }
        
        base_price = base_prices.get(symbol, 100.0)
        
        return {
            "symbol": symbol,
            "name": symbol.replace('-USD', '').replace('-', ' '),
            "price": base_price,
            "change": base_price * 0.025,  # %2.5 artış
            "change_percent": 2.5,
            "volume": "1.2B",
            "market_cap": "N/A",
            "last_updated": datetime.now().strftime("%H:%M:%S"),
            "currency": "USD",
            "sector": "Technology"
        }
    
    def _get_fallback_fear_greed(self) -> Dict:
        """Fallback Fear & Greed"""
        return {
            "value": 72,
            "value_classification": "Greed",
            "timestamp": datetime.now().timestamp(),
            "last_updated": datetime.now().strftime("%H:%M:%S")
        }
    
    def _get_fallback_crypto_data(self) -> Dict:
        """Fallback crypto market data"""
        return {
            "total_market_cap": 2340000000000,  # $2.34T
            "total_volume": 85000000000,        # $85B
            "btc_dominance": 54.2,
            "market_cap_change_24h": 2.8
        }

    def _get_coin_name(self, symbol: str) -> str:
        """Coin adını döndür"""
        names = {
            "BTC-USD": "Bitcoin",
            "ETH-USD": "Ethereum", 
            "SOL-USD": "Solana",
            "LTC-USD": "Litecoin",
            "ADA-USD": "Cardano",
            "DOT-USD": "Polkadot",
            "LINK-USD": "Chainlink",
            "UNI-USD": "Uniswap",
            "AVAX-USD": "Avalanche",
            "MATIC-USD": "Polygon",
            "XRP-USD": "Ripple",
            "DOGE-USD": "Dogecoin",
            "SHIB-USD": "Shiba Inu",
            "BCH-USD": "Bitcoin Cash",
            "XLM-USD": "Stellar"
        }
        return names.get(symbol, symbol.replace('-USD', ''))
    
    def _get_coin_icon(self, symbol: str) -> str:
        """Coin icon class'ını döndür"""
        icons = {
            "BTC-USD": "fab fa-bitcoin",
            "ETH-USD": "fab fa-ethereum",
            "SOL-USD": "fas fa-sun",
            "LTC-USD": "fas fa-coins",
            "ADA-USD": "fas fa-diamond",
            "DOT-USD": "fas fa-circle",
            "LINK-USD": "fas fa-link",
            "UNI-USD": "fas fa-exchange-alt",
            "AVAX-USD": "fas fa-mountain",
            "MATIC-USD": "fas fa-polygon",
            "XRP-USD": "fas fa-bolt",
            "DOGE-USD": "fas fa-dog",
            "SHIB-USD": "fas fa-fire",
            "BCH-USD": "fas fa-cash-register",
            "XLM-USD": "fas fa-star"
        }
        return icons.get(symbol, "fas fa-coins")
    
    def _get_chart_color(self, symbol: str, alpha: float = 1.0) -> str:
        """Chart rengini döndür"""
        colors = {
            "BTC-USD": f"rgba(255, 153, 0, {alpha})",
            "ETH-USD": f"rgba(138, 43, 226, {alpha})",
            "SOL-USD": f"rgba(0, 255, 255, {alpha})",
            "LTC-USD": f"rgba(192, 192, 192, {alpha})",
            "ADA-USD": f"rgba(0, 150, 136, {alpha})",
            "DOT-USD": f"rgba(233, 30, 99, {alpha})",
            "LINK-USD": f"rgba(33, 150, 243, {alpha})",
            "UNI-USD": f"rgba(255, 64, 129, {alpha})",
            "AVAX-USD": f"rgba(255, 87, 34, {alpha})",
            "MATIC-USD": f"rgba(156, 39, 176, {alpha})",
            "XRP-USD": f"rgba(0, 188, 212, {alpha})",
            "DOGE-USD": f"rgba(255, 193, 7, {alpha})",
            "SHIB-USD": f"rgba(255, 61, 0, {alpha})",
            "BCH-USD": f"rgba(76, 175, 80, {alpha})",
            "XLM-USD": f"rgba(63, 81, 181, {alpha})"
        }
        return colors.get(symbol, f"rgba(158, 158, 158, {alpha})")
    
    def _get_fallback_chart_data(self, symbol: str) -> Dict:
        """Fallback chart verisi"""
        return {
            "chart_data": {
                "labels": [],
                "datasets": [{
                    "label": f"{symbol} Price",
                    "data": [],
                    "borderColor": self._get_chart_color(symbol),
                    "backgroundColor": self._get_chart_color(symbol, alpha=0.1),
                    "borderWidth": 2,
                    "fill": True,
                    "tension": 0.4
                }]
            },
            "stats": {
                "current_price": 0,
                "price_change": 0,
                "price_change_percent": 0,
                "high": 0,
                "low": 0,
                "volume": "0",
                "period": "1mo"
            },
            "symbol": symbol,
            "name": self._get_coin_name(symbol)
        }

# Global instance
live_data_service = LiveDataService()
