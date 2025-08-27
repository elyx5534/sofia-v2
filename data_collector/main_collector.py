"""
Sofia V2 - Main Data Collection Orchestrator
Coordinates all free data collection systems
Replaces $2000/month paid APIs with free alternatives
"""

import asyncio
import logging
import json
import sys
import os
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from data_collector.config import Config
from data_collector.crypto.price_collector import FreeCryptoPriceCollector
from data_collector.crypto.whale_tracker import FreeWhaleTracker
from data_collector.crypto.news_collector import FreeCryptoNewsCollector

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/data_collector.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class SofiaFreeDataCollector:
    """Main orchestrator for Sofia V2 free data collection system"""
    
    def __init__(self):
        self.config = Config()
        self.running = False
        
        # Initialize collectors
        self.crypto_collector = FreeCryptoPriceCollector(self.config)
        self.whale_tracker = FreeWhaleTracker(self.config) 
        self.news_collector = FreeCryptoNewsCollector(self.config)
        
        # Data storage
        self.latest_data = {
            'crypto_prices': {},
            'whale_alerts': [],
            'news': [],
            'market_sentiment': {},
            'collection_stats': {
                'last_update': None,
                'total_coins_tracked': 0,
                'total_news_sources': 0,
                'whale_alerts_today': 0
            }
        }
        
    async def start(self):
        """Start all data collection processes"""
        if self.running:
            return
            
        self.running = True
        logger.info("🚀 Starting Sofia V2 Free Data Collection System")
        logger.info("💰 Replacing $2000/month APIs with free alternatives!")
        
        # Start all collectors
        await self.crypto_collector.start()
        await self.whale_tracker.start()
        await self.news_collector.start()
        
        # Start collection loops
        tasks = [
            self.crypto_price_collection_loop(),
            self.whale_tracking_loop(),
            self.news_collection_loop(),
            self.data_integration_loop(),
            self.stats_reporting_loop()
        ]
        
        logger.info("🔄 All data collection loops started")
        await asyncio.gather(*tasks)
        
    async def stop(self):
        """Stop all data collection"""
        self.running = False
        
        await self.crypto_collector.stop()
        await self.whale_tracker.stop()
        await self.news_collector.stop()
        
        logger.info("📴 Sofia Free Data Collection System stopped")
        
    async def crypto_price_collection_loop(self):
        """Collect crypto prices every 5 seconds"""
        logger.info("💹 Starting crypto price collection loop")
        
        while self.running:
            try:
                # Collect from all free sources
                price_data = await self.crypto_collector.collect_all_prices()
                
                if price_data:
                    self.latest_data['crypto_prices'] = price_data
                    self.latest_data['collection_stats']['total_coins_tracked'] = len(price_data)
                    
                    # Send to Sofia main system
                    await self.send_to_sofia('crypto_prices', price_data)
                    
                    logger.info(f"💹 Collected prices for {len(price_data)} cryptocurrencies")
                
                await asyncio.sleep(self.config.CRYPTO_PRICE_INTERVAL)
                
            except Exception as e:
                logger.error(f"Crypto price collection error: {e}")
                await asyncio.sleep(10)
                
    async def whale_tracking_loop(self):
        """Track whale transactions every 10 seconds"""
        logger.info("🐋 Starting whale tracking loop")
        
        while self.running:
            try:
                whale_alerts = await self.whale_tracker.get_whale_alerts()
                
                if whale_alerts:
                    self.latest_data['whale_alerts'] = whale_alerts
                    self.latest_data['collection_stats']['whale_alerts_today'] += len(whale_alerts)
                    
                    # Send high-impact alerts immediately
                    for alert in whale_alerts:
                        if alert['impact_score'] >= 70:
                            await self.send_to_sofia('whale_alert', alert)
                            logger.warning(f"🚨 HIGH IMPACT WHALE: {alert['blockchain']} ${alert['value_usd']:,.0f}")
                    
                    logger.info(f"🐋 Tracked {len(whale_alerts)} whale transactions")
                
                await asyncio.sleep(self.config.WHALE_ALERT_INTERVAL)
                
            except Exception as e:
                logger.error(f"Whale tracking error: {e}")
                await asyncio.sleep(30)
                
    async def news_collection_loop(self):
        """Collect crypto news every minute"""
        logger.info("📰 Starting news collection loop")
        
        while self.running:
            try:
                news_data = await self.news_collector.collect_all_news()
                
                if news_data.get('articles'):
                    self.latest_data['news'] = news_data['articles']
                    self.latest_data['market_sentiment'] = news_data['sentiment_summary']
                    self.latest_data['collection_stats']['total_news_sources'] = news_data['total_sources']
                    
                    # Send breaking news immediately
                    breaking_news = [
                        article for article in news_data['articles'] 
                        if article['importance_score'] >= 80
                    ]
                    
                    for news in breaking_news:
                        await self.send_to_sofia('breaking_news', news)
                        logger.warning(f"🔥 BREAKING: {news['title'][:100]}...")
                    
                    logger.info(f"📰 Collected {len(news_data['articles'])} news articles from {news_data['total_sources']} sources")
                
                await asyncio.sleep(self.config.NEWS_INTERVAL)
                
            except Exception as e:
                logger.error(f"News collection error: {e}")
                await asyncio.sleep(60)
                
    async def data_integration_loop(self):
        """Integrate collected data and send to Sofia"""
        logger.info("🔗 Starting data integration loop")
        
        while self.running:
            try:
                # Prepare integrated data package
                integrated_data = {
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'crypto_prices': self.latest_data['crypto_prices'],
                    'whale_alerts': self.latest_data['whale_alerts'][-10:],  # Latest 10
                    'top_news': sorted(
                        self.latest_data['news'][:20], 
                        key=lambda x: x.get('importance_score', 0), 
                        reverse=True
                    ),
                    'market_sentiment': self.latest_data['market_sentiment'],
                    'collection_stats': self.latest_data['collection_stats']
                }
                
                # Send complete data package to Sofia
                await self.send_to_sofia('integrated_data', integrated_data)
                
                # Update stats
                self.latest_data['collection_stats']['last_update'] = datetime.now(timezone.utc).isoformat()
                
                await asyncio.sleep(30)  # Send integrated data every 30 seconds
                
            except Exception as e:
                logger.error(f"Data integration error: {e}")
                await asyncio.sleep(30)
                
    async def stats_reporting_loop(self):
        """Report collection statistics"""
        while self.running:
            try:
                stats = self.latest_data['collection_stats']
                
                logger.info("📊 DATA COLLECTION STATS:")
                logger.info(f"   💹 Cryptocurrencies tracked: {stats['total_coins_tracked']}")
                logger.info(f"   🐋 Whale alerts today: {stats['whale_alerts_today']}")
                logger.info(f"   📰 News sources active: {stats['total_news_sources']}")
                logger.info(f"   🕒 Last update: {stats['last_update']}")
                
                # Check system health
                if stats['total_coins_tracked'] == 0:
                    logger.warning("⚠️  No crypto price data - checking sources...")
                    
                if stats['whale_alerts_today'] == 0:
                    logger.info("🐋 No whale alerts yet today (normal)")
                    
                await asyncio.sleep(300)  # Report every 5 minutes
                
            except Exception as e:
                logger.error(f"Stats reporting error: {e}")
                await asyncio.sleep(300)
                
    async def send_to_sofia(self, data_type: str, data):
        """Send data to Sofia V2 main system"""
        try:
            # This will integrate with Sofia's WebSocket or API
            # For now, just log the data
            
            if data_type == 'crypto_prices':
                logger.info(f"📤 Sending {len(data)} crypto prices to Sofia")
            elif data_type == 'whale_alert':
                logger.info(f"📤 Sending whale alert: ${data.get('value_usd', 0):,.0f} {data.get('blockchain', '')}")
            elif data_type == 'breaking_news':
                logger.info(f"📤 Sending breaking news: {data.get('title', '')[:50]}...")
            elif data_type == 'integrated_data':
                logger.info(f"📤 Sending integrated data package to Sofia")
                
            # TODO: Implement actual integration with Sofia WebSocket/API
            # await self.send_websocket_data(data_type, data)
            # await self.send_http_webhook(data_type, data)
            
        except Exception as e:
            logger.error(f"Error sending data to Sofia: {e}")

