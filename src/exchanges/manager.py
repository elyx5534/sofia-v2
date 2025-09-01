"""
Multi-Exchange Manager
Handles routing, balancing, and arbitrage across multiple exchanges
"""

import asyncio
import logging
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import time

from src.exchanges.base import (
    BaseExchange, Balance, Ticker, OrderBook, Order,
    OrderType, OrderSide, ExchangeStatus
)
from src.exchanges.binance_exchange import BinanceExchange
from src.exchanges.mock_exchange import MockExchange

logger = logging.getLogger(__name__)

@dataclass
class ExchangeRoute:
    """Best route for trading"""
    exchange: str
    symbol: str
    price: Decimal
    available_amount: Decimal
    fee: Decimal
    total_cost: Decimal
    slippage: Decimal = Decimal(0)
    
    @property
    def effective_price(self) -> Decimal:
        """Price including fees and slippage"""
        return self.price * (1 + self.fee + self.slippage)

@dataclass
class ArbitrageOpportunity:
    """Arbitrage opportunity between exchanges"""
    buy_exchange: str
    sell_exchange: str
    symbol: str
    buy_price: Decimal
    sell_price: Decimal
    profit_percentage: Decimal
    max_amount: Decimal
    estimated_profit: Decimal
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))

@dataclass
class ExchangeMetrics:
    """Exchange performance metrics"""
    exchange: str
    latency_ms: int
    success_rate: float
    total_volume: Decimal
    total_fees: Decimal
    uptime_percentage: float
    last_error: Optional[str] = None
    error_count: int = 0

