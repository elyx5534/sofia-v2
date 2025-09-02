"""
ClickHouse writer module for Sofia V2.
Subscribes to NATS and writes market data to ClickHouse.
"""

import asyncio
import json
import logging
import os
import time
from datetime import UTC, datetime
from typing import Dict, List, Optional

import orjson
from clickhouse_driver import Client as CHClient
from dotenv import load_dotenv
from nats.aio.client import Client as NATS
from pydantic import BaseModel

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class OHLCVData(BaseModel):
    """OHLCV data model"""

    ts: datetime
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    trades: int = 0


class ClickHouseWriter:
    """Writes market data to ClickHouse"""

    BATCH_SIZE = 1000
    FLUSH_INTERVAL = 1.0  # seconds
    OHLCV_INTERVAL = 1  # seconds for 1s OHLCV

    def __init__(self, ch_config: Dict, nats_client: NATS):
        self.ch_config = ch_config
        self.nats = nats_client
        self.ch_client: Optional[CHClient] = None
        self.running = False

        # Buffers for batch inserts
        self.tick_buffer: List[Dict] = []
        self.ohlcv_buffer: Dict[str, Dict] = {}  # symbol -> OHLCV accumulator
        self.last_flush = time.time()
        self.last_ohlcv_ts = datetime.now(UTC).replace(microsecond=0)

        # Statistics
        self.stats = {
            "ticks_received": 0,
            "ticks_written": 0,
            "ohlcv_written": 0,
            "errors": 0,
            "start_time": time.time(),
        }

    def connect_clickhouse(self) -> bool:
        """Connect to ClickHouse"""
        try:
            self.ch_client = CHClient(
                host=self.ch_config.get("host", "localhost"),
                port=self.ch_config.get("port", 9000),
                user=self.ch_config.get("user", "sofia"),
                password=self.ch_config.get("password", "sofia2024"),
                database=self.ch_config.get("database", "sofia"),
            )

            # Test connection
            result = self.ch_client.execute("SELECT 1")
            logger.info(f"Connected to ClickHouse: {self.ch_config['host']}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to ClickHouse: {e}")
            self.stats["errors"] += 1
            return False

    async def process_tick(self, msg):
        """Process incoming tick message"""
        try:
            # Parse message data
            data = orjson.loads(msg.data)

            # Convert timestamp to datetime
            ts = datetime.fromtimestamp(data["ts"] / 1000, UTC)

            # Add to tick buffer
            tick = {
                "ts": ts,
                "symbol": data["symbol"],
                "price": data["price"],
                "volume": data["volume"],
                "bid": data.get("bid", 0),
                "ask": data.get("ask", 0),
                "src": data.get("src", "binance"),
            }
            self.tick_buffer.append(tick)
            self.stats["ticks_received"] += 1

            # Update OHLCV accumulator
            symbol = data["symbol"]
            price = data["price"]
            volume = data["volume"]

            if symbol not in self.ohlcv_buffer:
                self.ohlcv_buffer[symbol] = {
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "volume": volume,
                    "trades": 1,
                    "first_ts": ts,
                }
            else:
                ohlcv = self.ohlcv_buffer[symbol]
                ohlcv["high"] = max(ohlcv["high"], price)
                ohlcv["low"] = min(ohlcv["low"], price)
                ohlcv["close"] = price
                ohlcv["volume"] += volume
                ohlcv["trades"] += 1

            # Check if batch is ready to flush
            if len(self.tick_buffer) >= self.BATCH_SIZE:
                await self.flush_ticks()

            # Check if OHLCV interval has passed
            current_ts = datetime.now(UTC).replace(microsecond=0)
            if (current_ts - self.last_ohlcv_ts).total_seconds() >= self.OHLCV_INTERVAL:
                await self.flush_ohlcv(self.last_ohlcv_ts)
                self.last_ohlcv_ts = current_ts

        except Exception as e:
            logger.error(f"Error processing tick: {e}")
            self.stats["errors"] += 1

    async def flush_ticks(self):
        """Flush tick buffer to ClickHouse"""
        if not self.tick_buffer:
            return

        try:
            # Insert batch into ClickHouse
            self.ch_client.execute(
                "INSERT INTO market_ticks (ts, symbol, price, volume, bid, ask, src) VALUES",
                self.tick_buffer,
            )

            self.stats["ticks_written"] += len(self.tick_buffer)
            logger.debug(f"Flushed {len(self.tick_buffer)} ticks to ClickHouse")

            # Clear buffer
            self.tick_buffer.clear()
            self.last_flush = time.time()

        except Exception as e:
            logger.error(f"Error flushing ticks to ClickHouse: {e}")
            self.stats["errors"] += 1

    async def flush_ohlcv(self, ts: datetime):
        """Flush OHLCV data to ClickHouse"""
        if not self.ohlcv_buffer:
            return

        try:
            ohlcv_data = []
            for symbol, data in self.ohlcv_buffer.items():
                ohlcv_data.append(
                    {
                        "ts": ts,
                        "symbol": symbol,
                        "open": data["open"],
                        "high": data["high"],
                        "low": data["low"],
                        "close": data["close"],
                        "volume": data["volume"],
                        "trades": data["trades"],
                    }
                )

            if ohlcv_data:
                # Insert into ClickHouse
                self.ch_client.execute(
                    "INSERT INTO ohlcv_1s (ts, symbol, open, high, low, close, volume, trades) VALUES",
                    ohlcv_data,
                )

                self.stats["ohlcv_written"] += len(ohlcv_data)
                logger.debug(f"Flushed {len(ohlcv_data)} OHLCV records to ClickHouse")

            # Clear OHLCV buffer
            self.ohlcv_buffer.clear()

        except Exception as e:
            logger.error(f"Error flushing OHLCV to ClickHouse: {e}")
            self.stats["errors"] += 1

    async def periodic_flush(self):
        """Periodically flush buffers"""
        while self.running:
            try:
                await asyncio.sleep(self.FLUSH_INTERVAL)

                # Flush ticks if any in buffer
                if self.tick_buffer:
                    await self.flush_ticks()

                # Log statistics periodically
                if int(time.time()) % 60 == 0:
                    stats = self.get_stats()
                    logger.info(f"Writer stats: {json.dumps(stats, indent=2)}")

            except Exception as e:
                logger.error(f"Error in periodic flush: {e}")

    async def run(self):
        """Main run loop"""
        self.running = True

        # Connect to ClickHouse
        if not self.connect_clickhouse():
            logger.error("Failed to connect to ClickHouse, exiting")
            return

        # Subscribe to all tick subjects
        subscription = await self.nats.subscribe("ticks.*", cb=self.process_tick)
        logger.info("Subscribed to NATS ticks.* subjects")

        # Start periodic flush task
        flush_task = asyncio.create_task(self.periodic_flush())

        try:
            # Keep running until stopped
            while self.running:
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        finally:
            # Final flush
            await self.flush_ticks()
            current_ts = datetime.now(UTC).replace(microsecond=0)
            await self.flush_ohlcv(current_ts)

            # Cleanup
            flush_task.cancel()
            await subscription.unsubscribe()

            if self.ch_client:
                self.ch_client.disconnect()

            logger.info("Writer stopped")

    async def stop(self):
        """Stop the writer"""
        self.running = False

    def get_stats(self) -> Dict:
        """Get writer statistics"""
        uptime = time.time() - self.stats["start_time"]
        return {
            **self.stats,
            "uptime_seconds": uptime,
            "ticks_per_second": self.stats["ticks_received"] / uptime if uptime > 0 else 0,
            "buffer_size": len(self.tick_buffer),
        }


