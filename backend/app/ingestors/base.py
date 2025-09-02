"""
Sofia V2 Realtime DataHub - Base Exchange Ingestor
Common functionality for exchange WebSocket ingestors
"""

import asyncio
import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import structlog
import websockets
from tenacity import retry, stop_after_attempt, wait_exponential

from ..bus import EventBus, EventType
from ..config import Settings

logger = structlog.get_logger(__name__)


class BaseExchangeIngestor(ABC):
    """
    Base class for exchange WebSocket ingestors
    Provides common reconnection logic, error handling, and event publishing
    """

    def __init__(self, exchange_name: str, event_bus: EventBus, settings: Settings):
        self.exchange_name = exchange_name
        self.event_bus = event_bus
        self.settings = settings
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.is_running = False
        self.is_connected = False
        self.reconnect_count = 0
        self.last_message_time: Optional[datetime] = None

        # Exchange-specific config
        self.exchange_config = settings.get_exchange_config(exchange_name)
        self.symbols = settings.symbols_list

        logger.info(f"{self.exchange_name} ingestor initialized", symbols=self.symbols)

    @abstractmethod
    def get_websocket_url(self) -> str:
        """Get WebSocket URL for this exchange"""
        pass

    @abstractmethod
    def get_subscription_message(self) -> Dict[str, Any]:
        """Get subscription message for configured symbols and streams"""
        pass

    @abstractmethod
    async def process_message(self, message: str):
        """Process incoming WebSocket message"""
        pass

    def normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol format for this exchange"""
        return symbol

    async def emit_trade(self, trade_data: Dict[str, Any]):
        """Emit normalized trade event"""
        normalized_trade = {
            "exchange": self.exchange_name,
            "symbol": trade_data.get("symbol"),
            "price": float(trade_data.get("price", 0)),
            "quantity": float(trade_data.get("quantity", 0)),
            "side": trade_data.get("side"),  # 'buy' or 'sell'
            "timestamp": trade_data.get("timestamp"),
            "trade_id": trade_data.get("trade_id"),
            "usd_value": trade_data.get("usd_value", 0),
        }
        await self.event_bus.publish(EventType.TRADE, normalized_trade)

    async def emit_orderbook(self, orderbook_data: Dict[str, Any]):
        """Emit normalized orderbook event"""
        normalized_orderbook = {
            "exchange": self.exchange_name,
            "symbol": orderbook_data.get("symbol"),
            "bids": orderbook_data.get("bids", []),
            "asks": orderbook_data.get("asks", []),
            "timestamp": orderbook_data.get("timestamp"),
        }
        await self.event_bus.publish(EventType.ORDERBOOK, normalized_orderbook)

    async def emit_liquidation(self, liquidation_data: Dict[str, Any]):
        """Emit normalized liquidation event"""
        normalized_liquidation = {
            "exchange": self.exchange_name,
            "symbol": liquidation_data.get("symbol"),
            "side": liquidation_data.get("side"),
            "price": float(liquidation_data.get("price", 0)),
            "quantity": float(liquidation_data.get("quantity", 0)),
            "timestamp": liquidation_data.get("timestamp"),
            "usd_value": liquidation_data.get("usd_value", 0),
        }
        await self.event_bus.publish(EventType.LIQUIDATION, normalized_liquidation)

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2, min=1, max=30))
    async def _connect(self) -> websockets.WebSocketClientProtocol:
        """Connect to WebSocket with retry logic"""
        url = self.get_websocket_url()
        logger.info(f"Connecting to {self.exchange_name} WebSocket", url=url)

        try:
            websocket = await websockets.connect(
                url,
                ping_interval=self.settings.ping_interval,
                ping_timeout=self.settings.connection_timeout,
                close_timeout=10,
            )

            self.reconnect_count = 0  # Reset on successful connection
            logger.info(f"Connected to {self.exchange_name} WebSocket")
            return websocket

        except Exception as e:
            self.reconnect_count += 1
            logger.error(
                f"Failed to connect to {self.exchange_name}",
                error=str(e),
                reconnect_count=self.reconnect_count,
            )
            raise

    async def _subscribe(self, websocket: websockets.WebSocketClientProtocol):
        """Send subscription message"""
        subscription = self.get_subscription_message()
        if subscription:
            await websocket.send(json.dumps(subscription))
            logger.info(f"Sent subscription to {self.exchange_name}", subscription=subscription)

    async def _handle_message(self, message: str):
        """Handle incoming message with error isolation"""
        try:
            self.last_message_time = datetime.now(timezone.utc)
            await self.process_message(message)
        except Exception as e:
            logger.error(
                f"Error processing {self.exchange_name} message",
                error=str(e),
                message=message[:200],
            )

    async def _message_loop(self):
        """Main message processing loop"""
        while self.is_running:
            try:
                # Connect/reconnect
                self.websocket = await self._connect()
                self.is_connected = True

                # Subscribe to streams
                await self._subscribe(self.websocket)

                # Emit connection status
                await self.event_bus.publish(
                    EventType.CONNECTION_STATUS,
                    {
                        "exchange": self.exchange_name,
                        "status": "connected",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )

                # Process messages
                async for message in self.websocket:
                    if not self.is_running:
                        break
                    await self._handle_message(message)

            except websockets.exceptions.ConnectionClosed:
                logger.warning(f"{self.exchange_name} connection closed")
                self.is_connected = False
            except asyncio.CancelledError:
                logger.info(f"{self.exchange_name} message loop cancelled")
                break
            except Exception as e:
                logger.error(
                    f"{self.exchange_name} connection error",
                    error=str(e),
                    reconnect_count=self.reconnect_count,
                )
                self.is_connected = False

                # Emit connection status
                await self.event_bus.publish(
                    EventType.CONNECTION_STATUS,
                    {
                        "exchange": self.exchange_name,
                        "status": "disconnected",
                        "error": str(e),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )

                # Exponential backoff before retry
                backoff = min(2**self.reconnect_count, self.settings.max_reconnect_delay)
                await asyncio.sleep(backoff)
            finally:
                if self.websocket:
                    await self.websocket.close()
                    self.websocket = None

    async def start(self):
        """Start the ingestor"""
        if self.is_running:
            return

        self.is_running = True
        logger.info(f"Starting {self.exchange_name} ingestor")

        await self._message_loop()

    async def stop(self):
        """Stop the ingestor"""
        self.is_running = False
        self.is_connected = False

        if self.websocket:
            await self.websocket.close()
            self.websocket = None

        logger.info(f"{self.exchange_name} ingestor stopped")

    def is_connected_status(self) -> bool:
        """Check if currently connected"""
        return self.is_connected

    def get_status(self) -> Dict[str, Any]:
        """Get ingestor status"""
        return {
            "exchange": self.exchange_name,
            "running": self.is_running,
            "connected": self.is_connected,
            "reconnect_count": self.reconnect_count,
            "last_message_time": (
                self.last_message_time.isoformat() if self.last_message_time else None
            ),
            "symbols": self.symbols,
        }
