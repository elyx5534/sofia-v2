"""
Sofia V2 Realtime DataHub - Binance Ingestor
WebSocket ingestor for Binance Spot and Futures
"""

import json
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

import structlog

from .base import BaseExchangeIngestor
from ..bus import EventBus
from ..config import Settings

logger = structlog.get_logger(__name__)

class BinanceIngestor(BaseExchangeIngestor):
    """Binance WebSocket ingestor for spot and futures markets"""
    
    def __init__(self, event_bus: EventBus, settings: Settings):
        super().__init__('binance', event_bus, settings)
        
        # Binance stream configuration
        self.spot_enabled = settings.binance_spot
        self.futures_enabled = settings.binance_futures
        self.streams = self.exchange_config.get('streams', ['trade', 'depth@100ms', 'kline_1m'])
        
        # Choose primary WebSocket URL (spot vs futures)
        endpoints = self.exchange_config.get('endpoints', {})
        if self.spot_enabled:
            self.ws_url = endpoints.get('spot_ws', 'wss://stream.binance.com:9443/ws')
        else:
            self.ws_url = endpoints.get('futures_ws', 'wss://fstream.binance.com/ws')
        
        logger.info("Binance ingestor configured",
                   spot_enabled=self.spot_enabled,
                   futures_enabled=self.futures_enabled,
                   streams=self.streams,
                   ws_url=self.ws_url)
    
    def get_websocket_url(self) -> str:
        """Get Binance WebSocket URL"""
        return self.ws_url
    
    def normalize_symbol(self, symbol: str) -> str:
        """Convert symbol to Binance format (BTCUSDT)"""
        return symbol.upper()
    
    def get_subscription_message(self) -> Dict[str, Any]:
        """Build Binance subscription message for multiple streams"""
        stream_names = []
        
        for symbol in self.symbols:
            binance_symbol = self.normalize_symbol(symbol).lower()
            
            for stream_type in self.streams:
                if stream_type == 'trade':
                    stream_names.append(f"{binance_symbol}@trade")
                elif stream_type.startswith('depth'):
                    stream_names.append(f"{binance_symbol}@{stream_type}")
                elif stream_type.startswith('kline'):
                    stream_names.append(f"{binance_symbol}@{stream_type}")
                elif stream_type == 'forceOrder' and self.futures_enabled:
                    # Liquidations (futures only)
                    stream_names.append(f"{binance_symbol}@forceOrder")
        
        return {
            "method": "SUBSCRIBE",
            "params": stream_names,
            "id": 1
        }
    
    async def process_message(self, message: str):
        """Process Binance WebSocket message"""
        try:
            data = json.loads(message)
            
            # Handle subscription response
            if 'result' in data:
                if data['result'] is None and data.get('id') == 1:
                    logger.info("Binance subscription successful")
                return
            
            # Handle stream data
            if 'stream' in data and 'data' in data:
                stream = data['stream']
                stream_data = data['data']
                
                await self._process_stream_data(stream, stream_data)
            
        except json.JSONDecodeError:
            logger.warning("Invalid JSON from Binance", message=message[:200])
        except Exception as e:
            logger.error("Error processing Binance message", error=str(e))
    
    async def _process_stream_data(self, stream: str, data: Dict[str, Any]):
        """Process specific stream data"""
        try:
            if '@trade' in stream:
                await self._process_trade(data)
            elif '@depth' in stream:
                await self._process_depth(data)
            elif '@kline' in stream:
                await self._process_kline(data)
            elif '@forceOrder' in stream:
                await self._process_force_order(data)
            else:
                logger.debug("Unhandled Binance stream", stream=stream)
                
        except Exception as e:
            logger.error("Error processing Binance stream data",
                        stream=stream,
                        error=str(e))
    
    async def _process_trade(self, data: Dict[str, Any]):
        """Process trade data"""
        try:
            symbol = data.get('s', '').upper()
            price = float(data.get('p', 0))
            quantity = float(data.get('q', 0))
            
            trade_data = {
                'symbol': symbol,
                'price': price,
                'quantity': quantity,
                'side': 'sell' if data.get('m', False) else 'buy',  # m = true means market maker (sell)
                'timestamp': datetime.fromtimestamp(data.get('T', 0) / 1000, tz=timezone.utc).isoformat(),
                'trade_id': str(data.get('t', '')),
                'usd_value': price * quantity if 'USDT' in symbol else 0
            }
            
            await self.emit_trade(trade_data)
            
        except (ValueError, KeyError) as e:
            logger.warning("Invalid Binance trade data", data=data, error=str(e))
    
    async def _process_depth(self, data: Dict[str, Any]):
        """Process orderbook depth data"""
        try:
            symbol = data.get('s', '').upper()
            
            # Convert bid/ask arrays to [price, quantity] format
            bids = [[float(bid[0]), float(bid[1])] for bid in data.get('b', [])]
            asks = [[float(ask[0]), float(ask[1])] for ask in data.get('a', [])]
            
            orderbook_data = {
                'symbol': symbol,
                'bids': bids,
                'asks': asks,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            await self.emit_orderbook(orderbook_data)
            
        except (ValueError, KeyError) as e:
            logger.warning("Invalid Binance depth data", data=data, error=str(e))
    
    async def _process_kline(self, data: Dict[str, Any]):
        """Process kline (candlestick) data - can be used for volume analysis"""
        try:
            kline = data.get('k', {})
            
            if kline.get('x', False):  # Only process closed klines
                symbol = kline.get('s', '').upper()
                volume = float(kline.get('v', 0))
                close_time = datetime.fromtimestamp(kline.get('T', 0) / 1000, tz=timezone.utc).isoformat()
                
                # Could emit volume surge events here based on historical analysis
                logger.debug("Binance kline closed",
                           symbol=symbol,
                           volume=volume,
                           close_time=close_time)
                
        except (ValueError, KeyError) as e:
            logger.warning("Invalid Binance kline data", data=data, error=str(e))
    
    async def _process_force_order(self, data: Dict[str, Any]):
        """Process forced liquidation orders (futures only)"""
        try:
            # Binance force order structure
            order = data.get('o', {})
            
            symbol = order.get('s', '').upper()
            price = float(order.get('p', 0))
            quantity = float(order.get('q', 0))
            side = order.get('S', '').lower()  # BUY or SELL
            
            liquidation_data = {
                'symbol': symbol,
                'side': side,
                'price': price,
                'quantity': quantity,
                'timestamp': datetime.fromtimestamp(order.get('T', 0) / 1000, tz=timezone.utc).isoformat(),
                'usd_value': price * quantity if 'USDT' in symbol else 0
            }
            
            await self.emit_liquidation(liquidation_data)
            
            logger.info("Binance liquidation detected",
                       symbol=symbol,
                       side=side,
                       usd_value=liquidation_data['usd_value'])
            
        except (ValueError, KeyError) as e:
            logger.warning("Invalid Binance force order data", data=data, error=str(e))