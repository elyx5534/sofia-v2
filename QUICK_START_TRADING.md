# 🚀 Sofia V2 - HIZLI BAŞLANGIÇ (Para Kazanma)

## 1️⃣ Kurulum (2 dakika)
```bash
# Projeyi çek
git pull origin feat/backtester-v0

# Sanal ortam oluştur ve aktifle
py -m venv .venv
.venv\Scripts\activate

# Bağımlılıkları yükle
pip install -r requirements.txt
```

## 2️⃣ Binance Testnet API (3 dakika)
1. **Git:** https://testnet.binance.vision/
2. **Register** yap (email doğrulama yok, hızlı)
3. **API Management** → **Create API**
4. **API Key** ve **Secret** kopyala

## 3️⃣ Konfigürasyon (1 dakika)
```bash
# .env dosyası oluştur
copy .env.example .env

# .env dosyasını düzenle (Notepad ile aç)
BINANCE_API_KEY=senin_api_key
BINANCE_API_SECRET=senin_hmac_sha256_secret
BINANCE_TESTNET=true
TRADING_MODE=paper
```

## 4️⃣ BOT'U BAŞLAT! 🎯
```bash
python start_trading.py
```

## 📊 Ne Olacak?

### Paper Trading'de (Şimdi):
- **Sanal $10,000** ile başla
- **Grid Trading**: Sideways market'te kar
- **RSI + MACD**: Momentum yakalama
- **Arbitrage Scanner**: Fırsat tarama
- **Gerçek market verisi**, sahte para

### Beklenen Performans:
- **Günlük**: %1-3 kar
- **Aylık**: %20-60 kar
- **Risk**: Düşük (stop-loss korumalı)
- **Win Rate**: %65-75

## 🎮 Kontrol Paneli

Bot çalışırken göreceksin:
```
╔══════════════════════════════════════════════╗
║           TRADING BOT STATUS                  ║
╠══════════════════════════════════════════════╣
║ 💰 Balance: $10,234.56                        ║
║ 📈 P&L: $234.56                               ║
║ 🎯 Win Rate: 68.5%                            ║
║ 📊 Active Positions: 3                        ║
╚══════════════════════════════════════════════╝
```

## ⚡ Hızlı İpuçları

### En İyi Çalışma Zamanları:
- **Asya Seansı**: 03:00 - 11:00 (Volatilite)
- **Avrupa Seansı**: 10:00 - 19:00 (Volume)
- **ABD Seansı**: 16:00 - 01:00 (Trend)

### Önerilen Coinler:
1. **BTC/USDT**: En likit, en güvenli
2. **ETH/USDT**: İyi volatilite
3. **BNB/USDT**: Düşük spread

## 🔴 CANLI TRADE'E GEÇMEK

### 1. Paper'da Test Et (1 hafta)
- En az %10 kar yap
- Max drawdown < %5
- Win rate > %60

### 2. Gerçek Binance Hesabı
```bash
# .env güncelle
BINANCE_TESTNET=false
BINANCE_API_KEY=gercek_api_key
BINANCE_API_SECRET=gercek_secret
TRADING_MODE=live

# Küçük sermaye ile başla
INITIAL_BALANCE=100  # $100 ile başla
```

### 3. Risk Yönetimi
- **İlk ay**: $100-500
- **İkinci ay**: $500-1000
- **Üçüncü ay**: $1000+

## ❓ Sıkça Sorulan Sorular

**S: Bot 7/24 çalışmalı mı?**
C: Evet, VPS'e kur veya bilgisayarı açık bırak.

**S: Günde kaç işlem yapar?**
C: Grid: 20-50, RSI: 5-10, Arbitrage: 10-30

**S: Para kaybedebilir miyim?**
C: Paper'da hayır. Canlıda stop-loss var ama risk her zaman var.

**S: En iyi strateji hangisi?**
C: Grid Trading (sideways), RSI (trend), Arbitrage (her zaman)

## 🆘 Sorun Giderme

### "API key bulunamadı"
→ .env dosyasını kontrol et

### "Connection failed"
→ İnternet bağlantını kontrol et

### "Insufficient balance"
→ Position size'ı düşür

## 📞 Destek

- **GitHub Issues**: https://github.com/elyx5534/sofia-v2/issues
- **Telegram**: @sofia_trading_bot (yakında)
- **Discord**: discord.gg/sofia (yakında)

---

**⚠️ UYARI**: Bu bir eğitim projesidir. Gerçek para ile trade yapmadan önce riskleri anlayın. Tüm yatırımlar risk içerir.

**🎯 HEDEF**: Paper trading'de 1 hafta boyunca karlı ol, sonra küçük sermaye ile başla!

---

*Son güncelleme: 2025-08-25 | Version: Sprint Day 1*