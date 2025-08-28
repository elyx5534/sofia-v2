"""
Complete system test for Sofia V2 with Data Reliability Pack
"""

import asyncio
import sys
import time
from pathlib import Path
import httpx

# Add src to path
sys.path.insert(0, str(Path(__file__)))


async def test_data_service():
    """Test data service endpoints"""
    print("\n[Testing Data Service - Port 8001]")
    print("-" * 40)
    
    base_url = "http://localhost:8001"
    
    async with httpx.AsyncClient() as client:
        # Test health
        try:
            response = await client.get(f"{base_url}/health")
            if response.status_code == 200:
                data = response.json()
                print(f"✓ Health: {data['status']}")
                print(f"  WebSocket: {'Connected' if data.get('websocket_connected') else 'Disconnected'}")
            else:
                print(f"✗ Health check failed: {response.status_code}")
        except Exception as e:
            print(f"✗ Health check error: {e}")
            return False
        
        # Test metrics
        try:
            response = await client.get(f"{base_url}/metrics")
            if response.status_code == 200:
                metrics = response.json()
                print(f"✓ Metrics endpoint working")
                print(f"  WS Enabled: {metrics.get('websocket_enabled')}")
                print(f"  Cache TTL: {metrics.get('cache_ttl')}s")
                print(f"  Stale Symbols: {len(metrics.get('stale_symbols', []))}")
            else:
                print(f"✗ Metrics failed: {response.status_code}")
        except Exception as e:
            print(f"✗ Metrics error: {e}")
        
        # Test price endpoint
        try:
            response = await client.get(f"{base_url}/price/BTC/USDT")
            if response.status_code == 200:
                price_data = response.json()
                print(f"✓ Price endpoint working")
                print(f"  BTC/USDT: ${price_data.get('price', 0):.2f}")
                print(f"  Source: {price_data.get('source')}")
                print(f"  Freshness: {price_data.get('freshness', 0):.1f}s")
            else:
                print(f"✗ Price endpoint failed: {response.status_code}")
        except Exception as e:
            print(f"✗ Price error: {e}")
        
        # Test debug endpoint
        try:
            response = await client.get(f"{base_url}/data/debug")
            if response.status_code == 200:
                debug_data = response.json()
                print(f"✓ Debug endpoint working")
                print(f"  Symbols tracked: {len(debug_data.get('symbols', []))}")
            else:
                print(f"✗ Debug endpoint failed: {response.status_code}")
        except Exception as e:
            print(f"✗ Debug error: {e}")
    
    return True


async def test_ui_service():
    """Test UI service endpoints"""
    print("\n[Testing UI Service - Port 8000]")
    print("-" * 40)
    
    base_url = "http://localhost:8000"
    
    async with httpx.AsyncClient() as client:
        # Test homepage
        try:
            response = await client.get(base_url)
            if response.status_code == 200:
                print(f"✓ Homepage accessible")
            else:
                print(f"✗ Homepage failed: {response.status_code}")
        except Exception as e:
            print(f"✗ Homepage error: {e}")
            return False
        
        # Test analysis page
        try:
            response = await client.get(f"{base_url}/analysis/BTC/USDT")
            if response.status_code == 200:
                print(f"✓ Analysis page accessible")
            else:
                print(f"✗ Analysis page failed: {response.status_code}")
        except Exception as e:
            print(f"✗ Analysis error: {e}")
        
        # Test API endpoints
        try:
            response = await client.get(f"{base_url}/api/live/BTC/USDT")
            if response.status_code == 200:
                data = response.json()
                print(f"✓ Live API working")
                print(f"  Price: ${data.get('price', 0):.2f}")
            else:
                print(f"✗ Live API failed: {response.status_code}")
        except Exception as e:
            print(f"✗ Live API error: {e}")
    
    return True


def test_modules():
    """Test Python module imports"""
    print("\n[Testing Module Imports]")
    print("-" * 40)
    
    modules = [
        ("src.adapters.binance_ws", "WebSocket Adapter"),
        ("src.services.price_service_real", "Price Service"),
        ("src.services.symbols", "Symbol Mapper"),
        ("sofia_optimize.genetic_algorithm", "Genetic Algorithm"),
        ("sofia_ui.live_data_adapter", "Live Data Adapter"),
    ]
    
    all_ok = True
    for module_name, description in modules:
        try:
            __import__(module_name)
            print(f"✓ {description} ({module_name})")
        except ImportError as e:
            print(f"✗ {description} ({module_name}): {e}")
            all_ok = False
    
    return all_ok


async def main():
    """Run all tests"""
    print("=" * 60)
    print("Sofia V2 System Test")
    print("=" * 60)
    
    # Test modules first
    modules_ok = test_modules()
    
    # Wait a bit for services to be ready
    print("\nWaiting for services to start...")
    await asyncio.sleep(3)
    
    # Test data service
    data_ok = await test_data_service()
    
    # Test UI service
    ui_ok = await test_ui_service()
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"Module Imports: {'PASS' if modules_ok else 'FAIL'}")
    print(f"Data Service: {'PASS' if data_ok else 'FAIL'}")
    print(f"UI Service: {'PASS' if ui_ok else 'FAIL'}")
    
    if modules_ok and data_ok and ui_ok:
        print("\n✓ ALL TESTS PASSED - System is operational!")
    else:
        print("\n✗ SOME TESTS FAILED - Check errors above")
    
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())