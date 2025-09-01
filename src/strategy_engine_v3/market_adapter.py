"""
Market Adapter - Unified interface for multiple market types.

Provides abstraction layer for:
- Cryptocurrency exchanges
- Traditional equity markets
- Forex markets
- Commodity futures
"""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class MarketType(str, Enum):
    """Supported market types."""
    
    CRYPTO = "crypto"
    EQUITY = "equity"
    FOREX = "forex"
    COMMODITY = "commodity"


class OrderType(str, Enum):
    """Order types."""
    
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderSide(str, Enum):
    """Order sides."""
    
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    """Order status."""
    
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class MarketData(BaseModel):
    """Unified market data structure."""
    
    symbol: str
    market_type: MarketType
    timestamp: datetime
    bid: float
    ask: float
    last: float
    volume: float
    open: float
    high: float
    low: float
    close: float
    

class Order(BaseModel):
    """Unified order structure."""
    
    id: Optional[str] = None
    symbol: str
    market_type: MarketType
    side: OrderSide
    type: OrderType
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    average_price: float = 0.0
    timestamp: datetime = datetime.utcnow()
    

class Position(BaseModel):
    """Unified position structure."""
    
    symbol: str
    market_type: MarketType
    side: str  # long/short
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float = 0.0
    timestamp: datetime


class MarketAdapter(ABC):
    """
    Abstract base class for market adapters.
    
    Each market type (crypto, equity, forex) implements this interface
    to provide unified access to market operations.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize market adapter with configuration."""
        self.config = config
        self.market_type = self._get_market_type()
        
    @abstractmethod
    def _get_market_type(self) -> MarketType:
        """Get the market type for this adapter."""
        pass
        
    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the market/exchange."""
        pass
        
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the market/exchange."""
        pass
        
    @abstractmethod
    async def get_market_data(self, symbol: str) -> MarketData:
        """Get current market data for a symbol."""
        pass
        
    @abstractmethod
    async def get_historical_data(
        self, 
        symbol: str, 
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[MarketData]:
        """Get historical market data."""
        pass
        
    @abstractmethod
    async def place_order(self, order: Order) -> Order:
        """Place an order."""
        pass
        
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        pass
        
    @abstractmethod
    async def get_order_status(self, order_id: str) -> Order:
        """Get order status."""
        pass
        
    @abstractmethod
    async def get_positions(self) -> List[Position]:
        """Get all open positions."""
        pass
        
    @abstractmethod
    async def get_balance(self) -> Dict[str, float]:
        """Get account balance."""
        pass


class CryptoAdapter(MarketAdapter):
    """Adapter for cryptocurrency exchanges."""
    
    def _get_market_type(self) -> MarketType:
        return MarketType.CRYPTO
        
    async def connect(self) -> bool:
        """Connect to crypto exchange."""
        # Mock implementation for now
        return True
        
    async def disconnect(self) -> None:
        """Disconnect from crypto exchange."""
        pass
        
    async def get_market_data(self, symbol: str) -> MarketData:
        """Get crypto market data."""
        # Mock implementation
        return MarketData(
            symbol=symbol,
            market_type=self.market_type,
            timestamp=datetime.utcnow(),
            bid=45000.0,
            ask=45001.0,
            last=45000.5,
            volume=1234567.89,
            open=44500.0,
            high=45500.0,
            low=44000.0,
            close=45000.0
        )
        
    async def get_historical_data(
        self, 
        symbol: str, 
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[MarketData]:
        """Get historical crypto data."""
        # Mock implementation
        return [
            MarketData(
                symbol=symbol,
                market_type=self.market_type,
                timestamp=start_date,
                bid=44000.0,
                ask=44001.0,
                last=44000.5,
                volume=1000000.0,
                open=43500.0,
                high=44500.0,
                low=43000.0,
                close=44000.0
            )
        ]
        
    async def place_order(self, order: Order) -> Order:
        """Place crypto order."""
        order.id = f"crypto_{datetime.utcnow().timestamp()}"
        order.status = OrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.average_price = order.price or 45000.0
        return order
        
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel crypto order."""
        return True
        
    async def get_order_status(self, order_id: str) -> Order:
        """Get crypto order status."""
        return Order(
            id=order_id,
            symbol="BTC/USDT",
            market_type=self.market_type,
            side=OrderSide.BUY,
            type=OrderType.LIMIT,
            quantity=1.0,
            price=45000.0,
            status=OrderStatus.FILLED,
            filled_quantity=1.0,
            average_price=45000.0
        )
        
    async def get_positions(self) -> List[Position]:
        """Get crypto positions."""
        return [
            Position(
                symbol="BTC/USDT",
                market_type=self.market_type,
                side="long",
                quantity=1.0,
                entry_price=44000.0,
                current_price=45000.0,
                unrealized_pnl=1000.0,
                timestamp=datetime.utcnow()
            )
        ]
        
    async def get_balance(self) -> Dict[str, float]:
        """Get crypto balance."""
        return {
            "USDT": 10000.0,
            "BTC": 1.5,
            "ETH": 10.0
        }


class EquityAdapter(MarketAdapter):
    """Adapter for traditional equity markets."""
    
    def _get_market_type(self) -> MarketType:
        return MarketType.EQUITY
        
    async def connect(self) -> bool:
        """Connect to equity broker."""
        return True
        
    async def disconnect(self) -> None:
        """Disconnect from equity broker."""
        pass
        
    async def get_market_data(self, symbol: str) -> MarketData:
        """Get equity market data."""
        return MarketData(
            symbol=symbol,
            market_type=self.market_type,
            timestamp=datetime.utcnow(),
            bid=150.00,
            ask=150.01,
            last=150.00,
            volume=5000000.0,
            open=149.00,
            high=151.00,
            low=148.50,
            close=150.00
        )
        
    async def get_historical_data(
        self, 
        symbol: str, 
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[MarketData]:
        """Get historical equity data."""
        return []
        
    async def place_order(self, order: Order) -> Order:
        """Place equity order."""
        order.id = f"equity_{datetime.utcnow().timestamp()}"
        order.status = OrderStatus.FILLED
        return order
        
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel equity order."""
        return True
        
    async def get_order_status(self, order_id: str) -> Order:
        """Get equity order status."""
        return Order(
            id=order_id,
            symbol="AAPL",
            market_type=self.market_type,
            side=OrderSide.BUY,
            type=OrderType.MARKET,
            quantity=100,
            status=OrderStatus.FILLED
        )
        
    async def get_positions(self) -> List[Position]:
        """Get equity positions."""
        return []
        
    async def get_balance(self) -> Dict[str, float]:
        """Get equity account balance."""
        return {"USD": 100000.0}


class MarketAdapterFactory:
    """Factory for creating market adapters."""
    
    _adapters = {
        MarketType.CRYPTO: CryptoAdapter,
        MarketType.EQUITY: EquityAdapter,
    }
    
    @classmethod
    def create(cls, market_type: MarketType, config: Dict[str, Any]) -> MarketAdapter:
        """Create a market adapter for the specified market type."""
        adapter_class = cls._adapters.get(market_type)
        if not adapter_class:
            raise ValueError(f"Unsupported market type: {market_type}")
        return adapter_class(config)