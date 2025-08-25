"""
Sofia V2 Trading Bot - Quick Start Script

Usage:
1. Copy .env.example to .env
2. Add your Binance testnet API keys
3. Run: python start_trading.py
"""

import asyncio
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.live_trading.trading_bot import TradingBot, TradingMode, BotConfig
from src.strategies.grid_trading import GridTradingStrategy, GridConfig
from src.exchanges.binance_connector import BinanceConfig, BinanceConnector


async def main():
    """Main trading bot runner."""
    
    # Load environment variables
    load_dotenv()
    
    print("""
    ╔══════════════════════════════════════════════╗
    ║      Sofia V2 - AI Trading Platform         ║
    ║         💰 PARA KAZANMA MODU 💰            ║
    ╚══════════════════════════════════════════════╝
    """)
    
    # Check for API keys
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    
    if not api_key or api_key == "your_testnet_api_key_here":
        print("⚠️  UYARI: Binance API key bulunamadı!")
        print("📝 Yapmanız gerekenler:")
        print("1. https://testnet.binance.vision/ adresine git")
        print("2. Kayıt ol ve API key oluştur")
        print("3. .env dosyasına API key ve secret ekle")
        print("\nŞimdilik DEMO modda devam ediyoruz...\n")
        
        # Continue in demo mode
        api_key = "demo"
        api_secret = "demo"
    
    # Configure bot
    config = BotConfig(
        mode=TradingMode.PAPER,  # Always start in paper mode
        initial_balance=float(os.getenv("INITIAL_BALANCE", 10000)),
        max_positions=int(os.getenv("MAX_POSITIONS", 5)),
        position_size=float(os.getenv("POSITION_SIZE", 0.1)),
        stop_loss=float(os.getenv("STOP_LOSS", 0.02)),
        take_profit=float(os.getenv("TAKE_PROFIT", 0.05)),
        trailing_stop=os.getenv("TRAILING_STOP", "true").lower() == "true"
    )
    
    print(f"📊 Trading Mode: {config.mode}")
    print(f"💵 Initial Balance: ${config.initial_balance}")
    print(f"📈 Max Positions: {config.max_positions}")
    print(f"💼 Position Size: {config.position_size * 100}%")
    print(f"🛑 Stop Loss: {config.stop_loss * 100}%")
    print(f"✅ Take Profit: {config.take_profit * 100}%")
    print()
    
    # Create bot
    bot = TradingBot(config)
    
    # Add strategies
    print("🎯 Loading Strategies...")
    
    # 1. Grid Trading Strategy
    if os.getenv("ENABLE_GRID_TRADING", "true").lower() == "true":
        grid_config = GridConfig(
            symbol="BTC/USDT",
            grid_levels=int(os.getenv("GRID_LEVELS", 10)),
            grid_spacing=float(os.getenv("GRID_SPACING", 0.005)),
            quantity_per_grid=float(os.getenv("GRID_AMOUNT", 100))
        )
        grid_strategy = GridTradingStrategy(grid_config)
        bot.add_strategy("grid_trading", grid_strategy)
        print("  ✅ Grid Trading Strategy loaded")
    
    # 2. RSI + MACD Strategy (existing)
    if os.getenv("ENABLE_RSI_MACD", "true").lower() == "true":
        # Import existing strategy
        try:
            from src.strategy_engine.strategies import RSIStrategy
            rsi_strategy = RSIStrategy()
            bot.add_strategy("rsi_macd", rsi_strategy)
            print("  ✅ RSI + MACD Strategy loaded")
        except:
            print("  ⚠️  RSI + MACD Strategy not available")
    
    print()
    print("🚀 Starting Trading Bot...")
    print("=" * 50)
    
    # Start monitoring task
    async def monitor():
        """Monitor bot performance."""
        while True:
            try:
                status = bot.get_status()
                
                # Clear screen (Windows)
                os.system('cls' if os.name == 'nt' else 'clear')
                
                print(f"""
╔══════════════════════════════════════════════════════════╗
║                   TRADING BOT STATUS                      ║
╠══════════════════════════════════════════════════════════╣
║ 🕐 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                        ║
║ 📊 Mode: {status['mode'].upper():<48}║
║ 🟢 Status: {'RUNNING' if status['is_running'] else 'STOPPED':<46}║
╠══════════════════════════════════════════════════════════╣
║                      ACCOUNT                              ║
╠══════════════════════════════════════════════════════════╣
""")
                
                if status['mode'] == 'paper' and 'account' in status:
                    account = status['account'].get('account', {})
                    metrics = status['account'].get('metrics', {})
                    
                    print(f"║ 💰 Balance: ${account.get('current_balance', 0):,.2f}")
                    print(f"║ 📈 P&L: ${account.get('total_pnl', 0):,.2f}")
                    print(f"║ 🎯 Win Rate: {metrics.get('win_rate', 0):.1f}%")
                    print(f"║ 📊 Sharpe: {metrics.get('sharpe_ratio', 0):.2f}")
                
                print(f"""╠══════════════════════════════════════════════════════════╣
║                     POSITIONS                             ║
╠══════════════════════════════════════════════════════════╣
║ 📂 Active Positions: {status['active_positions']:<37}║
║ 📨 Pending Signals: {status['pending_signals']:<38}║
║ 🎯 Active Strategies: {len(status['strategies']):<36}║
╠══════════════════════════════════════════════════════════╣
║                   RECENT SIGNALS                          ║
╠══════════════════════════════════════════════════════════╣""")
                
                # Show recent signals
                for signal in status.get('recent_signals', [])[-3:]:
                    print(f"║ {signal.get('symbol', 'N/A'):8} | {signal.get('action', 'N/A'):6} | Conf: {signal.get('confidence', 0):.2f} | {signal.get('strategy', 'N/A')[:15]:<15}║")
                
                print("""╠══════════════════════════════════════════════════════════╣
║ Press Ctrl+C to stop the bot                              ║
╚══════════════════════════════════════════════════════════╝
""")
                
                await asyncio.sleep(5)  # Update every 5 seconds
                
            except Exception as e:
                print(f"Monitor error: {e}")
                await asyncio.sleep(5)
    
    # Start bot and monitor
    try:
        await asyncio.gather(
            bot.start(),
            monitor()
        )
    except KeyboardInterrupt:
        print("\n🛑 Stopping bot...")
        await bot.stop()
        print("✅ Bot stopped successfully")
        
        # Show final statistics
        status = bot.get_status()
        if 'account' in status:
            metrics = status['account'].get('metrics', {})
            print("\n📊 FINAL STATISTICS:")
            print(f"  Total Return: {metrics.get('total_return', 0):.2f}%")
            print(f"  Win Rate: {metrics.get('win_rate', 0):.1f}%")
            print(f"  Max Drawdown: {metrics.get('max_drawdown', 0):.2f}%")
            print(f"  Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.2f}")
            print(f"  Total Trades: {status['account'].get('account', {}).get('total_trades', 0)}")


if __name__ == "__main__":
    # Check Python version
    if sys.version_info < (3, 9):
        print("❌ Python 3.9+ required")
        sys.exit(1)
    
    # Run the bot
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)