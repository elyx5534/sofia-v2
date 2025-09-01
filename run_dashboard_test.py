#!/usr/bin/env python3
"""
Run Dashboard E2E Test
"""

import subprocess
import sys
import time
import os

def check_npm_packages():
    """Check if Playwright is installed"""
    try:
        result = subprocess.run(
            ["npm", "list", "@playwright/test"],
            capture_output=True,
            text=True
        )
        if "empty" in result.stdout or "not found" in result.stderr:
            print("📦 Installing Playwright...")
            subprocess.run(["npm", "install", "-D", "@playwright/test"])
            subprocess.run(["npx", "playwright", "install", "chromium"])
    except Exception as e:
        print(f"⚠️  Error checking npm packages: {e}")

def start_api():
    """Start API server"""
    print("🚀 Starting API server...")
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "src.api.main:app", "--port", "8000"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    
    # Wait for API to start
    print("⏳ Waiting for API to start...")
    time.sleep(5)
    
    # Test if API is running
    import requests
    try:
        response = requests.get("http://localhost:8000/api/health", timeout=5)
        if response.status_code == 200:
            print("✅ API server is running")
            return process
    except:
        pass
    
    print("❌ Failed to start API server")
    process.terminate()
    return None

def run_e2e_test():
    """Run the E2E test"""
    print("\n🧪 Running Dashboard E2E Tests...")
    print("-" * 50)
    
    try:
        result = subprocess.run(
            ["npx", "playwright", "test", "tests/e2e/dashboard.spec.ts", "--project=chromium"],
            capture_output=True,
            text=True
        )
        
        print(result.stdout)
        
        if result.returncode == 0:
            print("\n✅ All E2E tests passed!")
            return True
        else:
            print("\n❌ Some tests failed:")
            print(result.stderr)
            return False
            
    except FileNotFoundError:
        print("❌ Playwright not found. Installing...")
        check_npm_packages()
        return False
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return False

def main():
    """Main runner"""
    print("=" * 50)
    print("Dashboard E2E Test Runner")
    print("=" * 50)
    
    # Check/install dependencies
    check_npm_packages()
    
    # Start API
    api_process = start_api()
    if not api_process:
        print("Cannot run tests without API server")
        sys.exit(1)
    
    try:
        # Run tests
        success = run_e2e_test()
        
        if success:
            print("\n🎉 Dashboard E2E tests completed successfully!")
        else:
            print("\n⚠️  Some tests failed. Check the output above.")
            
    finally:
        # Cleanup
        print("\n🧹 Cleaning up...")
        if api_process:
            api_process.terminate()
            print("API server stopped")
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)