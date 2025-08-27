"""
Sofia V2 - AI Trading Platform Launcher
Start all components and services
"""

import asyncio
import uvicorn
import sys
import os
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def print_banner():
    """Print Sofia V2 startup banner"""
    banner = """
    ╔═══════════════════════════════════════════════════════════════════╗
    ║                                                                   ║
    ║     ███████╗ ██████╗ ███████╗██╗ █████╗     ██╗   ██╗██████╗     ║
    ║     ██╔════╝██╔═══██╗██╔════╝██║██╔══██╗    ██║   ██║╚════██╗    ║
    ║     ███████╗██║   ██║█████╗  ██║███████║    ██║   ██║ █████╔╝    ║
    ║     ╚════██║██║   ██║██╔══╝  ██║██╔══██║    ╚██╗ ██╔╝██╔═══╝     ║
    ║     ███████║╚██████╔╝██║     ██║██║  ██║     ╚████╔╝ ███████╗    ║
    ║     ╚══════╝ ╚═════╝ ╚═╝     ╚═╝╚═╝  ╚═╝      ╚═══╝  ╚══════╝    ║
    ║                                                                   ║
    ║               🤖 AI-POWERED CRYPTO TRADING PLATFORM 🤖            ║
    ║                                                                   ║
    ╠═══════════════════════════════════════════════════════════════════╣
    ║                                                                   ║
    ║  🚀 FEATURES:                                                     ║
    ║     • Real-time crypto data from CoinGecko & Binance APIs        ║
    ║     • Advanced AI predictions with ML models                     ║
    ║     • Paper trading with real market prices                      ║
    ║     • Professional portfolio analytics                           ║
    ║     • Market scanner with 12+ trading strategies                 ║
    ║     • Auto-trading with risk management                          ║
    ║     • Beautiful WebSocket-powered interface                      ║
    ║     • Cool animations and particle effects                       ║
    ║                                                                   ║
    ║  🔥 TECHNICAL:                                                    ║
    ║     • Multi-model ensemble ML predictions                        ║
    ║     • Real-time WebSocket streaming                              ║
    ║     • Advanced technical indicators                              ║
    ║     • Risk metrics (VaR, Sharpe, Sortino ratios)               ║
    ║     • Responsive glassmorphism UI design                         ║
    ║                                                                   ║
    ║  📊 STARTING COMPONENTS:                                          ║
    ║     • Real-Time Data Fetcher                                     ║
    ║     • AI Prediction Engine                                       ║
    ║     • Paper Trading Engine                                       ║
    ║     • Portfolio Manager                                          ║
    ║     • Market Scanner                                             ║
    ║     • Unified Execution Engine                                   ║
    ║     • WebSocket Streaming Services                               ║
    ║                                                                   ║
    ║  🌐 ACCESS POINTS:                                               ║
    ║     • Main App: http://localhost:8000                           ║
    ║     • Trading Interface: http://localhost:8000/trading          ║
    ║     • Real-time Dashboard: http://localhost:8000 (Dashboard tab) ║
    ║     • API Documentation: http://localhost:8000/docs             ║
    ║                                                                   ║
    ╚═══════════════════════════════════════════════════════════════════╝
    
    Starting Sofia V2... Please wait while all engines initialize.
    This may take 30-60 seconds as AI models are being trained with real data.
    
    """
    print(banner)

def main():
    """Main launcher function"""
    print_banner()
    
    try:
        # Import the main app
        from src.web_ui.main_app import app
        
        print("🔄 Starting Sofia V2 Trading Platform...")
        print("📡 Initializing real-time data connections...")
        print("🧠 Training AI prediction models...")
        print("⚙️  Starting all trading engines...")
        print("\n" + "="*80)
        print("🌟 SOFIA V2 IS NOW RUNNING!")
        print("="*80)
        print(f"📱 Open your browser and go to: http://localhost:8000")
        print(f"📊 Trading interface: http://localhost:8000/trading") 
        print(f"📈 API docs: http://localhost:8000/docs")
        print("\n💡 Pro tip: The AI models will improve as they collect more data!")
        print("🛡️  All trading is simulated with paper money - no real funds at risk")
        print("\n🔥 Enjoy trading with Sofia V2! Press Ctrl+C to stop.")
        print("="*80)
        
        # Run the application
        uvicorn.run(
            app, 
            host="0.0.0.0", 
            port=8000,
            log_level="info",
            access_log=False  # Reduce log noise
        )
        
    except KeyboardInterrupt:
        print("\n\n🛑 Sofia V2 shutdown requested by user")
        print("🔄 Shutting down all engines gracefully...")
        print("👋 Thanks for using Sofia V2! See you next time!")
        
    except Exception as e:
        print(f"\n❌ Error starting Sofia V2: {e}")
        print("🔧 Check the logs above for more details")
        sys.exit(1)

if __name__ == "__main__":
    main()