"""
Multi-exchange WebSocket ingester with Redis Streams publishing
Supports Binance, OKX, Coinbase, Bybit with exponential backoff and deduplication
"""

import asyncio
import json
import logging
import os
import random
import time
import hashlib
from typing import Dict, Optional, Any, Set, List
from dataclasses import dataclass, asdict
from enum import Enum
import websockets
import redis.asyncio as redis
from prometheus_client import Counter, Histogram, Gauge

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Prometheus metrics
TICK_COUNTER = Counter('crypto_ticks_total', 'Total ticks received', ['exchange', 'symbol'])
RECONNECT_COUNTER = Counter('crypto_reconnects_total', 'Total reconnects', ['exchange'])
CONNECTION_GAUGE = Gauge('crypto_connections_active', 'Active connections', ['exchange'])
STALE_GAUGE = Gauge('crypto_stale_ratio', 'Stale data ratio', ['exchange'])
MESSAGE_LATENCY = Histogram('crypto_message_latency_seconds', 'Message processing latency', ['exchange'])


class Exchange(Enum):
    BINANCE = "binance"
    OKX = "okx"
    COINBASE = "coinbase"
    BYBIT = "bybit"


@dataclass
class Tick:
    """Standardized tick data structure"""
    exchange: str
    symbol: str
    price: float
    volume: float
    timestamp: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    high_24h: Optional[float] = None
    low_24h: Optional[float] = None
    change_24h: Optional[float] = None
    
    def to_redis_key(self) -> str:
        """Generate Redis Stream key"""
        return f"ticks.{self.exchange}.{self.symbol}"
    
    def get_dedup_hash(self) -> str:
        """Generate deduplication hash"""
        data = f"{self.exchange}:{self.symbol}:{self.price}:{self.volume}:{int(self.timestamp)}"
        return hashlib.md5(data.encode()).hexdigest()[:8]


