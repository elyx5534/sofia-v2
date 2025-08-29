"""
Live Trading Adapter using CCXT
"""

import os
import time
import uuid
import asyncio
import logging
from typing import Dict, Any, Optional, List, Tuple
from decimal import Decimal
from datetime import datetime
from enum import Enum
import json
import ccxt.async_support as ccxt
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


class OrderState(Enum):
    """Order state machine"""
    NEW = "NEW"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


@dataclass
class Order:
    """Order data structure"""
    order_id: str
    client_order_id: str
    symbol: str
    side: str  # buy|sell
    type: str  # limit|market
    quantity: Decimal
    price: Optional[Decimal]
    state: OrderState
    filled_quantity: Decimal = Decimal("0")
    average_price: Optional[Decimal] = None
    created_at: datetime = None
    updated_at: datetime = None
    exchange_order_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['state'] = self.state.value
        d['quantity'] = str(self.quantity)
        d['price'] = str(self.price) if self.price else None
        d['filled_quantity'] = str(self.filled_quantity)
        d['average_price'] = str(self.average_price) if self.average_price else None
        d['created_at'] = self.created_at.isoformat() if self.created_at else None
        d['updated_at'] = self.updated_at.isoformat() if self.updated_at else None
        return d


class LiveAdapter:
    """Live trading adapter with CCXT"""
    
    def __init__(self, exchange_name: str = None, testnet: bool = True):
        self.exchange_name = exchange_name or os.getenv('EXCHANGE', 'binance')
        self.testnet = testnet or os.getenv('MODE') == 'testnet'
        self.api_key = os.getenv('API_KEY')
        self.api_secret = os.getenv('API_SECRET')
        
        # Initialize exchange
        self.exchange = None
        self.orders: Dict[str, Order] = {}
        self.rate_limit_delay = 0.5  # Base delay in seconds
        self.max_retries = 3
        self.timeout = 10000  # 10 seconds default
        
        # Correlation tracking
        self.correlation_id = None
        
    async def initialize(self):
        """Initialize exchange connection"""
        try:
            exchange_class = getattr(ccxt, self.exchange_name)
            
            config = {
                'apiKey': self.api_key,
                'secret': self.api_secret,
                'enableRateLimit': True,
                'timeout': self.timeout,
                'options': {
                    'defaultType': 'spot',
                    'adjustForTimeDifference': True
                }
            }
            
            # Testnet configuration
            if self.testnet:
                if self.exchange_name == 'binance':
                    config['urls'] = {
                        'api': {
                            'public': 'https://testnet.binance.vision/api',
                            'private': 'https://testnet.binance.vision/api',
                        }
                    }
                config['options']['test'] = True
                config['options']['sandbox'] = True
            
            self.exchange = exchange_class(config)
            
            # Load markets
            await self.exchange.load_markets()
            
            # Check time sync
            await self._check_time_sync()
            
            logger.info(f"LiveAdapter initialized: {self.exchange_name} ({'testnet' if self.testnet else 'live'})")
            
        except Exception as e:
            logger.error(f"Failed to initialize exchange: {e}")
            raise
    
    async def _check_time_sync(self):
        """Check NTP time drift"""
        try:
            server_time = await self.exchange.fetch_time()
            local_time = int(time.time() * 1000)
            drift_ms = abs(server_time - local_time)
            
            if drift_ms > 1000:
                raise ValueError(f"Time drift too large: {drift_ms}ms. Please sync system time.")
            
            logger.info(f"Time sync OK: drift={drift_ms}ms")
            return drift_ms
            
        except Exception as e:
            logger.error(f"Time sync check failed: {e}")
            raise
    
    def _generate_client_order_id(self, strategy: str = "manual") -> str:
        """Generate idempotent client order ID"""
        timestamp = int(time.time() * 1000)
        rand = uuid.uuid4().hex[:6]
        return f"SOFIA-{strategy}-{timestamp}-{rand}"
    
    async def _with_retry(self, func, *args, **kwargs):
        """Execute with retry and rate limit handling"""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                # Add jitter to rate limit delay
                delay = self.rate_limit_delay * (1 + attempt * 0.5)
                await asyncio.sleep(delay)
                
                # Execute function
                result = await func(*args, **kwargs)
                return result
                
            except ccxt.RateLimitExceeded as e:
                logger.warning(f"Rate limit exceeded, attempt {attempt + 1}/{self.max_retries}")
                await asyncio.sleep(5 * (attempt + 1))  # Exponential backoff
                last_error = e
                
            except ccxt.NetworkError as e:
                logger.warning(f"Network error, attempt {attempt + 1}/{self.max_retries}: {e}")
                await asyncio.sleep(2 * (attempt + 1))
                last_error = e
                
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                raise
        
        raise last_error
    
    async def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        strategy: str = "manual",
        correlation_id: Optional[str] = None
    ) -> Order:
        """
        Create a new order
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            side: 'buy' or 'sell'
            order_type: 'limit' or 'market'
            quantity: Order quantity
            price: Order price (required for limit orders)
            strategy: Strategy identifier
            correlation_id: Correlation ID for tracking
        """
        self.correlation_id = correlation_id or str(uuid.uuid4())
        
        try:
            # Generate client order ID
            client_order_id = self._generate_client_order_id(strategy)
            
            # Apply precision
            market = self.exchange.market(symbol)
            amount = float(self.exchange.amount_to_precision(symbol, float(quantity)))
            
            params = {
                'clientOrderId': client_order_id,
                'newOrderRespType': 'FULL'  # Get full response
            }
            
            # Create order based on type
            if order_type == 'limit':
                if price is None:
                    raise ValueError("Price required for limit orders")
                price_precise = float(self.exchange.price_to_precision(symbol, float(price)))
                
                # Check min notional
                notional = amount * price_precise
                min_notional = market.get('limits', {}).get('cost', {}).get('min', 10)
                if notional < min_notional:
                    raise ValueError(f"Order notional {notional} below minimum {min_notional}")
                
                response = await self._with_retry(
                    self.exchange.create_limit_order,
                    symbol, side, amount, price_precise, params
                )
            else:
                response = await self._with_retry(
                    self.exchange.create_market_order,
                    symbol, side, amount, params
                )
            
            # Create order object
            order = Order(
                order_id=client_order_id,
                client_order_id=client_order_id,
                symbol=symbol,
                side=side,
                type=order_type,
                quantity=Decimal(str(amount)),
                price=Decimal(str(price)) if price else None,
                state=OrderState.NEW,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                exchange_order_id=response.get('id')
            )
            
            # Store order
            self.orders[client_order_id] = order
            
            # Log structured
            logger.info(json.dumps({
                'event': 'order_created',
                'orderId': client_order_id,
                'clientOrderId': client_order_id,
                'corrId': self.correlation_id,
                'symbol': symbol,
                'side': side,
                'type': order_type,
                'quantity': str(quantity),
                'price': str(price) if price else None
            }))
            
            return order
            
        except Exception as e:
            logger.error(f"Failed to create order: {e}", extra={
                'corrId': self.correlation_id,
                'symbol': symbol,
                'side': side
            })
            raise
    
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an order"""
        try:
            response = await self._with_retry(
                self.exchange.cancel_order,
                order_id, symbol
            )
            
            # Update order state
            if order_id in self.orders:
                self.orders[order_id].state = OrderState.CANCELED
                self.orders[order_id].updated_at = datetime.now()
            
            logger.info(json.dumps({
                'event': 'order_canceled',
                'orderId': order_id,
                'symbol': symbol,
                'corrId': self.correlation_id
            }))
            
            return True
            
        except ccxt.OrderNotFound:
            logger.warning(f"Order not found: {order_id}")
            return False
        except Exception as e:
            logger.error(f"Failed to cancel order: {e}")
            raise
    
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """Get open orders"""
        try:
            orders = await self._with_retry(
                self.exchange.fetch_open_orders,
                symbol
            )
            
            # Convert to Order objects
            result = []
            for order_data in orders:
                order = self._parse_order(order_data)
                result.append(order)
                
                # Update internal state
                if order.client_order_id:
                    self.orders[order.client_order_id] = order
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to fetch open orders: {e}")
            raise
    
    def _parse_order(self, order_data: Dict[str, Any]) -> Order:
        """Parse exchange order data to Order object"""
        client_order_id = order_data.get('clientOrderId') or order_data.get('id')
        
        # Map exchange status to OrderState
        status = order_data.get('status', '').upper()
        state_map = {
            'OPEN': OrderState.NEW,
            'PARTIALLY_FILLED': OrderState.PARTIAL,
            'FILLED': OrderState.FILLED,
            'CANCELED': OrderState.CANCELED,
            'CANCELLED': OrderState.CANCELED,
            'REJECTED': OrderState.REJECTED,
            'EXPIRED': OrderState.EXPIRED
        }
        state = state_map.get(status, OrderState.NEW)
        
        return Order(
            order_id=order_data.get('id'),
            client_order_id=client_order_id,
            symbol=order_data.get('symbol'),
            side=order_data.get('side'),
            type=order_data.get('type'),
            quantity=Decimal(str(order_data.get('amount', 0))),
            price=Decimal(str(order_data.get('price', 0))) if order_data.get('price') else None,
            state=state,
            filled_quantity=Decimal(str(order_data.get('filled', 0))),
            average_price=Decimal(str(order_data.get('average', 0))) if order_data.get('average') else None,
            created_at=datetime.fromtimestamp(order_data.get('timestamp', 0) / 1000) if order_data.get('timestamp') else None,
            updated_at=datetime.fromtimestamp(order_data.get('lastTradeTimestamp', 0) / 1000) if order_data.get('lastTradeTimestamp') else None,
            exchange_order_id=order_data.get('id')
        )
    
    async def resync(self) -> Dict[str, Any]:
        """Resync OMS state with exchange"""
        try:
            logger.info("Starting OMS resync...")
            
            # Fetch open orders
            open_orders = await self.get_open_orders()
            
            # Fetch recent trades
            since = int((datetime.now().timestamp() - 86400) * 1000)  # Last 24 hours
            trades = await self._with_retry(
                self.exchange.fetch_my_trades,
                None, since
            )
            
            # Rebuild state
            self.orders.clear()
            
            for order in open_orders:
                self.orders[order.client_order_id] = order
            
            # Process trades to update order states
            for trade in trades:
                order_id = trade.get('order')
                if order_id in self.orders:
                    order = self.orders[order_id]
                    order.filled_quantity += Decimal(str(trade.get('amount', 0)))
                    
                    if order.filled_quantity >= order.quantity:
                        order.state = OrderState.FILLED
            
            result = {
                'open_orders': len(open_orders),
                'recent_trades': len(trades),
                'synced_orders': len(self.orders),
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"OMS resync complete: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Resync failed: {e}")
            raise
    
    async def close(self):
        """Close exchange connection"""
        if self.exchange:
            await self.exchange.close()
            logger.info("LiveAdapter closed")