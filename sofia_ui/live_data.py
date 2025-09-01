"""
<<<<<<< HEAD
Sofia V2 - Modern Data Service (Zufridy Style)
Gerçek zamanlı crypto verileri, WebSocket stream'leri ve trading indicators
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np
import ccxt
import websockets
import yfinance as yf
from ta.trend import SMAIndicator, MACD
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands
import sqlite3
from pathlib import Path
import aiosqlite
=======
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
>>>>>>> 96de1d9

# Logging ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

<<<<<<< HEAD
class ModernDataService:
    """Modern crypto data service - Zufridy style"""
    
    def __init__(self):
        self.cache = {}
        self.cache_duration = 30  # 30 saniye cache
        self.websocket_connections = {}
        self.price_streams = {}
        
        # CCXT exchange setup
        self.exchange = ccxt.binance({
            'apiKey': '',  # API key gerekirse
            'secret': '',  # Secret gerekirse
            'sandbox': False,
            'enableRateLimit': True,
        })
        
        # Desteklenen crypto pairs
        self.supported_pairs = [
            'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'LTC/USDT', 'ADA/USDT',
            'DOT/USDT', 'LINK/USDT', 'UNI/USDT', 'AVAX/USDT', 'MATIC/USDT',
            'XRP/USDT', 'DOGE/USDT', 'SHIB/USDT', 'BCH/USDT', 'XLM/USDT',
            'ATOM/USDT', 'NEAR/USDT', 'FTM/USDT', 'ALGO/USDT', 'VET/USDT'
        ]
        
        # Database setup
        self.db_path = Path(__file__).parent / "data" / "trades.db"
        self.db_path.parent.mkdir(exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """Database'i başlat"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Trade history table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    amount REAL NOT NULL,
                    price REAL NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    strategy TEXT,
                    pnl REAL
                )
            ''')
            
            # Price history table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume REAL
                )
            ''')
            
            conn.commit()
            conn.close()
            logger.info("Database initialized successfully")
            
        except Exception as e:
            logger.error(f"Database initialization error: {e}")
    
    async def get_live_price(self, symbol: str) -> Dict:
        """Canlı fiyat verisi al (CCXT + YFinance)"""
=======
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
>>>>>>> 96de1d9
        try:
            # Cache kontrolü
            cache_key = f"price_{symbol}"
            if self._is_cached(cache_key):
                return self.cache[cache_key]['data']
            
<<<<<<< HEAD
            # CCXT'den veri çek
            try:
                ticker = await self.exchange.fetch_ticker(symbol)
                price = ticker['last']
                change = ticker['change']
                change_percent = ticker['percentage']
                volume = ticker['quoteVolume']
                
                data = {
                    "symbol": symbol,
                    "name": self._get_coin_name(symbol),
                    "price": float(price),
                    "change": float(change),
                    "change_percent": round(float(change_percent), 2),
                    "volume": self._format_volume(float(volume)),
                    "high_24h": float(ticker['high']),
                    "low_24h": float(ticker['low']),
                    "last_updated": datetime.now().strftime("%H:%M:%S"),
                    "source": "CCXT"
                }
                
            except Exception as e:
                logger.warning(f"CCXT failed for {symbol}, trying YFinance: {e}")
                # Fallback to YFinance
                data = await self._get_yfinance_price(symbol)
            
            # Cache'e kaydet
            self._cache_data(cache_key, data)
            
            logger.info(f"Live price fetched for {symbol}: ${data['price']:.2f}")
            return data
            
        except Exception as e:
            logger.error(f"Error fetching live price for {symbol}: {str(e)}")
            return self._get_fallback_data(symbol)
    
    async def _get_yfinance_price(self, symbol: str) -> Dict:
        """YFinance'den fiyat al"""
        try:
            # Symbol'ü YFinance formatına çevir
            yf_symbol = symbol.replace('/', '-')
            ticker = yf.Ticker(yf_symbol)
=======
            # YFinance ile veri çek
            ticker = yf.Ticker(symbol)
            info = ticker.info
>>>>>>> 96de1d9
            hist = ticker.history(period="2d")
            
            if hist.empty:
                return self._get_fallback_data(symbol)
            
            current_price = hist['Close'].iloc[-1]
            previous_price = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
            
            change = current_price - previous_price
            change_percent = (change / previous_price) * 100 if previous_price != 0 else 0
            