async def main():
    """Main entry point"""
    print("""
    ╔════════════════════════════════════════════════════════════════════╗
    ║                                                                    ║
    ║               🚀 SOFIA V2 FREE DATA COLLECTION SYSTEM 🚀           ║
    ║                                                                    ║
    ║                    💰 REPLACING $2000/MONTH APIS 💰               ║
    ║                                                                    ║
    ╠════════════════════════════════════════════════════════════════════╣
    ║                                                                    ║
    ║  🔥 FREE DATA SOURCES:                                             ║
    ║     • CoinGecko API (10-30 calls/minute)                          ║
    ║     • Binance WebSocket (unlimited, real-time)                    ║ 
    ║     • Multiple exchange APIs (CCXT)                               ║
    ║     • 10+ crypto news RSS feeds                                   ║
    ║     • Etherscan whale tracking (100k calls/day per key)          ║
    ║     • BlockCypher Bitcoin tracking                                ║
    ║     • CoinMarketCap public endpoints                             ║
    ║                                                                    ║
    ║  ⚡ COLLECTION SPEED:                                              ║
    ║     • Crypto prices: Every 5 seconds                             ║
    ║     • Whale alerts: Every 10 seconds                             ║
    ║     • News feeds: Every 60 seconds                               ║
    ║     • Market sentiment: Real-time analysis                       ║
    ║                                                                    ║
    ║  🎯 TRACKED DATA:                                                  ║
    ║     • 100+ cryptocurrencies                                       ║
    ║     • Large whale transactions                                    ║
    ║     • Breaking crypto news                                        ║
    ║     • Market sentiment analysis                                   ║
    ║                                                                    ║
    ╚════════════════════════════════════════════════════════════════════╝
    
    Starting data collection in 3 seconds...
    Press Ctrl+C to stop
    """)
    
    await asyncio.sleep(3)
    
    collector = SofiaFreeDataCollector()
    
    try:
        await collector.start()
    except KeyboardInterrupt:
        logger.info("🛑 Shutdown requested by user")
        await collector.stop()
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        await collector.stop()

if __name__ == "__main__":
    asyncio.run(main())