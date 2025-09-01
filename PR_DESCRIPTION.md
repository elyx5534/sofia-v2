# feat(data-hub): yfinance+ccxt tabanlı FastAPI ve SQLite cache (v0)

## 📋 Kapsam

Bu PR, Sofia v2 platformuna **Data Hub v0** modülünü eklemektedir. Modül, equity ve kripto varlıklar için OHLCV (Open, High, Low, Close, Volume) verilerini sağlayan bir FastAPI servisidir.

### Özellikler:
- ✅ **Equity Verileri**: Yahoo Finance (yfinance) entegrasyonu
- ✅ **Kripto Verileri**: CCXT ile çoklu borsa desteği (varsayılan: Binance)
- ✅ **Akıllı Cache**: SQLite tabanlı, TTL destekli (varsayılan: 10 dakika)
- ✅ **Asenkron Mimari**: Yüksek performans için async/await
- ✅ **Sembol Arama**: Equity ve kripto sembolleri için arama
- ✅ **Hata Yönetimi**: Detaylı hata kodları (404, 422, 502, 503)
- ✅ **API Dokümantasyonu**: Otomatik Swagger/ReDoc

### Endpointler:
- `GET /health` - Sağlık kontrolü
- `GET /symbols` - Sembol arama
- `GET /ohlcv` - OHLCV veri çekme (cache destekli)
- `DELETE /cache` - Süresi dolmuş cache temizleme

## 🧪 Test

### Kapsam:
- ✅ Health endpoint testleri
- ✅ Symbol search testleri (equity/crypto)
- ✅ OHLCV endpoint testleri
- ✅ Cache hit/miss senaryoları
- ✅ TTL expiry testleri
- ✅ Hata durumu testleri (404, 503)
- ✅ Test coverage: %70+

### Test Çalıştırma:
```bash
pytest tests/ -v --cov=src --cov-report=term-missing
```

## ⚠️ Risk

### Düşük Risk:
- Yeni modül, mevcut kodu etkilemiyor
- İzole mimari, bağımsız çalışıyor
- SQLite yerel veritabanı kullanımı

### Orta Risk:
- Yahoo Finance rate limiting (çözüm: retry mekanizması eklenebilir)
- Büyük veri setlerinde SQLite performansı (çözüm: PostgreSQL'e geçiş)

### Azaltma Stratejileri:
1. Cache TTL ayarlanabilir (env variable)
2. Provider timeout konfigüre edilebilir
3. nocache parametresi ile cache bypass mümkün

## 📊 İzleme

### Metrikleri:
- Response time (FastAPI built-in)
- Cache hit/miss oranı (loglarda)
- Provider hataları (503 status code)
- Endpoint kullanım istatistikleri

### Log Seviyeleri:
- `INFO`: Normal operasyonlar
- `WARNING`: Cache miss, yavaş yanıtlar
- `ERROR`: Provider hataları, veritabanı hataları

### Monitoring Önerileri:
1. Prometheus metrikleri eklenebilir
2. Grafana dashboard'u kurulabilir
3. Alert kuralları tanımlanabilir

## 🚀 Deployment

### Lokal Çalıştırma:
```bash
# Bağımlılıkları yükle
pip install -r requirements.txt

# Environment ayarla
cp .env.example .env

# Servisi başlat
uvicorn src.data_hub.api:app --reload
```

### Örnek Kullanım:
```bash
# Equity sembol arama
curl "http://localhost:8000/symbols?query=AAPL&asset_type=equity"

# OHLCV veri çekme
curl "http://localhost:8000/ohlcv?symbol=AAPL&asset_type=equity&timeframe=1d"

# Kripto veri çekme
curl "http://localhost:8000/ohlcv?symbol=BTC/USDT&asset_type=crypto&exchange=binance"
```

## 📝 Notlar

- İlk istekte veri provider'dan çekilir ve cache'e yazılır
- İkinci istekte aynı parametrelerle cache'den sunulur
- TTL süresi dolduğunda otomatik olarak yeniden fetch edilir
- nocache=true parametresi ile cache atlanabilir

## ✅ Checklist

- [x] Kod yazıldı ve test edildi
- [x] Unit testler eklendi (%70+ coverage)
- [x] Dokümantasyon güncellendi (README)
- [x] Environment örneği eklendi (.env.example)
- [x] CI pipeline güncellendi
- [x] Linting ve type checking geçti
- [x] Security scan (bandit) geçti
