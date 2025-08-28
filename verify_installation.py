"""
Verify Data Reliability Pack installation
"""

import os
import sys
import json
from pathlib import Path

def check_file_exists(filepath, description):
    """Check if a file exists"""
    if Path(filepath).exists():
        print(f"[OK] {description}: {filepath}")
        return True
    else:
        print(f"[FAIL] {description}: {filepath} not found")
        return False

def check_imports():
    """Check required imports"""
    try:
        import websockets
        print("[OK] websockets module imported")
    except ImportError:
        print("[FAIL] websockets module not available")
        return False
    
    try:
        import httpx
        print("[OK] httpx module imported")
    except ImportError:
        print("[FAIL] httpx module not available")
        return False
    
    try:
        import fastapi
        print("[OK] fastapi module imported")
    except ImportError:
        print("[FAIL] fastapi module not available")
        return False
    
    return True

def main():
    print("=" * 60)
    print("Sofia V2 Data Reliability Pack - Installation Verification")
    print("=" * 60)
    print()
    
    # Check directory structure
    print("Checking directory structure...")
    base_path = Path(__file__).parent
    
    dirs_ok = all([
        check_file_exists(base_path / "src/adapters/binance_ws.py", "WebSocket adapter"),
        check_file_exists(base_path / "src/services/price_service_real.py", "Price service"),
        check_file_exists(base_path / "src/services/symbols.py", "Symbol mapper"),
        check_file_exists(base_path / "src/config/symbol_map.json", "Symbol config"),
        check_file_exists(base_path / "src/api/main.py", "API server"),
        check_file_exists(base_path / "scripts/sofiactl_data.py", "CLI tool"),
        check_file_exists(base_path / "tests/test_symbol_map.py", "Symbol test"),
        check_file_exists(base_path / "tests/test_metrics_contract.py", "Metrics test"),
    ])
    
    print()
    print("Checking Python imports...")
    imports_ok = check_imports()
    
    print()
    print("Checking symbol configuration...")
    try:
        with open(base_path / "src/config/symbol_map.json", 'r') as f:
            config = json.load(f)
            symbols = list(config.get('mappings', {}).keys())
            print(f"[OK] Symbol mappings loaded: {len(symbols)} symbols")
            print(f"     Symbols: {', '.join(symbols[:6])}")
    except Exception as e:
        print(f"[FAIL] Could not load symbol config: {e}")
    
    print()
    print("Checking environment defaults...")
    env_vars = {
        'SOFIA_WS_ENABLED': os.getenv('SOFIA_WS_ENABLED', 'true'),
        'SOFIA_WS_PING_SEC': os.getenv('SOFIA_WS_PING_SEC', '20'),
        'SOFIA_PRICE_CACHE_TTL': os.getenv('SOFIA_PRICE_CACHE_TTL', '10'),
    }
    for key, value in env_vars.items():
        print(f"  {key}={value}")
    
    print()
    print("=" * 60)
    if dirs_ok and imports_ok:
        print("VERIFICATION PASSED - Ready to start service")
        print()
        print("Next steps:")
        print("1. Start service: start_data_service.bat")
        print("2. Check status: python scripts/sofiactl_data.py status")
        print("3. Run tests: run_tests.bat")
    else:
        print("VERIFICATION FAILED - Please check errors above")
    print("=" * 60)

if __name__ == "__main__":
    main()