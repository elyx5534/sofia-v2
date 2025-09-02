"""
Binance WebSocket data ingestion module for Sofia V2.
Connects to Binance streams and publishes to NATS.
"""

import asyncio
import json
import logging
import os
import time
from typing import Dict, List, Optional, Set
from urllib.parse import urlencode

import aiohttp
import orjson
from dotenv import load_dotenv
from nats.aio.client import Client as NATS
from pydantic import BaseModel, Field

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class MarketTick(BaseModel):
    """Market tick data model"""

    ts: float = Field(description="Timestamp in milliseconds")
    symbol: str
    price: float
    volume: float
    bid: float = 0.0
    ask: float = 0.0
    src: str = "binance"


class BinanceWSClient:
    """Binance WebSocket client for real-time market data"""

    BASE_URL = "wss://stream.binance.com:9443/stream"
    RECONNECT_DELAY = 5  # seconds
    HEARTBEAT_INTERVAL = 30  # seconds
    MAX_RECONNECT_ATTEMPTS = 10

    def __init__(self, symbols: List[str], nats_client: NATS):
        self.symbols = [s.lower() for s in symbols]
        self.nats = nats_client
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.running = False
        self.stats = {
            "messages_received": 0,
            "messages_published": 0,
            "errors": 0,
            "reconnects": 0,
            "start_time": time.time(),
        }
        self._subscribed_streams: Set[str] = set()

    async def connect(self) -> bool:
        """Establish WebSocket connection to Binance"""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()

            # Build stream names for mini ticker
            streams = [f"{symbol}@miniTicker" for symbol in self.symbols]
            params = {"streams": "/".join(streams)}
            url = f"{self.BASE_URL}?{urlencode(params)}"

            logger.info(f"Connecting to Binance WebSocket with {len(self.symbols)} symbols...")
            self.ws = await self.session.ws_connect(url, heartbeat=self.HEARTBEAT_INTERVAL)
            self._subscribed_streams = set(streams)

            logger.info("Connected to Binance WebSocket successfully")
            self.stats["reconnects"] += 1
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Binance WebSocket: {e}")
            self.stats["errors"] += 1
            return False

    async def disconnect(self):
        """Close WebSocket connection"""
        if self.ws:
            await self.ws.close()
            self.ws = None
        if self.session:
            await self.session.close()
            self.session = None
        logger.info("Disconnected from Binance WebSocket")

    async def process_message(self, msg: Dict):
        """Process incoming WebSocket message"""
        try:
            if "stream" not in msg or "data" not in msg:
                return

            stream = msg["stream"]
            data = msg["data"]

            # Process mini ticker data
            if stream.endswith("@miniTicker"):
                tick = MarketTick(
                    ts=data["E"],  # Event time
                    symbol=data["s"].upper(),
                    price=float(data["c"]),  # Close price
                    volume=float(data["v"]),  # Volume
                    bid=float(data.get("b", 0)),  # Best bid price
                    ask=float(data.get("a", 0)),  # Best ask price
                )

                # Publish to NATS
                subject = f"ticks.{tick.symbol}"
                await self.nats.publish(subject, orjson.dumps(tick.model_dump()))

                self.stats["messages_published"] += 1

                # Log every 1000 messages
                if self.stats["messages_published"] % 1000 == 0:
                    logger.info(f"Published {self.stats['messages_published']} messages")

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            self.stats["errors"] += 1

    async def run(self):
        """Main run loop for WebSocket client"""
        self.running = True
        reconnect_attempts = 0

        while self.running and reconnect_attempts < self.MAX_RECONNECT_ATTEMPTS:
            try:
                if not await self.connect():
                    reconnect_attempts += 1
                    await asyncio.sleep(self.RECONNECT_DELAY)
                    continue

                reconnect_attempts = 0  # Reset on successful connection

                async for msg in self.ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = orjson.loads(msg.data)
                        self.stats["messages_received"] += 1
                        await self.process_message(data)

                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        logger.error(f"WebSocket error: {msg.data}")
                        self.stats["errors"] += 1
                        break

                    elif msg.type == aiohttp.WSMsgType.CLOSED:
                        logger.warning("WebSocket connection closed")
                        break

            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                self.stats["errors"] += 1

            # Reconnect after delay
            if self.running:
                logger.info(f"Reconnecting in {self.RECONNECT_DELAY} seconds...")
                await self.disconnect()
                await asyncio.sleep(self.RECONNECT_DELAY)
                reconnect_attempts += 1

        logger.warning("WebSocket client stopped")
        await self.disconnect()

    async def stop(self):
        """Stop the WebSocket client"""
        self.running = False
        await self.disconnect()

    def get_stats(self) -> Dict:
        """Get client statistics"""
        uptime = time.time() - self.stats["start_time"]
        return {
            **self.stats,
            "uptime_seconds": uptime,
            "msg_per_second": self.stats["messages_received"] / uptime if uptime > 0 else 0,
            "subscribed_symbols": len(self.symbols),
        }


async def main():
    """Main entry point for Binance WebSocket client"""
    # Load environment
    load_dotenv(".env.paper")

    # Get configuration
    symbols_str = os.getenv("SYMBOLS", "BTCUSDT,ETHUSDT,BNBUSDT")
    symbols = [s.strip() for s in symbols_str.split(",") if s.strip()]
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")

    logger.info(f"Starting Binance WebSocket client for {len(symbols)} symbols")
    logger.info(f"NATS URL: {nats_url}")

    # Connect to NATS
    nc = NATS()
    try:
        await nc.connect(nats_url)
        logger.info("Connected to NATS")
    except Exception as e:
        logger.error(f"Failed to connect to NATS: {e}")
        return

    # Create and run WebSocket client
    client = BinanceWSClient(symbols, nc)

    # Setup signal handlers for graceful shutdown
    import signal

    def signal_handler(sig, frame):
        logger.info("Received shutdown signal")
        asyncio.create_task(client.stop())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Run client
        await client.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        # Print final stats
        stats = client.get_stats()
        logger.info(f"Final statistics: {json.dumps(stats, indent=2)}")

        # Cleanup
        await client.stop()
        await nc.close()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
