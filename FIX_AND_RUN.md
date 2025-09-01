# 🔧 Sofia V2 - Fix and Run Guide

## ⚠️ Problem Çözümü

Sistem şu anda çalışmıyor çünkü bazı modüller eksik. İşte adım adım çözüm:

## 📋 Hızlı Başlangıç (Windows PowerShell)

### 1️⃣ Önce Sistemi Test Et
```powershell
python start_system.py
```

Bu komut:
- Import hatalarını kontrol eder
- Docker servislerini başlatır
- Hangi modüllerin çalıştığını gösterir

### 2️⃣ Eksik Bağımlılıkları Yükle
```powershell
# Virtual environment oluştur/aktif et
python -m venv .venv
.\.venv\Scripts\Activate

# Bağımlılıkları yükle
pip install -r requirements.txt

# Eksik paketleri yükle (eğer hata alırsanız)
pip install requests
```

### 3️⃣ Docker Servislerini Başlat
```powershell
# Docker Desktop'ın açık olduğundan emin ol
docker compose -f infra/docker-compose.yml up -d

# Servisleri kontrol et
docker ps
```

### 4️⃣ Sistemi Başlat

#### Otomatik (Tek Komut):
```powershell
.\scripts\sofia_dev.ps1
```

#### Manuel (Ayrı Terminaller):
```powershell
# Terminal 1: DataHub
python -m sofia_datahub

# Terminal 2: Paper Trading
python -m sofia_backtest.paper

# Terminal 3: Web UI
python -m sofia_ui.server_v2
```

## 🔍 Sorun Giderme

### "Module not found" Hatası
```powershell
# Python path'e ekle
$env:PYTHONPATH = "D:\BORSA2\sofia-v2"
```

### Docker Bağlantı Hatası
```powershell
# Docker servislerini yeniden başlat
docker compose -f infra/docker-compose.yml down
docker compose -f infra/docker-compose.yml up -d
```

### Web UI Açılmıyor
```powershell
# Portu kontrol et
netstat -an | findstr 8000

# Farklı port dene
python -m sofia_ui.server_v2 --port 8001
```

## ✅ Çalıştığını Nasıl Anlarım?

### 1. CLI Status Kontrolü:
```powershell
python -m sofia_cli status
```

Çıktı şöyle olmalı:
```
System Status
├─ ClickHouse    ✓ Connected
├─ NATS          ✓ Connected
├─ Redis         ✓ Connected
├─ DataHub       ✓ Running
└─ Paper Trading ✓ Running
```

### 2. Web UI Kontrolü:
Tarayıcıda aç: http://localhost:8000

Göreceğiniz:
- Live ticker'lar
- Portfolio durumu
- PnL metrikleri
- Recent trades

### 3. Data Flow Kontrolü:
```powershell
# ClickHouse'da veri var mı?
curl "http://localhost:8123/?query=SELECT count() FROM sofia.market_ticks"

# Redis'te state var mı?
redis-cli GET paper:state
```

## 🚀 Basit Test Senaryosu

### 1. Portfolio Uygula:
```powershell
python -m sofia_cli portfolio apply --file configs/portfolio/paper_default.yaml
```

### 2. Backtest Çalıştır:
```powershell
python -m sofia_cli backtest BTCUSDT --strategy trend --days 30
```

### 3. UI'da İzle:
http://localhost:8000 adresini aç ve:
- Dashboard'da pozisyonları gör
- Analysis/BTCUSDT sayfasında detayları incele

## 📊 Beklenen Sonuçlar

### DataHub Çalışıyor:
```
INFO - Connected to NATS
INFO - Connected to Binance WebSocket
INFO - Published 1000 messages
```

### Paper Trading Çalışıyor:
```
INFO - Paper trading engine started
INFO - Grid strategy initialized for ETHUSDT
INFO - Trend strategy initialized for BTCUSDT
```

### Web UI Çalışıyor:
```
INFO - Uvicorn running on http://0.0.0.0:8000
INFO - Connected to NATS
INFO - Connected to Redis
```

## 🆘 Hala Çalışmıyorsa

### Temiz Kurulum:
```powershell
# 1. Virtual environment'ı sil ve yeniden oluştur
Remove-Item -Recurse -Force .venv
python -m venv .venv
.\.venv\Scripts\Activate

# 2. Tüm bağımlılıkları yeniden yükle
pip install --upgrade pip
pip install -r requirements.txt

# 3. Docker'ı temizle ve yeniden başlat
docker compose -f infra/docker-compose.yml down -v
docker compose -f infra/docker-compose.yml up -d

# 4. Test et
python start_system.py
```

### Minimum Test:
```powershell
# Sadece CLI'yi test et
python -m sofia_cli version
python -m sofia_cli status

# Sadece UI'yı test et (mock data ile)
python simple_server.py  # Eğer varsa
```

## 📝 Önemli Notlar

1. **Docker Desktop** açık olmalı
2. **Python 3.11+** gerekli
3. **Virtual environment** aktif olmalı
4. Portlar boş olmalı: 8000, 8123, 4222, 6379, 3000

## 🎯 Başarılı Kurulum Sonrası

- **Dashboard:** http://localhost:8000
- **Grafana:** http://localhost:3000 (admin/sofia2024)
- **ClickHouse:** http://localhost:8123

Artık Sofia V2 paper trading sistemi çalışıyor olmalı! 🚀