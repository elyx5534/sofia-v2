#!/usr/bin/env python3
"""
Sofia V2 DataHub - Manuel Test Script
Gerçek zamanlı veri akışını ve API'leri test eder
"""

import asyncio
import json
import sys
import time
from pathlib import Path

import httpx
import websockets

# Backend dizinini Python path'e ekle
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/ws"

async def test_rest_endpoints():
    """REST API endpoint'lerini test et"""
    print("🌐 REST API Testleri")
    print("=" * 50)
    
    endpoints = [
        "/health",
        "/health/detailed", 
        "/config",
        "/symbols",
        "/exchanges",
        "/detectors",
        "/storage"
    ]
    
    async with httpx.AsyncClient() as client:
        for endpoint in endpoints:
            try:
                response = await client.get(f"{BASE_URL}{endpoint}", timeout=5)
                if response.status_code == 200:
                    print(f"✅ {endpoint} - OK ({response.status_code})")
                    
                    # Bazı önemli yanıtları göster
                    if endpoint in ["/health", "/config"]:
                        data = response.json()
                        print(f"   📋 {json.dumps(data, indent=4)}")
                        
                else:
                    print(f"❌ {endpoint} - ERROR ({response.status_code})")
                    
            except Exception as e:
                print(f"❌ {endpoint} - EXCEPTION: {e}")
    
    print()

async def test_websocket_connection():
    """WebSocket bağlantısını test et"""
    print("🔌 WebSocket Bağlantı Testi")
    print("=" * 50)
    
    try:
        async with websockets.connect(WS_URL) as websocket:
            print("✅ WebSocket bağlantısı kuruldu")
            
            # Ping gönder
            await websocket.send("ping")
            print("📤 Ping gönderildi")
            
            # Yanıt bekle
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                if response == "pong":
                    print("📥 Pong alındı - Bağlantı aktif!")
                else:
                    print(f"📥 Yanıt alındı: {response}")
            except asyncio.TimeoutError:
                print("⏰ Ping yanıtı zaman aşımına uğradı")
            
            print("🎧 Real-time veri dinleniyor (10 saniye)...")
            
            # 10 saniye veri dinle
            message_count = 0
            start_time = time.time()
            
            while time.time() - start_time < 10:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=1)
                    data = json.loads(message)
                    message_count += 1
                    
                    # İlk birkaç mesajı detaylı göster
                    if message_count <= 3:
                        print(f"📊 Mesaj {message_count}: {data['type']}")
                        if 'data' in data:
                            # Sadece önemli alanları göster
                            sample_data = {}
                            for key in ['symbol', 'exchange', 'price', 'side', 'title'][:3]:
                                if key in data['data']:
                                    sample_data[key] = data['data'][key]
                            print(f"   📋 {json.dumps(sample_data, indent=6)}")
                    elif message_count % 10 == 0:
                        print(f"📈 {message_count} mesaj alındı...")
                        
                except asyncio.TimeoutError:
                    continue
                except json.JSONDecodeError:
                    print("❌ JSON decode hatası")
                    continue
            
            print(f"🏁 Test tamamlandı. Toplam {message_count} mesaj alındı.")
            
    except Exception as e:
        print(f"❌ WebSocket bağlantı hatası: {e}")
        print("💡 DataHub'ın çalıştığından emin olun: .\\scripts\\run.ps1")
    
    print()

async def test_data_directory():
    """Veri dizinini kontrol et"""
    print("📁 Veri Dizini Kontrolü") 
    print("=" * 50)
    
    data_dir = Path("data")
    
    if data_dir.exists():
        print("✅ Data dizini mevcut")
        
        # Alt dizinleri kontrol et
        subdirs = ["trades", "orderbook", "liquidations", "news", "alerts"]
        for subdir in subdirs:
            subdir_path = data_dir / subdir
            if subdir_path.exists():
                files = list(subdir_path.glob("*.parquet"))
                print(f"📂 {subdir}: {len(files)} dosya")
            else:
                print(f"📂 {subdir}: dizin mevcut değil")
    else:
        print("❌ Data dizini mevcut değil (normal, henüz veri gelmemiş olabilir)")
    
    print()

async def run_comprehensive_test():
    """Kapsamlı test süiti"""
    print("🚀 Sofia V2 DataHub - Kapsamlı Test")
    print("=" * 60)
    print()
    
    # DataHub'ın çalışıp çalışmadığını kontrol et
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/health", timeout=5)
            if response.status_code != 200:
                raise Exception("Health check failed")
    except Exception:
        print("❌ DataHub çalışmıyor!")
        print("💡 Önce DataHub'ı başlatın: .\\scripts\\run.ps1")
        print()
        return False
    
    print("✅ DataHub çalışıyor, testlere başlanıyor...\n")
    
    # Testleri sırayla çalıştır
    await test_rest_endpoints()
    await test_websocket_connection() 
    await test_data_directory()
    
    print("🎉 Tüm testler tamamlandı!")
    print()
    print("📋 Sonraki Adımlar:")
    print("1. WebSocket'ten gelen verileri inceleyin")
    print("2. /metrics endpoint'ini Prometheus ile izleyin")
    print("3. data/ dizinindeki Parquet dosyalarını kontrol edin")
    print("4. Production için Windows Service kurulumu yapın")
    print()
    
    return True

def main():
    """Ana test fonksiyonu"""
    try:
        result = asyncio.run(run_comprehensive_test())
        return 0 if result else 1
    except KeyboardInterrupt:
        print("\n🛑 Test kullanıcı tarafından durduruldu")
        return 1
    except Exception as e:
        print(f"\n❌ Test hatası: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())