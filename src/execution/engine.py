"""
Advanced Execution Engine with TWAP and Microstructure
"""

import os
import logging
import asyncio
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from dataclasses import dataclass, asdict
import numpy as np
import json
from enum import Enum

logger = logging.getLogger(__name__)


class OrderStyle(Enum):
    POST_ONLY = "post_only"
    IOC = "ioc"  # Immediate or Cancel
    MARKET = "market"
    TWAP = "twap"


@dataclass
class ExecutionSlice:
    """Individual slice of a TWAP order"""
    slice_id: str
    parent_order_id: str
    symbol: str
    side: str
    quantity: Decimal
    price: Decimal
    offset_bps: int
    timestamp: datetime
    status: str = "pending"
    filled_quantity: Decimal = Decimal('0')
    avg_fill_price: Decimal = Decimal('0')
    slippage_bps: float = 0.0


@dataclass
class ExecutionMetrics:
    """Execution quality metrics"""
    symbol: str
    total_quantity: Decimal
    avg_fill_price: Decimal
    vwap_benchmark: Decimal
    slippage_bps: float
    fill_ratio: float
    effective_spread_bps: float
    queue_slip_bps: float
    execution_time_ms: int
    style: str


class SmartExecutionEngine:
    """Advanced execution with microstructure awareness"""
    
    def __init__(self):
        self.config = {
            'EXECUTION_STYLE': os.getenv('EXECUTION_STYLE', 'post_only_first'),
            'TWAP_SLOTS': int(os.getenv('TWAP_SLOTS', '10')),
            'DYNAMIC_OFFSET_BPS': int(os.getenv('DYNAMIC_OFFSET_BPS', '2')),
            'QUEUE_DEPTH_MIN': int(os.getenv('QUEUE_DEPTH_MIN', '50000')),
            'MAX_SLICE_USD': int(os.getenv('MAX_SLICE_USD', '5000')),
            'DRIFT_TOLERANCE_BPS': int(os.getenv('DRIFT_TOLERANCE_BPS', '20')),
            'POST_ONLY_TIMEOUT_MS': int(os.getenv('POST_ONLY_TIMEOUT_MS', '5000')),
            'ANTI_SPIKE_BAND_BPS': int(os.getenv('ANTI_SPIKE_BAND_BPS', '100'))
        }
        
        # Execution state
        self.active_orders: Dict[str, Any] = {}
        self.twap_orders: Dict[str, List[ExecutionSlice]] = {}
        self.execution_metrics: List[ExecutionMetrics] = []
        
        # Market microstructure data
        self.order_books: Dict[str, Dict] = {}
        self.last_trades: Dict[str, List] = {}
        self.spread_history: Dict[str, List[float]] = {}
        
        # Anti-spoofing
        self.price_history: Dict[str, List[Tuple[datetime, float]]] = {}
        self.spike_filter_active = True
        
    async def execute_order(self, symbol: str, side: str, quantity: Decimal, 
                          target_price: Optional[Decimal] = None,
                          style: OrderStyle = OrderStyle.POST_ONLY) -> Dict[str, Any]:
        """Execute order with intelligent routing"""
        
        order_id = f"{symbol}_{side}_{int(time.time() * 1000000)}"
        start_time = datetime.now()
        
        logger.info(f"Executing {side} {quantity} {symbol} with {style.value}")
        
        try:
            # Get current market data
            market_data = await self._get_market_data(symbol)
            if not market_data:
                return {'error': 'Market data unavailable'}
            
            # Apply anti-spike filter
            if self.spike_filter_active and self._is_price_spike(symbol, market_data['mid_price']):
                logger.warning(f"Price spike detected for {symbol}, delaying execution")
                await asyncio.sleep(2)  # Wait for spike to settle
                market_data = await self._get_market_data(symbol)
            
            # Determine execution strategy
            order_value_usd = float(quantity * market_data['mid_price'])
            
            if order_value_usd > self.config['MAX_SLICE_USD']:
                # Large order - use TWAP
                result = await self._execute_twap(order_id, symbol, side, quantity, market_data)
            else:
                # Small order - use smart routing
                result = await self._execute_single(order_id, symbol, side, quantity, target_price, style, market_data)
            
            # Calculate execution metrics
            if result.get('status') == 'filled':
                metrics = self._calculate_execution_metrics(symbol, side, quantity, result, market_data, start_time)
                self.execution_metrics.append(metrics)
                
                logger.info(f"Execution complete: {symbol} slippage={metrics.slippage_bps:.1f}bps, "
                          f"fill_ratio={metrics.fill_ratio:.1%}")
            
            return result
            
        except Exception as e:
            logger.error(f"Execution failed for {order_id}: {e}")
            return {'error': str(e), 'order_id': order_id}
    
    async def _execute_single(self, order_id: str, symbol: str, side: str, 
                            quantity: Decimal, target_price: Optional[Decimal],
                            style: OrderStyle, market_data: Dict) -> Dict[str, Any]:
        """Execute single order with smart routing"""
        
        # Calculate execution price with dynamic offset
        offset_bps = self._calculate_dynamic_offset(symbol, market_data)
        
        if side == 'buy':
            if style == OrderStyle.POST_ONLY:
                exec_price = market_data['bid'] * (1 + offset_bps / 10000)
            else:
                exec_price = market_data['ask']
        else:  # sell
            if style == OrderStyle.POST_ONLY:
                exec_price = market_data['ask'] * (1 - offset_bps / 10000)
            else:
                exec_price = market_data['bid']
        
        # Try post-only first if configured
        if self.config['EXECUTION_STYLE'] == 'post_only_first':
            result = await self._try_post_only(order_id, symbol, side, quantity, exec_price)
            
            # If post-only fails, fallback to IOC
            if result.get('status') != 'filled':
                logger.info(f"Post-only timeout for {order_id}, falling back to IOC")
                result = await self._execute_ioc(order_id, symbol, side, quantity, market_data)
        else:
            # Direct execution based on style
            if style == OrderStyle.POST_ONLY:
                result = await self._try_post_only(order_id, symbol, side, quantity, exec_price)
            elif style == OrderStyle.IOC:
                result = await self._execute_ioc(order_id, symbol, side, quantity, market_data)
            else:
                result = await self._execute_market(order_id, symbol, side, quantity, market_data)
        
        return result
    
    async def _execute_twap(self, parent_order_id: str, symbol: str, side: str, 
                          total_quantity: Decimal, market_data: Dict) -> Dict[str, Any]:
        """Execute large order using TWAP"""
        
        n_slices = self.config['TWAP_SLOTS']
        slice_quantity = total_quantity / n_slices
        
        logger.info(f"TWAP execution: {total_quantity} {symbol} in {n_slices} slices")
        
        slices = []
        filled_quantity = Decimal('0')
        total_cost = Decimal('0')
        
        for i in range(n_slices):
            slice_id = f"{parent_order_id}_slice_{i}"
            
            # Get fresh market data
            current_market_data = await self._get_market_data(symbol)
            if not current_market_data:
                break
            
            # Check drift tolerance
            price_drift = abs(current_market_data['mid_price'] - market_data['mid_price']) / market_data['mid_price']
            if price_drift > self.config['DRIFT_TOLERANCE_BPS'] / 10000:
                logger.warning(f"Price drift {price_drift*10000:.1f}bps exceeds tolerance, adjusting")
                market_data = current_market_data
            
            # Execute slice
            slice_result = await self._execute_single(
                slice_id, symbol, side, slice_quantity, 
                None, OrderStyle.POST_ONLY, current_market_data
            )
            
            if slice_result.get('status') == 'filled':
                slice_qty = Decimal(str(slice_result['filled_quantity']))
                slice_price = Decimal(str(slice_result['avg_fill_price']))
                
                filled_quantity += slice_qty
                total_cost += slice_qty * slice_price
                
                # Create slice record
                execution_slice = ExecutionSlice(
                    slice_id=slice_id,
                    parent_order_id=parent_order_id,
                    symbol=symbol,
                    side=side,
                    quantity=slice_qty,
                    price=slice_price,
                    offset_bps=self._calculate_dynamic_offset(symbol, current_market_data),
                    timestamp=datetime.now(),
                    status='filled',
                    filled_quantity=slice_qty,
                    avg_fill_price=slice_price
                )
                
                slices.append(execution_slice)
            
            # Wait between slices (randomized to avoid detection)
            wait_time = np.random.uniform(2, 8)  # 2-8 seconds
            await asyncio.sleep(wait_time)
        
        # Store TWAP order record
        self.twap_orders[parent_order_id] = slices
        
        # Calculate TWAP results
        if filled_quantity > 0:
            avg_price = total_cost / filled_quantity
            fill_ratio = float(filled_quantity / total_quantity)
            
            return {
                'order_id': parent_order_id,
                'status': 'filled' if fill_ratio > 0.95 else 'partial',
                'filled_quantity': float(filled_quantity),
                'avg_fill_price': float(avg_price),
                'fill_ratio': fill_ratio,
                'n_slices': len(slices),
                'execution_style': 'twap'
            }
        else:
            return {
                'order_id': parent_order_id,
                'status': 'failed',
                'error': 'No fills in TWAP execution'
            }
    
    async def _try_post_only(self, order_id: str, symbol: str, side: str, 
                           quantity: Decimal, price: Decimal) -> Dict[str, Any]:
        """Try post-only order with timeout"""
        
        # Simulate post-only execution
        start_time = time.time()
        timeout_ms = self.config['POST_ONLY_TIMEOUT_MS']
        
        # Check order book depth at our price level
        market_data = await self._get_market_data(symbol)
        queue_depth = self._estimate_queue_depth(symbol, price, side, market_data)
        
        if queue_depth < self.config['QUEUE_DEPTH_MIN']:
            logger.info(f"Insufficient queue depth for post-only: {queue_depth}")
            return {'status': 'rejected', 'reason': 'insufficient_depth'}
        
        # Simulate waiting for fill
        await asyncio.sleep(min(timeout_ms / 1000, 3))  # Max 3 second wait for demo
        
        # Mock fill probability based on market conditions
        volatility = market_data.get('volatility', 0.01)
        fill_probability = min(0.8 + volatility * 10, 0.95)  # Higher vol = higher fill chance
        
        if np.random.random() < fill_probability:
            # Simulate maker fee advantage
            effective_price = price * (1 - 0.0001)  # 1bps maker rebate
            
            return {
                'order_id': order_id,
                'status': 'filled',
                'filled_quantity': float(quantity),
                'avg_fill_price': float(effective_price),
                'execution_style': 'post_only',
                'fees_bps': 1,  # Maker fees
                'execution_time_ms': int((time.time() - start_time) * 1000)
            }
        else:
            return {
                'order_id': order_id,
                'status': 'timeout',
                'reason': 'post_only_timeout'
            }
    
    async def _execute_ioc(self, order_id: str, symbol: str, side: str, 
                         quantity: Decimal, market_data: Dict) -> Dict[str, Any]:
        """Execute IOC (Immediate or Cancel) order"""
        
        start_time = time.time()
        
        # Use current best bid/ask with slight improvement
        if side == 'buy':
            exec_price = market_data['ask'] * (1 - 0.0001)  # Slight improvement
        else:
            exec_price = market_data['bid'] * (1 + 0.0001)
        
        # Simulate IOC execution
        # Fill ratio depends on order book depth
        available_liquidity = market_data.get('ask_size' if side == 'buy' else 'bid_size', float(quantity))
        fill_ratio = min(float(quantity) / available_liquidity, 1.0) if available_liquidity > 0 else 0.8
        
        filled_quantity = quantity * Decimal(str(fill_ratio))
        
        if filled_quantity > 0:
            # Add taker fees and slippage
            slippage_bps = np.random.uniform(5, 15)  # 0.5-1.5 bps slippage
            actual_price = exec_price * (1 + slippage_bps / 10000 * (1 if side == 'buy' else -1))
            
            return {
                'order_id': order_id,
                'status': 'filled' if fill_ratio > 0.99 else 'partial',
                'filled_quantity': float(filled_quantity),
                'avg_fill_price': float(actual_price),
                'fill_ratio': fill_ratio,
                'execution_style': 'ioc',
                'fees_bps': 10,  # Taker fees
                'slippage_bps': slippage_bps,
                'execution_time_ms': int((time.time() - start_time) * 1000)
            }
        else:
            return {
                'order_id': order_id,
                'status': 'failed',
                'error': 'No liquidity available'
            }
    
    async def _execute_market(self, order_id: str, symbol: str, side: str, 
                            quantity: Decimal, market_data: Dict) -> Dict[str, Any]:
        """Execute market order (immediate)"""
        
        start_time = time.time()
        
        # Market order hits multiple levels
        if side == 'buy':
            exec_price = market_data['ask'] * (1 + 0.0005)  # Market impact
        else:
            exec_price = market_data['bid'] * (1 - 0.0005)
        
        # Higher slippage for market orders
        slippage_bps = np.random.uniform(10, 30)
        actual_price = exec_price * (1 + slippage_bps / 10000 * (1 if side == 'buy' else -1))
        
        return {
            'order_id': order_id,
            'status': 'filled',
            'filled_quantity': float(quantity),
            'avg_fill_price': float(actual_price),
            'fill_ratio': 1.0,
            'execution_style': 'market',
            'fees_bps': 10,
            'slippage_bps': slippage_bps,
            'execution_time_ms': int((time.time() - start_time) * 1000)
        }
    
    async def _get_market_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get current market data with order book"""
        
        try:
            # Mock market data - in production would fetch from exchange
            base_prices = {
                'BTC/USDT': 67500,
                'ETH/USDT': 3450,
                'AAPL': 186,
                'MSFT': 422
            }
            
            base_price = base_prices.get(symbol, 100)
            spread_bps = np.random.uniform(2, 8)  # 0.2-0.8 bps spread
            
            spread = base_price * spread_bps / 10000
            mid_price = base_price
            bid = mid_price - spread/2
            ask = mid_price + spread/2
            
            # Mock order book depth
            bid_size = np.random.uniform(50000, 200000)
            ask_size = np.random.uniform(50000, 200000)
            
            # Mock volatility (for fill probability)
            volatility = np.random.uniform(0.01, 0.03)  # 1-3% daily
            
            market_data = {
                'symbol': symbol,
                'timestamp': datetime.now(),
                'mid_price': mid_price,
                'bid': bid,
                'ask': ask,
                'spread_bps': spread_bps,
                'bid_size': bid_size,
                'ask_size': ask_size,
                'volatility': volatility,
                'last_price': mid_price
            }
            
            # Update order book cache
            self.order_books[symbol] = market_data
            
            return market_data
            
        except Exception as e:
            logger.error(f"Failed to get market data for {symbol}: {e}")
            return None
    
    def _calculate_dynamic_offset(self, symbol: str, market_data: Dict) -> int:
        """Calculate dynamic price offset based on spread and volatility"""
        
        spread_bps = market_data.get('spread_bps', 5)
        volatility = market_data.get('volatility', 0.02)
        
        # Base offset from config
        base_offset = self.config['DYNAMIC_OFFSET_BPS']
        
        # Adjust based on spread (tighter spread = smaller offset)
        spread_factor = min(spread_bps / 5, 2.0)  # Normalize to 5bps baseline
        
        # Adjust based on volatility (higher vol = larger offset for protection)
        vol_factor = min(volatility * 100, 3.0)  # Scale volatility
        
        dynamic_offset = base_offset * spread_factor * vol_factor
        
        return int(np.clip(dynamic_offset, 1, 20))  # 1-20 bps range
    
    def _estimate_queue_depth(self, symbol: str, price: Decimal, side: str, market_data: Dict) -> float:
        """Estimate queue depth at price level"""
        
        if side == 'buy':
            best_bid = market_data['bid']
            if price <= best_bid:
                # At or better than best bid
                return market_data.get('bid_size', 100000)
            else:
                # Worse than best bid - assume less depth
                return market_data.get('bid_size', 100000) * 0.3
        else:  # sell
            best_ask = market_data['ask']
            if price >= best_ask:
                # At or better than best ask
                return market_data.get('ask_size', 100000)
            else:
                # Worse than best ask - assume less depth
                return market_data.get('ask_size', 100000) * 0.3
    
    def _is_price_spike(self, symbol: str, current_price: float) -> bool:
        """Detect price spikes using recent price history"""
        
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        
        # Add current price
        self.price_history[symbol].append((datetime.now(), current_price))
        
        # Keep only last 60 seconds
        cutoff_time = datetime.now() - timedelta(seconds=60)
        self.price_history[symbol] = [
            (ts, price) for ts, price in self.price_history[symbol] 
            if ts > cutoff_time
        ]
        
        if len(self.price_history[symbol]) < 5:
            return False
        
        # Calculate recent price statistics
        recent_prices = [price for _, price in self.price_history[symbol]]
        price_mean = np.mean(recent_prices)
        price_std = np.std(recent_prices)
        
        if price_std == 0:
            return False
        
        # Detect spike (> 3 standard deviations)
        z_score = abs(current_price - price_mean) / price_std
        
        return z_score > 3.0
    
    def _calculate_execution_metrics(self, symbol: str, side: str, quantity: Decimal,
                                   execution_result: Dict, market_data: Dict, 
                                   start_time: datetime) -> ExecutionMetrics:
        """Calculate execution quality metrics"""
        
        filled_qty = Decimal(str(execution_result['filled_quantity']))
        avg_fill_price = Decimal(str(execution_result['avg_fill_price']))
        
        # VWAP benchmark (use mid price as proxy)
        vwap_benchmark = Decimal(str(market_data['mid_price']))
        
        # Calculate slippage
        if side == 'buy':
            slippage = (avg_fill_price - vwap_benchmark) / vwap_benchmark * 10000
        else:
            slippage = (vwap_benchmark - avg_fill_price) / vwap_benchmark * 10000
        
        # Effective spread
        spread_bps = market_data.get('spread_bps', 5)
        effective_spread = execution_result.get('slippage_bps', slippage)
        
        # Queue slippage (difference from quoted price)
        if side == 'buy':
            quote_price = market_data['ask']
        else:
            quote_price = market_data['bid']
        
        queue_slip = abs(avg_fill_price - quote_price) / quote_price * 10000
        
        # Execution time
        execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
        
        return ExecutionMetrics(
            symbol=symbol,
            total_quantity=quantity,
            avg_fill_price=avg_fill_price,
            vwap_benchmark=vwap_benchmark,
            slippage_bps=float(slippage),
            fill_ratio=execution_result.get('fill_ratio', 1.0),
            effective_spread_bps=effective_spread,
            queue_slip_bps=queue_slip,
            execution_time_ms=execution_time,
            style=execution_result.get('execution_style', 'unknown')
        )
    
    def get_execution_report(self, lookback_hours: int = 24) -> Dict[str, Any]:
        """Get execution quality report"""
        
        cutoff_time = datetime.now() - timedelta(hours=lookback_hours)
        
        # Filter recent executions
        recent_metrics = [m for m in self.execution_metrics 
                         if m.execution_time_ms > 0]  # Simple filter for demo
        
        if not recent_metrics:
            return {
                'period_hours': lookback_hours,
                'total_executions': 0,
                'error': 'No recent executions'
            }
        
        # Calculate aggregate metrics
        slippages = [m.slippage_bps for m in recent_metrics]
        fill_ratios = [m.fill_ratio for m in recent_metrics]
        execution_times = [m.execution_time_ms for m in recent_metrics]
        
        # By style breakdown
        style_breakdown = {}
        for metric in recent_metrics:
            style = metric.style
            if style not in style_breakdown:
                style_breakdown[style] = {
                    'count': 0,
                    'avg_slippage': 0,
                    'avg_fill_ratio': 0,
                    'total_volume': 0
                }
            
            style_breakdown[style]['count'] += 1
            style_breakdown[style]['avg_slippage'] += metric.slippage_bps
            style_breakdown[style]['avg_fill_ratio'] += metric.fill_ratio
            style_breakdown[style]['total_volume'] += float(metric.total_quantity)
        
        # Average the metrics
        for style_data in style_breakdown.values():
            if style_data['count'] > 0:
                style_data['avg_slippage'] /= style_data['count']
                style_data['avg_fill_ratio'] /= style_data['count']
        
        return {
            'period_hours': lookback_hours,
            'total_executions': len(recent_metrics),
            'avg_slippage_bps': np.mean(slippages),
            'p95_slippage_bps': np.percentile(slippages, 95),
            'avg_fill_ratio': np.mean(fill_ratios),
            'min_fill_ratio': np.min(fill_ratios),
            'avg_execution_time_ms': np.mean(execution_times),
            'p95_execution_time_ms': np.percentile(execution_times, 95),
            'style_breakdown': style_breakdown,
            'gate_status': {
                'slippage_p95_ok': np.percentile(slippages, 95) <= 50,
                'fill_ratio_ok': np.mean(fill_ratios) >= 0.95,
                'execution_time_ok': np.mean(execution_times) <= 2000
            }
        }