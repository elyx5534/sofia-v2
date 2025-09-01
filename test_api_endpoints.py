#!/usr/bin/env python3
"""
Quick test to verify API endpoints are working
"""

import requests
import sys

def test_endpoints():
    """Test main API endpoints"""
    base_url = "http://localhost:8000"
    
    print("Testing API Endpoints...")
    print("-" * 40)
    
    # Test /api/health
    try:
        response = requests.get(f"{base_url}/api/health", timeout=5)
        if response.status_code == 200 and response.json().get("status") == "ok":
            print("✅ /api/health - OK")
        else:
            print(f"❌ /api/health - Failed: {response.status_code}")
    except Exception as e:
        print(f"❌ /api/health - Error: {e}")
        print("\n⚠️  Make sure the API is running:")
        print("    uvicorn src.api.main:app --port 8000")
        return False
    
    # Test /live-proof
    try:
        response = requests.get(f"{base_url}/live-proof?symbol=BTC/USDT", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "symbol" in data and "bid" in data and "ask" in data:
                print(f"✅ /live-proof - OK (BTC: ${data.get('last', 'N/A')})")
            else:
                print(f"❌ /live-proof - Invalid response format")
        else:
            print(f"❌ /live-proof - Failed: {response.status_code}")
    except Exception as e:
        print(f"❌ /live-proof - Error: {e}")
    
    # Test /health (detailed)
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "healthy":
                print("✅ /health - OK (detailed health)")
            else:
                print(f"❌ /health - Unhealthy status")
        else:
            print(f"❌ /health - Failed: {response.status_code}")
    except Exception as e:
        print(f"❌ /health - Error: {e}")
    
    # Test /docs
    try:
        response = requests.get(f"{base_url}/docs", timeout=5)
        if response.status_code == 200:
            print("✅ /docs - Swagger UI available")
        else:
            print(f"❌ /docs - Failed: {response.status_code}")
    except Exception as e:
        print(f"❌ /docs - Error: {e}")
    
    print("-" * 40)
    print("Test complete!")
    return True

if __name__ == "__main__":
    success = test_endpoints()
    sys.exit(0 if success else 1)