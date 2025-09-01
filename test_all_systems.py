"""
Sofia V2 - Comprehensive System Test
Tests all components and provides a complete status report
"""

import sys
import time
import asyncio
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

# Test results storage
test_results = {
    "passed": [],
    "failed": [],
    "warnings": []
}

def print_header(title: str):
    """Print formatted header"""
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)

def print_test(name: str, status: str, details: str = ""):
    """Print test result"""
    symbols = {
        "pass": "[OK]",
        "fail": "[FAIL]",
        "warn": "[WARN]",
        "info": "[INFO]"
    }
    
    symbol = symbols.get(status, "[?]")
    print(f"{symbol} {name}")
    if details:
        print(f"      {details}")
    
    # Store result
    if status == "pass":
        test_results["passed"].append(name)
    elif status == "fail":
        test_results["failed"].append((name, details))
    elif status == "warn":
        test_results["warnings"].append((name, details))

def test_python_version():
    """Test Python version"""
    version = sys.version_info
    if version.major == 3 and version.minor >= 11:
        print_test("Python Version", "pass", f"Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print_test("Python Version", "fail", f"Python 3.11+ required, found {version.major}.{version.minor}")
        return False

def test_imports():
    """Test all required imports"""
    modules = [
        ("fastapi", "Web framework"),
        ("uvicorn", "ASGI server"),
        ("websockets", "WebSocket support"),
        ("redis", "Redis client"),
        ("orjson", "JSON serialization"),
        ("aiohttp", "Async HTTP"),
        ("nats", "NATS messaging"),
        ("pandas", "Data analysis"),
        ("numpy", "Numerical computing"),
        ("pydantic", "Data validation"),
        ("typer", "CLI framework"),
        ("rich", "Terminal formatting"),
        ("httpx", "HTTP client"),
        ("yaml", "YAML support")
    ]
    
    all_ok = True
    for module, description in modules:
        try:
            __import__(module)
            print_test(f"Import {module}", "pass", description)
        except ImportError as e:
            print_test(f"Import {module}", "fail", str(e))
            all_ok = False
    
    return all_ok

def test_sofia_modules():
    """Test Sofia-specific modules"""
    modules = [
        ("sofia_datahub", "Data ingestion module"),
        ("sofia_strategies", "Trading strategies"),
        ("sofia_backtest.paper", "Paper trading engine"),
        ("sofia_cli", "Command-line interface"),
    ]
    
    all_ok = True
    for module, description in modules:
        try:
            __import__(module)
            print_test(f"Sofia module: {module}", "pass", description)
        except ImportError as e:
            print_test(f"Sofia module: {module}", "fail", str(e))
            all_ok = False
    
    return all_ok

def test_configuration_files():
    """Test configuration files exist"""
    config_files = [
        "configs/strategies/grid.yaml",
        "configs/strategies/trend.yaml",
        "configs/portfolio/paper_default.yaml",
        "infra/docker-compose.yml",
        "infra/ch_bootstrap.sql",
    ]
    
    all_ok = True
    for config_file in config_files:
        path = Path(config_file)
        if path.exists():
            print_test(f"Config file: {config_file}", "pass")
        else:
            print_test(f"Config file: {config_file}", "fail", "File not found")
            all_ok = False
    
    return all_ok

def test_services():
    """Test external services connectivity"""
    import requests
    
    services = [
        ("http://localhost:8123/ping", "ClickHouse"),
        ("http://localhost:8222/varz", "NATS"),
        ("http://localhost:3000/api/health", "Grafana"),
    ]
    
    all_ok = True
    for url, service in services:
        try:
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                print_test(f"Service: {service}", "pass", f"Reachable at {url}")
            else:
                print_test(f"Service: {service}", "warn", f"Returned status {response.status_code}")
        except:
            print_test(f"Service: {service}", "warn", "Not running (Docker may be stopped)")
            all_ok = False
    
    # Redis test
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, socket_connect_timeout=2)
        r.ping()
        print_test("Service: Redis", "pass", "Connected successfully")
    except:
        print_test("Service: Redis", "warn", "Not running (Docker may be stopped)")
        all_ok = False
    
    return all_ok

def test_demo_servers():
    """Test if demo servers are accessible"""
    import requests
    
    demos = [
        ("http://localhost:8000", "Quick Demo"),
        ("http://localhost:8001", "Ultimate Dashboard"),
    ]
    
    for url, name in demos:
        try:
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                print_test(f"Demo: {name}", "pass", f"Running at {url}")
            else:
                print_test(f"Demo: {name}", "info", f"Not running (start with: python {name.lower().replace(' ', '_')}.py)")
        except:
            print_test(f"Demo: {name}", "info", "Not currently running")