<<<<<<< HEAD
            return {
                "symbol": symbol,
                "name": self._get_coin_name(symbol),
                "price": float(current_price),
                "change": float(change),
                "change_percent": round(float(change_percent), 2),
                "volume": self._format_volume(float(hist['Volume'].iloc[-1])),
                "high_24h": float(hist['High'].iloc[-1]),
                "low_24h": float(hist['Low'].iloc[-1]),
                "last_updated": datetime.now().strftime("%H:%M:%S"),
                "source": "YFinance"
            }
            
        except Exception as e:
            logger.error(f"YFinance error for {symbol}: {e}")
            return self._get_fallback_data(symbol)
    
    async def get_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 100) -> Dict:
        """
        OHLCV verisi al (TradingView uyumlu)
        
        Args:
            symbol: Trading pair (örn: BTC/USDT)
            timeframe: 1m, 5m, 15m, 1h, 4h, 1d
            limit: Kaç candle alınacak
        """
        try:
            cache_key = f"ohlcv_{symbol}_{timeframe}_{limit}"
            if self._is_cached(cache_key):
                return self.cache[cache_key]['data']
            
            # CCXT'den OHLCV al
            ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            
            # DataFrame'e çevir
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            # TradingView formatına çevir
            tv_data = {
                "symbol": symbol,
                "timeframe": timeframe,
                "data": df.to_dict('records'),
                "last_updated": datetime.now().strftime("%H:%M:%S")
            }
            
            # Cache'e kaydet
            self._cache_data(cache_key, tv_data)
            
            # Database'e kaydet
            await self._save_price_history(symbol, df)
            
            return tv_data
            
        except Exception as e:
            logger.error(f"Error fetching OHLCV for {symbol}: {str(e)}")
            return self._get_fallback_ohlcv(symbol, timeframe)
    
    async def get_indicators(self, symbol: str, timeframe: str = '1h') -> Dict:
        """
        Trading indicators hesapla (RSI, MACD, Bollinger Bands)
        """
        try:
            # OHLCV verisi al
            ohlcv_data = await self.get_ohlcv(symbol, timeframe, 100)
            
            if not ohlcv_data.get('data'):
                return self._get_fallback_indicators(symbol)
            
            # DataFrame oluştur
            df = pd.DataFrame(ohlcv_data['data'])
            
            # Indicators hesapla
            indicators = {}
            
            # RSI
            rsi_indicator = RSIIndicator(df['close'])
            indicators['rsi'] = float(rsi_indicator.rsi().iloc[-1])
            
            # MACD
            macd_indicator = MACD(df['close'])
            indicators['macd'] = float(macd_indicator.macd().iloc[-1])
            indicators['macd_signal'] = float(macd_indicator.macd_signal().iloc[-1])
            indicators['macd_histogram'] = float(macd_indicator.macd_diff().iloc[-1])
            
            # SMA
            sma_20 = SMAIndicator(df['close'], window=20)
            sma_50 = SMAIndicator(df['close'], window=50)
            indicators['sma_20'] = float(sma_20.sma_indicator().iloc[-1])
            indicators['sma_50'] = float(sma_50.sma_indicator().iloc[-1])
            
            # Bollinger Bands
            bb_indicator = BollingerBands(df['close'])
            indicators['bb_upper'] = float(bb_indicator.bollinger_hband().iloc[-1])
            indicators['bb_middle'] = float(bb_indicator.bollinger_mavg().iloc[-1])
            indicators['bb_lower'] = float(bb_indicator.bollinger_lband().iloc[-1])
            
            # Current price
            indicators['current_price'] = float(df['close'].iloc[-1])
            
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "indicators": indicators,
=======
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
>>>>>>> 96de1d9
                "last_updated": datetime.now().strftime("%H:%M:%S")
            }
            
        except Exception as e:
