"""
Slippage & Price Health Gates with Order Book Simulation
"""

import os
import json
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal, ROUND_DOWN
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import numpy as np
from collections import deque

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class OrderBookLevel:
    """Order book price level"""
    price: Decimal
    quantity: Decimal
    orders: int
    timestamp: datetime


@dataclass
class SlippageEstimate:
    """Slippage estimation result"""
    symbol: str
    side: str
    quantity: Decimal
    avg_fill_price: Decimal
    best_price: Decimal
    slippage_bps: Decimal
    slippage_usd: Decimal
    market_impact_bps: Decimal
    confidence: float
    liquidity_score: float


class OrderBookSimulator:
    """Simulates order book for slippage calculation"""
    
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.bids: List[OrderBookLevel] = []
        self.asks: List[OrderBookLevel] = []
        self.last_update = None
        self.spread_history = deque(maxlen=100)
        self.liquidity_metrics = {}
        
    def update_order_book(self, bids: List[Tuple], asks: List[Tuple]):
        """Update order book with new data"""
        self.bids = [
            OrderBookLevel(
                price=Decimal(str(price)),
                quantity=Decimal(str(qty)),
                orders=orders if len(bid) > 2 else 1,
                timestamp=datetime.now()
            )
            for bid in bids
            for price, qty, *orders in [bid]
        ]
        
        self.asks = [
            OrderBookLevel(
                price=Decimal(str(price)),
                quantity=Decimal(str(qty)),
                orders=orders if len(ask) > 2 else 1,
                timestamp=datetime.now()
            )
            for ask in asks
            for price, qty, *orders in [ask]
        ]
        
        self.last_update = datetime.now()
        
        # Track spread
        if self.bids and self.asks:
            spread_bps = ((self.asks[0].price - self.bids[0].price) / self.bids[0].price) * 10000
            self.spread_history.append(float(spread_bps))
        
        # Calculate liquidity metrics
        self._calculate_liquidity_metrics()
    
    def _calculate_liquidity_metrics(self):
        """Calculate order book liquidity metrics"""
        if not self.bids or not self.asks:
            return
        
        mid_price = (self.bids[0].price + self.asks[0].price) / 2
        
        # Calculate depth at various levels
        depth_levels = [10, 25, 50, 100]  # basis points
        
        for level_bps in depth_levels:
            level_pct = Decimal(str(level_bps / 10000))
            
            bid_depth = Decimal("0")
            ask_depth = Decimal("0")
            
            bid_threshold = mid_price * (1 - level_pct)
            ask_threshold = mid_price * (1 + level_pct)
            
            for bid in self.bids:
                if bid.price >= bid_threshold:
                    bid_depth += bid.quantity * bid.price
            
            for ask in self.asks:
                if ask.price <= ask_threshold:
                    ask_depth += ask.quantity * ask.price
            
            self.liquidity_metrics[f'depth_{level_bps}bps'] = {
                'bid': float(bid_depth),
                'ask': float(ask_depth),
                'total': float(bid_depth + ask_depth)
            }
    
    def estimate_slippage(self, side: str, quantity: Decimal) -> SlippageEstimate:
        """Estimate slippage for an order"""
        if side == "buy":
            levels = self.asks
            best_price = self.asks[0].price if self.asks else Decimal("0")
        else:
            levels = self.bids
            best_price = self.bids[0].price if self.bids else Decimal("0")
        
        if not levels or best_price == 0:
            return SlippageEstimate(
                symbol=self.symbol,
                side=side,
                quantity=quantity,
                avg_fill_price=Decimal("0"),
                best_price=Decimal("0"),
                slippage_bps=Decimal("999999"),
                slippage_usd=Decimal("0"),
                market_impact_bps=Decimal("0"),
                confidence=0.0,
                liquidity_score=0.0
            )
        
        # Simulate order fill
        remaining = quantity
        total_cost = Decimal("0")
        levels_touched = 0
        
        for level in levels:
            if remaining <= 0:
                break
            
            fill_qty = min(remaining, level.quantity)
            total_cost += fill_qty * level.price
            remaining -= fill_qty
            levels_touched += 1
        
        # Calculate average fill price
        if quantity > remaining:
            avg_fill_price = total_cost / (quantity - remaining)
        else:
            # Not enough liquidity
            avg_fill_price = levels[-1].price if levels else best_price
        
        # Calculate slippage
        if side == "buy":
            slippage_bps = ((avg_fill_price - best_price) / best_price) * 10000
        else:
            slippage_bps = ((best_price - avg_fill_price) / best_price) * 10000
        
        slippage_usd = abs(avg_fill_price - best_price) * quantity
        
        # Calculate market impact
        pre_trade_mid = (self.bids[0].price + self.asks[0].price) / 2 if self.bids and self.asks else best_price
        post_trade_mid = self._estimate_post_trade_mid(side, quantity)
        market_impact_bps = abs((post_trade_mid - pre_trade_mid) / pre_trade_mid) * 10000
        
        # Calculate confidence score
        confidence = self._calculate_confidence(levels_touched, remaining)
        
        # Calculate liquidity score
        liquidity_score = self._calculate_liquidity_score()
        
        return SlippageEstimate(
            symbol=self.symbol,
            side=side,
            quantity=quantity,
            avg_fill_price=avg_fill_price,
            best_price=best_price,
            slippage_bps=slippage_bps,
            slippage_usd=slippage_usd,
            market_impact_bps=market_impact_bps,
            confidence=confidence,
            liquidity_score=liquidity_score
        )
    
    def _estimate_post_trade_mid(self, side: str, quantity: Decimal) -> Decimal:
        """Estimate mid price after trade execution"""
        # Simplified model - assumes linear impact
        impact_factor = Decimal("0.0001")  # 1 bps per unit
        
        if side == "buy":
            # Buying pushes price up
            return (self.bids[0].price + self.asks[0].price) / 2 * (1 + impact_factor * quantity)
        else:
            # Selling pushes price down
            return (self.bids[0].price + self.asks[0].price) / 2 * (1 - impact_factor * quantity)
    
    def _calculate_confidence(self, levels_touched: int, remaining: Decimal) -> float:
        """Calculate confidence score for slippage estimate"""
        if remaining > 0:
            # Not enough liquidity
            return 0.5
        
        if levels_touched == 1:
            # Filled at best price
            return 1.0
        elif levels_touched <= 3:
            return 0.9
        elif levels_touched <= 5:
            return 0.8
        else:
            return 0.7
    
    def _calculate_liquidity_score(self) -> float:
        """Calculate overall liquidity score (0-1)"""
        if not self.liquidity_metrics:
            return 0.0
        
        # Average spread
        avg_spread = np.mean(self.spread_history) if self.spread_history else 100
        spread_score = max(0, 1 - avg_spread / 100)  # Lower spread = higher score
        
        # Depth score
        depth_10bps = self.liquidity_metrics.get('depth_10bps', {}).get('total', 0)
        depth_score = min(1, depth_10bps / 1000000)  # Normalize to $1M
        
        # Combined score
        return (spread_score + depth_score) / 2