class ExchangeManager:
    """Manages multiple exchange connections and operations"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.exchanges: Dict[str, BaseExchange] = {}
        self.exchange_configs = config.get("exchanges", {})
        self.test_mode = config.get("test_mode", False)
        
        # Routing preferences
        self.prefer_low_fees = config.get("prefer_low_fees", True)
        self.max_slippage = Decimal(str(config.get("max_slippage", "0.002")))
        
        # Arbitrage settings
        self.min_arbitrage_profit = Decimal(str(config.get("min_arbitrage_profit", "0.001")))
        self.arbitrage_enabled = config.get("arbitrage_enabled", True)
        
        # Balance management
        self.min_balance_threshold = Decimal(str(config.get("min_balance", "10")))
        self.rebalance_threshold = Decimal(str(config.get("rebalance_threshold", "0.2")))
        
        # Monitoring
        self.metrics: Dict[str, ExchangeMetrics] = {}
        self.monitoring_interval = config.get("monitoring_interval", 60)
        
        # Cache
        self.price_cache: Dict[str, Dict[str, Ticker]] = defaultdict(dict)
        self.balance_cache: Dict[str, Dict[str, Balance]] = defaultdict(dict)
        self.orderbook_cache: Dict[str, Dict[str, OrderBook]] = defaultdict(dict)
        
        # Tasks
        self.monitor_task = None
        self.arbitrage_task = None
    
    async def initialize(self):
        """Initialize all configured exchanges"""
        for exchange_name, exchange_config in self.exchange_configs.items():
            try:
                logger.info(f"Initializing {exchange_name}...")
                
                if self.test_mode or exchange_config.get("mock", False):
                    exchange = MockExchange(exchange_config)
                elif exchange_name.lower() == "binance":
                    exchange = BinanceExchange(exchange_config)
                # Add other exchanges here
                else:
                    logger.warning(f"Unknown exchange type: {exchange_name}")
                    continue
                
                if await exchange.connect():
                    self.exchanges[exchange_name] = exchange
                    self.metrics[exchange_name] = ExchangeMetrics(
                        exchange=exchange_name,
                        latency_ms=0,
                        success_rate=100.0,
                        total_volume=Decimal(0),
                        total_fees=Decimal(0),
                        uptime_percentage=100.0
                    )
                    logger.info(f"{exchange_name} initialized successfully")
                else:
                    logger.error(f"Failed to initialize {exchange_name}")
                    
            except Exception as e:
                logger.error(f"Error initializing {exchange_name}: {e}")
        
        # Start monitoring tasks
        if self.exchanges:
            self.monitor_task = asyncio.create_task(self._monitor_exchanges())
            if self.arbitrage_enabled:
                self.arbitrage_task = asyncio.create_task(self._scan_arbitrage())
    
    async def shutdown(self):
        """Shutdown all exchanges and tasks"""
        # Cancel tasks
        if self.monitor_task:
            self.monitor_task.cancel()
        if self.arbitrage_task:
            self.arbitrage_task.cancel()
        
        # Disconnect exchanges
        for exchange in self.exchanges.values():
            await exchange.disconnect()
    
    async def get_best_price(
        self, 
        symbol: str, 
        side: OrderSide, 
        amount: Decimal
    ) -> Optional[ExchangeRoute]:
        """Get best price across all exchanges"""
        best_route = None
        best_effective_price = Decimal('Infinity') if side == OrderSide.BUY else Decimal(0)
        
        for exchange_name, exchange in self.exchanges.items():
            if exchange.status != ExchangeStatus.CONNECTED:
                continue
            
            try:
                # Get orderbook
                orderbook = await exchange.get_orderbook(symbol)
                
                # Calculate effective price with slippage
                if side == OrderSide.BUY:
                    orders = orderbook.asks
                else:
                    orders = orderbook.bids
                
                if not orders:
                    continue
                
                # Calculate weighted average price for the amount
                remaining = amount
                total_cost = Decimal(0)
                total_amount = Decimal(0)
                
                for price, available in orders:
                    if remaining <= 0:
                        break
                    
                    fill_amount = min(remaining, available)
                    total_cost += price * fill_amount
                    total_amount += fill_amount
                    remaining -= fill_amount
                
                if total_amount < amount * Decimal('0.95'):  # Can't fill 95% of order
                    continue
                
                avg_price = total_cost / total_amount if total_amount > 0 else Decimal(0)
                slippage = abs(avg_price - orders[0][0]) / orders[0][0] if orders[0][0] > 0 else Decimal(0)
                
                # Check balance
                balance = await self._get_exchange_balance(exchange_name, symbol, side)
                if not balance or balance < amount * avg_price:
                    continue
                
                # Calculate fee
                fee = exchange.taker_fee
                
                route = ExchangeRoute(
                    exchange=exchange_name,
                    symbol=symbol,
                    price=avg_price,
                    available_amount=total_amount,
                    fee=fee,
                    total_cost=total_cost * (1 + fee),
                    slippage=slippage
                )
                
                # Compare effective prices
                if side == OrderSide.BUY:
                    if route.effective_price < best_effective_price:
                        best_effective_price = route.effective_price
                        best_route = route
                else:
                    if route.effective_price > best_effective_price:
                        best_effective_price = route.effective_price
                        best_route = route
                        
            except Exception as e:
                logger.error(f"Error getting price from {exchange_name}: {e}")
                continue
        
        return best_route
    
    async def route_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        amount: Decimal,
        price: Optional[Decimal] = None,
        exchange_preference: Optional[str] = None
    ) -> Order:
        """Route order to best exchange"""
        
        # If specific exchange requested
        if exchange_preference and exchange_preference in self.exchanges:
            exchange = self.exchanges[exchange_preference]
            return await exchange.place_order(symbol, side, order_type, amount, price)
        
        # Find best route
        if order_type == OrderType.MARKET:
            route = await self.get_best_price(symbol, side, amount)
            if not route:
                raise Exception("No valid route found for order")
            
            exchange = self.exchanges[route.exchange]
            order = await exchange.place_order(symbol, side, order_type, amount)
            
            # Update metrics
            self.metrics[route.exchange].total_volume += amount * route.price
            self.metrics[route.exchange].total_fees += route.fee * amount * route.price
            
            return order
        else:
            # For limit orders, use exchange with best fees
            best_exchange = min(
                self.exchanges.items(),
                key=lambda x: x[1].taker_fee if x[1].status == ExchangeStatus.CONNECTED else float('inf')
            )
            
            if best_exchange[1].status != ExchangeStatus.CONNECTED:
                raise Exception("No connected exchanges available")
            
            return await best_exchange[1].place_order(symbol, side, order_type, amount, price)
    
    async def get_aggregated_balance(self) -> Dict[str, Decimal]:
        """Get total balance across all exchanges"""
        aggregated = defaultdict(Decimal)
        
        for exchange_name, exchange in self.exchanges.items():
            if exchange.status != ExchangeStatus.CONNECTED:
                continue
            
            try:
                balances = await exchange.get_balance()
                for currency, balance in balances.items():
                    aggregated[currency] += balance.total
                    self.balance_cache[exchange_name][currency] = balance
            except Exception as e:
                logger.error(f"Error getting balance from {exchange_name}: {e}")
        
        return dict(aggregated)
    
    async def rebalance_funds(
        self,
        target_allocations: Dict[str, Dict[str, Decimal]]
    ) -> List[Dict[str, Any]]:
        """Rebalance funds across exchanges"""
        transfers = []
        current_balances = self.balance_cache
        
        for currency, exchange_targets in target_allocations.items():
            total_balance = sum(
                balance.get(currency, Balance(currency, Decimal(0), Decimal(0), Decimal(0))).total
                for balance in current_balances.values()
            )
            
            for exchange_name, target_percentage in exchange_targets.items():
                if exchange_name not in self.exchanges:
                    continue
                
                target_amount = total_balance * target_percentage
                current_amount = current_balances.get(exchange_name, {}).get(
                    currency, Balance(currency, Decimal(0), Decimal(0), Decimal(0))
                ).total
                
                difference = target_amount - current_amount
                
                if abs(difference) > total_balance * self.rebalance_threshold:
                    # Need to rebalance
                    if difference > 0:
                        # Need to transfer TO this exchange
                        source = self._find_source_exchange(currency, difference, exchange_name)
                        if source:
                            transfers.append({
                                "from": source,
                                "to": exchange_name,
                                "currency": currency,
                                "amount": abs(difference)
                            })
                    # If difference < 0, another exchange will pull from here
        
        # Execute transfers (would need withdrawal/deposit implementation)
        for transfer in transfers:
            logger.info(f"Rebalance: {transfer['amount']} {transfer['currency']} "
                       f"from {transfer['from']} to {transfer['to']}")
        
        return transfers
    
    async def scan_arbitrage(self, symbols: List[str]) -> List[ArbitrageOpportunity]:
        """Scan for arbitrage opportunities"""
        opportunities = []
        
        for symbol in symbols:
            prices = {}
            
            # Get prices from all exchanges
            for exchange_name, exchange in self.exchanges.items():
                if exchange.status != ExchangeStatus.CONNECTED:
                    continue
                
                try:
                    ticker = await exchange.get_ticker(symbol)
                    prices[exchange_name] = ticker
                    self.price_cache[exchange_name][symbol] = ticker
                except Exception as e:
                    logger.debug(f"Could not get {symbol} from {exchange_name}: {e}")
            
            # Find arbitrage opportunities
            if len(prices) < 2:
                continue
            
            for buy_ex, buy_ticker in prices.items():
                for sell_ex, sell_ticker in prices.items():
                    if buy_ex == sell_ex:
                        continue
                    
                    buy_price = buy_ticker.ask
                    sell_price = sell_ticker.bid
                    
                    if buy_price <= 0 or sell_price <= 0:
                        continue
                    
                    # Calculate profit including fees
                    buy_fee = self.exchanges[buy_ex].taker_fee
                    sell_fee = self.exchanges[sell_ex].taker_fee
                    
                    effective_buy = buy_price * (1 + buy_fee)
                    effective_sell = sell_price * (1 - sell_fee)
                    
                    profit_percentage = (effective_sell - effective_buy) / effective_buy
                    
                    if profit_percentage > self.min_arbitrage_profit:
                        # Calculate max amount based on orderbook depth
                        max_amount = await self._calculate_arbitrage_amount(
                            buy_ex, sell_ex, symbol
                        )
                        
                        if max_amount > 0:
                            estimated_profit = max_amount * (effective_sell - effective_buy)
                            
                            opportunities.append(ArbitrageOpportunity(
                                buy_exchange=buy_ex,
                                sell_exchange=sell_ex,
                                symbol=symbol,
                                buy_price=buy_price,
                                sell_price=sell_price,
                                profit_percentage=profit_percentage,
                                max_amount=max_amount,
                                estimated_profit=estimated_profit
                            ))
        
        return sorted(opportunities, key=lambda x: x.estimated_profit, reverse=True)
    
    async def execute_arbitrage(self, opportunity: ArbitrageOpportunity) -> Dict[str, Any]:
        """Execute an arbitrage trade"""
        try:
            # Place buy order
            buy_exchange = self.exchanges[opportunity.buy_exchange]
            buy_order = await buy_exchange.place_order(
                opportunity.symbol,
                OrderSide.BUY,
                OrderType.MARKET,
                opportunity.max_amount
            )
            
            # Place sell order
            sell_exchange = self.exchanges[opportunity.sell_exchange]
            sell_order = await sell_exchange.place_order(
                opportunity.symbol,
                OrderSide.SELL,
                OrderType.MARKET,
                opportunity.max_amount
            )
            
            # Calculate actual profit
            actual_profit = (
                sell_order.price * sell_order.filled - 
                buy_order.price * buy_order.filled -
                buy_order.fee - sell_order.fee
            )
            
            return {
                "success": True,
                "buy_order": buy_order,
                "sell_order": sell_order,
                "actual_profit": actual_profit,
                "opportunity": opportunity
            }
            
        except Exception as e:
            logger.error(f"Arbitrage execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "opportunity": opportunity
            }
    
    async def get_latency_report(self) -> Dict[str, int]:
        """Get latency for all exchanges"""
        latencies = {}
        
        for name, exchange in self.exchanges.items():
            latency = await exchange.ping()
            latencies[name] = latency
            self.metrics[name].latency_ms = latency
        
        return latencies
    
    async def emergency_cancel_all(self) -> Dict[str, List[str]]:
        """Cancel all open orders across all exchanges"""
        cancelled = {}
        
        for name, exchange in self.exchanges.items():
            if exchange.status != ExchangeStatus.CONNECTED:
                continue
            
            try:
                open_orders = await exchange.get_open_orders()
                cancelled[name] = []
                
                for order in open_orders:
                    if await exchange.cancel_order(order.id, order.symbol):
                        cancelled[name].append(order.id)
                        
                logger.info(f"Cancelled {len(cancelled[name])} orders on {name}")
                
            except Exception as e:
                logger.error(f"Error cancelling orders on {name}: {e}")
        
        return cancelled
    
    async def _monitor_exchanges(self):
        """Monitor exchange health"""
        while True:
            try:
                await asyncio.sleep(self.monitoring_interval)
                
                for name, exchange in self.exchanges.items():
                    # Check connection
                    if exchange.status == ExchangeStatus.DISCONNECTED:
                        logger.info(f"Attempting to reconnect {name}...")
                        await exchange.reconnect_websocket()
                    
                    # Update metrics
                    health = await exchange.health_check()
                    
                    if name in self.metrics:
                        self.metrics[name].latency_ms = health['latency_ms']
                        self.metrics[name].error_count = health['error_count']
                        
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
    
    async def _scan_arbitrage(self):
        """Continuously scan for arbitrage opportunities"""
        symbols = self.config.get("arbitrage_symbols", ["BTC/USDT", "ETH/USDT"])
        
        while self.arbitrage_enabled:
            try:
                await asyncio.sleep(5)  # Scan every 5 seconds
                
                opportunities = await self.scan_arbitrage(symbols)
                
                for opp in opportunities[:3]:  # Top 3 opportunities
                    logger.info(
                        f"Arbitrage: {opp.symbol} "
                        f"Buy {opp.buy_exchange} @ {opp.buy_price} "
                        f"Sell {opp.sell_exchange} @ {opp.sell_price} "
                        f"Profit: {opp.profit_percentage:.2%}"
                    )
                    
            except Exception as e:
                logger.error(f"Arbitrage scan error: {e}")
    
    async def _get_exchange_balance(
        self,
        exchange_name: str,
        symbol: str,
        side: OrderSide
    ) -> Optional[Decimal]:
        """Get available balance for trading"""
        base, quote = self.exchanges[exchange_name].parse_symbol(symbol)
        
        if side == OrderSide.BUY:
            # Need quote currency
            currency = quote
        else:
            # Need base currency
            currency = base
        
        if exchange_name in self.balance_cache:
            balance = self.balance_cache[exchange_name].get(currency)
            if balance:
                return balance.free
        
        return None
    
    def _find_source_exchange(
        self,
        currency: str,
        amount: Decimal,
        exclude: str
    ) -> Optional[str]:
        """Find exchange with sufficient balance"""
        for exchange_name, balances in self.balance_cache.items():
            if exchange_name == exclude:
                continue
            
            balance = balances.get(currency)
            if balance and balance.free >= amount:
                return exchange_name
        
        return None
    
    async def _calculate_arbitrage_amount(
        self,
        buy_exchange: str,
        sell_exchange: str,
        symbol: str
    ) -> Decimal:
        """Calculate maximum arbitrage amount"""
        try:
            # Get orderbooks
            buy_book = await self.exchanges[buy_exchange].get_orderbook(symbol, 10)
            sell_book = await self.exchanges[sell_exchange].get_orderbook(symbol, 10)
            
            # Get available balances
            base, quote = self.exchanges[buy_exchange].parse_symbol(symbol)
            
            buy_balance = await self._get_exchange_balance(buy_exchange, symbol, OrderSide.BUY)
            sell_balance = await self._get_exchange_balance(sell_exchange, symbol, OrderSide.SELL)
            
            if not buy_balance or not sell_balance:
                return Decimal(0)
            
            # Calculate max amount based on orderbook liquidity
            max_buy = min(buy_book.get_depth('ask', 5), buy_balance / buy_book.best_ask if buy_book.best_ask else Decimal(0))
            max_sell = min(sell_book.get_depth('bid', 5), sell_balance)
            
            return min(max_buy, max_sell) * Decimal('0.95')  # Use 95% to be safe
            
        except Exception as e:
            logger.error(f"Error calculating arbitrage amount: {e}")
            return Decimal(0)