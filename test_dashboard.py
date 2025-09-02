#!/usr/bin/env python3
"""
Test Dashboard Endpoints
"""

import json
import sys
from pathlib import Path

import requests


def test_dashboard():
    """Test dashboard endpoints"""
    base_url = "http://localhost:8000"

    print("Testing Dashboard Endpoints...")
    print("=" * 50)

    # Test dashboard HTML
    try:
        response = requests.get(f"{base_url}/dashboard", timeout=5)
        if response.status_code == 200 and "Sofia V2 P&L Dashboard" in response.text:
            print("✅ /dashboard - HTML served successfully")
        else:
            print(f"❌ /dashboard - Failed: {response.status_code}")
    except Exception as e:
        print(f"❌ /dashboard - Error: {e}")
        print("\n⚠️  Make sure the API is running:")
        print("    uvicorn src.api.main:app --port 8000")
        return False

    # Test P&L summary endpoint
    try:
        response = requests.get(f"{base_url}/api/pnl/summary", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print("✅ /api/pnl/summary - OK")
            print(f"   - Initial Capital: ${data.get('initial_capital', 0)}")
            print(f"   - Final Capital: ${data.get('final_capital', 0)}")
            print(f"   - Total P&L: ${data.get('total_pnl', 0):.2f}")
            print(f"   - Source: {data.get('source', 'unknown')}")
        else:
            print(f"❌ /api/pnl/summary - Failed: {response.status_code}")
    except Exception as e:
        print(f"❌ /api/pnl/summary - Error: {e}")

    # Test logs tail endpoint
    try:
        response = requests.get(f"{base_url}/api/pnl/logs/tail?n=5", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print("✅ /api/pnl/logs/tail - OK")
            print(f"   - Lines returned: {data.get('count', 0)}")
            print(f"   - Total lines in log: {data.get('total_lines', 0)}")
        else:
            print(f"❌ /api/pnl/logs/tail - Failed: {response.status_code}")
    except Exception as e:
        print(f"❌ /api/pnl/logs/tail - Error: {e}")

    # Create test P&L summary if none exists
    pnl_path = Path("logs/pnl_summary.json")
    if not pnl_path.exists():
        print("\n📝 Creating test P&L summary...")
        pnl_path.parent.mkdir(exist_ok=True)
        test_summary = {
            "initial_capital": 1000,
            "final_capital": 1015.50,
            "realized_pnl": 15.50,
            "unrealized_pnl": 0,
            "total_pnl": 15.50,
            "pnl_percentage": 1.55,
            "total_trades": 25,
            "win_rate": 68.0,
            "start_timestamp": "2024-01-01T09:00:00",
            "end_timestamp": "2024-01-01T09:30:00",
        }
        with open(pnl_path, "w") as f:
            json.dump(test_summary, f, indent=2)
        print(f"   Created test data at {pnl_path}")

    print("\n" + "=" * 50)
    print("Dashboard test complete!")
    print("\n🌐 Open http://localhost:8000/dashboard to see the live dashboard")

    return True


if __name__ == "__main__":
    success = test_dashboard()
    sys.exit(0 if success else 1)
