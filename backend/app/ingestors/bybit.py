"""
Sofia V2 Realtime DataHub - Bybit Ingestor
WebSocket ingestor for Bybit exchange
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict

import structlog

from ..bus import EventBus
from ..config import Settings
from .base import BaseExchangeIngestor

logger = structlog.get_logger(__name__)


class BybitIngestor(BaseExchangeIngestor):
    """Bybit WebSocket ingestor"""

    def __init__(self, event_bus: EventBus, settings: Settings):
        super().__init__("bybit", event_bus, settings)

        self.streams = self.exchange_config.get(
            "streams", ["publicTrade", "orderbook.25", "allLiquidation"]
        )
        endpoints = self.exchange_config.get("endpoints", {})
        self.ws_url = endpoints.get("ws", "wss://stream.bybit.com/v5/public/spot")

        logger.info("Bybit ingestor configured", streams=self.streams, ws_url=self.ws_url)

    def get_websocket_url(self) -> str:
        """Get Bybit WebSocket URL"""
        return self.ws_url

    def normalize_symbol(self, symbol: str) -> str:
        """Convert symbol to Bybit format (BTCUSDT)"""
        return symbol.upper()

    def get_subscription_message(self) -> Dict[str, Any]:
        """Build Bybit subscription message"""
        topics = []

        for symbol in self.symbols:
            bybit_symbol = self.normalize_symbol(symbol)

            for stream_type in self.streams:
                if stream_type == "publicTrade":
                    topics.append(f"publicTrade.{bybit_symbol}")
                elif stream_type.startswith("orderbook"):
                    topics.append(f"{stream_type}.{bybit_symbol}")
                elif stream_type == "allLiquidation":
                    # Global liquidation stream
                    if f"liquidation.{bybit_symbol}" not in topics:
                        topics.append(f"liquidation.{bybit_symbol}")

        return {"op": "subscribe", "args": topics}

    async def process_message(self, message: str):
        """Process Bybit WebSocket message"""
        try:
            data = json.loads(message)

            # Handle subscription response
            if data.get("success") is True and data.get("op") == "subscribe":
                logger.info("Bybit subscription successful")
                return
            elif data.get("success") is False:
                logger.error("Bybit subscription failed", data=data)
                return

            # Handle ping/pong
            if data.get("op") == "pong":
                return

            # Handle topic data
            if "topic" in data and "data" in data:
                topic = data["topic"]
                topic_data = data["data"]

                await self._process_topic_data(topic, topic_data)

        except json.JSONDecodeError:
            logger.warning("Invalid JSON from Bybit", message=message[:200])
        except Exception as e:
            logger.error("Error processing Bybit message", error=str(e))

    async def _process_topic_data(self, topic: str, data: Any):
        """Process topic-specific data"""
        try:
            if topic.startswith("publicTrade."):
                symbol = topic.split(".")[1]
                # data is a list of trades
                if isinstance(data, list):
                    for trade_item in data:
                        await self._process_trade(symbol, trade_item)

            elif topic.startswith("orderbook."):
                symbol = topic.split(".")[1]
                await self._process_orderbook(symbol, data)

            elif topic.startswith("liquidation."):
                symbol = topic.split(".")[1]
                # data is a list of liquidations
                if isinstance(data, list):
                    for liq_item in data:
                        await self._process_liquidation(symbol, liq_item)
            else:
                logger.debug("Unhandled Bybit topic", topic=topic)

        except Exception as e:
            logger.error("Error processing Bybit topic data", topic=topic, error=str(e))

    async def _process_trade(self, symbol: str, data: Dict[str, Any]):
        """Process trade data"""
        try:
            price = float(data.get("p", 0))
            quantity = float(data.get("v", 0))

            trade_data = {
                "symbol": symbol.upper(),
                "price": price,
                "quantity": quantity,
                "side": data.get("S", "").lower(),  # Buy or Sell
                "timestamp": datetime.fromtimestamp(
                    int(data.get("T", 0)) / 1000, tz=timezone.utc
                ).isoformat(),
                "trade_id": str(data.get("i", "")),
                "usd_value": price * quantity if "USDT" in symbol.upper() else 0,
            }

            await self.emit_trade(trade_data)

        except (ValueError, KeyError) as e:
            logger.warning("Invalid Bybit trade data", data=data, error=str(e))

    async def _process_orderbook(self, symbol: str, data: Dict[str, Any]):
        """Process orderbook data"""
        try:
            # Bybit sends both snapshot and delta updates
            # Handle both 'b' (bids) and 'a' (asks) arrays
            bids = [[float(bid[0]), float(bid[1])] for bid in data.get("b", [])]
            asks = [[float(ask[0]), float(ask[1])] for ask in data.get("a", [])]

            orderbook_data = {
                "symbol": symbol.upper(),
                "bids": bids,
                "asks": asks,
                "timestamp": datetime.fromtimestamp(
                    int(data.get("ts", 0)) / 1000, tz=timezone.utc
                ).isoformat(),
            }

            await self.emit_orderbook(orderbook_data)

        except (ValueError, KeyError) as e:
            logger.warning("Invalid Bybit orderbook data", data=data, error=str(e))

    async def _process_liquidation(self, symbol: str, data: Dict[str, Any]):
        """Process liquidation data"""
        try:
            price = float(data.get("price", 0))
            quantity = float(data.get("size", 0))
            side = data.get("side", "").lower()

            liquidation_data = {
                "symbol": symbol.upper(),
                "side": side,
                "price": price,
                "quantity": quantity,
                "timestamp": datetime.fromtimestamp(
                    int(data.get("updatedTime", 0)) / 1000, tz=timezone.utc
                ).isoformat(),
                "usd_value": price * quantity if "USDT" in symbol.upper() else 0,
            }

            await self.emit_liquidation(liquidation_data)

            logger.info(
                "Bybit liquidation detected",
                symbol=symbol,
                side=side,
                usd_value=liquidation_data["usd_value"],
            )

        except (ValueError, KeyError) as e:
            logger.warning("Invalid Bybit liquidation data", data=data, error=str(e))
