"""
Sofia V2 - Free Data Collection System Configuration
Comprehensive config for collecting crypto, BIST, and social data without paid APIs
"""

import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Central configuration for all data collection"""
    
    # API Keys (Free accounts)
    ETHERSCAN_API_KEYS = [
        os.getenv('ETHERSCAN_KEY_1', 'YourApiKeyToken'),
        os.getenv('ETHERSCAN_KEY_2', 'YourApiKeyToken'), 
        os.getenv('ETHERSCAN_KEY_3', 'YourApiKeyToken')
    ]
    
    BSCSCAN_API_KEY = os.getenv('BSCSCAN_KEY', 'YourApiKeyToken')
    POLYGONSCAN_API_KEY = os.getenv('POLYGONSCAN_KEY', 'YourApiKeyToken')
    
    # Telegram (Free from my.telegram.org)
    TELEGRAM_API_ID = os.getenv('TELEGRAM_API_ID', '0')
    TELEGRAM_API_HASH = os.getenv('TELEGRAM_API_HASH', 'your_hash')
    
    # Rate Limiting Settings
    MAX_REQUESTS_PER_SECOND = 2
    REQUEST_DELAY_RANGE = (0.5, 2.0)  # Random delay range
    RETRY_COUNT = 3
    BACKOFF_FACTOR = 2
    
    # Cache Settings  
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
    CACHE_TTL = 30  # Seconds
    
    # Data Collection Intervals
    CRYPTO_PRICE_INTERVAL = 5  # Seconds
    BIST_DATA_INTERVAL = 10
    NEWS_INTERVAL = 60
    SOCIAL_SENTIMENT_INTERVAL = 30
    WHALE_ALERT_INTERVAL = 10
    
    # Whale Tracking Thresholds
    WHALE_THRESHOLD_ETH = 100
    WHALE_THRESHOLD_BTC = 5
    WHALE_THRESHOLD_BNB = 1000
    WHALE_THRESHOLD_USD = 100000
    
    # Free API Endpoints
    COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"
    BINANCE_WS_URL = "wss://stream.binance.com:9443/ws"
    COINBASE_WS_URL = "wss://ws-feed.exchange.coinbase.com"
    KRAKEN_WS_URL = "wss://ws.kraken.com"
    
    # Free RSS Feed URLs
    RSS_FEEDS = {
        'cointelegraph': 'https://cointelegraph.com/rss',
        'coindesk': 'https://www.coindesk.com/arc/outboundfeeds/rss/',
        'decrypt': 'https://decrypt.co/feed',
        'newsbtc': 'https://www.newsbtc.com/feed/',
        'bitcoinist': 'https://bitcoinist.com/feed/',
        'crypto_daily': 'https://cryptodaily.co.uk/feed',
        'block_works': 'https://blockworks.co/rss.xml',
        'crypto_slate': 'https://cryptoslate.com/feed/',
        'coin_journal': 'https://coinjournal.net/news/feed/',
        'beincrypto': 'https://beincrypto.com/feed/'
    }
    
    # BIST Free Scraping Sources
    BIST_SOURCES = {
        'bigpara': 'https://bigpara.hurriyet.com.tr/borsa/',
        'mynet_finance': 'https://finans.mynet.com/borsa/',
        'investing_tr': 'https://tr.investing.com/equities/turkey',
        'bloomberght': 'https://www.bloomberght.com/borsa/',
        'foreks': 'https://www.foreks.com/hisse-senetleri',
        'matriks': 'https://www.matriksdata.com/borsa/',
        'borsagundem': 'https://www.borsagundem.com/borsa/',
        'hangihisse': 'https://hangihisse.com/'
    }
    
    # Telegram Channels for Whale Alerts (Free)
    TELEGRAM_CHANNELS = [
        '@whale_alert',
        '@binanceexchange', 
        '@ethereum',
        '@bitcoin',
        '@cryptonews',
        '@btc_eth_news',
        '@crypto_whale_tracker',
        '@defi_whale_tracker'
    ]
    
    # Twitter/X Keywords for Sentiment
    TWITTER_KEYWORDS = [
        '$BTC', '$ETH', '$BNB', '$SOL', '$ADA', '$XRP',
        'Bitcoin', 'Ethereum', 'crypto pump', 'crypto dump',
        'whale alert', 'large transaction', 'crypto news',
        '#crypto', '#DeFi', '#Bitcoin', '#Ethereum',
        'bull run', 'bear market', 'altcoin season'
    ]
    
    # Crypto Symbols to Track (Top 100)
    TRACKED_SYMBOLS = [
        # Major coins
        'BTC', 'ETH', 'BNB', 'XRP', 'ADA', 'SOL', 'DOGE', 'DOT', 'MATIC', 'SHIB',
        'AVAX', 'LTC', 'UNI', 'LINK', 'ALGO', 'VET', 'FIL', 'ICP', 'HBAR', 'NEAR',
        # DeFi tokens
        'AAVE', 'COMP', 'MKR', 'CRV', 'SNX', 'YFI', 'SUSHI', '1INCH', 'BAL', 'LDO',
        # Exchange tokens
        'FTT', 'HT', 'OKB', 'LEO', 'CRO', 'GT', 'KCS', 'WBT',
        # Memecoins  
        'PEPE', 'FLOKI', 'BABYDOGE', 'SAFEMOON', 'BONK',
        # Layer 1s
        'ATOM', 'LUNA', 'EGLD', 'ONE', 'FLOW', 'ROSE', 'KLAY', 'WAVES'
    ]
    
    # BIST Stocks to Track (BIST 30)
    BIST_STOCKS = [
        'THYAO', 'EREGL', 'ASELS', 'TUPRS', 'SAHOL', 'SISE', 'AKBNK', 'GARAN', 
        'ISCTR', 'YKBNK', 'KCHOL', 'TCELL', 'BIMAS', 'FROTO', 'TOASO', 'PETKM',
        'ARCLK', 'EKGYO', 'HALKB', 'VAKBN', 'KOZAL', 'KOZAA', 'MGROS', 'VESBE',
        'VESTL', 'TTKOM', 'KRDMD', 'TAVHL', 'PGSUS', 'SODA'
    ]
    
    # User Agents for Web Scraping
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ]
    
    # Proxy Settings (Optional)
    USE_PROXY = os.getenv('USE_PROXY', 'false').lower() == 'true'
    PROXY_LIST = [
        # Add free proxy servers if needed
        # 'http://proxy1:port',
        # 'http://proxy2:port',
    ]
    
    # Database Settings
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///sofia_data.db')
    INFLUXDB_URL = os.getenv('INFLUXDB_URL', 'http://localhost:8086')
    INFLUXDB_TOKEN = os.getenv('INFLUXDB_TOKEN', '')
    INFLUXDB_ORG = os.getenv('INFLUXDB_ORG', 'sofia')
    INFLUXDB_BUCKET = os.getenv('INFLUXDB_BUCKET', 'crypto_data')
    
    # Webhook URLs for Sofia Integration
    SOFIA_WEBHOOK_URL = os.getenv('SOFIA_WEBHOOK_URL', 'http://localhost:8000/api/data-webhook')
    SOFIA_WS_URL = os.getenv('SOFIA_WS_URL', 'ws://localhost:8000/ws/data-collector')
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'logs/data_collector.log')
    
    # Feature Flags
    ENABLE_CRYPTO_COLLECTION = True
    ENABLE_BIST_COLLECTION = True  
    ENABLE_NEWS_COLLECTION = True
    ENABLE_WHALE_TRACKING = True
    ENABLE_SOCIAL_MONITORING = True
    ENABLE_SENTIMENT_ANALYSIS = True
    
    # Anti-Detection Settings
    USE_RANDOM_DELAYS = True
    ROTATE_USER_AGENTS = True
    USE_SESSION_ROTATION = True
    MAX_CONCURRENT_REQUESTS = 3
    
    @classmethod
    def get_random_user_agent(cls):
        """Get random user agent for web scraping"""
        import random
        return random.choice(cls.USER_AGENTS)
    
    @classmethod  
    def get_request_delay(cls):
        """Get random delay to avoid detection"""
        import random
        return random.uniform(*cls.REQUEST_DELAY_RANGE)