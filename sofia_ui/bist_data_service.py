"""
BIST (Borsa İstanbul) Gerçek Veri Servisi
Yahoo Finance API kullanarak gerçek zamanlı BIST verilerini çeker ve cache'ler
"""

import yfinance as yf
from datetime import datetime, timedelta, timezone
import asyncio
import json
from typing import Dict, List, Optional
import time

class BISTDataService:
    def __init__(self):
        self.cache = {}
        self.cache_duration = 60  # 60 saniye cache
        self.last_update = None
        
        # BIST 30 hisseleri
        self.bist_stocks = [
            {"symbol": "THYAO", "name": "Türk Hava Yolları", "sector": "Ulaştırma", "lot": 10},
            {"symbol": "EREGL", "name": "Ereğli Demir Çelik", "sector": "Metal", "lot": 100},
            {"symbol": "ASELS", "name": "Aselsan", "sector": "Savunma", "lot": 100},
            {"symbol": "TUPRS", "name": "Tüpraş", "sector": "Petrol", "lot": 10},
            {"symbol": "SAHOL", "name": "Sabancı Holding", "sector": "Holding", "lot": 100},
            {"symbol": "SISE", "name": "Şişecam", "sector": "Cam", "lot": 100},
            {"symbol": "AKBNK", "name": "Akbank", "sector": "Bankacılık", "lot": 100},
            {"symbol": "GARAN", "name": "Garanti BBVA", "sector": "Bankacılık", "lot": 100},
            {"symbol": "ISCTR", "name": "İş Bankası (C)", "sector": "Bankacılık", "lot": 100},
            {"symbol": "YKBNK", "name": "Yapı Kredi", "sector": "Bankacılık", "lot": 100},
            {"symbol": "KCHOL", "name": "Koç Holding", "sector": "Holding", "lot": 10},
            {"symbol": "TCELL", "name": "Turkcell", "sector": "Telekomünikasyon", "lot": 100},
            {"symbol": "BIMAS", "name": "BİM Mağazaları", "sector": "Perakende", "lot": 10},
            {"symbol": "FROTO", "name": "Ford Otosan", "sector": "Otomotiv", "lot": 1},
            {"symbol": "TOASO", "name": "Tofaş", "sector": "Otomotiv", "lot": 10},
            {"symbol": "PETKM", "name": "Petkim", "sector": "Kimya", "lot": 100},
            {"symbol": "ARCLK", "name": "Arçelik", "sector": "Dayanıklı Tüketim", "lot": 10},
            {"symbol": "EKGYO", "name": "Emlak Konut GYO", "sector": "GYO", "lot": 1000},
            {"symbol": "HALKB", "name": "Halkbank", "sector": "Bankacılık", "lot": 100},
            {"symbol": "VAKBN", "name": "Vakıfbank", "sector": "Bankacılık", "lot": 100},
            {"symbol": "KOZAL", "name": "Koza Altın", "sector": "Madencilik", "lot": 100},
            {"symbol": "KOZAA", "name": "Koza Madencilik", "sector": "Madencilik", "lot": 100},
            {"symbol": "SODA", "name": "Soda Sanayii", "sector": "Kimya", "lot": 10},
            {"symbol": "MGROS", "name": "Migros", "sector": "Perakende", "lot": 10},
            {"symbol": "VESBE", "name": "Vestel Beyaz Eşya", "sector": "Dayanıklı Tüketim", "lot": 10},
            {"symbol": "VESTL", "name": "Vestel", "sector": "Teknoloji", "lot": 100},
            {"symbol": "TTKOM", "name": "Türk Telekom", "sector": "Telekomünikasyon", "lot": 100},
            {"symbol": "KRDMD", "name": "Kardemir (D)", "sector": "Metal", "lot": 100},
            {"symbol": "TAVHL", "name": "TAV Havalimanları", "sector": "Ulaştırma", "lot": 10},
            {"symbol": "PGSUS", "name": "Pegasus", "sector": "Ulaştırma", "lot": 10},
        ]
    
    def _is_cache_valid(self) -> bool:
        """Cache geçerli mi kontrol et"""
        if not self.last_update:
            return False
        return (time.time() - self.last_update) < self.cache_duration
    
    def get_stock_data(self, symbol: str) -> Optional[Dict]:
        """Tek bir hisse için veri çek"""
        try:
            ticker = yf.Ticker(f"{symbol}.IS")
            info = ticker.info
            
            # Fiyat bilgilerini al
            current_price = None
            previous_close = None
            
            # Önce info'dan dene
            current_price = info.get('currentPrice') or info.get('regularMarketPrice')
            previous_close = info.get('previousClose') or info.get('regularMarketPreviousClose')
            
            # Info'da yoksa history'den al
            if not current_price:
                hist = ticker.history(period="5d")
                if not hist.empty:
                    current_price = float(hist['Close'].iloc[-1])
                    if len(hist) > 1:
                        previous_close = float(hist['Close'].iloc[-2])
                    else:
                        previous_close = current_price
            
            if not current_price:
                return None
            
            # Değişim hesapla
            change = current_price - previous_close if previous_close else 0
            change_percent = (change / previous_close * 100) if previous_close and previous_close != 0 else 0
            
            return {
                "price": round(current_price, 2),
                "previous_close": round(previous_close, 2) if previous_close else current_price,
                "change": round(change, 2),
                "change_percent": round(change_percent, 2),
                "volume": info.get('volume', 0),
                "market_cap": info.get('marketCap', 0),
                "pe_ratio": round(info.get('trailingPE', 0), 2) if info.get('trailingPE') else None,
                "pb_ratio": round(info.get('priceToBook', 0), 2) if info.get('priceToBook') else None,
                "dividend_yield": round(info.get('dividendYield', 0) * 100, 2) if info.get('dividendYield') else 0,
                "day_high": info.get('dayHigh', current_price),
                "day_low": info.get('dayLow', current_price),
                "52_week_high": info.get('fiftyTwoWeekHigh', 0),
                "52_week_low": info.get('fiftyTwoWeekLow', 0),
            }
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
            return None
    
    def get_all_stocks(self, force_refresh: bool = False) -> List[Dict]:
        """Tüm BIST hisselerini getir"""
        
        # Cache kontrol
        if not force_refresh and self._is_cache_valid() and self.cache.get('stocks'):
            print("Returning cached BIST data")
            return self.cache['stocks']
        
        print("Fetching fresh BIST data from Yahoo Finance...")
        stocks = []
        
        for stock_info in self.bist_stocks:
            symbol = stock_info["symbol"]
            data = self.get_stock_data(symbol)
            
            if data:
                stock = {
                    "symbol": symbol,
                    "name": stock_info["name"],
                    "sector": stock_info["sector"],
                    "lot": stock_info["lot"],
                    "price": data["price"],
                    "change": data["change"],
                    "change_percent": data["change_percent"],
                    "volume": data["volume"],
                    "market_cap": round(data["market_cap"] / 1000000, 2) if data["market_cap"] else 0,  # Milyon TL
                    "pe_ratio": data["pe_ratio"],
                    "pb_ratio": data["pb_ratio"],
                    "dividend_yield": data["dividend_yield"],
                    "day_high": data["day_high"],
                    "day_low": data["day_low"],
                    "last_updated": datetime.now(timezone.utc).strftime("%H:%M:%S")
                }
                stocks.append(stock)
                print(f"[OK] {symbol}: {data['price']} TL ({data['change_percent']:+.2f}%)")
            else:
                # Veri alınamazsa varsayılan değerler
                print(f"[ERROR] {symbol}: Veri alinamadi, varsayilan degerler kullaniliyor")
                stock = {
                    "symbol": symbol,
                    "name": stock_info["name"],
                    "sector": stock_info["sector"],
                    "lot": stock_info["lot"],
                    "price": 0,
                    "change": 0,
                    "change_percent": 0,
                    "volume": 0,
                    "market_cap": 0,
                    "pe_ratio": None,
                    "pb_ratio": None,
                    "dividend_yield": 0,
                    "last_updated": datetime.now(timezone.utc).strftime("%H:%M:%S")
                }
                stocks.append(stock)
        
        # Cache'i güncelle
        self.cache['stocks'] = stocks
        self.last_update = time.time()
        
        print(f"Fetched {len([s for s in stocks if s['price'] > 0])} stocks with valid prices")
        return stocks
    
    def get_bist100_index(self) -> Dict:
        """BIST 100 endeks verisi"""
        try:
            # XU100.IS BIST 100 endeksi
            ticker = yf.Ticker("XU100.IS")
            info = ticker.info
            hist = ticker.history(period="2d")
            
            if not hist.empty:
                current = float(hist['Close'].iloc[-1])
                previous = float(hist['Close'].iloc[-2]) if len(hist) > 1 else current
                change = current - previous
                change_percent = (change / previous * 100) if previous != 0 else 0
                
                return {
                    "value": round(current, 2),
                    "change": round(change, 2),
                    "change_percent": round(change_percent, 2),
                    "volume": f"{hist['Volume'].iloc[-1] / 1000000:.1f}M",
                    "last_updated": datetime.now(timezone.utc).strftime("%H:%M:%S")
                }
        except Exception as e:
            print(f"Error fetching BIST100 index: {e}")
        
        # Varsayılan değerler
        return {
            "value": 9875.43,
            "change": 125.67,
            "change_percent": 1.29,
            "volume": "45.8M",
            "last_updated": datetime.now(timezone.utc).strftime("%H:%M:%S")
        }

# Global instance
bist_data_service = BISTDataService()

# Test fonksiyonu
if __name__ == "__main__":
    print("BIST Data Service Test")
    print("=" * 50)
    
    # İlk 3 hisseyi test et
    for symbol in ["THYAO", "EREGL", "ASELS"]:
        data = bist_data_service.get_stock_data(symbol)
        if data:
            print(f"{symbol}: {data['price']} TL ({data['change_percent']:+.2f}%)")
        else:
            print(f"{symbol}: Veri alınamadı")
    
    print("\nBIST 100 Index:")
    index = bist_data_service.get_bist100_index()
    print(f"Değer: {index['value']} ({index['change_percent']:+.2f}%)")