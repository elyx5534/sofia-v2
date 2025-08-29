#!/usr/bin/env python3
"""
Sofia V2 API Startup Script
Starts the main API server with all endpoints
"""

import os
import sys
import time
import subprocess
import signal

def start_api():
    """Start the API server"""
    print("🚀 Starting Sofia V2 API...")
    
    # API configuration
    api_host = os.getenv("SOFIA_API_HOST", "127.0.0.1")
    api_port = int(os.getenv("SOFIA_API_PORT", "8013"))
    
    # Start API
    cmd = [
        sys.executable, "-m", "uvicorn",
        "src.api.main:app",
        "--host", api_host,
        "--port", str(api_port),
        "--reload"
    ]
    
    print(f"📡 API will be available at http://{api_host}:{api_port}")
    print("📊 Health check: http://{api_host}:{api_port}/health")
    print("🎯 AI Score: POST http://{api_host}:{api_port}/ai/score")
    print("💰 Trade Account: GET http://{api_host}:{api_port}/trade/account")
    print("📈 Metrics: GET http://{api_host}:{api_port}/metrics")
    print("\nPress Ctrl+C to stop")
    
    try:
        process = subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n👋 Shutting down API...")
        sys.exit(0)

if __name__ == "__main__":
    start_api()