#!/usr/bin/env python
"""Run the complete Sofia Trading Platform."""

import asyncio
import uvicorn
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


async def main():
    """Run all services."""
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║                                                          ║
    ║           SOFIA TRADING PLATFORM v2.0                   ║
    ║                                                          ║
    ║   Professional Trading Dashboard & Engine               ║
    ║                                                          ║
    ╚══════════════════════════════════════════════════════════╝
    
    Starting services...
    """)
    
    # Start Web UI
    print("🌐 Starting Web UI on http://localhost:8000")
    
    config = uvicorn.Config(
        "web_ui.app:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=True,
    )
    
    server = uvicorn.Server(config)
    
    print("""
    ✅ Platform is ready!
    
    📊 Dashboard: http://localhost:8000
    📡 WebSocket: ws://localhost:8000/ws
    📚 API Docs: http://localhost:8000/docs
    
    Press Ctrl+C to stop
    """)
    
    await server.serve()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Shutting down Sofia Trading Platform...")
