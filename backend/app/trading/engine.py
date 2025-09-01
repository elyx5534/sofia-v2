"""
Sofia V2 Trading Engine - Professional Algorithmic Trading System
World-class trading strategies competing with professional hedge funds
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple, Union
from enum import Enum
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import numpy as np
import pandas as pd
from collections import deque, defaultdict
import math

import structlog

from ..bus import EventBus, EventType
from ..config import Settings

logger = structlog.get_logger(__name__)

class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TRAILING_STOP = "trailing_stop"

class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"

class OrderStatus(Enum):
    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"

class TradingMode(Enum):
    PAPER = "paper"          # Simulated trading
    LIVE = "live"            # Real trading
    BACKTEST = "backtest"    # Historical backtesting

@dataclass
class Position:
    """Trading position representation"""
    symbol: str
    side: OrderSide
    size: float
    entry_price: float
    current_price: float
    entry_time: datetime
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    def update_price(self, price: float):
        """Update current price and calculate unrealized PnL"""
        self.current_price = price
        if self.side == OrderSide.BUY:
            self.unrealized_pnl = (price - self.entry_price) * self.size
        else:
            self.unrealized_pnl = (self.entry_price - price) * self.size

@dataclass
class Order:
    """Trading order representation"""
    id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    size: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_size: float = 0.0
    filled_price: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    filled_at: Optional[datetime] = None
    strategy_id: str = ""
    
class Portfolio:
    """Portfolio management with risk controls"""
    
    def __init__(self, initial_balance: float = 100000.0, max_risk_per_trade: float = 0.02):
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.max_risk_per_trade = max_risk_per_trade
        
        self.positions: Dict[str, Position] = {}
        self.orders: Dict[str, Order] = {}
        self.trade_history: List[Dict[str, Any]] = []
        
        # Performance metrics
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.largest_win = 0.0
        self.largest_loss = 0.0
        self.consecutive_wins = 0
        self.consecutive_losses = 0
        self.max_drawdown = 0.0
        self.peak_balance = initial_balance
        
    def calculate_position_size(self, symbol: str, entry_price: float, stop_loss: float) -> float:
        """Calculate position size based on risk management"""
        if stop_loss <= 0 or entry_price <= 0:
            return 0.0
        
        risk_per_share = abs(entry_price - stop_loss)
        max_risk_amount = self.current_balance * self.max_risk_per_trade
        
        if risk_per_share > 0:
            position_size = max_risk_amount / risk_per_share
            # Don't risk more than 10% of balance on single trade
            max_position_value = self.current_balance * 0.1
            max_size_by_value = max_position_value / entry_price
            
            return min(position_size, max_size_by_value)
        
        return 0.0
    
    def add_position(self, position: Position):
        """Add new position to portfolio"""
        self.positions[position.symbol] = position
        
    def close_position(self, symbol: str, exit_price: float, exit_time: datetime) -> float:
        """Close position and calculate realized PnL"""
        if symbol not in self.positions:
            return 0.0
        
        position = self.positions[symbol]
        
        if position.side == OrderSide.BUY:
            pnl = (exit_price - position.entry_price) * position.size
        else:
            pnl = (position.entry_price - exit_price) * position.size
        
        # Update portfolio balance
        self.current_balance += pnl
        
        # Update statistics
        self.total_trades += 1
        if pnl > 0:
            self.winning_trades += 1
            self.consecutive_wins += 1
            self.consecutive_losses = 0
            self.largest_win = max(self.largest_win, pnl)
        else:
            self.losing_trades += 1
            self.consecutive_losses += 1
            self.consecutive_wins = 0
            self.largest_loss = min(self.largest_loss, pnl)
        
        # Track drawdown
        if self.current_balance > self.peak_balance:
            self.peak_balance = self.current_balance
        else:
            drawdown = (self.peak_balance - self.current_balance) / self.peak_balance
            self.max_drawdown = max(self.max_drawdown, drawdown)
        
        # Record trade
        trade_record = {
            'symbol': symbol,
            'side': position.side.value,
            'size': position.size,
            'entry_price': position.entry_price,
            'exit_price': exit_price,
            'entry_time': position.entry_time,
            'exit_time': exit_time,
            'pnl': pnl,
            'duration': exit_time - position.entry_time
        }
        self.trade_history.append(trade_record)
        
        # Remove position
        del self.positions[symbol]
        
        return pnl
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get portfolio performance metrics"""
        win_rate = self.winning_trades / max(self.total_trades, 1) * 100
        avg_win = sum(t['pnl'] for t in self.trade_history if t['pnl'] > 0) / max(self.winning_trades, 1)
        avg_loss = sum(t['pnl'] for t in self.trade_history if t['pnl'] < 0) / max(self.losing_trades, 1)
        profit_factor = abs(avg_win * self.winning_trades) / abs(avg_loss * self.losing_trades) if self.losing_trades > 0 else float('inf')
        
        total_return = (self.current_balance - self.initial_balance) / self.initial_balance * 100
        
        return {
            'current_balance': self.current_balance,
            'total_return_pct': total_return,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate_pct': win_rate,
            'profit_factor': profit_factor,
            'largest_win': self.largest_win,
            'largest_loss': self.largest_loss,
            'max_drawdown_pct': self.max_drawdown * 100,
            'consecutive_wins': self.consecutive_wins,
            'consecutive_losses': self.consecutive_losses,
            'positions_count': len(self.positions)
        }

