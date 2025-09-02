"""
Sofia V2 DataHub main module.
Orchestrates WebSocket data ingestion and ClickHouse writing.
"""

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

from dotenv import load_dotenv
from nats.aio.client import Client as NATS

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sofia_datahub.ch_writer import ClickHouseWriter
from sofia_datahub.ws_binance import BinanceWSClient

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class DataHub:
    """Main DataHub orchestrator"""

    def __init__(self):
        self.nats_client: Optional[NATS] = None
        self.ws_client: Optional[BinanceWSClient] = None
        self.ch_writer: Optional[ClickHouseWriter] = None
        self.running = False

    async def initialize(self):
        """Initialize DataHub components"""
        # Load environment
        env_file = ".env.paper"
        if os.path.exists(".env.live"):
            mode = os.getenv("MODE", "paper")
            if mode == "live":
                env_file = ".env.live"

        load_dotenv(env_file)
        logger.info(f"Loaded environment from {env_file}")

        # Get configuration
        symbols_str = os.getenv("SYMBOLS", "BTCUSDT,ETHUSDT,BNBUSDT")
        symbols = [s.strip() for s in symbols_str.split(",") if s.strip()]
        nats_url = os.getenv("NATS_URL", "nats://localhost:4222")

        ch_config = {
            "host": os.getenv("CLICKHOUSE_HOST", "localhost"),
            "port": int(os.getenv("CLICKHOUSE_PORT", "9000")),
            "user": os.getenv("CLICKHOUSE_USER", "sofia"),
            "password": os.getenv("CLICKHOUSE_PASSWORD", "sofia2024"),
            "database": os.getenv("CLICKHOUSE_DB", "sofia"),
        }

        logger.info(f"Configuration loaded: {len(symbols)} symbols")

        # Connect to NATS
        self.nats_client = NATS()
        try:
            await self.nats_client.connect(nats_url)
            logger.info("Connected to NATS")
        except Exception as e:
            logger.error(f"Failed to connect to NATS: {e}")
            raise

        # Create components
        self.ws_client = BinanceWSClient(symbols, self.nats_client)
        self.ch_writer = ClickHouseWriter(ch_config, self.nats_client)

        logger.info("DataHub initialized successfully")

    async def run(self):
        """Run DataHub components"""
        self.running = True

        # Start components
        tasks = [
            asyncio.create_task(self.ws_client.run()),
            asyncio.create_task(self.ch_writer.run()),
        ]

        logger.info("DataHub running...")

        try:
            # Wait for all tasks
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("Tasks cancelled")
        except Exception as e:
            logger.error(f"Error running DataHub: {e}")
        finally:
            self.running = False

    async def shutdown(self):
        """Shutdown DataHub gracefully"""
        logger.info("Shutting down DataHub...")

        if self.ws_client:
            await self.ws_client.stop()

        if self.ch_writer:
            await self.ch_writer.stop()

        if self.nats_client:
            await self.nats_client.close()

        logger.info("DataHub shutdown complete")


async def main():
    """Main entry point"""
    logger.info("Starting Sofia V2 DataHub")

    # Create DataHub instance
    hub = DataHub()

    # Setup signal handlers
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}")
        asyncio.create_task(hub.shutdown())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Initialize and run
        await hub.initialize()
        await hub.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        await hub.shutdown()


if __name__ == "__main__":
    # Windows event loop policy
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(main())
