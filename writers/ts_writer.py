"""
Time-series writer for QuestDB/TimescaleDB with OHLCV aggregation
Supports append-only writes with 1s/1m OHLCV aggregation and metrics tracking
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Any, List, Union
from collections import defaultdict, deque
import json
import psycopg2
import asyncpg
import redis.asyncio as redis
from prometheus_client import Counter, Histogram, Gauge, Summary
import pandas as pd

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Prometheus metrics
WRITES_TOTAL = Counter('ts_writes_total', 'Total writes to time-series DB', ['db_type', 'table'])
WRITE_ERRORS = Counter('ts_write_errors_total', 'Total write errors', ['db_type', 'error_type'])
WRITE_LATENCY = Histogram('ts_write_latency_seconds', 'Write operation latency', ['db_type', 'table'])
BUS_LAG_MS = Histogram('ts_bus_lag_milliseconds', 'Message bus lag', ['exchange', 'symbol'])
WRITER_QUEUE_SIZE = Gauge('ts_writer_queue_size', 'Writer queue size', ['exchange', 'symbol'])
STALE_RATIO = Gauge('ts_stale_ratio', 'Ratio of stale messages', ['exchange'])
RECONNECT_TOTAL = Counter('ts_reconnects_total', 'Total DB reconnections', ['db_type'])
BATCH_SIZE = Summary('ts_batch_size', 'Batch size distribution', ['db_type'])


@dataclass
class OHLCV:
    """OHLCV data structure"""
    exchange: str
    symbol: str
    timestamp: int  # Unix timestamp in seconds
    timeframe: str  # '1s', '1m', '5m', '1h', etc.
    open: float
    high: float
    low: float
    close: float
    volume: float
    count: int = 0  # Number of ticks aggregated
    vwap: Optional[float] = None  # Volume-weighted average price
    
    def __post_init__(self):
        if self.vwap is None and self.volume > 0:
            self.vwap = self.close  # Approximation if not calculated


@dataclass
class Tick:
    """Tick data from Redis stream"""
    exchange: str
    symbol: str
    price: float
    volume: float
    timestamp: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    
    @classmethod
    def from_redis_message(cls, message: Dict[str, bytes]) -> 'Tick':
        """Create Tick from Redis stream message"""
        return cls(
            exchange=message[b'exchange'].decode(),
            symbol=message[b'symbol'].decode(),
            price=float(message[b'price']),
            volume=float(message[b'volume']),
            timestamp=float(message[b'timestamp']),
            bid=float(message[b'bid']) if b'bid' in message and message[b'bid'] else None,
            ask=float(message[b'ask']) if b'ask' in message and message[b'ask'] else None
        )


class OHLCVAggregator:
    """OHLCV aggregation engine"""
    
    def __init__(self, timeframes: List[str] = None):
        self.timeframes = timeframes or ['1s', '1m', '5m', '15m', '1h', '4h', '1d']
        self.aggregators = {}  # {(exchange, symbol, timeframe): OHLCVState}
        
        # Timeframe conversion to seconds
        self.timeframe_seconds = {
            '1s': 1,
            '1m': 60,
            '5m': 300,
            '15m': 900,
            '1h': 3600,
            '4h': 14400,
            '1d': 86400
        }
    
    def process_tick(self, tick: Tick) -> List[OHLCV]:
        """Process tick and return completed OHLCV bars"""
        completed_bars = []
        
        for timeframe in self.timeframes:
            bars = self._process_tick_for_timeframe(tick, timeframe)
            completed_bars.extend(bars)
        
        return completed_bars
    
    def _process_tick_for_timeframe(self, tick: Tick, timeframe: str) -> List[OHLCV]:
        """Process tick for specific timeframe"""
        key = (tick.exchange, tick.symbol, timeframe)
        interval_seconds = self.timeframe_seconds[timeframe]
        
        # Calculate bar timestamp (aligned to timeframe)
        bar_timestamp = int(tick.timestamp // interval_seconds) * interval_seconds
        
        if key not in self.aggregators:
            self.aggregators[key] = {
                'timestamp': bar_timestamp,
                'open': tick.price,
                'high': tick.price,
                'low': tick.price,
                'close': tick.price,
                'volume': tick.volume,
                'count': 1,
                'vwap_sum': tick.price * tick.volume,
                'vwap_volume': tick.volume
            }
            return []
        
        aggregator = self.aggregators[key]
        
        # Check if we need to close current bar and start new one
        if bar_timestamp > aggregator['timestamp']:
            # Close current bar
            completed_bar = OHLCV(
                exchange=tick.exchange,
                symbol=tick.symbol,
                timestamp=aggregator['timestamp'],
                timeframe=timeframe,
                open=aggregator['open'],
                high=aggregator['high'],
                low=aggregator['low'],
                close=aggregator['close'],
                volume=aggregator['volume'],
                count=aggregator['count'],
                vwap=aggregator['vwap_sum'] / aggregator['vwap_volume'] if aggregator['vwap_volume'] > 0 else aggregator['close']
            )
            
            # Start new bar
            self.aggregators[key] = {
                'timestamp': bar_timestamp,
                'open': tick.price,
                'high': tick.price,
                'low': tick.price,
                'close': tick.price,
                'volume': tick.volume,
                'count': 1,
                'vwap_sum': tick.price * tick.volume,
                'vwap_volume': tick.volume
            }
            
            return [completed_bar]
        
        else:
            # Update current bar
            aggregator['high'] = max(aggregator['high'], tick.price)
            aggregator['low'] = min(aggregator['low'], tick.price)
            aggregator['close'] = tick.price
            aggregator['volume'] += tick.volume
            aggregator['count'] += 1
            aggregator['vwap_sum'] += tick.price * tick.volume
            aggregator['vwap_volume'] += tick.volume
            
            return []


class QuestDBWriter:
    """QuestDB writer implementation"""
    
    def __init__(self, connection_params: Dict[str, Any]):
        self.connection_params = connection_params
        self.pool = None
        self.connected = False
        
    async def connect(self):
        """Establish connection pool to QuestDB"""
        try:
            self.pool = await asyncpg.create_pool(**self.connection_params)
            self.connected = True
            logger.info("Connected to QuestDB")
            
            # Create tables if not exist
            await self._create_tables()
            
        except Exception as e:
            logger.error(f"QuestDB connection error: {e}")
            RECONNECT_TOTAL.labels(db_type='questdb').inc()
            raise
    
    async def _create_tables(self):
        """Create OHLCV tables if they don't exist"""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS ohlcv (
            timestamp TIMESTAMP,
            exchange SYMBOL CAPACITY 10,
            symbol SYMBOL CAPACITY 100,
            timeframe SYMBOL CAPACITY 10,
            open DOUBLE,
            high DOUBLE,
            low DOUBLE,
            close DOUBLE,
            volume DOUBLE,
            count INT,
            vwap DOUBLE
        ) timestamp(timestamp) PARTITION BY DAY;
        """
        
        create_ticks_sql = """
        CREATE TABLE IF NOT EXISTS ticks (
            timestamp TIMESTAMP,
            exchange SYMBOL CAPACITY 10,
            symbol SYMBOL CAPACITY 100,
            price DOUBLE,
            volume DOUBLE,
            bid DOUBLE,
            ask DOUBLE
        ) timestamp(timestamp) PARTITION BY DAY;
        """
        
        async with self.pool.acquire() as conn:
            await conn.execute(create_table_sql)
            await conn.execute(create_ticks_sql)
            logger.info("QuestDB tables created/verified")
    
    async def write_ticks(self, ticks: List[Tick]) -> bool:
        """Write raw ticks to QuestDB"""
        if not self.connected or not ticks:
            return False
        
        start_time = time.time()
        
        try:
            insert_sql = """
            INSERT INTO ticks (timestamp, exchange, symbol, price, volume, bid, ask)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """
            
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    for tick in ticks:
                        await conn.execute(
                            insert_sql,
                            tick.timestamp * 1000000,  # Convert to microseconds for QuestDB
                            tick.exchange,
                            tick.symbol,
                            tick.price,
                            tick.volume,
                            tick.bid,
                            tick.ask
                        )
            
            WRITES_TOTAL.labels(db_type='questdb', table='ticks').inc(len(ticks))
            WRITE_LATENCY.labels(db_type='questdb', table='ticks').observe(time.time() - start_time)
            BATCH_SIZE.labels(db_type='questdb').observe(len(ticks))
            
            return True
            
        except Exception as e:
            logger.error(f"QuestDB tick write error: {e}")
            WRITE_ERRORS.labels(db_type='questdb', error_type='tick_write').inc()
            return False
    
    async def write_ohlcv(self, bars: List[OHLCV]) -> bool:
        """Write OHLCV bars to QuestDB"""
        if not self.connected or not bars:
            return False
        
        start_time = time.time()
        
        try:
            insert_sql = """
            INSERT INTO ohlcv (timestamp, exchange, symbol, timeframe, open, high, low, close, volume, count, vwap)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            """
            
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    for bar in bars:
                        await conn.execute(
                            insert_sql,
                            bar.timestamp * 1000000,  # Convert to microseconds
                            bar.exchange,
                            bar.symbol,
                            bar.timeframe,
                            bar.open,
                            bar.high,
                            bar.low,
                            bar.close,
                            bar.volume,
                            bar.count,
                            bar.vwap
                        )
            
            WRITES_TOTAL.labels(db_type='questdb', table='ohlcv').inc(len(bars))
            WRITE_LATENCY.labels(db_type='questdb', table='ohlcv').observe(time.time() - start_time)
            
            return True
            
        except Exception as e:
            logger.error(f"QuestDB OHLCV write error: {e}")
            WRITE_ERRORS.labels(db_type='questdb', error_type='ohlcv_write').inc()
            return False
    
    async def close(self):
        """Close connection pool"""
        if self.pool:
            await self.pool.close()
            self.connected = False


class TimescaleDBWriter:
    """TimescaleDB writer implementation (fallback)"""
    
    def __init__(self, connection_params: Dict[str, Any]):
        self.connection_params = connection_params
        self.pool = None
        self.connected = False
    
    async def connect(self):
        """Establish connection pool to TimescaleDB"""
        try:
            self.pool = await asyncpg.create_pool(**self.connection_params)
            self.connected = True
            logger.info("Connected to TimescaleDB")
            
            # Create tables and hypertables
            await self._create_tables()
            
        except Exception as e:
            logger.error(f"TimescaleDB connection error: {e}")
            RECONNECT_TOTAL.labels(db_type='timescaledb').inc()
            raise
    
    async def _create_tables(self):
        """Create OHLCV tables and hypertables"""
        create_ohlcv_sql = """
        CREATE TABLE IF NOT EXISTS ohlcv (
            timestamp TIMESTAMPTZ NOT NULL,
            exchange TEXT NOT NULL,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            open DOUBLE PRECISION,
            high DOUBLE PRECISION,
            low DOUBLE PRECISION,
            close DOUBLE PRECISION,
            volume DOUBLE PRECISION,
            count INTEGER,
            vwap DOUBLE PRECISION
        );
        """
        
        create_ticks_sql = """
        CREATE TABLE IF NOT EXISTS ticks (
            timestamp TIMESTAMPTZ NOT NULL,
            exchange TEXT NOT NULL,
            symbol TEXT NOT NULL,
            price DOUBLE PRECISION,
            volume DOUBLE PRECISION,
            bid DOUBLE PRECISION,
            ask DOUBLE PRECISION
        );
        """
        
        async with self.pool.acquire() as conn:
            await conn.execute(create_ohlcv_sql)
            await conn.execute(create_ticks_sql)
            
            # Create hypertables (ignore if already exists)
            try:
                await conn.execute("SELECT create_hypertable('ohlcv', 'timestamp', if_not_exists => TRUE);")
                await conn.execute("SELECT create_hypertable('ticks', 'timestamp', if_not_exists => TRUE);")
            except Exception as e:
                logger.warning(f"Hypertable creation warning: {e}")
            
            # Create indexes
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_time ON ohlcv (symbol, timestamp);")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_ticks_symbol_time ON ticks (symbol, timestamp);")
            
            logger.info("TimescaleDB tables/hypertables created/verified")
    
    async def write_ticks(self, ticks: List[Tick]) -> bool:
        """Write raw ticks to TimescaleDB"""
        if not self.connected or not ticks:
            return False
        
        start_time = time.time()
        
        try:
            insert_sql = """
            INSERT INTO ticks (timestamp, exchange, symbol, price, volume, bid, ask)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """
            
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    for tick in ticks:
                        await conn.execute(
                            insert_sql,
                            pd.to_datetime(tick.timestamp, unit='s'),
                            tick.exchange,
                            tick.symbol,
                            tick.price,
                            tick.volume,
                            tick.bid,
                            tick.ask
                        )
            
            WRITES_TOTAL.labels(db_type='timescaledb', table='ticks').inc(len(ticks))
            WRITE_LATENCY.labels(db_type='timescaledb', table='ticks').observe(time.time() - start_time)
            BATCH_SIZE.labels(db_type='timescaledb').observe(len(ticks))
            
            return True
            
        except Exception as e:
            logger.error(f"TimescaleDB tick write error: {e}")
            WRITE_ERRORS.labels(db_type='timescaledb', error_type='tick_write').inc()
            return False
    
    async def write_ohlcv(self, bars: List[OHLCV]) -> bool:
        """Write OHLCV bars to TimescaleDB"""
        if not self.connected or not bars:
            return False
        
        start_time = time.time()
        
        try:
            insert_sql = """
            INSERT INTO ohlcv (timestamp, exchange, symbol, timeframe, open, high, low, close, volume, count, vwap)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            """
            
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    for bar in bars:
                        await conn.execute(
                            insert_sql,
                            pd.to_datetime(bar.timestamp, unit='s'),
                            bar.exchange,
                            bar.symbol,
                            bar.timeframe,
                            bar.open,
                            bar.high,
                            bar.low,
                            bar.close,
                            bar.volume,
                            bar.count,
                            bar.vwap
                        )
            
            WRITES_TOTAL.labels(db_type='timescaledb', table='ohlcv').inc(len(bars))
            WRITE_LATENCY.labels(db_type='timescaledb', table='ohlcv').observe(time.time() - start_time)
            
            return True
            
        except Exception as e:
            logger.error(f"TimescaleDB OHLCV write error: {e}")
            WRITE_ERRORS.labels(db_type='timescaledb', error_type='ohlcv_write').inc()
            return False
    
    async def close(self):
        """Close connection pool"""
        if self.pool:
            await self.pool.close()
            self.connected = False


class TimeSeriesWriter:
    """Main time-series writer with failover capability"""
    
    def __init__(self):
        self.redis_client = None
        self.primary_writer = None
        self.fallback_writer = None
        self.aggregator = OHLCVAggregator()
        
        # Configuration
        self.batch_size = int(os.getenv('TS_BATCH_SIZE', '100'))
        self.flush_interval = int(os.getenv('TS_FLUSH_INTERVAL', '5'))  # seconds
        self.max_queue_size = int(os.getenv('TS_MAX_QUEUE_SIZE', '10000'))
        self.stale_threshold = int(os.getenv('TS_STALE_THRESHOLD', '30'))  # seconds
        
        # Buffers
        self.tick_buffer = deque(maxlen=self.max_queue_size)
        self.ohlcv_buffer = deque(maxlen=self.max_queue_size)
        
        # Metrics tracking
        self.last_flush = time.time()
        self.consumer_group = os.getenv('TS_CONSUMER_GROUP', 'ts_writers')
        self.consumer_name = os.getenv('TS_CONSUMER_NAME', f'writer_{os.getpid()}')
        
        # Stream tracking
        self.stream_positions = {}
    
    async def start(self):
        """Initialize connections and start processing"""
        # Connect to Redis
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        self.redis_client = redis.from_url(redis_url)
        
        # Setup primary writer (QuestDB)
        questdb_params = {
            'host': os.getenv('QUESTDB_HOST', 'localhost'),
            'port': int(os.getenv('QUESTDB_PORT', '8812')),
            'database': os.getenv('QUESTDB_DB', 'qdb'),
            'user': os.getenv('QUESTDB_USER', 'admin'),
            'password': os.getenv('QUESTDB_PASSWORD', 'quest')
        }
        
        try:
            self.primary_writer = QuestDBWriter(questdb_params)
            await self.primary_writer.connect()
            logger.info("Primary writer (QuestDB) connected")
        except Exception as e:
            logger.warning(f"Primary writer connection failed: {e}")
        
        # Setup fallback writer (TimescaleDB)
        timescaledb_params = {
            'host': os.getenv('TIMESCALEDB_HOST', 'localhost'),
            'port': int(os.getenv('TIMESCALEDB_PORT', '5432')),
            'database': os.getenv('TIMESCALEDB_DB', 'timeseries'),
            'user': os.getenv('TIMESCALEDB_USER', 'postgres'),
            'password': os.getenv('TIMESCALEDB_PASSWORD', 'password')
        }
        
        try:
            self.fallback_writer = TimescaleDBWriter(timescaledb_params)
            await self.fallback_writer.connect()
            logger.info("Fallback writer (TimescaleDB) connected")
        except Exception as e:
            logger.warning(f"Fallback writer connection failed: {e}")
        
        # Start processing tasks
        tasks = [
            asyncio.create_task(self.stream_consumer()),
            asyncio.create_task(self.flush_processor()),
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def stream_consumer(self):
        """Consume ticks from Redis Streams"""
        logger.info("Starting Redis stream consumer")
        
        # Discover available streams
        stream_pattern = "ticks.*"
        streams = {}
        
        while True:
            try:
                # Discover new streams
                for key in await self.redis_client.scan_iter(match=stream_pattern):
                    key_str = key.decode()
                    if key_str not in streams:
                        streams[key_str] = '>'  # Start from latest
                        logger.info(f"Discovered new stream: {key_str}")
                
                if not streams:
                    await asyncio.sleep(1)
                    continue
                
                # Create consumer group if not exists
                for stream_key in streams.keys():
                    try:
                        await self.redis_client.xgroup_create(
                            stream_key, self.consumer_group, '$', mkstream=True
                        )
                    except redis.RedisError:
                        pass  # Group already exists
                
                # Read from streams
                stream_list = [(k, '>') for k in streams.keys()]
                messages = await self.redis_client.xreadgroup(
                    self.consumer_group,
                    self.consumer_name,
                    streams=dict(stream_list),
                    count=self.batch_size,
                    block=1000  # Block for 1 second
                )
                
                for stream, msgs in messages:
                    stream_str = stream.decode()
                    
                    for msg_id, fields in msgs:
                        try:
                            # Parse tick
                            tick = Tick.from_redis_message(fields)
                            
                            # Calculate bus lag
                            bus_lag_ms = (time.time() - tick.timestamp) * 1000
                            BUS_LAG_MS.labels(
                                exchange=tick.exchange, 
                                symbol=tick.symbol
                            ).observe(bus_lag_ms)
                            
                            # Check for stale data
                            if bus_lag_ms > self.stale_threshold * 1000:
                                STALE_RATIO.labels(exchange=tick.exchange).inc()
                                logger.warning(f"Stale tick: {tick.exchange}/{tick.symbol} lag={bus_lag_ms:.1f}ms")
                                continue
                            
                            # Add to buffer
                            self.tick_buffer.append(tick)
                            WRITER_QUEUE_SIZE.labels(
                                exchange=tick.exchange, 
                                symbol=tick.symbol
                            ).set(len(self.tick_buffer))
                            
                            # Process OHLCV aggregation
                            completed_bars = self.aggregator.process_tick(tick)
                            self.ohlcv_buffer.extend(completed_bars)
                            
                            # Acknowledge message
                            await self.redis_client.xack(stream, self.consumer_group, msg_id)
                            
                        except Exception as e:
                            logger.error(f"Tick processing error: {e}")
                
            except Exception as e:
                logger.error(f"Stream consumer error: {e}")
                await asyncio.sleep(1)
    
    async def flush_processor(self):
        """Flush buffers to database periodically"""
        while True:
            try:
                await asyncio.sleep(self.flush_interval)
                
                current_time = time.time()
                should_flush = (
                    len(self.tick_buffer) >= self.batch_size or
                    len(self.ohlcv_buffer) >= self.batch_size or
                    (current_time - self.last_flush) > self.flush_interval
                )
                
                if should_flush:
                    await self.flush_buffers()
                    self.last_flush = current_time
                    
            except Exception as e:
                logger.error(f"Flush processor error: {e}")
    
    async def flush_buffers(self):
        """Flush tick and OHLCV buffers to database"""
        if not self.tick_buffer and not self.ohlcv_buffer:
            return
        
        # Prepare batches
        tick_batch = []
        ohlcv_batch = []
        
        # Extract from buffers
        while self.tick_buffer and len(tick_batch) < self.batch_size:
            tick_batch.append(self.tick_buffer.popleft())
        
        while self.ohlcv_buffer and len(ohlcv_batch) < self.batch_size:
            ohlcv_batch.append(self.ohlcv_buffer.popleft())
        
        if not tick_batch and not ohlcv_batch:
            return
        
        logger.debug(f"Flushing {len(tick_batch)} ticks, {len(ohlcv_batch)} OHLCV bars")
        
        # Try primary writer first
        success = False
        if self.primary_writer and self.primary_writer.connected:
            try:
                if tick_batch:
                    await self.primary_writer.write_ticks(tick_batch)
                if ohlcv_batch:
                    await self.primary_writer.write_ohlcv(ohlcv_batch)
                success = True
                logger.debug("Primary writer flush successful")
            except Exception as e:
                logger.error(f"Primary writer flush failed: {e}")
        
        # Fallback to secondary writer
        if not success and self.fallback_writer and self.fallback_writer.connected:
            try:
                if tick_batch:
                    await self.fallback_writer.write_ticks(tick_batch)
                if ohlcv_batch:
                    await self.fallback_writer.write_ohlcv(ohlcv_batch)
                success = True
                logger.debug("Fallback writer flush successful")
            except Exception as e:
                logger.error(f"Fallback writer flush failed: {e}")
        
        if not success:
            # Re-add to buffers if both writers failed
            for tick in reversed(tick_batch):
                self.tick_buffer.appendleft(tick)
            for bar in reversed(ohlcv_batch):
                self.ohlcv_buffer.appendleft(bar)
            
            logger.error("All writers failed, data returned to buffers")
    
    async def stop(self):
        """Stop processing and close connections"""
        logger.info("Stopping time-series writer")
        
        # Final flush
        await self.flush_buffers()
        
        # Close database connections
        if self.primary_writer:
            await self.primary_writer.close()
        if self.fallback_writer:
            await self.fallback_writer.close()
        
        # Close Redis connection
        if self.redis_client:
            await self.redis_client.close()
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get writer health status"""
        return {
            'tick_buffer_size': len(self.tick_buffer),
            'ohlcv_buffer_size': len(self.ohlcv_buffer),
            'primary_writer_connected': self.primary_writer.connected if self.primary_writer else False,
            'fallback_writer_connected': self.fallback_writer.connected if self.fallback_writer else False,
            'last_flush': self.last_flush,
            'aggregator_state_count': len(self.aggregator.aggregators)
        }


async def main():
    """Main entry point"""
    logger.info("Starting Time-Series Writer")
    
    writer = TimeSeriesWriter()
    
    try:
        await writer.start()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        await writer.stop()


if __name__ == "__main__":
    asyncio.run(main())