<<<<<<< HEAD
            logger.error(f"Error calculating indicators for {symbol}: {str(e)}")
            return self._get_fallback_indicators(symbol)
    
    async def get_all_crypto_prices(self) -> Dict[str, Dict]:
        """Tüm desteklenen crypto'ların fiyatlarını al"""
        results = {}
        
        # Paralel olarak tüm fiyatları al
        tasks = [self.get_live_price(symbol) for symbol in self.supported_pairs]
        prices = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, price_data in enumerate(prices):
            if isinstance(price_data, Exception):
                logger.error(f"Error fetching {self.supported_pairs[i]}: {price_data}")
                results[self.supported_pairs[i]] = self._get_fallback_data(self.supported_pairs[i])
            else:
                results[self.supported_pairs[i]] = price_data
        
        return results
    
    async def start_price_stream(self, symbol: str):
        """WebSocket price stream başlat"""
        try:
            if symbol in self.price_streams:
                return
            
            # Binance WebSocket URL
            ws_url = f"wss://stream.binance.com:9443/ws/{symbol.lower().replace('/', '')}@ticker"
            
            async def price_stream():
                try:
                    async with websockets.connect(ws_url) as websocket:
                        logger.info(f"WebSocket connected for {symbol}")
                        
                        while True:
                            try:
                                message = await websocket.recv()
                                data = json.loads(message)
                                
                                # Price data'yı işle
                                price_info = {
                                    "symbol": symbol,
                                    "price": float(data['c']),
                                    "change": float(data['P']),
                                    "change_percent": float(data['P']),
                                    "volume": self._format_volume(float(data['v'])),
                                    "high_24h": float(data['h']),
                                    "low_24h": float(data['l']),
                                    "last_updated": datetime.now().strftime("%H:%M:%S"),
                                    "source": "WebSocket"
                                }
                                
                                # Cache'e kaydet
                                cache_key = f"price_{symbol}"
                                self._cache_data(cache_key, price_info)
                                
                                # WebSocket listeners'a gönder
                                if symbol in self.websocket_connections:
                                    for ws in self.websocket_connections[symbol]:
                                        try:
                                            await ws.send(json.dumps(price_info))
                                        except:
                                            pass
                                
                            except websockets.exceptions.ConnectionClosed:
                                logger.warning(f"WebSocket connection closed for {symbol}")
                                break
                            except Exception as e:
                                logger.error(f"WebSocket error for {symbol}: {e}")
                                break
                                
                except Exception as e:
                    logger.error(f"WebSocket connection error for {symbol}: {e}")
            
            # Stream'i başlat
            self.price_streams[symbol] = asyncio.create_task(price_stream())
            
        except Exception as e:
            logger.error(f"Error starting price stream for {symbol}: {e}")
    
    async def _save_price_history(self, symbol: str, df: pd.DataFrame):
        """Price history'yi database'e kaydet"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                for _, row in df.iterrows():
                    await db.execute('''
                        INSERT INTO price_history (symbol, timestamp, open, high, low, close, volume)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (symbol, row['timestamp'], row['open'], row['high'], row['low'], row['close'], row['volume']))
                await db.commit()
        except Exception as e:
            logger.error(f"Error saving price history: {e}")
    
    async def save_trade(self, symbol: str, side: str, amount: float, price: float, strategy: str = None, pnl: float = None):
        """Trade'i database'e kaydet"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    INSERT INTO trades (symbol, side, amount, price, strategy, pnl)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (symbol, side, amount, price, strategy, pnl))
                await db.commit()
                logger.info(f"Trade saved: {side} {amount} {symbol} @ {price}")
        except Exception as e:
            logger.error(f"Error saving trade: {e}")
    
    def _get_coin_name(self, symbol: str) -> str:
        """Coin adını döndür"""
        names = {
            'BTC/USDT': 'Bitcoin',
            'ETH/USDT': 'Ethereum',
            'SOL/USDT': 'Solana',
            'LTC/USDT': 'Litecoin',
            'ADA/USDT': 'Cardano',
            'DOT/USDT': 'Polkadot',
            'LINK/USDT': 'Chainlink',
            'UNI/USDT': 'Uniswap',
            'AVAX/USDT': 'Avalanche',
            'MATIC/USDT': 'Polygon',
            'XRP/USDT': 'Ripple',
            'DOGE/USDT': 'Dogecoin',
            'SHIB/USDT': 'Shiba Inu',
            'BCH/USDT': 'Bitcoin Cash',
            'XLM/USDT': 'Stellar',
            'ATOM/USDT': 'Cosmos',
            'NEAR/USDT': 'NEAR Protocol',
            'FTM/USDT': 'Fantom',
            'ALGO/USDT': 'Algorand',
            'VET/USDT': 'VeChain'
        }
        return names.get(symbol, symbol.split('/')[0])
    
    def _get_coin_icon(self, symbol: str) -> str:
        """Coin icon class'ını döndür"""
        icons = {
            'BTC/USDT': 'fab fa-bitcoin',
            'ETH/USDT': 'fab fa-ethereum',
            'SOL/USDT': 'fas fa-sun',
            'LTC/USDT': 'fas fa-coins',
            'ADA/USDT': 'fas fa-diamond',
            'DOT/USDT': 'fas fa-circle',
            'LINK/USDT': 'fas fa-link',
            'UNI/USDT': 'fas fa-exchange-alt',
            'AVAX/USDT': 'fas fa-mountain',
            'MATIC/USDT': 'fas fa-polygon',
            'XRP/USDT': 'fas fa-bolt',
            'DOGE/USDT': 'fas fa-dog',
            'SHIB/USDT': 'fas fa-fire',
            'BCH/USDT': 'fas fa-cash-register',
            'XLM/USDT': 'fas fa-star',
            'ATOM/USDT': 'fas fa-atom',
            'NEAR/USDT': 'fas fa-satellite',
            'FTM/USDT': 'fas fa-ghost',
            'ALGO/USDT': 'fas fa-cube',
            'VET/USDT': 'fas fa-car'
        }
        return icons.get(symbol, 'fas fa-coins')
