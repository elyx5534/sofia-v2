"""
Sofia V2 Ultimate Launcher
Launches the beautiful purple template with all advanced features
"""

import sys

import uvicorn


def print_ultimate_banner():
    """Print Sofia V2 Ultimate startup banner"""
    banner = """
    ================================================================

         SOFIA V2 ULTIMATE - PURPLE EDITION

              AI-POWERED CRYPTO TRADING PLATFORM

                 WITH BEAUTIFUL PURPLE INTERFACE
    ================================================================

    ULTIMATE FEATURES:
     * Beautiful Purple Glassmorphism UI
     * Floating Particles & Glow Animations
     * Real-time AI Predictions (5 ML Models)
     * Advanced Portfolio Analytics
     * Market Scanner with 12+ Strategies
     * Paper Trading with Real Crypto Prices
     * WebSocket Live Data Streaming
     * Professional Risk Management

    ENHANCED VISUALS:
     * Gradient borders with glow effects
     * Animated trading signals
     * AI-powered particle system
     * Real-time chart animations
     * Cool hover effects & transitions

    ULTIMATE DASHBOARD TABS:
     * Dashboard - Real-time overview
     * Portfolio - Advanced analytics
     * AI Predictions - ML model forecasts
     * Market Scanner - Trading opportunities
     * Trading Console - AI trading control

    ACCESS POINTS:
     * Ultimate Dashboard: http://localhost:8007
     * Main App (Simple): http://localhost:8005
     * API Documentation: http://localhost:8007/docs

    ================================================================

    Starting Sofia V2 Ultimate... Prepare to be amazed!
    All AI models training with real crypto data...

    """
    print(banner)


def main():
    """Main launcher for Sofia V2 Ultimate"""
    print_ultimate_banner()

    try:
        print("Starting Sofia V2 Ultimate Dashboard...")
        print("Loading beautiful purple interface...")
        print("Initializing AI prediction models...")
        print("Starting real-time data streams...")
        print("\n" + "=" * 80)
        print("SOFIA V2 ULTIMATE IS NOW LIVE!")
        print("=" * 80)
        print("Ultimate Dashboard: http://localhost:8007")
        print("Simple Version: http://localhost:8005")
        print("API Documentation: http://localhost:8007/docs")
        print("\nFeatures include:")
        print("- Beautiful purple glassmorphism UI")
        print("- Real-time AI predictions")
        print("- Advanced portfolio analytics")
        print("- Market scanner with trading signals")
        print("- Paper trading with real crypto prices")
        print("- Floating particles & animations")
        print("\nAll trading is simulated - no real money at risk!")
        print("Enjoy the most beautiful crypto trading platform!")
        print("=" * 80)

        # Import and run the ultimate dashboard
        from src.web_ui.sofia_ultimate_dashboard import app

        uvicorn.run(app, host="0.0.0.0", port=8007, log_level="info", access_log=False)

    except KeyboardInterrupt:
        print("\n\nSofia V2 Ultimate shutdown requested")
        print("Shutting down all engines gracefully...")
        print("Thanks for using Sofia V2 Ultimate!")

    except Exception as e:
        print(f"\nError starting Sofia V2 Ultimate: {e}")
        print("Check the logs above for more details")
        sys.exit(1)


if __name__ == "__main__":
    main()
