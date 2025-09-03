"""
Trading Bot API Routes
"""

import asyncio
import logging
from typing import List

import aiohttp

from src.adapters.web.fastapi_adapter import APIRouter, JSONResponse
from src.trading.simple_bot import BotStatus
from src.trading.strategies import StrategyType
from src.trading.trade_simulator import TradingSimulator
from src.trading.turkish_bot import TurkishTradingBot

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/bot", tags=["Trading Bot"])
bot = TurkishTradingBot(initial_balance_try=100000.0)
bot_tasks = {}
simulator = TradingSimulator(bot)
simulation_task = None


async def fetch_prices(symbol: str = "BTC/USDT", limit: int = 50) -> List[float]:
    """Fetch price data from data hub"""
    try:
        async with aiohttp.ClientSession() as session:
            url = f"http://127.0.0.1:8001/ohlcv?symbol={symbol}&asset_type=crypto&timeframe=5m&limit={limit}"
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("data"):
                        return [candle["close"] for candle in data["data"]]
    except Exception as e:
        logger.error(f"Error fetching prices: {e}")
    return []


async def bot_loop_for_coin(symbol: str):
    """Bot loop for a specific coin"""
    global bot
    while bot.status == BotStatus.RUNNING:
        try:
            prices = await fetch_prices(symbol)
            if prices and len(prices) >= 30:
                current_price = prices[-1]
                if symbol in bot.positions:
                    bot.positions[symbol].update_pnl(current_price)
                bot.indicators[symbol] = {
                    "rsi": bot.strategies.calculate_rsi(prices),
                    "macd": bot.strategies.calculate_macd(prices),
                    "ma_crossover": bot.strategies.calculate_ma_crossover(prices),
                    "bollinger": bot.strategies.calculate_bollinger_bands(prices),
                }
                signal = None
                confidence = "medium"
                if bot.strategy_type == StrategyType.RSI:
                    signal = bot.strategies.get_rsi_signal(prices)
                elif bot.strategy_type == StrategyType.MACD:
                    signal = bot.strategies.get_macd_signal(prices)
                elif bot.strategy_type == StrategyType.MA_CROSSOVER:
                    signal = bot.strategies.get_ma_crossover_signal(prices)
                elif bot.strategy_type == StrategyType.BOLLINGER:
                    signal = bot.strategies.get_bollinger_signal(prices)
                else:
                    signal, metadata = bot.strategies.get_combined_signal(prices)
                    if metadata:
                        confidence = metadata.get("confidence", "medium")
                if signal:
                    trade = bot.execute_trade(symbol, signal, current_price, confidence)
                    if trade["amount"] > 0:
                        logger.info(f"Trade executed for {symbol}: {trade}")
            await asyncio.sleep(30)
        except Exception as e:
            logger.error(f"Bot error for {symbol}: {e}")
            await asyncio.sleep(60)


async def bot_main_loop():
    """Main bot loop that manages all coins"""
    global bot, bot_tasks
    while bot.status == BotStatus.RUNNING:
        try:
            for symbol in bot.watchlist:
                if symbol not in bot_tasks or bot_tasks[symbol].done():
                    bot_tasks[symbol] = asyncio.create_task(bot_loop_for_coin(symbol))
                    logger.info(f"Started monitoring {symbol}")
            for symbol in list(bot_tasks.keys()):
                if symbol not in bot.watchlist and symbol != "__main__":
                    if not bot_tasks[symbol].done():
                        bot_tasks[symbol].cancel()
                    del bot_tasks[symbol]
                    logger.info(f"Stopped monitoring {symbol}")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Main bot loop error: {e}")
            bot.status = BotStatus.ERROR
            break


@router.post("/start")
async def start_bot():
    """Start the trading bot with simulator"""
    global bot, bot_tasks, simulator, simulation_task
    if bot.status == BotStatus.RUNNING:
        return {"message": "Bot is already running"}
    bot.start()
    simulation_task = asyncio.create_task(simulator.run_simulation())
    bot_tasks["__simulator__"] = simulation_task
    return {
        "message": "Bot started successfully with simulator",
        "status": bot.status.value,
        "strategy": bot.strategy_type.value,
        "coins": list(bot.watchlist)[:20],
        "balance_try": bot.balance_try,
        "currency": "TRY",
    }


@router.post("/stop")
async def stop_bot():
    """Stop the trading bot"""
    global bot, bot_tasks, simulator
    if bot.status != BotStatus.RUNNING:
        return {"message": "Bot is not running"}
    bot.stop()
    simulator.stop()
    for task in bot_tasks.values():
        if not task.done():
            task.cancel()
    bot_tasks.clear()
    return {"message": "Bot stopped successfully", "status": bot.status.value}