class PriceHealthGate:
    """Price health monitoring and gating"""
    
    def __init__(self):
        self.price_bands: Dict[str, Dict] = {}
        self.stale_thresholds = {
            'crypto': 60,    # 60 seconds for crypto
            'equity': 300,   # 5 minutes for equities
            'forex': 30      # 30 seconds for forex
        }
        self.price_history: Dict[str, deque] = {}
        self.anomaly_detectors: Dict[str, Any] = {}
        
    def set_price_band(self, symbol: str, lower_band: Decimal, upper_band: Decimal, asset_type: str = 'crypto'):
        """Set acceptable price band for symbol"""
        self.price_bands[symbol] = {
            'lower': lower_band,
            'upper': upper_band,
            'asset_type': asset_type,
            'updated': datetime.now()
        }
        
        if symbol not in self.price_history:
            self.price_history[symbol] = deque(maxlen=1000)
        
        logger.info(f"Price band set for {symbol}: {lower_band} - {upper_band}")
    
    def check_price_health(self, symbol: str, price: Decimal, timestamp: Optional[datetime] = None) -> Dict[str, Any]:
        """Check if price is healthy"""
        timestamp = timestamp or datetime.now()
        
        result = {
            'symbol': symbol,
            'price': str(price),
            'timestamp': timestamp.isoformat(),
            'healthy': True,
            'issues': [],
            'confidence': 1.0
        }
        
        # Check price band
        if symbol in self.price_bands:
            band = self.price_bands[symbol]
            
            if price < band['lower']:
                result['healthy'] = False
                result['issues'].append(f"Price below lower band ({band['lower']})")
                result['confidence'] *= 0.5
            elif price > band['upper']:
                result['healthy'] = False
                result['issues'].append(f"Price above upper band ({band['upper']})")
                result['confidence'] *= 0.5
        
        # Check staleness
        if symbol in self.price_history and self.price_history[symbol]:
            last_update = self.price_history[symbol][-1]['timestamp']
            age_seconds = (timestamp - last_update).total_seconds()
            
            asset_type = self.price_bands.get(symbol, {}).get('asset_type', 'crypto')
            stale_threshold = self.stale_thresholds.get(asset_type, 60)
            
            if age_seconds > stale_threshold:
                result['healthy'] = False
                result['issues'].append(f"Stale price data ({age_seconds:.0f}s old)")
                result['confidence'] *= 0.3
        
        # Check for anomalies
        anomaly = self._detect_anomaly(symbol, price)
        if anomaly['is_anomaly']:
            result['issues'].append(f"Price anomaly detected: {anomaly['reason']}")
            result['confidence'] *= anomaly['confidence']
            
            if anomaly['severity'] == 'high':
                result['healthy'] = False
        
        # Store price in history
        if symbol not in self.price_history:
            self.price_history[symbol] = deque(maxlen=1000)
        
        self.price_history[symbol].append({
            'price': price,
            'timestamp': timestamp
        })
        
        return result
    
    def _detect_anomaly(self, symbol: str, price: Decimal) -> Dict[str, Any]:
        """Detect price anomalies"""
        if symbol not in self.price_history or len(self.price_history[symbol]) < 10:
            return {'is_anomaly': False, 'confidence': 1.0}
        
        # Get recent prices
        recent_prices = [float(p['price']) for p in list(self.price_history[symbol])[-20:]]
        current_price = float(price)
        
        # Calculate statistics
        mean_price = np.mean(recent_prices)
        std_price = np.std(recent_prices)
        
        if std_price == 0:
            return {'is_anomaly': False, 'confidence': 1.0}
        
        # Z-score test
        z_score = abs((current_price - mean_price) / std_price)
        
        if z_score > 4:
            return {
                'is_anomaly': True,
                'reason': f"Extreme deviation (z-score: {z_score:.2f})",
                'severity': 'high',
                'confidence': 0.1
            }
        elif z_score > 3:
            return {
                'is_anomaly': True,
                'reason': f"High deviation (z-score: {z_score:.2f})",
                'severity': 'medium',
                'confidence': 0.5
            }
        elif z_score > 2:
            return {
                'is_anomaly': True,
                'reason': f"Moderate deviation (z-score: {z_score:.2f})",
                'severity': 'low',
                'confidence': 0.8
            }
        
        # Check for sudden jumps
        if len(recent_prices) > 1:
            last_price = recent_prices[-1]
            price_change_pct = abs((current_price - last_price) / last_price) * 100
            
            if price_change_pct > 10:
                return {
                    'is_anomaly': True,
                    'reason': f"Sudden price jump ({price_change_pct:.1f}%)",
                    'severity': 'high',
                    'confidence': 0.2
                }
            elif price_change_pct > 5:
                return {
                    'is_anomaly': True,
                    'reason': f"Large price movement ({price_change_pct:.1f}%)",
                    'severity': 'medium',
                    'confidence': 0.6
                }
        
        return {'is_anomaly': False, 'confidence': 1.0}
    
    def update_bands_dynamically(self, symbol: str):
        """Update price bands based on recent volatility"""
        if symbol not in self.price_history or len(self.price_history[symbol]) < 100:
            return
        
        prices = [float(p['price']) for p in list(self.price_history[symbol])[-100:]]
        
        # Calculate Bollinger Bands
        mean = np.mean(prices)
        std = np.std(prices)
        
        # 3 standard deviations
        lower_band = Decimal(str(mean - 3 * std))
        upper_band = Decimal(str(mean + 3 * std))
        
        # Update bands
        self.set_price_band(symbol, lower_band, upper_band)
        
        logger.info(f"Dynamic bands updated for {symbol}: {lower_band:.2f} - {upper_band:.2f}")


