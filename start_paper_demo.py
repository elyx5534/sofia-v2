#!/usr/bin/env python3
"""
Start Paper Trading Demo
Launches API and runs paper trading session
"""

import asyncio
import subprocess
import sys
import time
from pathlib import Path


def start_api():
    """Start the API server in background"""
    print("🚀 Starting API server...")
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "src.api.main:app", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for API to start
    time.sleep(3)

    # Test if API is running
    import requests

    try:
        response = requests.get("http://localhost:8000/api/health", timeout=5)
        if response.status_code == 200:
            print("✅ API server started successfully")
            return process
    except:
        pass

    print("❌ Failed to start API server")
    process.terminate()
    return None


async def run_paper_session():
    """Run paper trading session"""
    print("\n📊 Starting Paper Trading Session...")
    print("-" * 40)

    # Import the session runner
    sys.path.append(str(Path(__file__).parent))
    from tools.run_paper_session import run_paper_session

    try:
        # Run 5-minute demo session
        summary = await run_paper_session(duration_minutes=5)

        print("\n" + "=" * 60)
        print("DEMO COMPLETE")
        print("=" * 60)
        print(f"Total P&L: ${summary['total_pnl']:.2f} USDT")
        print(f"Return: {summary['pnl_percentage']:.2f}%")
        print(f"Trades: {summary['total_trades']}")

        # Show where to find details
        print("\n📁 Output Files:")
        print("  - logs/paper_audit.log - Trade details")
        print("  - logs/paper_session_summary.json - Session summary")

        return True

    except Exception as e:
        print(f"❌ Paper trading failed: {e}")
        return False


async def main():
    """Main demo runner"""
    print("=" * 60)
    print("SOFIA V2 - PAPER TRADING DEMO")
    print("=" * 60)

    # Start API
    api_process = start_api()
    if not api_process:
        print("Cannot proceed without API server")
        sys.exit(1)

    try:
        # Run paper trading
        success = await run_paper_session()

        if success:
            print("\n✅ Demo completed successfully!")
        else:
            print("\n❌ Demo failed")

    finally:
        # Cleanup
        print("\n🧹 Cleaning up...")
        if api_process:
            api_process.terminate()
            print("API server stopped")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Demo interrupted by user")
        sys.exit(1)