@router.get("/status")
async def get_bot_status():
    """Get bot status and statistics"""
    global bot, simulator
    if bot.status == BotStatus.RUNNING:
        for symbol in bot.active_coins:
            if hasattr(simulator, "price_simulator"):
                price_data = simulator.price_simulator.get_price_data(symbol)
                if symbol in bot.positions:
                    bot.positions[symbol].update_pnl(price_data["price"], bot.usd_to_try)
    return bot.get_portfolio_stats()


@router.get("/trades")
async def get_trades(limit: int = 50):
    """Get trade history"""
    global bot
    trades = bot.all_trades[-limit:] if bot.all_trades else []
    return {"trades": trades, "total": len(bot.all_trades), "displayed": len(trades)}


@router.post("/reset")
async def reset_bot():
    """Reset bot to initial state"""
    global bot, bot_tasks
    if bot.status == BotStatus.RUNNING:
        bot.stop()
        for task in bot_tasks.values():
            if not task.done():
                task.cancel()
        bot_tasks.clear()
    bot.reset()
    return {
        "message": "Bot reset successfully",
        "status": bot.status.value,
        "balance_try": bot.balance_try,
    }


@router.post("/strategy")
async def set_strategy(strategy: str):
    """Change trading strategy"""
    global bot
    if bot.status == BotStatus.RUNNING:
        return JSONResponse(
            status_code=400, content={"error": "Cannot change strategy while bot is running"}
        )
    try:
        strategy_type = StrategyType(strategy)
        bot.set_strategy(strategy_type)
        return {"message": f"Strategy changed to {strategy}", "strategy": strategy}
    except ValueError:
        return JSONResponse(
            status_code=400,
            content={
                "error": f"Invalid strategy: {strategy}. Valid options: {[s.value for s in StrategyType]}"
            },
        )


@router.post("/coins/add")
async def add_coin(symbol: str):
    """Add a coin to track"""
    global bot
    bot.add_coin(symbol)
    return {"message": f"Added {symbol} to tracking", "active_coins": bot.active_coins}


@router.post("/coins/remove")
async def remove_coin(symbol: str):
    """Remove a coin from tracking"""
    global bot
    bot.remove_coin(symbol)
    return {"message": f"Removed {symbol} from tracking", "active_coins": bot.active_coins}


@router.get("/strategies")
async def get_strategies():
    """Get available strategies"""
    return {
        "strategies": [s.value for s in StrategyType],
        "current": bot.strategy_type.value,
        "descriptions": {
            "rsi": "Relative Strength Index - Buy oversold, sell overbought",
            "macd": "Moving Average Convergence Divergence - Trend following",
            "ma_crossover": "Moving Average Crossover - Trend changes",
            "bollinger": "Bollinger Bands - Volatility based",
            "combined": "Combined signals from all strategies",
        },
    }


@router.get("/coins/available")
async def get_available_coins():
    """Get list of available coins to trade"""
    return {"popular": bot.POPULAR_COINS, "all": bot.ALL_COINS, "total": len(bot.ALL_COINS)}


@router.get("/coins/watchlist")
async def get_watchlist():
    """Get current watchlist"""
    return {
        "watchlist": list(bot.watchlist),
        "count": len(bot.watchlist),
        "active_positions": list(bot.active_coins),
        "max_coins": bot.max_coins_to_trade,
    }


@router.post("/coins/watchlist/add")
async def add_to_watchlist(symbols: List[str]):
    """Add coins to watchlist"""
    bot.add_coins_to_watchlist(symbols)
    return {
        "message": f"Added {len(symbols)} coins to watchlist",
        "watchlist": list(bot.watchlist),
        "count": len(bot.watchlist),
    }


@router.post("/coins/watchlist/remove")
async def remove_from_watchlist(symbol: str):
    """Remove coin from watchlist"""
    if symbol in bot.watchlist:
        bot.watchlist.remove(symbol)
        return {"message": f"Removed {symbol} from watchlist", "watchlist": list(bot.watchlist)}
    return {"error": f"{symbol} not in watchlist"}


@router.post("/settings")
async def update_settings(
    rsi_oversold: int = 30, rsi_overbought: int = 70, position_size: float = 0.1
):
    """Update bot settings"""
    global bot
    if bot.status == BotStatus.RUNNING:
        return JSONResponse(
            status_code=400, content={"error": "Cannot update settings while bot is running"}
        )
    bot.rsi_oversold = rsi_oversold
    bot.rsi_overbought = rsi_overbought
    bot.position_size = position_size
    return {
        "message": "Settings updated successfully",
        "settings": {
            "rsi_oversold": bot.rsi_oversold,
            "rsi_overbought": bot.rsi_overbought,
            "position_size": bot.position_size,
        },
    }