class BaseStrategy(ABC):
    """Base class for all trading strategies"""
    
    def __init__(self, name: str, portfolio: Portfolio, settings: Dict[str, Any] = None):
        self.name = name
        self.portfolio = portfolio
        self.settings = settings or {}
        self.enabled = True
        self.market_data = {}  # symbol -> deque of recent prices
        self.indicators = {}   # symbol -> indicator values
        
        # Strategy performance
        self.total_signals = 0
        self.successful_signals = 0
        
    @abstractmethod
    async def analyze(self, symbol: str, price_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Analyze market data and return trading signal"""
        pass
    
    @abstractmethod
    def get_risk_params(self, symbol: str, current_price: float) -> Tuple[Optional[float], Optional[float]]:
        """Get stop loss and take profit levels"""
        pass
    
    def update_market_data(self, symbol: str, price: float, volume: float, timestamp: datetime):
        """Update market data for strategy analysis"""
        if symbol not in self.market_data:
            self.market_data[symbol] = deque(maxlen=1000)
        
        self.market_data[symbol].append({
            'price': price,
            'volume': volume,
            'timestamp': timestamp
        })

class TradingEngine:
    """Professional trading engine with multiple strategies"""
    
    def __init__(self, event_bus: EventBus, settings: Settings, initial_balance: float = 100000.0):
        self.event_bus = event_bus
        self.settings = settings
        self.portfolio = Portfolio(initial_balance)
        self.trading_mode = TradingMode.PAPER
        
        self.strategies: List[BaseStrategy] = []
        self.active_symbols = set(settings.symbols_list)
        
        # Market data storage
        self.price_data: Dict[str, deque] = defaultdict(lambda: deque(maxlen=5000))
        self.volume_data: Dict[str, deque] = defaultdict(lambda: deque(maxlen=5000))
        self.last_prices: Dict[str, float] = {}
        
        # Performance tracking
        self.start_time = datetime.now(timezone.utc)
        self.last_analysis_time = {}
        
        # Subscribe to market data events
        self.event_bus.subscribe(EventType.TRADE, self._process_trade_data)
        
        logger.info("Trading engine initialized",
                   initial_balance=initial_balance,
                   symbols=list(self.active_symbols),
                   mode=self.trading_mode.value)
    
    def add_strategy(self, strategy: BaseStrategy):
        """Add trading strategy to engine"""
        self.strategies.append(strategy)
        logger.info("Strategy added to trading engine",
                   strategy=strategy.name,
                   total_strategies=len(self.strategies))
    
    def set_trading_mode(self, mode: TradingMode):
        """Set trading mode (paper/live/backtest)"""
        self.trading_mode = mode
        logger.info("Trading mode changed", mode=mode.value)
    
    async def _process_trade_data(self, trade_data: Dict[str, Any]):
        """Process incoming trade data and run strategies"""
        try:
            symbol = trade_data.get('symbol')
            price = float(trade_data.get('price', 0))
            volume = float(trade_data.get('quantity', 0))
            timestamp_str = trade_data.get('timestamp')
            
            if not symbol or symbol not in self.active_symbols:
                return
            
            # Parse timestamp
            if timestamp_str:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            else:
                timestamp = datetime.now(timezone.utc)
            
            # Update market data
            self.price_data[symbol].append(price)
            self.volume_data[symbol].append(volume)
            self.last_prices[symbol] = price
            
            # Update existing positions
            if symbol in self.portfolio.positions:
                self.portfolio.positions[symbol].update_price(price)
            
            # Run strategies (but not too frequently)
            current_time = timestamp
            if symbol not in self.last_analysis_time or \
               (current_time - self.last_analysis_time[symbol]).seconds >= 1:
                
                await self._run_strategies(symbol, {
                    'price': price,
                    'volume': volume,
                    'timestamp': timestamp,
                    'exchange': trade_data.get('exchange'),
                    'side': trade_data.get('side')
                })
                
                self.last_analysis_time[symbol] = current_time
                
        except Exception as e:
            logger.error("Error processing trade data", error=str(e))
    
    async def _run_strategies(self, symbol: str, market_data: Dict[str, Any]):
        """Run all enabled strategies for a symbol"""
        for strategy in self.strategies:
            if not strategy.enabled:
                continue
            
            try:
                # Update strategy's market data
                strategy.update_market_data(
                    symbol, 
                    market_data['price'],
                    market_data['volume'], 
                    market_data['timestamp']
                )
                
                # Get trading signal
                signal = await strategy.analyze(symbol, market_data)
                
                if signal:
                    await self._process_trading_signal(signal, strategy)
                    
            except Exception as e:
                logger.error("Strategy analysis error",
                           strategy=strategy.name,
                           symbol=symbol,
                           error=str(e))
    
    async def _process_trading_signal(self, signal: Dict[str, Any], strategy: BaseStrategy):
        """Process trading signal from strategy"""
        try:
            symbol = signal['symbol']
            side = OrderSide(signal['side'])
            current_price = self.last_prices.get(symbol, 0)
            
            if current_price <= 0:
                return
            
            # Check if we already have a position
            has_position = symbol in self.portfolio.positions
            
            if has_position:
                existing_position = self.portfolio.positions[symbol]
                
                # If signal suggests closing position
                if signal.get('action') == 'close' or \
                   (side != existing_position.side and signal.get('action') != 'add'):
                    
                    pnl = self.portfolio.close_position(
                        symbol, 
                        current_price,
                        datetime.now(timezone.utc)
                    )
                    
                    await self.event_bus.publish(EventType.BIG_TRADE, {
                        'type': 'position_closed',
                        'strategy': strategy.name,
                        'symbol': symbol,
                        'pnl': pnl,
                        'price': current_price,
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    })
                    
                    logger.info("Position closed",
                               strategy=strategy.name,
                               symbol=symbol,
                               pnl=pnl,
                               price=current_price)
                return
            
            # Open new position
            if signal.get('action') in ['buy', 'sell', 'open']:
                stop_loss, take_profit = strategy.get_risk_params(symbol, current_price)
                
                if stop_loss:
                    position_size = self.portfolio.calculate_position_size(
                        symbol, current_price, stop_loss
                    )
                    
                    if position_size > 0:
                        position = Position(
                            symbol=symbol,
                            side=side,
                            size=position_size,
                            entry_price=current_price,
                            current_price=current_price,
                            entry_time=datetime.now(timezone.utc),
                            stop_loss=stop_loss,
                            take_profit=take_profit
                        )
                        
                        self.portfolio.add_position(position)
                        
                        # Emit trading event
                        await self.event_bus.publish(EventType.BIG_TRADE, {
                            'type': 'position_opened',
                            'strategy': strategy.name,
                            'symbol': symbol,
                            'side': side.value,
                            'size': position_size,
                            'entry_price': current_price,
                            'stop_loss': stop_loss,
                            'take_profit': take_profit,
                            'timestamp': datetime.now(timezone.utc).isoformat()
                        })
                        
                        logger.info("Position opened",
                                   strategy=strategy.name,
                                   symbol=symbol,
                                   side=side.value,
                                   size=position_size,
                                   price=current_price)
                        
        except Exception as e:
            logger.error("Error processing trading signal", error=str(e))
    
    def get_status(self) -> Dict[str, Any]:
        """Get trading engine status"""
        portfolio_metrics = self.portfolio.get_metrics()
        
        strategy_status = []
        for strategy in self.strategies:
            success_rate = strategy.successful_signals / max(strategy.total_signals, 1) * 100
            strategy_status.append({
                'name': strategy.name,
                'enabled': strategy.enabled,
                'total_signals': strategy.total_signals,
                'success_rate': success_rate
            })
        
        return {
            'trading_mode': self.trading_mode.value,
            'active_symbols': list(self.active_symbols),
            'strategies': strategy_status,
            'portfolio': portfolio_metrics,
            'market_data_points': {
                symbol: len(prices) for symbol, prices in self.price_data.items()
            },
            'uptime_seconds': (datetime.now(timezone.utc) - self.start_time).total_seconds()
        }