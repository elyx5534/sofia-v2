"""
Sofia V2 Realtime DataHub - OKX Ingestor
WebSocket ingestor for OKX exchange
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List

import structlog

from ..bus import EventBus
from ..config import Settings
from .base import BaseExchangeIngestor

logger = structlog.get_logger(__name__)


class OKXIngestor(BaseExchangeIngestor):
    """OKX WebSocket ingestor"""

    def __init__(self, event_bus: EventBus, settings: Settings):
        super().__init__("okx", event_bus, settings)

        self.streams = self.exchange_config.get(
            "streams", ["trades", "books5", "liquidation-orders"]
        )
        endpoints = self.exchange_config.get("endpoints", {})
        self.ws_url = endpoints.get("ws", "wss://ws.okx.com:8443/ws/v5/public")

        logger.info("OKX ingestor configured", streams=self.streams, ws_url=self.ws_url)

    def get_websocket_url(self) -> str:
        """Get OKX WebSocket URL"""
        return self.ws_url

    def normalize_symbol(self, symbol: str) -> str:
        """Convert symbol to OKX format (BTC-USDT)"""
        if "USDT" in symbol.upper():
            base = symbol.upper().replace("USDT", "")
            return f"{base}-USDT"
        return symbol.upper()

    def get_subscription_message(self) -> Dict[str, Any]:
        """Build OKX subscription message"""
        args = []

        for symbol in self.symbols:
            okx_symbol = self.normalize_symbol(symbol)

            for stream_type in self.streams:
                if stream_type == "trades":
                    args.append({"channel": "trades", "instId": okx_symbol})
                elif stream_type == "books5":
                    args.append({"channel": "books5", "instId": okx_symbol})
                elif stream_type == "liquidation-orders":
                    args.append({"channel": "liquidation-orders", "instType": "SPOT"})

        return {"op": "subscribe", "args": args}

    async def process_message(self, message: str):
        """Process OKX WebSocket message"""
        try:
            data = json.loads(message)

            # Handle subscription response
            if data.get("event") == "subscribe":
                if data.get("code") == "0":
                    logger.info("OKX subscription successful", channel=data.get("arg"))
                else:
                    logger.error("OKX subscription failed", data=data)
                return

            # Handle ping/pong
            if data.get("event") == "error":
                logger.error("OKX error event", data=data)
                return

            # Handle channel data
            if "arg" in data and "data" in data:
                channel_info = data["arg"]
                channel_data = data["data"]

                await self._process_channel_data(channel_info, channel_data)

        except json.JSONDecodeError:
            logger.warning("Invalid JSON from OKX", message=message[:200])
        except Exception as e:
            logger.error("Error processing OKX message", error=str(e))

    async def _process_channel_data(self, channel_info: Dict[str, Any], data: List[Dict[str, Any]]):
        """Process channel-specific data"""
        try:
            channel = channel_info.get("channel")

            for item in data:
                if channel == "trades":
                    await self._process_trade(channel_info, item)
                elif channel == "books5":
                    await self._process_books(channel_info, item)
                elif channel == "liquidation-orders":
                    await self._process_liquidation(item)
                else:
                    logger.debug("Unhandled OKX channel", channel=channel)

        except Exception as e:
            logger.error(
                "Error processing OKX channel data",
                channel=channel_info.get("channel"),
                error=str(e),
            )

    async def _process_trade(self, channel_info: Dict[str, Any], data: Dict[str, Any]):
        """Process trade data"""
        try:
            symbol = channel_info.get("instId", "").replace("-", "")  # Convert BTC-USDT to BTCUSDT
            price = float(data.get("px", 0))
            quantity = float(data.get("sz", 0))

            trade_data = {
                "symbol": symbol,
                "price": price,
                "quantity": quantity,
                "side": data.get("side", "").lower(),  # buy or sell
                "timestamp": datetime.fromtimestamp(
                    int(data.get("ts", 0)) / 1000, tz=timezone.utc
                ).isoformat(),
                "trade_id": str(data.get("tradeId", "")),
                "usd_value": price * quantity if "USDT" in symbol else 0,
            }

            await self.emit_trade(trade_data)

        except (ValueError, KeyError) as e:
            logger.warning("Invalid OKX trade data", data=data, error=str(e))

    async def _process_books(self, channel_info: Dict[str, Any], data: Dict[str, Any]):
        """Process orderbook data"""
        try:
            symbol = channel_info.get("instId", "").replace("-", "")  # Convert BTC-USDT to BTCUSDT

            # Convert bid/ask arrays to [price, quantity] format
            bids = [[float(bid[0]), float(bid[1])] for bid in data.get("bids", [])]
            asks = [[float(ask[0]), float(ask[1])] for ask in data.get("asks", [])]

            orderbook_data = {
                "symbol": symbol,
                "bids": bids,
                "asks": asks,
                "timestamp": datetime.fromtimestamp(
                    int(data.get("ts", 0)) / 1000, tz=timezone.utc
                ).isoformat(),
            }

            await self.emit_orderbook(orderbook_data)

        except (ValueError, KeyError) as e:
            logger.warning("Invalid OKX books data", data=data, error=str(e))

    async def _process_liquidation(self, data: Dict[str, Any]):
        """Process liquidation data"""
        try:
            details = data.get("details", [{}])[0] if data.get("details") else {}

            symbol = details.get("instId", "").replace("-", "")  # Convert BTC-USDT to BTCUSDT
            price = float(details.get("bkPx", 0))  # Bankruptcy price
            quantity = float(details.get("sz", 0))
            side = details.get("side", "").lower()

            liquidation_data = {
                "symbol": symbol,
                "side": side,
                "price": price,
                "quantity": quantity,
                "timestamp": datetime.fromtimestamp(
                    int(data.get("ts", 0)) / 1000, tz=timezone.utc
                ).isoformat(),
                "usd_value": price * quantity if "USDT" in symbol else 0,
            }

            await self.emit_liquidation(liquidation_data)

            logger.info(
                "OKX liquidation detected",
                symbol=symbol,
                side=side,
                usd_value=liquidation_data["usd_value"],
            )

        except (ValueError, KeyError) as e:
            logger.warning("Invalid OKX liquidation data", data=data, error=str(e))