class SlippageController:
    """Main slippage and price health controller"""
    
    def __init__(self):
        self.order_books: Dict[str, OrderBookSimulator] = {}
        self.price_gate = PriceHealthGate()
        self.max_slippage_bps = Decimal("50")  # 50 bps default
        self.min_liquidity_score = 0.5
        
        # Metrics
        self.slippage_events = []
        self.gate_rejections = []
        
    def pre_trade_check(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
        current_price: Decimal
    ) -> Dict[str, Any]:
        """Perform pre-trade slippage and price health checks"""
        logger.info(f"Pre-trade check: {side} {quantity} {symbol} @ {current_price}")
        
        result = {
            'symbol': symbol,
            'side': side,
            'quantity': str(quantity),
            'current_price': str(current_price),
            'timestamp': datetime.now().isoformat(),
            'approved': True,
            'checks': {},
            'warnings': [],
            'rejections': []
        }
        
        # Price health check
        price_health = self.price_gate.check_price_health(symbol, current_price)
        result['checks']['price_health'] = price_health
        
        if not price_health['healthy']:
            result['approved'] = False
            result['rejections'].append(f"Price health check failed: {', '.join(price_health['issues'])}")
            self.gate_rejections.append({
                'timestamp': datetime.now(),
                'symbol': symbol,
                'reason': 'price_health',
                'details': price_health['issues']
            })
        
        # Slippage check
        if symbol in self.order_books:
            slippage = self.order_books[symbol].estimate_slippage(side, quantity)
            result['checks']['slippage'] = asdict(slippage)
            
            if slippage.slippage_bps > self.max_slippage_bps:
                result['approved'] = False
                result['rejections'].append(
                    f"Slippage too high: {slippage.slippage_bps:.0f}bps > {self.max_slippage_bps}bps"
                )
                self.gate_rejections.append({
                    'timestamp': datetime.now(),
                    'symbol': symbol,
                    'reason': 'slippage',
                    'slippage_bps': float(slippage.slippage_bps)
                })
            elif slippage.slippage_bps > self.max_slippage_bps / 2:
                result['warnings'].append(
                    f"High slippage warning: {slippage.slippage_bps:.0f}bps"
                )
            
            if slippage.liquidity_score < self.min_liquidity_score:
                result['warnings'].append(
                    f"Low liquidity: score {slippage.liquidity_score:.2f}"
                )
        else:
            result['warnings'].append("No order book data available for slippage check")
        
        # Log event
        if not result['approved']:
            logger.warning(f"Trade rejected: {result['rejections']}")
        elif result['warnings']:
            logger.warning(f"Trade warnings: {result['warnings']}")
        else:
            logger.info("Trade approved")
        
        return result
    
    def update_order_book(self, symbol: str, bids: List, asks: List):
        """Update order book for symbol"""
        if symbol not in self.order_books:
            self.order_books[symbol] = OrderBookSimulator(symbol)
        
        self.order_books[symbol].update_order_book(bids, asks)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get slippage controller metrics"""
        return {
            'total_rejections': len(self.gate_rejections),
            'recent_rejections': self.gate_rejections[-10:],
            'slippage_events': len(self.slippage_events),
            'monitored_symbols': list(self.order_books.keys()),
            'price_bands': {
                symbol: {
                    'lower': str(band['lower']),
                    'upper': str(band['upper'])
                }
                for symbol, band in self.price_gate.price_bands.items()
            }
        }