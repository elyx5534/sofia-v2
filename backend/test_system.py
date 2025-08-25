#!/usr/bin/env python3
"""
Sofia V2 Realtime DataHub - System Test
Basic validation of configuration and imports
"""

import sys
import os
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

def test_imports():
    """Test that all modules can be imported"""
    print("Testing imports...")
    
    try:
        from app.config import get_settings, Settings
        print("[OK] Configuration module imported")
        
        from app.bus import EventBus, EventType
        print("[OK] Event bus module imported")
        
        from app.news.cryptopanic_rss import CryptoPanicRSSIngestor
        print("[OK] News ingestor imported")
        
        from app.ingestors.binance import BinanceIngestor
        from app.ingestors.okx import OKXIngestor
        from app.ingestors.bybit import BybitIngestor
        from app.ingestors.coinbase import CoinbaseIngestor
        print("[OK] Exchange ingestors imported")
        
        from app.features.detectors import DetectorManager
        print("[OK] Anomaly detectors imported")
        
        from app.store.parquet import ParquetStore
        from app.store.timescale import TimescaleStore
        print("[OK] Storage modules imported")
        
        print("[OK] All imports successful!")
        return True
        
    except ImportError as e:
        print(f"[ERROR] Import error: {e}")
        return False

def test_configuration():
    """Test configuration loading and validation"""
    print("\nTesting configuration...")
    
    try:
        from app.config import get_settings
        settings = get_settings()
        
        print(f"[OK] Symbols: {settings.symbols_list}")
        print(f"[OK] Enabled exchanges: {settings.get_enabled_exchanges()}")
        print(f"[OK] News enabled: {settings.cryptopanic_enabled}")
        print(f"[OK] TimescaleDB enabled: {settings.use_timescale}")
        print(f"[OK] Metrics enabled: {settings.enable_metrics}")
        
        # Test validation
        is_valid = settings.validate_config()
        if is_valid:
            print("[OK] Configuration validation passed")
        else:
            print("[WARN] Configuration validation has warnings")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Configuration error: {e}")
        return False

def test_event_bus():
    """Test event bus functionality"""
    print("\nTesting event bus...")
    
    try:
        from app.bus import EventBus, EventType
        import asyncio
        
        bus = EventBus()
        test_received = []
        
        async def test_handler(data):
            test_received.append(data)
        
        # Subscribe and publish
        bus.subscribe(EventType.TRADE, test_handler)
        
        async def test_publish():
            await bus.publish(EventType.TRADE, {"test": "data"})
        
        # Run the test
        asyncio.run(test_publish())
        
        if test_received:
            print("[OK] Event bus pub/sub working")
            return True
        else:
            print("[ERROR] Event bus not working")
            return False
        
    except Exception as e:
        print(f"[ERROR] Event bus error: {e}")
        return False

def test_detectors():
    """Test anomaly detector initialization"""
    print("\nTesting anomaly detectors...")
    
    try:
        from app.bus import EventBus
        from app.config import get_settings
        from app.features.detectors import DetectorManager
        
        bus = EventBus()
        settings = get_settings()
        detector_manager = DetectorManager(bus, settings)
        
        status = detector_manager.get_status()
        print(f"[OK] Detector manager initialized")
        print(f"  - Big trade detector: {status['big_trade_detector']['enabled']}")
        print(f"  - Liquidation spike detector: {status['liquidation_spike_detector']['enabled']}")
        print(f"  - Volume surge detector: {status['volume_surge_detector']['enabled']}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Detector initialization error: {e}")
        return False

def test_storage():
    """Test storage module initialization"""
    print("\nTesting storage modules...")
    
    try:
        from app.bus import EventBus
        from app.config import get_settings
        from app.store.parquet import ParquetStore
        from app.store.timescale import TimescaleStore
        
        bus = EventBus()
        settings = get_settings()
        
        # Test Parquet store
        parquet_store = ParquetStore(bus, settings)
        parquet_status = parquet_store.get_status()
        print(f"[OK] Parquet store initialized (enabled: {parquet_status['enabled']})")
        
        # Test TimescaleDB store (if enabled)
        if settings.use_timescale:
            timescale_store = TimescaleStore(bus, settings)
            timescale_status = timescale_store.get_status()
            print(f"[OK] TimescaleDB store initialized (enabled: {timescale_status['enabled']})")
        else:
            print("[INFO] TimescaleDB store disabled in configuration")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Storage initialization error: {e}")
        return False

def main():
    """Run all tests"""
    print("Sofia V2 DataHub - System Test")
    print("=" * 50)
    
    tests = [
        ("Import Tests", test_imports),
        ("Configuration Tests", test_configuration),
        ("Event Bus Tests", test_event_bus),
        ("Detector Tests", test_detectors),
        ("Storage Tests", test_storage)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{test_name}")
        print("-" * 30)
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"[ERROR] Test failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\nTest Summary")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "PASSED" if result else "FAILED"
        print(f"[{status}] - {test_name}")
        if result:
            passed += 1
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("All tests passed! System is ready.")
        return 0
    else:
        print("Some tests failed. Check the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())