class ExchangeConnector:
    """Base class for exchange WebSocket connections"""
    
    def __init__(self, exchange: Exchange, redis_client: redis.Redis):
        self.exchange = exchange
        self.redis_client = redis_client
        self.ws = None
        self.running = False
        self.connected = False
        self.stale = False
        
        # Configuration from ENV
        self.symbols = self._get_symbols()
        self.ping_interval = int(os.getenv('CRYPTO_WS_PING_INTERVAL', '20'))
        self.stale_threshold = int(os.getenv('CRYPTO_STALE_THRESHOLD_SEC', '15'))
        
        # Reconnection parameters
        self.reconnect_attempts = 0
        self.max_reconnect_delay = int(os.getenv('CRYPTO_MAX_RECONNECT_DELAY', '60'))
        self.base_delay = float(os.getenv('CRYPTO_BASE_DELAY', '1.0'))
        self.jitter_factor = float(os.getenv('CRYPTO_JITTER_FACTOR', '0.1'))
        
        # Metrics tracking
        self.last_connect_ts = 0
        self.last_msg_ts = {}
        self.tick_counts = {}
        self.error_count = 0
        self.last_error = None
        
        # Deduplication cache
        self.dedup_cache: Set[str] = set()
        self.cache_size_limit = int(os.getenv('CRYPTO_DEDUP_CACHE_SIZE', '10000'))
        
        # Initialize per-symbol tracking
        for symbol in self.symbols:
            self.last_msg_ts[symbol] = 0
            self.tick_counts[symbol] = 0
    
    def _get_symbols(self) -> List[str]:
        """Get symbols list from environment"""
        symbols_env = os.getenv('CRYPTO_SYMBOLS', 'BTC/USDT,ETH/USDT,SOL/USDT')
        return [s.strip() for s in symbols_env.split(',')]
    
    def _get_reconnect_delay(self) -> float:
        """Calculate exponential backoff delay with jitter"""
        delay = min(self.base_delay * (2 ** self.reconnect_attempts), self.max_reconnect_delay)
        jitter = delay * self.jitter_factor * (random.random() * 2 - 1)  # ±jitter_factor
        return max(0.1, delay + jitter)
    
    async def connect(self):
        """Connect with exponential backoff retry logic"""
        self.running = True
        CONNECTION_GAUGE.labels(exchange=self.exchange.value).set(0)
        
        while self.running:
            try:
                if self.reconnect_attempts > 0:
                    delay = self._get_reconnect_delay()
                    logger.info(f"[{self.exchange.value}] Reconnecting in {delay:.1f}s (attempt {self.reconnect_attempts})")
                    await asyncio.sleep(delay)
                
                url = self.get_ws_url()
                logger.info(f"[{self.exchange.value}] Connecting to: {url}")
                
                async with websockets.connect(url, ping_interval=self.ping_interval) as ws:
                    self.ws = ws
                    self.connected = True
                    self.stale = False
                    self.last_connect_ts = time.time()
                    CONNECTION_GAUGE.labels(exchange=self.exchange.value).set(1)
                    
                    if self.reconnect_attempts > 0:
                        RECONNECT_COUNTER.labels(exchange=self.exchange.value).inc()
                    
                    self.reconnect_attempts = 0
                    logger.info(f"[{self.exchange.value}] Connected successfully")
                    
                    # Subscribe to symbols
                    await self.subscribe()
                    
                    # Start message handler and stale checker
                    tasks = [
                        asyncio.create_task(self.message_handler()),
                        asyncio.create_task(self.stale_checker()),
                    ]
                    
                    await asyncio.gather(*tasks, return_exceptions=True)
                    
            except Exception as e:
                self.connected = False
                CONNECTION_GAUGE.labels(exchange=self.exchange.value).set(0)
                self.error_count += 1
                self.last_error = str(e)
                self.reconnect_attempts += 1
                
                logger.error(f"[{self.exchange.value}] Connection error: {e}")
                
                if not self.running:
                    break
    
    async def subscribe(self):
        """Subscribe to symbol streams - implemented by subclasses"""
        raise NotImplementedError
    
    def get_ws_url(self) -> str:
        """Get WebSocket URL - implemented by subclasses"""
        raise NotImplementedError
    
    def parse_message(self, message: str) -> Optional[Tick]:
        """Parse WebSocket message - implemented by subclasses"""
        raise NotImplementedError
    
    async def message_handler(self):
        """Handle incoming WebSocket messages"""
        async for message in self.ws:
            start_time = time.time()
            
            try:
                tick = self.parse_message(message)
                if not tick:
                    continue
                
                # Deduplication check
                tick_hash = tick.get_dedup_hash()
                if tick_hash in self.dedup_cache:
                    continue
                
                # Add to dedup cache with size limit
                self.dedup_cache.add(tick_hash)
                if len(self.dedup_cache) > self.cache_size_limit:
                    # Remove oldest 10% of entries (approximate FIFO)
                    remove_count = self.cache_size_limit // 10
                    for _ in range(remove_count):
                        self.dedup_cache.pop()
                
                # Stale detection
                age = time.time() - tick.timestamp
                if age > self.stale_threshold:
                    logger.warning(f"[{self.exchange.value}] Stale tick for {tick.symbol}: {age:.1f}s old")
                    continue
                
                # Update metrics
                self.last_msg_ts[tick.symbol] = tick.timestamp
                self.tick_counts[tick.symbol] += 1
                TICK_COUNTER.labels(exchange=self.exchange.value, symbol=tick.symbol).inc()
                
                # Publish to Redis Stream
                await self.publish_tick(tick)
                
                # Record processing latency
                MESSAGE_LATENCY.labels(exchange=self.exchange.value).observe(time.time() - start_time)
                
            except Exception as e:
                logger.error(f"[{self.exchange.value}] Message processing error: {e}")
    
    async def publish_tick(self, tick: Tick):
        """Publish tick to Redis Stream"""
        try:
            stream_key = tick.to_redis_key()
            tick_data = asdict(tick)
            
            # Add to Redis Stream with MAXLEN to prevent unbounded growth
            max_len = int(os.getenv('REDIS_STREAM_MAXLEN', '10000'))
            await self.redis_client.xadd(stream_key, tick_data, maxlen=max_len, approximate=True)
            
            logger.debug(f"Published tick: {stream_key} -> {tick.price}")
            
        except Exception as e:
            logger.error(f"Redis publish error: {e}")
    
    async def stale_checker(self):
        """Check for stale data and update metrics"""
        while self.connected:
            await asyncio.sleep(5)
            
            current_time = time.time()
            stale_count = 0
            
            for symbol in self.symbols:
                if symbol in self.last_msg_ts:
                    age = current_time - self.last_msg_ts[symbol]
                    if age > self.stale_threshold:
                        stale_count += 1
            
            # Update stale ratio metric
            if self.symbols:
                stale_ratio = stale_count / len(self.symbols)
                STALE_GAUGE.labels(exchange=self.exchange.value).set(stale_ratio)
                
                if stale_ratio > 0.5:  # More than 50% stale
                    self.stale = True
                    logger.warning(f"[{self.exchange.value}] High stale ratio: {stale_ratio:.2%}")
    
    async def disconnect(self):
        """Disconnect WebSocket"""
        self.running = False
        self.connected = False
        CONNECTION_GAUGE.labels(exchange=self.exchange.value).set(0)
        if self.ws:
            await self.ws.close()