=======
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
>>>>>>> 96de1d9
    
    def _is_cached(self, key: str) -> bool:
        """Cache kontrolü"""
        if key not in self.cache:
            return False
<<<<<<< HEAD
=======
            
>>>>>>> 96de1d9
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
<<<<<<< HEAD
            'BTC/USDT': 67845.32,
            'ETH/USDT': 3456.78,
            'SOL/USDT': 98.45,
            'LTC/USDT': 78.23,
            'ADA/USDT': 0.45,
            'DOT/USDT': 6.78,
            'LINK/USDT': 12.34,
            'UNI/USDT': 5.67,
            'AVAX/USDT': 23.45,
            'MATIC/USDT': 0.89,
            'XRP/USDT': 0.56,
            'DOGE/USDT': 0.078,
            'SHIB/USDT': 0.000023,
            'BCH/USDT': 234.56,
            'XLM/USDT': 0.123,
            'ATOM/USDT': 8.90,
            'NEAR/USDT': 3.45,
            'FTM/USDT': 0.34,
            'ALGO/USDT': 0.23,
            'VET/USDT': 0.045
=======
            "BTC-USD": 67845.32,
            "ETH-USD": 3456.78,
            "AAPL": 178.25,
            "GOOGL": 142.33,
            "TSLA": 248.50,
            "MSFT": 378.85
>>>>>>> 96de1d9
        }
        
        base_price = base_prices.get(symbol, 100.0)
        
        return {
            "symbol": symbol,
            "name": self._get_coin_name(symbol),
            "price": base_price,
<<<<<<< HEAD
            "change": base_price * 0.025,
            "change_percent": 2.5,
            "volume": "1.2B",
            "high_24h": base_price * 1.05,
            "low_24h": base_price * 0.95,
            "last_updated": datetime.now().strftime("%H:%M:%S"),
            "source": "Fallback"
        }
    
    def _get_fallback_ohlcv(self, symbol: str, timeframe: str) -> Dict:
        """Fallback OHLCV verisi"""
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "data": [],
            "last_updated": datetime.now().strftime("%H:%M:%S")
        }
    
    def _get_fallback_indicators(self, symbol: str) -> Dict:
        """Fallback indicators"""
        return {
            "symbol": symbol,
            "timeframe": "1h",
            "indicators": {
                "rsi": 50.0,
                "macd": 0.0,
                "macd_signal": 0.0,
                "macd_histogram": 0.0,
                "sma_20": 100.0,
                "sma_50": 100.0,
                "bb_upper": 105.0,
                "bb_middle": 100.0,
                "bb_lower": 95.0,
                "current_price": 100.0
            },
            "last_updated": datetime.now().strftime("%H:%M:%S")
        }

# Global instance
live_data_service = ModernDataService()
=======
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
>>>>>>> 96de1d9
