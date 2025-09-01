"""
Sofia V2 System Startup Script
Simple script to test and start the system components
"""

import os
import sys
import time
import subprocess
from pathlib import Path

def check_docker():
    """Check if Docker is running"""
    try:
        result = subprocess.run(["docker", "ps"], capture_output=True, text=True)
        return result.returncode == 0
    except:
        return False

def check_service(url, service_name):
    """Check if a service is running"""
    try:
        import requests
        resp = requests.get(url, timeout=2)
        print(f"[OK] {service_name} is running")
        return True
    except:
        print(f"[FAIL] {service_name} is not running")
        return False

def start_infrastructure():
    """Start Docker infrastructure"""
    print("\n[START] Starting Docker infrastructure...")
    
    if not check_docker():
        print("[ERROR] Docker is not running. Please start Docker Desktop.")
        return False
    
    # Start Docker Compose
    compose_file = Path("infra/docker-compose.yml")
    if not compose_file.exists():
        print("[ERROR] Docker Compose file not found")
        return False
    
    print("Starting services with Docker Compose...")
    subprocess.run(["docker", "compose", "-f", "infra/docker-compose.yml", "up", "-d"])
    
    # Wait for services
    print("Waiting for services to start...")
    time.sleep(10)
    
    # Check services
    services_ok = True
    services_ok &= check_service("http://localhost:8123/ping", "ClickHouse")
    services_ok &= check_service("http://localhost:8222/varz", "NATS")
    
    return services_ok

def test_imports():
    """Test if all required modules can be imported"""
    print("\n[TEST] Testing imports...")
    
    modules_to_test = [
        ("sofia_datahub", "DataHub"),
        ("sofia_strategies", "Strategies"),
        ("sofia_backtest.paper", "Paper Trading"),
        ("sofia_cli", "CLI"),
    ]
    
    all_ok = True
    for module, name in modules_to_test:
        try:
            __import__(module)
            print(f"[OK] {name} module OK")
        except ImportError as e:
            print(f"[FAIL] {name} module failed: {e}")
            all_ok = False
    
    return all_ok

def main():
    """Main startup function"""
    print("=" * 60)
    print("Sofia V2 System Startup")
    print("=" * 60)
    
    # Test imports first
    if not test_imports():
        print("\n[ERROR] Module imports failed. Fixing...")
        
        # Try to fix common issues
        sys.path.insert(0, str(Path(__file__).parent))
        
        if not test_imports():
            print("[ERROR] Still failing. Please check your installation.")
            return 1
    
    # Start infrastructure
    if not start_infrastructure():
        print("\n[ERROR] Infrastructure startup failed")
        return 1
    
    print("\n[SUCCESS] System ready!")
    print("\n[INFO] Next steps:")
    print("1. Start DataHub:        python -m sofia_datahub")
    print("2. Start Paper Trading:  python -m sofia_backtest.paper")
    print("3. Start Web UI:         python -m sofia_ui.server_v2")
    print("\nOr use the all-in-one script:")
    print("   PowerShell: .\\scripts\\sofia_dev.ps1")
    print("   Bash:       ./scripts/sofia_dev.sh")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())