class BinanceConnector(ExchangeConnector):
    """Binance WebSocket connector"""
    
    def get_ws_url(self) -> str:
        base_url = "wss://stream.binance.com:9443/ws"
        # Use miniTicker for all symbols
        streams = [f"{self._normalize_symbol(s)}@miniTicker" for s in self.symbols]
        return f"{base_url}/{'/'.join(streams)}"
    
    def _normalize_symbol(self, symbol: str) -> str:
        """Convert BTC/USDT to BTCUSDT format"""
        return symbol.replace('/', '').lower()
    
    async def subscribe(self):
        """No explicit subscription needed for Binance miniTicker"""
        pass
    
    def parse_message(self, message: str) -> Optional[Tick]:
        try:
            data = json.loads(message)
            
            return Tick(
                exchange=self.exchange.value,
                symbol=data['s'],
                price=float(data['c']),
                volume=float(data['v']),
                timestamp=data['E'] / 1000,  # Convert to seconds
                high_24h=float(data['h']),
                low_24h=float(data['l']),
                change_24h=float(data['P'])
            )
            
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Binance parse error: {e}")
            return None


class OKXConnector(ExchangeConnector):
    """OKX WebSocket connector"""
    
    def get_ws_url(self) -> str:
        return "wss://ws.okx.com:8443/ws/v5/public"
    
    async def subscribe(self):
        """Subscribe to tickers channel"""
        args = [{"channel": "tickers", "instId": self._normalize_symbol(s)} for s in self.symbols]
        
        subscribe_msg = {
            "op": "subscribe",
            "args": args
        }
        
        await self.ws.send(json.dumps(subscribe_msg))
        logger.info(f"[OKX] Subscribed to {len(args)} symbols")
    
    def _normalize_symbol(self, symbol: str) -> str:
        """Convert BTC/USDT to BTC-USDT format"""
        return symbol.replace('/', '-')
    
    def parse_message(self, message: str) -> Optional[Tick]:
        try:
            data = json.loads(message)
            
            if 'data' not in data or not data['data']:
                return None
            
            tick_data = data['data'][0]
            
            return Tick(
                exchange=self.exchange.value,
                symbol=tick_data['instId'],
                price=float(tick_data['last']),
                volume=float(tick_data['vol24h']),
                timestamp=int(tick_data['ts']) / 1000,
                bid=float(tick_data['bidPx']) if tick_data['bidPx'] else None,
                ask=float(tick_data['askPx']) if tick_data['askPx'] else None,
                high_24h=float(tick_data['high24h']),
                low_24h=float(tick_data['low24h']),
                change_24h=float(tick_data['sodUtc0']) * 100  # Convert to percentage
            )
            
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"OKX parse error: {e}")
            return None


class CoinbaseConnector(ExchangeConnector):
    """Coinbase Pro WebSocket connector"""
    
    def get_ws_url(self) -> str:
        return "wss://ws-feed.exchange.coinbase.com"
    
    async def subscribe(self):
        """Subscribe to ticker channel"""
        subscribe_msg = {
            "type": "subscribe",
            "product_ids": [self._normalize_symbol(s) for s in self.symbols],
            "channels": ["ticker"]
        }
        
        await self.ws.send(json.dumps(subscribe_msg))
        logger.info(f"[Coinbase] Subscribed to {len(self.symbols)} symbols")
    
    def _normalize_symbol(self, symbol: str) -> str:
        """Convert BTC/USDT to BTC-USDT format"""
        return symbol.replace('/', '-')
    
    def parse_message(self, message: str) -> Optional[Tick]:
        try:
            data = json.loads(message)
            
            if data.get('type') != 'ticker':
                return None
            
            return Tick(
                exchange=self.exchange.value,
                symbol=data['product_id'],
                price=float(data['price']),
                volume=float(data['volume_24h']),
                timestamp=time.time(),  # Coinbase doesn't provide timestamp in ticker
                bid=float(data['best_bid']) if 'best_bid' in data else None,
                ask=float(data['best_ask']) if 'best_ask' in data else None,
                high_24h=float(data['high_24h']) if 'high_24h' in data else None,
                low_24h=float(data['low_24h']) if 'low_24h' in data else None
            )
            
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Coinbase parse error: {e}")
            return None