def test_cli_commands():
    """Test CLI commands"""
    commands = [
        (["python", "-m", "sofia_cli", "version"], "CLI version"),
        (["python", "-m", "sofia_cli", "status"], "CLI status"),
    ]
    
    for cmd, description in commands:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                print_test(f"CLI: {description}", "pass")
            else:
                print_test(f"CLI: {description}", "fail", result.stderr[:100])
        except subprocess.TimeoutExpired:
            print_test(f"CLI: {description}", "fail", "Command timed out")
        except Exception as e:
            print_test(f"CLI: {description}", "fail", str(e))

def test_strategies():
    """Test strategy modules"""
    try:
        from sofia_strategies import GridStrategy, TrendStrategy
        
        # Test Grid Strategy
        grid = GridStrategy({"base_qty": 20, "grid_levels": 5})
        grid.initialize("BTCUSDT", None)
        print_test("Strategy: Grid", "pass", "Initialized successfully")
        
        # Test Trend Strategy
        trend = TrendStrategy({"fast_ma": 20, "slow_ma": 60})
        trend.initialize("BTCUSDT", None)
        print_test("Strategy: Trend", "pass", "Initialized successfully")
        
        return True
    except Exception as e:
        print_test("Strategies", "fail", str(e))
        return False

async def test_websocket():
    """Test WebSocket connectivity"""
    try:
        import websockets
        
        # Try to connect to demo WebSocket
        try:
            async with websockets.connect("ws://localhost:8001/ws", timeout=2) as ws:
                print_test("WebSocket", "pass", "Connected to Ultimate Dashboard WS")
                return True
        except:
            print_test("WebSocket", "info", "Demo WebSocket not available (server not running)")
            return False
            
    except ImportError:
        print_test("WebSocket", "fail", "websockets module not installed")
        return False

def generate_report():
    """Generate final test report"""
    print_header("TEST REPORT SUMMARY")
    
    total_tests = len(test_results["passed"]) + len(test_results["failed"])
    
    print(f"\nTotal Tests: {total_tests}")
    print(f"Passed: {len(test_results['passed'])}")
    print(f"Failed: {len(test_results['failed'])}")
    print(f"Warnings: {len(test_results['warnings'])}")
    
    if test_results["failed"]:
        print("\n[FAILED TESTS]")
        for name, details in test_results["failed"]:
            print(f"  - {name}: {details}")
    
    if test_results["warnings"]:
        print("\n[WARNINGS]")
        for name, details in test_results["warnings"]:
            print(f"  - {name}: {details}")
    
    # Success rate
    if total_tests > 0:
        success_rate = (len(test_results["passed"]) / total_tests) * 100
        print(f"\nSuccess Rate: {success_rate:.1f}%")
        
        if success_rate == 100:
            print("\n[SUCCESS] All tests passed! System is fully operational.")
        elif success_rate >= 80:
            print("\n[GOOD] Most tests passed. System is mostly operational.")
        elif success_rate >= 60:
            print("\n[OK] Core functionality working. Some issues need attention.")
        else:
            print("\n[ATTENTION] Many tests failed. System needs configuration.")
    
    # Recommendations
    print("\n[RECOMMENDATIONS]")
    
    if any("Docker" in str(w) for w in test_results["warnings"]):
        print("  1. Start Docker Desktop and run: docker compose -f infra/docker-compose.yml up -d")
    
    if any("Import" in str(f) for f in test_results["failed"]):
        print("  2. Install missing packages: pip install -r requirements.txt")
    
    if len(test_results["failed"]) == 0:
        print("  1. System is ready! Start the Ultimate Dashboard:")
        print("     python sofia_ultimate_dashboard.py")
        print("  2. Or use the complete system:")
        print("     .\\scripts\\sofia_dev.ps1")

def main():
    """Run all tests"""
    print_header("SOFIA V2 SYSTEM TEST")
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Run tests
    print_header("Environment Tests")
    test_python_version()
    
    print_header("Dependencies Tests")
    test_imports()
    
    print_header("Sofia Modules Tests")
    test_sofia_modules()
    
    print_header("Configuration Tests")
    test_configuration_files()
    
    print_header("External Services Tests")
    test_services()
    
    print_header("Demo Servers Tests")
    test_demo_servers()
    
    print_header("CLI Tests")
    test_cli_commands()
    
    print_header("Strategy Tests")
    test_strategies()
    
    print_header("WebSocket Tests")
    asyncio.run(test_websocket())
    
    # Generate report
    generate_report()
    
    print("\n" + "=" * 60)
    print(" Test Complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()