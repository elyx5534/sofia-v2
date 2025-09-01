#!/usr/bin/env python
"""
🚀 SOFIA V2 - ONE-CLICK DEMO STARTER
=====================================
Tek komutla tüm sistemi başlatır!
"""

import subprocess
import time
import webbrowser
import sys
import os
from pathlib import Path

# Colors for terminal
GREEN = '\033[92m'
BLUE = '\033[94m'
YELLOW = '\033[93m'
RED = '\033[91m'
RESET = '\033[0m'

def print_banner():
    """ASCII art banner"""
    print(f"""{BLUE}
    ╔══════════════════════════════════════════════════════╗
    ║                                                      ║
    ║        🚀 SOFIA V2 - AI TRADING PLATFORM 🚀         ║
    ║                                                      ║
    ║        One-Click Demo Starter                       ║
    ║        Version: 2.0 Production Ready                ║
    ║                                                      ║
    ╚══════════════════════════════════════════════════════╝
    {RESET}""")

def check_requirements():
    """Check if all requirements are installed"""
    print(f"{YELLOW}📦 Checking requirements...{RESET}")
    
    # Check Python version
    if sys.version_info < (3, 10):
        print(f"{RED}❌ Python 3.10+ required. Current: {sys.version}{RESET}")
        return False
    
    # Check if requirements are installed
    try:
        import fastapi
        import uvicorn
        import aiohttp
        print(f"{GREEN}✅ All requirements installed!{RESET}")
        return True
    except ImportError:
        print(f"{YELLOW}📥 Installing requirements...{RESET}")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
        return True

def start_backend():
    """Start backend API server"""
    print(f"\n{BLUE}🔧 Starting Backend API on port 8003...{RESET}")
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "src.data_hub.api:app", "--host", "0.0.0.0", "--port", "8003"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

def start_frontend():
    """Start frontend server"""
    print(f"{BLUE}🎨 Starting Frontend on port 8000...{RESET}")
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "sofia_ui.server:app", "--host", "0.0.0.0", "--port", "8000", "--reload"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

def start_cloudflare(optional=True):
    """Start Cloudflare tunnel (optional)"""
    if optional:
        response = input(f"\n{YELLOW}🌐 Do you want to expose to internet via Cloudflare? (y/n): {RESET}").lower()
        if response != 'y':
            return None
    
    print(f"{BLUE}🌍 Starting Cloudflare Tunnel...{RESET}")
    process = subprocess.Popen(
        ["npx", "cloudflared", "tunnel", "--url", "http://localhost:8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Wait for URL
    for line in process.stderr:
        if "trycloudflare.com" in line:
            url = line.split("https://")[1].split()[0]
            print(f"\n{GREEN}🌐 Public URL: https://{url}{RESET}")
            break
    
    return process

def wait_for_server(port, name):
    """Wait for server to be ready"""
    import socket
    for i in range(30):  # 30 seconds timeout
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('localhost', port))
            sock.close()
            if result == 0:
                print(f"{GREEN}✅ {name} is ready!{RESET}")
                return True
        except:
            pass
        time.sleep(1)
    return False

def main():
    """Main function"""
    print_banner()
    
    # Check requirements
    if not check_requirements():
        print(f"{RED}❌ Failed to install requirements{RESET}")
        return
    
    # Start servers
    backend = start_backend()
    time.sleep(2)
    
    frontend = start_frontend()
    time.sleep(2)
    
    # Wait for servers
    if not wait_for_server(8003, "Backend API"):
        print(f"{RED}❌ Backend failed to start{RESET}")
        return
    
    if not wait_for_server(8000, "Frontend"):
        print(f"{RED}❌ Frontend failed to start{RESET}")
        return
    
    # Print access info
    print(f"\n{GREEN}{'='*60}{RESET}")
    print(f"{GREEN}🎉 SOFIA V2 is running successfully!{RESET}")
    print(f"{GREEN}{'='*60}{RESET}\n")
    
    print(f"{BLUE}📱 Access URLs:{RESET}")
    print(f"   🏠 Local:     http://localhost:8000")
    print(f"   🌐 Network:   http://0.0.0.0:8000")
    print(f"   📚 API Docs:  http://localhost:8003/docs")
    
    print(f"\n{BLUE}📑 Available Pages:{RESET}")
    pages = [
        ("Dashboard", "/dashboard"),
        ("Portfolio", "/portfolio"),
        ("Markets", "/markets"),
        ("Trading", "/trading"),
        ("Strategies", "/strategies"),
        ("Backtest", "/backtest"),
    ]
    for name, path in pages:
        print(f"   • {name}: http://localhost:8000{path}")
    
    # Optionally start Cloudflare
    cloudflare = start_cloudflare(optional=True)
    
    # Open browser
    print(f"\n{YELLOW}🌐 Opening browser...{RESET}")
    time.sleep(2)
    webbrowser.open("http://localhost:8000")
    
    print(f"\n{YELLOW}Press Ctrl+C to stop all servers...{RESET}\n")
    
    try:
        # Keep running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Shutting down...{RESET}")
        backend.terminate()
        frontend.terminate()
        if cloudflare:
            cloudflare.terminate()
        print(f"{GREEN}✅ All servers stopped. Goodbye!{RESET}")

if __name__ == "__main__":
    main()