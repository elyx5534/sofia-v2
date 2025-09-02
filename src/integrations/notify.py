"""
Notification Integration for Telegram and Discord
"""

import os
import asyncio
import aiohttp
import json
from typing import Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


async def send_telegram(message: str, chat_id: Optional[str] = None, bot_token: Optional[str] = None) -> bool:
    """
    Send message to Telegram
    
    Requires:
    - TELEGRAM_BOT_TOKEN environment variable or bot_token parameter
    - TELEGRAM_CHAT_ID environment variable or chat_id parameter
    """
    try:
        bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        
        if not bot_token or not chat_id:
            logger.warning("Telegram credentials not configured")
            return False
            
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        
        # Add timestamp to message
        timestamped_message = f"{message}\n\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        payload = {
            "chat_id": chat_id,
            "text": timestamped_message,
            "parse_mode": "HTML"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    logger.info("Telegram message sent successfully")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Telegram send failed: {response.status} - {error_text}")
                    return False
                    
    except Exception as e:
        logger.error(f"Telegram notification error: {e}")
        return False


async def send_discord(message: str, webhook_url: Optional[str] = None) -> bool:
    """
    Send message to Discord via webhook
    
    Requires:
    - DISCORD_WEBHOOK_URL environment variable or webhook_url parameter
    """
    try:
        webhook_url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL")
        
        if not webhook_url:
            logger.warning("Discord webhook not configured")
            return False
            
        # Format message for Discord
        embed = {
            "title": "Sofia V2 Trading Bot",
            "description": message,
            "color": 0x00ff00 if "resumed" in message.lower() else 0xff0000 if "paused" in message.lower() else 0x0099ff,
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {
                "text": "Sofia V2 Watchdog"
            }
        }
        
        payload = {
            "username": "Sofia Trading Bot",
            "embeds": [embed]
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload) as response:
                if response.status in [200, 204]:
                    logger.info("Discord message sent successfully")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Discord send failed: {response.status} - {error_text}")
                    return False
                    
    except Exception as e:
        logger.error(f"Discord notification error: {e}")
        return False


async def send_alert(message: str, priority: str = "normal") -> bool:
    """
    Send alert to all configured channels
    
    Args:
        message: Alert message to send
        priority: Alert priority (low, normal, high, critical)
    """
    results = []
    
    # Format message based on priority
    if priority == "critical":
        message = f"🚨 CRITICAL ALERT 🚨\n\n{message}"
    elif priority == "high":
        message = f"⚠️ HIGH PRIORITY ⚠️\n\n{message}"
    elif priority == "low":
        message = f"ℹ️ Info: {message}"
    
    # Send to all channels
    telegram_result = await send_telegram(message)
    discord_result = await send_discord(message)
    
    return telegram_result or discord_result


async def send_daily_report(report_data: dict) -> bool:
    """
    Send daily trading report to all channels
    """
    # Format report
    message = f"""
📊 **Daily Trading Report**

💰 **P&L Summary**
• Initial Capital: ${report_data.get('initial_capital', 0):.2f}
• Final Capital: ${report_data.get('final_capital', 0):.2f}
• Daily P&L: ${report_data.get('daily_pnl', 0):.2f} ({report_data.get('daily_pnl_pct', 0):.2f}%)
• Realized: ${report_data.get('realized_pnl', 0):.2f}
• Unrealized: ${report_data.get('unrealized_pnl', 0):.2f}

📈 **Trading Metrics**
• Total Trades: {report_data.get('total_trades', 0)}
• Win Rate: {report_data.get('win_rate', 0):.1f}%
• Maker Fill Rate: {report_data.get('maker_fill_rate', 0):.1f}%
• Avg Fill Time: {report_data.get('avg_fill_time_ms', 0):.0f}ms

🎯 **Risk Metrics**
• Max Drawdown: {report_data.get('max_drawdown', 0):.2f}%
• Sharpe Ratio: {report_data.get('sharpe_ratio', 0):.2f}
• Risk Status: {report_data.get('risk_status', 'NORMAL')}
"""
    
    return await send_alert(message, priority="normal")


# Test function
async def test_notifications():
    """Test notification channels"""
    test_message = "🧪 Test notification from Sofia V2 Trading Bot"
    
    print("Testing Telegram...")
    telegram_success = await send_telegram(test_message)
    print(f"Telegram: {'✅ Success' if telegram_success else '❌ Failed'}")
    
    print("Testing Discord...")
    discord_success = await send_discord(test_message)
    print(f"Discord: {'✅ Success' if discord_success else '❌ Failed'}")
    
    return telegram_success or discord_success


if __name__ == "__main__":
    # Run test
    asyncio.run(test_notifications())