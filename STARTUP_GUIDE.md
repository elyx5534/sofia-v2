# Sofia V2 - Windows Startup Guide 🚀

Bu kılavuz, Windows'ta Sofia V2'yi başlatırken karşılaşılan sorunları çözmek için hazırlanmıştır.

## 🔧 Karşılaşılan Sorunlar ve Çözümleri

### 1. Path Sorunları
**Sorun**: `Path D:\d\BORSA2\sofia-v2\sofia_ui was not found.`
**Çözüm**: Claude settings.local.json dosyasında path düzeltildi.

### 2. Cygwin/Bash Hataları
**Sorun**: `child_copy: cygheap read copy failed`
**Çözüm**: PowerShell ve Batch alternatifi eklendi.

### 3. Bun Memory Hatası
**Sorun**: `RangeError: Out of memory`
**Çözüm**: Node.js memory limitleri artırıldı, Bun yerine npm kullanımı.

## 🚀 Başlatma Seçenekleri

### Seçenek 1: Geliştirilmiş PowerShell Script (Önerilen)
```powershell
.\start_sofia.ps1
```

**Parametreler:**
- `-SkipFetch`: İlk veri çekmeyi atla
- `-SkipNews`: Haber güncellemesini atla
- `-Port 9000`: Farklı port kullan
- `-Debug`: Debug modunda çalıştır
- `-UseAlternativeUI`: Alternatif UI kullan

**Örnek:**
```powershell
.\start_sofia.ps1 -Port 9000 -Debug -SkipFetch
```

### Seçenek 2: Basit Batch Dosyası
```cmd
start_sofia.bat
```
- Execution policy sorunlarını önler
- Daha basit ve güvenilir
- Otomatik dependency kontrolü

### Seçenek 3: Orijinal PowerShell Script
```powershell
.\run.ps1
```
- Memory optimizasyonları eklendi
- Geliştirilmiş hata yönetimi

### Seçenek 4: Manuel Başlatma
```powershell
# Dependencies
pip install fastapi uvicorn ccxt pandas pyarrow polars httpx apscheduler loguru python-dotenv jinja2

# Start server
python sofia_cli.py web --host 127.0.0.1 --port 8000
```

## 🔍 Sorun Giderme

### Memory Sorunları
```powershell
# Node.js memory limiti artır
$env:NODE_OPTIONS = "--max_old_space_size=4096"
```

### Port Çakışması
```powershell
# Farklı port kullan
python sofia_cli.py web --port 9000
```

### Dependency Sorunları
```powershell
# Python packages
pip install --upgrade -r requirements.txt

# Node.js packages (opsiyonel)
npm install lightweight-charts --no-optional
```

### Alternatif UI
Eğer ana UI çalışmıyorsa:
```powershell
python -m uvicorn sofia_ui.server:app --host 127.0.0.1 --port 8000 --reload
```

## 📊 Sistem Gereksinimleri

- **Python**: 3.11+
- **Node.js**: 16+ (opsiyonel, charts için)
- **RAM**: En az 4GB (8GB önerilen)
- **Disk**: 1GB boş alan
- **OS**: Windows 10/11

## 🌐 Erişim Adresleri

Başarılı başlatma sonrası:
- **Ana Dashboard**: http://127.0.0.1:8000
- **API Dokümantasyonu**: http://127.0.0.1:8000/docs
- **Signals**: http://127.0.0.1:8000/signals
- **Charts**: http://127.0.0.1:8000/chart/BTC/USDT
- **News**: http://127.0.0.1:8000/news

## 🆘 Hala Sorun mu Var?

1. **PowerShell Execution Policy**:
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```

2. **Python PATH Sorunu**:
   - Python'u PATH'e ekleyin
   - `python` yerine `py` komutunu deneyin

3. **Port Kullanımda**:
   ```powershell
   netstat -ano | findstr :8000
   ```

4. **Alternatif Başlatma**:
   ```powershell
   .\start_sofia.bat
   ```

## 📝 Notlar

- İlk çalıştırma 5-10 dakika sürebilir (veri indirme)
- Charts için Node.js gerekli değil (fallback modu)
- Debug modu daha detaylı log sağlar
- Memory sorunları için sistem yeniden başlatın


