"""
Sofia V2 Realtime DataHub - Coinbase Ingestor
WebSocket ingestor for Coinbase Advanced Trade
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict

import structlog

from ..bus import EventBus
from ..config import Settings
from .base import BaseExchangeIngestor

logger = structlog.get_logger(__name__)


class CoinbaseIngestor(BaseExchangeIngestor):
    """Coinbase Advanced Trade WebSocket ingestor"""

    def __init__(self, event_bus: EventBus, settings: Settings):
        super().__init__("coinbase", event_bus, settings)

        self.streams = self.exchange_config.get("streams", ["ticker", "level2"])
        endpoints = self.exchange_config.get("endpoints", {})
        self.ws_url = endpoints.get("ws", "wss://advanced-trade-ws.coinbase.com")

        logger.info("Coinbase ingestor configured", streams=self.streams, ws_url=self.ws_url)

    def get_websocket_url(self) -> str:
        """Get Coinbase WebSocket URL"""
        return self.ws_url

    def normalize_symbol(self, symbol: str) -> str:
        """Convert symbol to Coinbase format (BTC-USD)"""
        if "USDT" in symbol.upper():
            base = symbol.upper().replace("USDT", "")
            return f"{base}-USD"  # Coinbase uses USD instead of USDT
        return symbol.upper()

    def get_subscription_message(self) -> Dict[str, Any]:
        """Build Coinbase subscription message"""
        product_ids = [self.normalize_symbol(symbol) for symbol in self.symbols]

        channels = []
        if "ticker" in self.streams:
            channels.append({"name": "ticker", "product_ids": product_ids})
        if "level2" in self.streams:
            channels.append({"name": "level2", "product_ids": product_ids})

        return {"type": "subscribe", "channels": channels}

    async def process_message(self, message: str):
        """Process Coinbase WebSocket message"""
        try:
            data = json.loads(message)

            # Handle subscription response
            if data.get("type") == "subscriptions":
                logger.info("Coinbase subscription successful", channels=data.get("channels", []))
                return
            elif data.get("type") == "error":
                logger.error("Coinbase error", message=data.get("message"))
                return

            # Handle channel data
            message_type = data.get("type")
            if message_type:
                await self._process_message_by_type(message_type, data)

        except json.JSONDecodeError:
            logger.warning("Invalid JSON from Coinbase", message=message[:200])
        except Exception as e:
            logger.error("Error processing Coinbase message", error=str(e))

    async def _process_message_by_type(self, message_type: str, data: Dict[str, Any]):
        """Process message by type"""
        try:
            if message_type == "ticker":
                await self._process_ticker(data)
            elif message_type == "l2update":
                await self._process_l2_update(data)
            elif message_type == "snapshot":
                await self._process_snapshot(data)
            else:
                logger.debug("Unhandled Coinbase message type", message_type=message_type)

        except Exception as e:
            logger.error(
                "Error processing Coinbase message type", message_type=message_type, error=str(e)
            )

    async def _process_ticker(self, data: Dict[str, Any]):
        """Process ticker data (includes trade information)"""
        try:
            product_id = data.get("product_id", "")
            symbol = product_id.replace("-", "")  # Convert BTC-USD to BTCUSD

            price = float(data.get("price", 0))

            # Coinbase ticker doesn't have quantity directly
            # Use best bid/ask for approximation or skip quantity
            best_bid = float(data.get("best_bid", 0))
            best_ask = float(data.get("best_ask", 0))

            # For trade-like data, we'll use the price change to infer direction
            open_price = float(data.get("open_24h", price))
            side = "buy" if price > open_price else "sell"

            trade_data = {
                "symbol": symbol,
                "price": price,
                "quantity": 0,  # Not available in ticker
                "side": side,
                "timestamp": data.get("time", datetime.now(timezone.utc).isoformat()),
                "trade_id": str(data.get("sequence", "")),
                "usd_value": 0,  # Would need volume data
            }

            # Only emit if we have meaningful data
            if price > 0:
                await self.emit_trade(trade_data)

        except (ValueError, KeyError) as e:
            logger.warning("Invalid Coinbase ticker data", data=data, error=str(e))

    async def _process_l2_update(self, data: Dict[str, Any]):
        """Process Level 2 orderbook updates"""
        try:
            product_id = data.get("product_id", "")
            symbol = product_id.replace("-", "")  # Convert BTC-USD to BTCUSD

            changes = data.get("changes", [])

            # Coinbase sends changes as [side, price, size]
            # We'll need to maintain orderbook state for full book
            # For now, just process the changes

            bids = []
            asks = []

            for change in changes:
                if len(change) >= 3:
                    side, price, size = change[0], float(change[1]), float(change[2])

                    if side == "buy":
                        bids.append([price, size])
                    elif side == "sell":
                        asks.append([price, size])

            if bids or asks:
                orderbook_data = {
                    "symbol": symbol,
                    "bids": bids,
                    "asks": asks,
                    "timestamp": data.get("time", datetime.now(timezone.utc).isoformat()),
                }

                await self.emit_orderbook(orderbook_data)

        except (ValueError, KeyError) as e:
            logger.warning("Invalid Coinbase L2 update data", data=data, error=str(e))

    async def _process_snapshot(self, data: Dict[str, Any]):
        """Process orderbook snapshot"""
        try:
            product_id = data.get("product_id", "")
            symbol = product_id.replace("-", "")  # Convert BTC-USD to BTCUSD

            # Convert bid/ask arrays to [price, quantity] format
            bids = [[float(bid[0]), float(bid[1])] for bid in data.get("bids", [])]
            asks = [[float(ask[0]), float(ask[1])] for ask in data.get("asks", [])]

            orderbook_data = {
                "symbol": symbol,
                "bids": bids,
                "asks": asks,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            await self.emit_orderbook(orderbook_data)

        except (ValueError, KeyError) as e:
            logger.warning("Invalid Coinbase snapshot data", data=data, error=str(e))
