"""
Asset Universe Orchestrator with Tiering and Rate Limiting
"""

import os
import json
import logging
import asyncio
import time
from typing import Dict, List, Any, Set, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import numpy as np
import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class AssetMetrics:
    """Asset scoring metrics for tiering"""
    symbol: str
    price: float
    volume_24h: float
    volume_1h: float
    spread_bps: float
    momentum_score: float
    volatility_score: float
    liquidity_score: float
    news_score: float
    combined_score: float
    tier: str
    active: bool
    last_update: datetime


@dataclass
class RateLimitState:
    """Rate limiting state for exchange"""
    exchange: str
    requests_per_minute: int
    requests_per_second: int
    request_times: deque
    last_reset: datetime
    blocked_until: Optional[datetime]
    total_requests: int
    rejected_requests: int


class UniverseOrchestrator:
    """Orchestrate trading universe with tiering and rate limits"""
    
    def __init__(self):
        self.config = {
            'MAX_CONCURRENCY': int(os.getenv('MAX_CONCURRENCY', '48')),
            'SCAN_RATE_SEC': int(os.getenv('SCAN_RATE_SEC', '5')),
            'T1_ASSETS': int(os.getenv('T1_ASSETS', '50')),
            'T2_ASSETS': int(os.getenv('T2_ASSETS', '150')),
            'T2_ROTATION_INTERVAL_MIN': int(os.getenv('T2_ROTATION_INTERVAL_MIN', '30')),
            
            # Rate limits
            'BINANCE_RPM_LIMIT': int(os.getenv('BINANCE_RPM_LIMIT', '1200')),
            'BINANCE_RPS_LIMIT': int(os.getenv('BINANCE_RPS_LIMIT', '10')),
            'GLOBAL_RPS_LIMIT': int(os.getenv('GLOBAL_RPS_LIMIT', '20')),
            
            # Order budget
            'MAX_ORDERS_PER_MINUTE': int(os.getenv('MAX_ORDERS_PER_MINUTE', '60')),
            'MAX_ORDERS_PER_SYMBOL_PER_MINUTE': int(os.getenv('MAX_ORDERS_PER_SYMBOL_PER_MINUTE', '5')),
            
            # Venue health
            'VENUE_ERROR_THRESHOLD': int(os.getenv('VENUE_ERROR_THRESHOLD', '5')),
            'VENUE_HEALTH_CHECK_SEC': int(os.getenv('VENUE_HEALTH_CHECK_SEC', '60'))
        }
        
        # Load asset universes
        self.crypto_symbols = self._load_crypto_symbols()
        self.equity_symbols = self._load_equity_symbols()
        self.all_symbols = self.crypto_symbols + self.equity_symbols
        
        # Asset state
        self.asset_metrics: Dict[str, AssetMetrics] = {}
        self.active_symbols: Set[str] = set()
        self.tier1_symbols: Set[str] = set()
        self.tier2_symbols: Set[str] = set()
        
        # Rate limiting
        self.rate_limiters: Dict[str, RateLimitState] = {}
        self.global_request_times = deque()
        self.order_budget = defaultdict(int)  # Orders per minute per symbol
        self.order_budget_reset_time = datetime.now()
        
        # Venue health
        self.venue_health: Dict[str, Dict[str, Any]] = {}
        self.parked_symbols: Set[str] = set()
        
        # Control
        self.running = False
        self.tasks: List[asyncio.Task] = []
        
        # Initialize rate limiters
        self._initialize_rate_limiters()
    
    def _load_crypto_symbols(self) -> List[str]:
        """Load crypto symbol list"""
        try:
            with open('data/symbols_crypto.json', 'r') as f:
                data = json.load(f)
                return data['tier1'] + data['tier2']
        except FileNotFoundError:
            logger.warning("Crypto symbols file not found, using defaults")
            return ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'ADA/USDT', 'SOL/USDT']
    
    def _load_equity_symbols(self) -> List[str]:
        """Load equity symbol list"""
        try:
            with open('data/symbols_equity.json', 'r') as f:
                data = json.load(f)
                return data['tier1'] + data['tier2']
        except FileNotFoundError:
            logger.warning("Equity symbols file not found, using defaults")
            return ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA']
    
    def _initialize_rate_limiters(self):
        """Initialize rate limiting for exchanges"""
        exchanges = ['binance', 'coinbase', 'kraken']
        
        for exchange in exchanges:
            rpm_limit = self.config.get(f'{exchange.upper()}_RPM_LIMIT', 600)
            rps_limit = self.config.get(f'{exchange.upper()}_RPS_LIMIT', 5)
            
            self.rate_limiters[exchange] = RateLimitState(
                exchange=exchange,
                requests_per_minute=rpm_limit,
                requests_per_second=rps_limit,
                request_times=deque(),
                last_reset=datetime.now(),
                blocked_until=None,
                total_requests=0,
                rejected_requests=0
            )
    
    async def start_orchestration(self):
        """Start universe orchestration"""
        if self.running:
            return
        
        self.running = True
        logger.info(f"Starting universe orchestration for {len(self.all_symbols)} symbols")
        
        # Initialize tiers
        await self._initialize_tiers()
        
        # Start monitoring tasks
        self.tasks = [
            asyncio.create_task(self._asset_scoring_loop()),
            asyncio.create_task(self._tier2_rotation_loop()),
            asyncio.create_task(self._venue_health_monitor()),
            asyncio.create_task(self._rate_limit_cleanup())
        ]
        
        logger.info(f"Orchestration started: T1={len(self.tier1_symbols)}, T2={len(self.tier2_symbols)}")
    
    async def stop_orchestration(self):
        """Stop orchestration"""
        self.running = False
        
        for task in self.tasks:
            task.cancel()
        
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        
        self.tasks.clear()
        logger.info("Universe orchestration stopped")
    
    async def _initialize_tiers(self):
        """Initialize tier assignments"""
        
        # Load tier definitions from symbol files
        try:
            with open('data/symbols_crypto.json', 'r') as f:
                crypto_data = json.load(f)
                tier1_crypto = set(crypto_data['tier1'])
                
            with open('data/symbols_equity.json', 'r') as f:
                equity_data = json.load(f)
                tier1_equity = set(equity_data['tier1'])
                
            self.tier1_symbols = tier1_crypto | tier1_equity
            
            # Initial T2 selection (top volume/momentum)
            tier2_crypto = set(crypto_data['tier2'][:self.config['T2_ASSETS']//2])
            tier2_equity = set(equity_data['tier2'][:self.config['T2_ASSETS']//2])
            
            self.tier2_symbols = tier2_crypto | tier2_equity
            self.active_symbols = self.tier1_symbols | self.tier2_symbols
            
        except Exception as e:
            logger.error(f"Failed to initialize tiers: {e}")
            # Fallback to first N symbols
            self.tier1_symbols = set(self.all_symbols[:self.config['T1_ASSETS']])
            self.tier2_symbols = set(self.all_symbols[self.config['T1_ASSETS']:self.config['T1_ASSETS']+self.config['T2_ASSETS']])
            self.active_symbols = self.tier1_symbols | self.tier2_symbols
    
    async def _asset_scoring_loop(self):
        """Continuously score assets for tier assignment"""
        
        while self.running:
            try:
                logger.info("Running asset scoring...")
                
                # Score all symbols (with rate limiting)
                await self._score_all_assets()
                
                await asyncio.sleep(self.config['SCAN_RATE_SEC'] * 60)  # Every 5 minutes
                
            except Exception as e:
                logger.error(f"Asset scoring error: {e}")
                await asyncio.sleep(300)
    
    async def _score_all_assets(self):
        """Score all assets for ranking"""
        
        # Process in batches to respect rate limits
        batch_size = self.config['MAX_CONCURRENCY']
        
        for i in range(0, len(self.all_symbols), batch_size):
            batch = self.all_symbols[i:i+batch_size]
            
            # Check global rate limit
            if not await self._check_global_rate_limit():
                logger.warning("Global rate limit hit, delaying batch")
                await asyncio.sleep(1)
            
            # Process batch concurrently
            tasks = [self._score_asset(symbol) for symbol in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for symbol, result in zip(batch, results):
                if isinstance(result, AssetMetrics):
                    self.asset_metrics[symbol] = result
                elif isinstance(result, Exception):
                    logger.error(f"Failed to score {symbol}: {result}")
            
            # Small delay between batches
            await asyncio.sleep(0.5)
    
    async def _score_asset(self, symbol: str) -> Optional[AssetMetrics]:
        """Score individual asset"""
        
        try:
            # Get market data (mock for now)
            market_data = await self._get_market_data(symbol)
            if not market_data:
                return None
            
            # Calculate component scores
            momentum_score = self._calculate_momentum_score(symbol, market_data)
            volatility_score = self._calculate_volatility_score(symbol, market_data)
            liquidity_score = self._calculate_liquidity_score(symbol, market_data)
            news_score = await self._get_news_score(symbol)
            
            # Combined score (weighted)
            combined_score = (
                momentum_score * 0.3 +
                volatility_score * 0.25 +
                liquidity_score * 0.3 +
                news_score * 0.15
            )
            
            # Determine tier
            current_tier = 'T1' if symbol in self.tier1_symbols else 'T2' if symbol in self.tier2_symbols else 'inactive'
            
            return AssetMetrics(
                symbol=symbol,
                price=market_data['price'],
                volume_24h=market_data['volume_24h'],
                volume_1h=market_data.get('volume_1h', 0),
                spread_bps=market_data['spread_bps'],
                momentum_score=momentum_score,
                volatility_score=volatility_score,
                liquidity_score=liquidity_score,
                news_score=news_score,
                combined_score=combined_score,
                tier=current_tier,
                active=symbol in self.active_symbols,
                last_update=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Failed to score asset {symbol}: {e}")
            return None
    
    async def _get_market_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get market data for symbol"""
        
        # Mock market data - in production would fetch from CCXT
        try:
            # Base prices for different asset types
            if 'BTC' in symbol:
                base_price = 67500
            elif 'ETH' in symbol:
                base_price = 3450
            elif symbol == 'AAPL':
                base_price = 186
            elif symbol == 'MSFT':
                base_price = 422
            else:
                # Random price based on symbol hash
                np.random.seed(hash(symbol) % 2**32)
                base_price = np.random.uniform(10, 1000)
            
            # Add realistic variation
            price_variation = np.random.uniform(-0.02, 0.02)  # ±2%
            current_price = base_price * (1 + price_variation)
            
            # Volume based on tier (T1 symbols have higher volume)
            if symbol in self.tier1_symbols:
                volume_24h = np.random.uniform(50000000, 200000000)  # $50M-200M
            else:
                volume_24h = np.random.uniform(5000000, 50000000)   # $5M-50M
            
            # Spread based on liquidity
            if volume_24h > 100000000:
                spread_bps = np.random.uniform(1, 5)  # Tight spread
            else:
                spread_bps = np.random.uniform(5, 20)  # Wider spread
            
            return {
                'symbol': symbol,
                'price': current_price,
                'volume_24h': volume_24h,
                'volume_1h': volume_24h / 24,
                'spread_bps': spread_bps,
                'timestamp': datetime.now()
            }
            
        except Exception as e:
            logger.error(f"Failed to get market data for {symbol}: {e}")
            return None
    
    def _calculate_momentum_score(self, symbol: str, market_data: Dict) -> float:
        """Calculate momentum score (0-1)"""
        
        # Mock momentum calculation
        # In production would use price returns over multiple timeframes
        price = market_data['price']
        
        # Simulate momentum based on price patterns
        np.random.seed(int(time.time()) + hash(symbol) % 1000)
        
        # Higher volume symbols tend to have better momentum signals
        volume = market_data['volume_24h']
        base_momentum = np.random.uniform(0.3, 0.8)
        
        # Volume boost
        if volume > 100000000:
            base_momentum += 0.1
        elif volume < 10000000:
            base_momentum -= 0.1
        
        return np.clip(base_momentum, 0, 1)
    
    def _calculate_volatility_score(self, symbol: str, market_data: Dict) -> float:
        """Calculate volatility score for trading opportunity"""
        
        # Mock volatility - in production would use ATR or realized vol
        spread_bps = market_data['spread_bps']
        
        # Moderate volatility is preferred (not too low, not too high)
        if 'USDT' in symbol:  # Crypto
            optimal_vol = 0.03  # 3% daily
            current_vol = spread_bps / 100 + np.random.uniform(0.01, 0.05)
        else:  # Equity
            optimal_vol = 0.02  # 2% daily
            current_vol = spread_bps / 200 + np.random.uniform(0.005, 0.03)
        
        # Score based on distance from optimal
        vol_distance = abs(current_vol - optimal_vol) / optimal_vol
        vol_score = max(0, 1 - vol_distance)
        
        return vol_score
    
    def _calculate_liquidity_score(self, symbol: str, market_data: Dict) -> float:
        """Calculate liquidity score"""
        
        volume = market_data['volume_24h']
        spread_bps = market_data['spread_bps']
        
        # Volume component (log scale)
        volume_score = min(np.log10(volume / 1000000) / 3, 1.0)  # $1M baseline
        
        # Spread component (inverse)
        spread_score = max(0, 1 - spread_bps / 50)  # 50bps baseline
        
        # Combined liquidity score
        liquidity_score = (volume_score * 0.7 + spread_score * 0.3)
        
        return np.clip(liquidity_score, 0, 1)
    
    async def _get_news_score(self, symbol: str) -> float:
        """Get news sentiment score for symbol"""
        
        try:
            # Would integrate with news sentiment analyzer
            # For now, return mock score
            np.random.seed(hash(symbol + str(datetime.now().hour)) % 2**32)
            
            # Some symbols have more news coverage
            if symbol in ['BTC/USDT', 'ETH/USDT', 'AAPL', 'MSFT', 'TSLA']:
                news_activity = np.random.uniform(0.4, 0.9)
            else:
                news_activity = np.random.uniform(0.0, 0.4)
            
            return news_activity
            
        except Exception as e:
            logger.error(f"Failed to get news score for {symbol}: {e}")
            return 0.0
    
    async def _tier2_rotation_loop(self):
        """Rotate T2 assets based on scores"""
        
        while self.running:
            try:
                logger.info("Running T2 rotation...")
                
                # Get all non-T1 symbols with scores
                candidates = []
                for symbol, metrics in self.asset_metrics.items():
                    if symbol not in self.tier1_symbols and symbol not in self.parked_symbols:
                        candidates.append((symbol, metrics.combined_score))
                
                # Sort by score
                candidates.sort(key=lambda x: x[1], reverse=True)
                
                # Select top T2_ASSETS for rotation
                new_tier2 = set([symbol for symbol, score in candidates[:self.config['T2_ASSETS']]])
                
                # Calculate rotation changes
                removed = self.tier2_symbols - new_tier2
                added = new_tier2 - self.tier2_symbols
                
                if removed or added:
                    logger.info(f"T2 rotation: -{len(removed)}, +{len(added)}")
                    
                    self.tier2_symbols = new_tier2
                    self.active_symbols = self.tier1_symbols | self.tier2_symbols
                    
                    # Log significant changes
                    if removed:
                        logger.info(f"Removed from T2: {list(removed)[:5]}...")
                    if added:
                        logger.info(f"Added to T2: {list(added)[:5]}...")
                
                await asyncio.sleep(self.config['T2_ROTATION_INTERVAL_MIN'] * 60)
                
            except Exception as e:
                logger.error(f"T2 rotation error: {e}")
                await asyncio.sleep(1800)
    
    async def _venue_health_monitor(self):
        """Monitor venue health and park unhealthy symbols"""
        
        while self.running:
            try:
                for exchange, rate_limiter in self.rate_limiters.items():
                    error_rate = rate_limiter.rejected_requests / max(rate_limiter.total_requests, 1)
                    
                    # Update venue health
                    self.venue_health[exchange] = {
                        'error_rate': error_rate,
                        'total_requests': rate_limiter.total_requests,
                        'rejected_requests': rate_limiter.rejected_requests,
                        'healthy': error_rate < 0.05,  # 5% error threshold
                        'last_check': datetime.now()
                    }
                    
                    # Park symbols if venue unhealthy
                    if error_rate > 0.1:  # 10% error rate
                        logger.warning(f"Venue {exchange} unhealthy (error rate {error_rate:.1%})")
                        
                        # Park symbols trading on this venue
                        venue_symbols = [s for s in self.active_symbols 
                                       if self._get_symbol_venue(s) == exchange]
                        
                        for symbol in venue_symbols[:10]:  # Park up to 10 symbols
                            self.parked_symbols.add(symbol)
                            logger.warning(f"Parked symbol {symbol} due to venue health")
                
                await asyncio.sleep(self.config['VENUE_HEALTH_CHECK_SEC'])
                
            except Exception as e:
                logger.error(f"Venue health monitor error: {e}")
                await asyncio.sleep(300)
    
    async def _rate_limit_cleanup(self):
        """Cleanup old rate limit data"""
        
        while self.running:
            try:
                now = datetime.now()
                cutoff_time = now - timedelta(minutes=1)
                
                # Cleanup global rate limit
                while self.global_request_times and self.global_request_times[0] < cutoff_time:
                    self.global_request_times.popleft()
                
                # Cleanup per-exchange rate limits
                for rate_limiter in self.rate_limiters.values():
                    while rate_limiter.request_times and rate_limiter.request_times[0] < cutoff_time:
                        rate_limiter.request_times.popleft()
                
                # Reset order budget
                if now - self.order_budget_reset_time > timedelta(minutes=1):
                    self.order_budget.clear()
                    self.order_budget_reset_time = now
                
                await asyncio.sleep(10)  # Cleanup every 10 seconds
                
            except Exception as e:
                logger.error(f"Rate limit cleanup error: {e}")
                await asyncio.sleep(60)
    
    async def _check_global_rate_limit(self) -> bool:
        """Check global rate limit"""
        
        now = datetime.now()
        cutoff_time = now - timedelta(seconds=1)
        
        # Remove old requests
        while self.global_request_times and self.global_request_times[0] < cutoff_time:
            self.global_request_times.popleft()
        
        # Check if under limit
        return len(self.global_request_times) < self.config['GLOBAL_RPS_LIMIT']
    
    async def check_exchange_rate_limit(self, exchange: str) -> bool:
        """Check exchange-specific rate limit"""
        
        if exchange not in self.rate_limiters:
            return True
        
        rate_limiter = self.rate_limiters[exchange]
        now = datetime.now()
        
        # Check if blocked
        if rate_limiter.blocked_until and now < rate_limiter.blocked_until:
            return False
        
        # Check RPS limit
        cutoff_time = now - timedelta(seconds=1)
        while rate_limiter.request_times and rate_limiter.request_times[0] < cutoff_time:
            rate_limiter.request_times.popleft()
        
        if len(rate_limiter.request_times) >= rate_limiter.requests_per_second:
            return False
        
        return True
    
    async def record_request(self, exchange: str, success: bool = True):
        """Record API request for rate limiting"""
        
        now = datetime.now()
        
        # Record global
        self.global_request_times.append(now)
        
        # Record exchange-specific
        if exchange in self.rate_limiters:
            rate_limiter = self.rate_limiters[exchange]
            rate_limiter.request_times.append(now)
            rate_limiter.total_requests += 1
            
            if not success:
                rate_limiter.rejected_requests += 1
                
                # Block exchange if too many errors
                if rate_limiter.rejected_requests > self.config['VENUE_ERROR_THRESHOLD']:
                    rate_limiter.blocked_until = now + timedelta(minutes=5)
                    logger.warning(f"Blocking {exchange} for 5 minutes due to errors")
    
    async def check_order_budget(self, symbol: str) -> bool:
        """Check order budget for symbol"""
        
        current_orders = self.order_budget[symbol]
        return current_orders < self.config['MAX_ORDERS_PER_SYMBOL_PER_MINUTE']
    
    async def record_order(self, symbol: str):
        """Record order for budget tracking"""
        self.order_budget[symbol] += 1
    
    def _get_symbol_venue(self, symbol: str) -> str:
        """Get primary venue for symbol"""
        
        if '/USDT' in symbol:
            return 'binance'
        elif '.' in symbol:  # Equity
            return 'alpaca'  # Mock
        else:
            return 'binance'  # Default
    
    def get_active_universe(self) -> Dict[str, Any]:
        """Get current active trading universe"""
        
        # Separate by tier
        tier1_metrics = {s: self.asset_metrics[s] for s in self.tier1_symbols if s in self.asset_metrics}
        tier2_metrics = {s: self.asset_metrics[s] for s in self.tier2_symbols if s in self.asset_metrics}
        
        # Calculate universe statistics
        total_volume = sum(m.volume_24h for m in self.asset_metrics.values())
        avg_score = np.mean([m.combined_score for m in self.asset_metrics.values()]) if self.asset_metrics else 0
        
        return {
            'tier1': {
                'symbols': list(self.tier1_symbols),
                'count': len(self.tier1_symbols),
                'metrics': {k: asdict(v) for k, v in tier1_metrics.items()}
            },
            'tier2': {
                'symbols': list(self.tier2_symbols),
                'count': len(self.tier2_symbols),
                'metrics': {k: asdict(v) for k, v in tier2_metrics.items()}
            },
            'universe_stats': {
                'total_symbols': len(self.all_symbols),
                'active_symbols': len(self.active_symbols),
                'parked_symbols': len(self.parked_symbols),
                'total_volume_24h': total_volume,
                'avg_combined_score': avg_score,
                'last_update': datetime.now().isoformat()
            },
            'rate_limits': {
                exchange: {
                    'total_requests': rl.total_requests,
                    'rejected_requests': rl.rejected_requests,
                    'error_rate': rl.rejected_requests / max(rl.total_requests, 1),
                    'blocked': rl.blocked_until.isoformat() if rl.blocked_until else None
                }
                for exchange, rl in self.rate_limiters.items()
            }
        }