async def main():
    """Main entry point for ClickHouse writer"""
    # Load environment
    load_dotenv(".env.paper")

    # Get configuration
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    ch_config = {
        "host": os.getenv("CLICKHOUSE_HOST", "localhost"),
        "port": int(os.getenv("CLICKHOUSE_PORT", "9000")),
        "user": os.getenv("CLICKHOUSE_USER", "sofia"),
        "password": os.getenv("CLICKHOUSE_PASSWORD", "sofia2024"),
        "database": os.getenv("CLICKHOUSE_DB", "sofia"),
    }

    logger.info("Starting ClickHouse writer")
    logger.info(f"NATS URL: {nats_url}")
    logger.info(f"ClickHouse: {ch_config['host']}:{ch_config['port']}/{ch_config['database']}")

    # Connect to NATS
    nc = NATS()
    try:
        await nc.connect(nats_url)
        logger.info("Connected to NATS")
    except Exception as e:
        logger.error(f"Failed to connect to NATS: {e}")
        return

    # Create and run writer
    writer = ClickHouseWriter(ch_config, nc)

    # Setup signal handlers
    import signal

    def signal_handler(sig, frame):
        logger.info("Received shutdown signal")
        asyncio.create_task(writer.stop())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        await writer.run()
    finally:
        # Print final stats
        stats = writer.get_stats()
        logger.info(f"Final statistics: {json.dumps(stats, indent=2)}")

        # Cleanup
        await nc.close()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
