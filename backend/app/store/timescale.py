"""
Sofia V2 Realtime DataHub - TimescaleDB Storage
High-performance time-series database storage (optional)
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
import structlog
import asyncpg
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from ..bus import EventBus, EventType
from ..config import Settings

logger = structlog.get_logger(__name__)

class TimescaleStore:
    """
    TimescaleDB storage for high-frequency time-series data
    Provides compression, retention policies, and fast queries
    """
    
    def __init__(self, event_bus: EventBus, settings: Settings):
        self.event_bus = event_bus
        self.settings = settings
        
        # Configuration
        self.enabled = settings.use_timescale
        self.database_url = settings.database_url
        
        # Connection pool
        self.engine = None
        self.session_factory = None
        self.connection_pool = None
        
        # Batch processing
        self.batch_size = 1000
        self.flush_interval = 30  # seconds
        
        # Data buffers
        self.trade_buffer: List[Dict[str, Any]] = []
        self.orderbook_buffer: List[Dict[str, Any]] = []
        self.liquidation_buffer: List[Dict[str, Any]] = []
        self.news_buffer: List[Dict[str, Any]] = []
        self.alert_buffer: List[Dict[str, Any]] = []
        
        # TimescaleDB configuration from YAML
        storage_config = settings.get_storage_config()
        timescale_config = storage_config.get('timescale', {})
        
        self.hypertable_chunk_time = timescale_config.get('hypertable_chunk_time', '1 day')
        self.retention_days = timescale_config.get('retention_days', 90)
        self.compression_after = timescale_config.get('compression_after', '7 days')
        
        if self.enabled and self.database_url:
            logger.info("TimescaleDB store initialized",
                       database_url=self.database_url.split('@')[0] + '@***',  # Hide credentials
                       retention_days=self.retention_days)
        elif self.enabled:
            logger.warning("TimescaleDB enabled but DATABASE_URL not provided")
            self.enabled = False
    
    async def initialize(self):
        """Initialize database connection and schema"""
        if not self.enabled:
            return
        
        try:
            # Create async engine
            self.engine = create_async_engine(
                self.database_url,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                echo=False
            )
            
            # Create session factory
            self.session_factory = sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Create connection pool for high-frequency inserts
            self.connection_pool = await asyncpg.create_pool(
                self.database_url.replace('+asyncpg', ''),
                min_size=5,
                max_size=20
            )
            
            # Initialize schema
            await self._create_schema()
            
            # Setup event subscriptions
            self._setup_event_subscriptions()
            
            logger.info("TimescaleDB connection established and schema initialized")
            
        except Exception as e:
            logger.error("Failed to initialize TimescaleDB", error=str(e))
            self.enabled = False
    
    def _setup_event_subscriptions(self):
        """Subscribe to data events"""
        self.event_bus.subscribe(EventType.TRADE, self._buffer_trade)
        self.event_bus.subscribe(EventType.ORDERBOOK, self._buffer_orderbook)
        self.event_bus.subscribe(EventType.LIQUIDATION, self._buffer_liquidation)
        self.event_bus.subscribe(EventType.NEWS, self._buffer_news)
        self.event_bus.subscribe(EventType.BIG_TRADE, self._buffer_alert)
        self.event_bus.subscribe(EventType.LIQ_SPIKE, self._buffer_alert)
        self.event_bus.subscribe(EventType.VOLUME_SURGE, self._buffer_alert)
    
    async def _create_schema(self):
        """Create TimescaleDB hypertables and indexes"""
        schema_sql = [
            # Trades table
            """
            CREATE TABLE IF NOT EXISTS trades (
                timestamp TIMESTAMPTZ NOT NULL,
                exchange TEXT NOT NULL,
                symbol TEXT NOT NULL,
                price DECIMAL(20,8) NOT NULL,
                quantity DECIMAL(20,8) NOT NULL,
                side TEXT NOT NULL,
                trade_id TEXT,
                usd_value DECIMAL(20,2)
            );
            """,
            
            # Create hypertable for trades
            """
            SELECT create_hypertable('trades', 'timestamp', chunk_time_interval => INTERVAL %s, if_not_exists => TRUE);
            """,
            
            # Orderbook table (snapshots)
            """
            CREATE TABLE IF NOT EXISTS orderbook_snapshots (
                timestamp TIMESTAMPTZ NOT NULL,
                exchange TEXT NOT NULL,
                symbol TEXT NOT NULL,
                best_bid DECIMAL(20,8),
                best_ask DECIMAL(20,8),
                bid_volume DECIMAL(20,8),
                ask_volume DECIMAL(20,8),
                spread DECIMAL(20,8)
            );
            """,
            
            # Create hypertable for orderbook
            """
            SELECT create_hypertable('orderbook_snapshots', 'timestamp', chunk_time_interval => INTERVAL %s, if_not_exists => TRUE);
            """,
            
            # Liquidations table
            """
            CREATE TABLE IF NOT EXISTS liquidations (
                timestamp TIMESTAMPTZ NOT NULL,
                exchange TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                price DECIMAL(20,8) NOT NULL,
                quantity DECIMAL(20,8) NOT NULL,
                usd_value DECIMAL(20,2)
            );
            """,
            
            # Create hypertable for liquidations
            """
            SELECT create_hypertable('liquidations', 'timestamp', chunk_time_interval => INTERVAL %s, if_not_exists => TRUE);
            """,
            
            # News table
            """
            CREATE TABLE IF NOT EXISTS news (
                timestamp TIMESTAMPTZ NOT NULL,
                source TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT,
                url TEXT,
                published_at TIMESTAMPTZ,
                guid TEXT,
                tags TEXT[]
            );
            """,
            
            # Create hypertable for news
            """
            SELECT create_hypertable('news', 'timestamp', chunk_time_interval => INTERVAL %s, if_not_exists => TRUE);
            """,
            
            # Alerts table
            """
            CREATE TABLE IF NOT EXISTS alerts (
                timestamp TIMESTAMPTZ NOT NULL,
                alert_type TEXT NOT NULL,
                exchange TEXT,
                symbol TEXT,
                data JSONB NOT NULL
            );
            """,
            
            # Create hypertable for alerts
            """
            SELECT create_hypertable('alerts', 'timestamp', chunk_time_interval => INTERVAL %s, if_not_exists => TRUE);
            """
        ]
        
        # Indexes for better query performance
        index_sql = [
            "CREATE INDEX IF NOT EXISTS trades_symbol_time_idx ON trades (symbol, timestamp DESC);",
            "CREATE INDEX IF NOT EXISTS trades_exchange_time_idx ON trades (exchange, timestamp DESC);",
            "CREATE INDEX IF NOT EXISTS liquidations_symbol_time_idx ON liquidations (symbol, timestamp DESC);",
            "CREATE INDEX IF NOT EXISTS alerts_type_time_idx ON alerts (alert_type, timestamp DESC);",
            "CREATE INDEX IF NOT EXISTS news_published_idx ON news (published_at DESC);",
        ]
        
        # Retention and compression policies
        policy_sql = [
            f"SELECT add_retention_policy('trades', INTERVAL '{self.retention_days} days', if_not_exists => TRUE);",
            f"SELECT add_retention_policy('orderbook_snapshots', INTERVAL '{self.retention_days} days', if_not_exists => TRUE);",
            f"SELECT add_retention_policy('liquidations', INTERVAL '{self.retention_days} days', if_not_exists => TRUE);",
            f"SELECT add_retention_policy('news', INTERVAL '{self.retention_days} days', if_not_exists => TRUE);",
            f"SELECT add_retention_policy('alerts', INTERVAL '{self.retention_days} days', if_not_exists => TRUE);",
            
            f"SELECT add_compression_policy('trades', INTERVAL '{self.compression_after}', if_not_exists => TRUE);",
            f"SELECT add_compression_policy('orderbook_snapshots', INTERVAL '{self.compression_after}', if_not_exists => TRUE);",
            f"SELECT add_compression_policy('liquidations', INTERVAL '{self.compression_after}', if_not_exists => TRUE);",
        ]
        
        try:
            async with self.engine.begin() as conn:
                # Create tables and hypertables
                for i, sql in enumerate(schema_sql):
                    if 'create_hypertable' in sql:
                        await conn.execute(text(sql), (self.hypertable_chunk_time,))
                    else:
                        await conn.execute(text(sql))
                
                # Create indexes
                for sql in index_sql:
                    await conn.execute(text(sql))
                
                # Setup retention and compression policies
                for sql in policy_sql:
                    try:
                        await conn.execute(text(sql))
                    except Exception as e:
                        # Policies might already exist, log but continue
                        logger.debug("Policy setup warning", sql=sql, error=str(e))
                        
            logger.info("TimescaleDB schema created successfully")
            
        except Exception as e:
            logger.error("Failed to create TimescaleDB schema", error=str(e))
            raise
    
    async def _buffer_trade(self, trade_data: Dict[str, Any]):
        """Buffer trade data for batch insert"""
        if not self.enabled:
            return
        
        self.trade_buffer.append({
            'timestamp': trade_data.get('timestamp'),
            'exchange': trade_data.get('exchange'),
            'symbol': trade_data.get('symbol'),
            'price': trade_data.get('price'),
            'quantity': trade_data.get('quantity'),
            'side': trade_data.get('side'),
            'trade_id': trade_data.get('trade_id'),
            'usd_value': trade_data.get('usd_value')
        })
        
        if len(self.trade_buffer) >= self.batch_size:
            await self._flush_trades()
    
    async def _buffer_orderbook(self, orderbook_data: Dict[str, Any]):
        """Buffer orderbook data for batch insert (sampled)"""
        if not self.enabled:
            return
        
        # Sample orderbook updates to reduce volume
        if len(self.orderbook_buffer) % 10 == 0:
            best_bid = None
            best_ask = None
            bid_volume = 0
            ask_volume = 0
            spread = None
            
            bids = orderbook_data.get('bids', [])
            asks = orderbook_data.get('asks', [])
            
            if bids:
                best_bid = float(bids[0][0])
                bid_volume = sum(float(bid[1]) for bid in bids[:5])  # Top 5 levels
            
            if asks:
                best_ask = float(asks[0][0])
                ask_volume = sum(float(ask[1]) for ask in asks[:5])
            
            if best_bid and best_ask:
                spread = best_ask - best_bid
            
            self.orderbook_buffer.append({
                'timestamp': orderbook_data.get('timestamp'),
                'exchange': orderbook_data.get('exchange'),
                'symbol': orderbook_data.get('symbol'),
                'best_bid': best_bid,
                'best_ask': best_ask,
                'bid_volume': bid_volume,
                'ask_volume': ask_volume,
                'spread': spread
            })
        
        if len(self.orderbook_buffer) >= self.batch_size // 10:
            await self._flush_orderbooks()
    
    async def _buffer_liquidation(self, liquidation_data: Dict[str, Any]):
        """Buffer liquidation data for batch insert"""
        if not self.enabled:
            return
        
        self.liquidation_buffer.append({
            'timestamp': liquidation_data.get('timestamp'),
            'exchange': liquidation_data.get('exchange'),
            'symbol': liquidation_data.get('symbol'),
            'side': liquidation_data.get('side'),
            'price': liquidation_data.get('price'),
            'quantity': liquidation_data.get('quantity'),
            'usd_value': liquidation_data.get('usd_value')
        })
        
        if len(self.liquidation_buffer) >= self.batch_size // 2:
            await self._flush_liquidations()
    
    async def _buffer_news(self, news_data: Dict[str, Any]):
        """Buffer news data for batch insert"""
        if not self.enabled:
            return
        
        self.news_buffer.append({
            'timestamp': news_data.get('timestamp'),
            'source': news_data.get('source'),
            'title': news_data.get('title'),
            'summary': news_data.get('summary'),
            'url': news_data.get('url'),
            'published_at': news_data.get('published_at'),
            'guid': news_data.get('guid'),
            'tags': news_data.get('tags', [])
        })
        
        if len(self.news_buffer) >= self.batch_size // 5:
            await self._flush_news()
    
    async def _buffer_alert(self, alert_data: Dict[str, Any]):
        """Buffer alert data for batch insert"""
        if not self.enabled:
            return
        
        # Determine alert type
        alert_type = 'unknown'
        if 'z_score' in alert_data:
            alert_type = 'big_trade' if 'usd_value' in alert_data else 'liq_spike'
        elif 'surge_ratio' in alert_data:
            alert_type = 'volume_surge'
        
        self.alert_buffer.append({
            'timestamp': alert_data.get('timestamp', datetime.now(timezone.utc).isoformat()),
            'alert_type': alert_type,
            'exchange': alert_data.get('exchange'),
            'symbol': alert_data.get('symbol'),
            'data': alert_data  # Store full data as JSONB
        })
        
        if len(self.alert_buffer) >= self.batch_size // 10:
            await self._flush_alerts()
    
    async def _flush_trades(self):
        """Batch insert trades to TimescaleDB"""
        if not self.trade_buffer or not self.connection_pool:
            return
        
        try:
            async with self.connection_pool.acquire() as conn:
                await conn.executemany(
                    """
                    INSERT INTO trades (timestamp, exchange, symbol, price, quantity, side, trade_id, usd_value)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    [(
                        trade['timestamp'],
                        trade['exchange'],
                        trade['symbol'],
                        trade['price'],
                        trade['quantity'],
                        trade['side'],
                        trade['trade_id'],
                        trade['usd_value']
                    ) for trade in self.trade_buffer]
                )
            
            logger.debug("Flushed trades to TimescaleDB", count=len(self.trade_buffer))
            self.trade_buffer.clear()
            
        except Exception as e:
            logger.error("Failed to flush trades to TimescaleDB", error=str(e))
    
    async def _flush_orderbooks(self):
        """Batch insert orderbook snapshots to TimescaleDB"""
        if not self.orderbook_buffer or not self.connection_pool:
            return
        
        try:
            async with self.connection_pool.acquire() as conn:
                await conn.executemany(
                    """
                    INSERT INTO orderbook_snapshots (timestamp, exchange, symbol, best_bid, best_ask, bid_volume, ask_volume, spread)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    [(
                        ob['timestamp'],
                        ob['exchange'],
                        ob['symbol'],
                        ob['best_bid'],
                        ob['best_ask'],
                        ob['bid_volume'],
                        ob['ask_volume'],
                        ob['spread']
                    ) for ob in self.orderbook_buffer]
                )
            
            logger.debug("Flushed orderbook snapshots to TimescaleDB", count=len(self.orderbook_buffer))
            self.orderbook_buffer.clear()
            
        except Exception as e:
            logger.error("Failed to flush orderbooks to TimescaleDB", error=str(e))
    
    async def _flush_liquidations(self):
        """Batch insert liquidations to TimescaleDB"""
        if not self.liquidation_buffer or not self.connection_pool:
            return
        
        try:
            async with self.connection_pool.acquire() as conn:
                await conn.executemany(
                    """
                    INSERT INTO liquidations (timestamp, exchange, symbol, side, price, quantity, usd_value)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    [(
                        liq['timestamp'],
                        liq['exchange'],
                        liq['symbol'],
                        liq['side'],
                        liq['price'],
                        liq['quantity'],
                        liq['usd_value']
                    ) for liq in self.liquidation_buffer]
                )
            
            logger.debug("Flushed liquidations to TimescaleDB", count=len(self.liquidation_buffer))
            self.liquidation_buffer.clear()
            
        except Exception as e:
            logger.error("Failed to flush liquidations to TimescaleDB", error=str(e))
    
    async def _flush_news(self):
        """Batch insert news to TimescaleDB"""
        if not self.news_buffer or not self.connection_pool:
            return
        
        try:
            async with self.connection_pool.acquire() as conn:
                await conn.executemany(
                    """
                    INSERT INTO news (timestamp, source, title, summary, url, published_at, guid, tags)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    [(
                        news['timestamp'],
                        news['source'],
                        news['title'],
                        news['summary'],
                        news['url'],
                        news['published_at'],
                        news['guid'],
                        news['tags']
                    ) for news in self.news_buffer]
                )
            
            logger.debug("Flushed news to TimescaleDB", count=len(self.news_buffer))
            self.news_buffer.clear()
            
        except Exception as e:
            logger.error("Failed to flush news to TimescaleDB", error=str(e))
    
    async def _flush_alerts(self):
        """Batch insert alerts to TimescaleDB"""
        if not self.alert_buffer or not self.connection_pool:
            return
        
        try:
            async with self.connection_pool.acquire() as conn:
                await conn.executemany(
                    """
                    INSERT INTO alerts (timestamp, alert_type, exchange, symbol, data)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    [(
                        alert['timestamp'],
                        alert['alert_type'],
                        alert['exchange'],
                        alert['symbol'],
                        alert['data']
                    ) for alert in self.alert_buffer]
                )
            
            logger.debug("Flushed alerts to TimescaleDB", count=len(self.alert_buffer))
            self.alert_buffer.clear()
            
        except Exception as e:
            logger.error("Failed to flush alerts to TimescaleDB", error=str(e))
    
    async def flush_all_buffers(self):
        """Force flush all buffers"""
        if not self.enabled:
            return
        
        await asyncio.gather(
            self._flush_trades(),
            self._flush_orderbooks(),
            self._flush_liquidations(),
            self._flush_news(),
            self._flush_alerts(),
            return_exceptions=True
        )
        
        logger.info("Force flushed all TimescaleDB buffers")
    
    async def periodic_flush(self):
        """Periodic flush task"""
        while True:
            try:
                await asyncio.sleep(self.flush_interval)
                await self.flush_all_buffers()
                
            except asyncio.CancelledError:
                logger.info("TimescaleDB periodic flush cancelled")
                break
            except Exception as e:
                logger.error("Error in TimescaleDB periodic flush", error=str(e))
                await asyncio.sleep(60)
    
    async def close(self):
        """Close database connections"""
        if self.connection_pool:
            await self.connection_pool.close()
        if self.engine:
            await self.engine.dispose()
        
        logger.info("TimescaleDB connections closed")
    
    def get_status(self) -> Dict[str, Any]:
        """Get storage status"""
        return {
            'enabled': self.enabled,
            'database_connected': self.connection_pool is not None and not self.connection_pool.closed(),
            'buffer_sizes': {
                'trades': len(self.trade_buffer),
                'orderbooks': len(self.orderbook_buffer),
                'liquidations': len(self.liquidation_buffer),
                'news': len(self.news_buffer),
                'alerts': len(self.alert_buffer)
            },
            'batch_size': self.batch_size,
            'flush_interval': self.flush_interval,
            'retention_days': self.retention_days,
            'compression_after': self.compression_after
        }