class BybitConnector(ExchangeConnector):
    """Bybit WebSocket connector"""
    
    def get_ws_url(self) -> str:
        return "wss://stream.bybit.com/v5/public/spot"
    
    async def subscribe(self):
        """Subscribe to tickers channel"""
        symbols = [self._normalize_symbol(s) for s in self.symbols]
        
        subscribe_msg = {
            "op": "subscribe",
            "args": [f"tickers.{symbol}" for symbol in symbols]
        }
        
        await self.ws.send(json.dumps(subscribe_msg))
        logger.info(f"[Bybit] Subscribed to {len(symbols)} symbols")
    
    def _normalize_symbol(self, symbol: str) -> str:
        """Convert BTC/USDT to BTCUSDT format"""
        return symbol.replace('/', '')
    
    def parse_message(self, message: str) -> Optional[Tick]:
        try:
            data = json.loads(message)
            
            if 'data' not in data:
                return None
            
            tick_data = data['data']
            
            return Tick(
                exchange=self.exchange.value,
                symbol=tick_data['symbol'],
                price=float(tick_data['lastPrice']),
                volume=float(tick_data['volume24h']),
                timestamp=int(tick_data['ts']) / 1000,
                bid=float(tick_data['bid1Price']) if 'bid1Price' in tick_data else None,
                ask=float(tick_data['ask1Price']) if 'ask1Price' in tick_data else None,
                high_24h=float(tick_data['highPrice24h']),
                low_24h=float(tick_data['lowPrice24h']),
                change_24h=float(tick_data['price24hPcnt']) * 100
            )
            
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Bybit parse error: {e}")
            return None


class CryptoWSManager:
    """Manager for all exchange WebSocket connections"""
    
    def __init__(self):
        self.redis_client = None
        self.connectors = {}
        self.tasks = []
        
        # Configuration
        self.enabled_exchanges = self._get_enabled_exchanges()
        
    def _get_enabled_exchanges(self) -> List[Exchange]:
        """Get enabled exchanges from environment"""
        enabled = os.getenv('CRYPTO_EXCHANGES', 'binance,okx,coinbase,bybit').lower().split(',')
        exchanges = []
        
        for exchange_name in enabled:
            exchange_name = exchange_name.strip()
            try:
                exchange = Exchange(exchange_name)
                exchanges.append(exchange)
            except ValueError:
                logger.warning(f"Unknown exchange: {exchange_name}")
        
        return exchanges
    
    async def start(self):
        """Start all exchange connections"""
        # Initialize Redis connection
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        self.redis_client = redis.from_url(redis_url)
        
        logger.info(f"Starting connections to {len(self.enabled_exchanges)} exchanges")
        
        # Create connectors
        connector_classes = {
            Exchange.BINANCE: BinanceConnector,
            Exchange.OKX: OKXConnector,
            Exchange.COINBASE: CoinbaseConnector,
            Exchange.BYBIT: BybitConnector
        }
        
        for exchange in self.enabled_exchanges:
            if exchange in connector_classes:
                connector = connector_classes[exchange](exchange, self.redis_client)
                self.connectors[exchange] = connector
                
                # Start connection task
                task = asyncio.create_task(connector.connect())
                self.tasks.append(task)
        
        logger.info(f"Started {len(self.tasks)} exchange connections")
        
        # Wait for all tasks
        await asyncio.gather(*self.tasks, return_exceptions=True)
    
    async def stop(self):
        """Stop all connections"""
        logger.info("Stopping all exchange connections")
        
        # Disconnect all connectors
        for connector in self.connectors.values():
            await connector.disconnect()
        
        # Cancel tasks
        for task in self.tasks:
            task.cancel()
        
        # Close Redis connection
        if self.redis_client:
            await self.redis_client.close()
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of all connections"""
        status = {
            'healthy': True,
            'exchanges': {},
            'total_ticks': 0,
            'stale_exchanges': []
        }
        
        for exchange, connector in self.connectors.items():
            exchange_status = {
                'connected': connector.connected,
                'stale': connector.stale,
                'error_count': connector.error_count,
                'last_error': connector.last_error,
                'symbols': {}
            }
            
            total_ticks = sum(connector.tick_counts.values())
            exchange_status['total_ticks'] = total_ticks
            status['total_ticks'] += total_ticks
            
            # Per-symbol status
            for symbol in connector.symbols:
                exchange_status['symbols'][symbol] = {
                    'tick_count': connector.tick_counts.get(symbol, 0),
                    'last_msg_ts': connector.last_msg_ts.get(symbol, 0),
                    'freshness_sec': time.time() - connector.last_msg_ts.get(symbol, 0) if connector.last_msg_ts.get(symbol, 0) > 0 else None
                }
            
            status['exchanges'][exchange.value] = exchange_status
            
            # Overall health check
            if not connector.connected or connector.stale:
                status['healthy'] = False
                if connector.stale:
                    status['stale_exchanges'].append(exchange.value)
        
        return status


async def main():
    """Main entry point"""
    logger.info("Starting Crypto WebSocket Ingester")
    
    manager = CryptoWSManager()
    
    try:
        await manager.start()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        await manager.stop()


if __name__ == "__main__":
    asyncio.run(main())