"""
Feature extraction system for AI models
Extracts technical features: r_1m, r_5m, r_1h, zscore_20, ATR%, RV, mom_14, vol_σ_1h
"""

import asyncio
import logging
import os
import time
import numpy as np
import pandas as pd
from dataclasses import dataclass, asdict
from typing import Dict, Optional, Any, List, Tuple
from collections import deque, defaultdict
import redis.asyncio as redis
from prometheus_client import Counter, Histogram, Gauge
import talib
from scipy import stats
import json

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Prometheus metrics
FEATURES_COMPUTED = Counter('ai_features_computed_total', 'Features computed', ['symbol', 'feature_type'])
FEATURE_COMPUTATION_TIME = Histogram('ai_feature_computation_seconds', 'Feature computation time', ['feature_type'])
FEATURE_CACHE_HITS = Counter('ai_feature_cache_hits_total', 'Feature cache hits', ['symbol'])
FEATURE_BUFFER_SIZE = Gauge('ai_feature_buffer_size', 'Feature buffer size', ['symbol'])
FEATURE_ERRORS = Counter('ai_feature_errors_total', 'Feature computation errors', ['symbol', 'error_type'])


@dataclass
class OHLCV:
    """OHLCV bar structure"""
    timestamp: float
    open: float
    high: float
    low: float
    close: float
    volume: float
    vwap: Optional[float] = None
    
    def to_array(self) -> np.ndarray:
        """Convert to numpy array for calculations"""
        return np.array([self.open, self.high, self.low, self.close, self.volume])


@dataclass
class FeatureVector:
    """Complete feature vector for a timestamp"""
    timestamp: float
    symbol: str
    
    # Price returns
    r_1m: Optional[float] = None      # 1-minute return
    r_5m: Optional[float] = None      # 5-minute return  
    r_1h: Optional[float] = None      # 1-hour return
    
    # Statistical features
    zscore_20: Optional[float] = None  # 20-period price Z-score
    
    # Volatility features
    atr_pct: Optional[float] = None    # Average True Range as percentage
    rv_1h: Optional[float] = None      # Realized volatility 1-hour
    vol_sigma_1h: Optional[float] = None  # Volume-weighted volatility
    
    # Momentum features
    mom_14: Optional[float] = None     # 14-period momentum
    rsi_14: Optional[float] = None     # 14-period RSI
    
    # Volume features
    vol_sma_20: Optional[float] = None # 20-period volume SMA
    vol_ratio: Optional[float] = None  # Current volume / SMA ratio
    
    # Price level features
    sma_20: Optional[float] = None     # 20-period Simple Moving Average
    ema_12: Optional[float] = None     # 12-period Exponential Moving Average
    bb_upper: Optional[float] = None   # Bollinger Band upper
    bb_lower: Optional[float] = None   # Bollinger Band lower
    bb_position: Optional[float] = None # Position within Bollinger Bands
    
    # Microstructure features
    bid_ask_spread: Optional[float] = None  # Bid-ask spread
    order_flow_imbalance: Optional[float] = None  # Order flow imbalance
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)
    
    def get_feature_names(self) -> List[str]:
        """Get list of feature names"""
        return [field for field in asdict(self).keys() if field not in ['timestamp', 'symbol']]
    
    def get_feature_values(self) -> List[float]:
        """Get feature values as list (excluding timestamp and symbol)"""
        data = asdict(self)
        return [data[field] for field in self.get_feature_names() if data[field] is not None]


class TechnicalIndicators:
    """Technical indicator calculations"""
    
    @staticmethod
    def calculate_returns(prices: np.ndarray, periods: List[int]) -> Dict[str, np.ndarray]:
        """Calculate returns for multiple periods"""
        returns = {}
        for period in periods:
            if len(prices) > period:
                returns[f'r_{period}'] = np.log(prices[period:] / prices[:-period])
            else:
                returns[f'r_{period}'] = np.array([])
        return returns
    
    @staticmethod
    def calculate_zscore(prices: np.ndarray, window: int = 20) -> np.ndarray:
        """Calculate rolling Z-score"""
        if len(prices) < window:
            return np.array([])
        
        zscores = np.full(len(prices), np.nan)
        for i in range(window - 1, len(prices)):
            window_data = prices[i - window + 1:i + 1]
            mean = np.mean(window_data)
            std = np.std(window_data, ddof=1)
            if std > 0:
                zscores[i] = (prices[i] - mean) / std
        
        return zscores
    
    @staticmethod
    def calculate_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
        """Calculate Average True Range"""
        if len(high) < period + 1:
            return np.array([])
        
        tr = talib.TRANGE(high, low, close)
        atr = talib.SMA(tr, timeperiod=period)
        return atr
    
    @staticmethod
    def calculate_realized_volatility(returns: np.ndarray, window: int) -> np.ndarray:
        """Calculate realized volatility"""
        if len(returns) < window:
            return np.array([])
        
        rv = np.full(len(returns), np.nan)
        for i in range(window - 1, len(returns)):
            window_returns = returns[i - window + 1:i + 1]
            rv[i] = np.sqrt(np.sum(window_returns ** 2))
        
        return rv
    
    @staticmethod
    def calculate_volume_weighted_volatility(returns: np.ndarray, volumes: np.ndarray, window: int) -> np.ndarray:
        """Calculate volume-weighted volatility"""
        if len(returns) < window or len(volumes) < window:
            return np.array([])
        
        vwv = np.full(len(returns), np.nan)
        for i in range(window - 1, len(returns)):
            window_returns = returns[i - window + 1:i + 1]
            window_volumes = volumes[i - window + 1:i + 1]
            
            if np.sum(window_volumes) > 0:
                weights = window_volumes / np.sum(window_volumes)
                weighted_mean = np.sum(weights * window_returns)
                weighted_var = np.sum(weights * (window_returns - weighted_mean) ** 2)
                vwv[i] = np.sqrt(weighted_var)
        
        return vwv
    
    @staticmethod
    def calculate_bollinger_bands(prices: np.ndarray, period: int = 20, std_dev: float = 2.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Calculate Bollinger Bands"""
        if len(prices) < period:
            empty = np.array([])
            return empty, empty, empty
        
        sma = talib.SMA(prices, timeperiod=period)
        std = talib.STDDEV(prices, timeperiod=period, nbdev=1)
        
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        
        return upper, lower, sma
    
    @staticmethod
    def calculate_order_flow_imbalance(bid_volumes: np.ndarray, ask_volumes: np.ndarray) -> np.ndarray:
        """Calculate order flow imbalance"""
        total_volume = bid_volumes + ask_volumes
        imbalance = np.where(total_volume > 0, (bid_volumes - ask_volumes) / total_volume, 0)
        return imbalance


class FeatureBuffer:
    """Buffer for OHLCV data and feature calculations"""
    
    def __init__(self, symbol: str, max_size: int = 1440):  # 24 hours of 1-minute bars
        self.symbol = symbol
        self.max_size = max_size
        self.ohlcv_buffer = deque(maxlen=max_size)
        self.feature_cache = {}
        self.last_feature_timestamp = 0
        
        # Technical indicators instance
        self.indicators = TechnicalIndicators()
    
    def add_ohlcv(self, bar: OHLCV):
        """Add OHLCV bar to buffer"""
        self.ohlcv_buffer.append(bar)
        
        # Update metrics
        FEATURE_BUFFER_SIZE.labels(symbol=self.symbol).set(len(self.ohlcv_buffer))
        
        # Clear cache if new data is significantly newer
        if bar.timestamp > self.last_feature_timestamp + 300:  # 5 minutes
            self.feature_cache.clear()
    
    def get_price_arrays(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Get price arrays for calculations"""
        if not self.ohlcv_buffer:
            empty = np.array([])
            return empty, empty, empty, empty, empty, empty
        
        timestamps = np.array([bar.timestamp for bar in self.ohlcv_buffer])
        opens = np.array([bar.open for bar in self.ohlcv_buffer])
        highs = np.array([bar.high for bar in self.ohlcv_buffer])
        lows = np.array([bar.low for bar in self.ohlcv_buffer])
        closes = np.array([bar.close for bar in self.ohlcv_buffer])
        volumes = np.array([bar.volume for bar in self.ohlcv_buffer])
        
        return timestamps, opens, highs, lows, closes, volumes
    
    def compute_features(self, timestamp: float) -> Optional[FeatureVector]:
        """Compute feature vector for given timestamp"""
        if not self.ohlcv_buffer:
            return None
        
        # Check cache first
        cache_key = f"{timestamp:.0f}"
        if cache_key in self.feature_cache:
            FEATURE_CACHE_HITS.labels(symbol=self.symbol).inc()
            return self.feature_cache[cache_key]
        
        try:
            start_time = time.time()
            
            # Get price arrays
            timestamps, opens, highs, lows, closes, volumes = self.get_price_arrays()
            
            if len(closes) < 20:  # Need minimum data for features
                return None
            
            # Find the index for the requested timestamp
            idx = -1  # Default to latest
            for i, ts in enumerate(timestamps):
                if abs(ts - timestamp) < 30:  # Within 30 seconds
                    idx = i
                    break
            
            if idx == -1:
                idx = len(timestamps) - 1
            
            # Initialize feature vector
            features = FeatureVector(timestamp=timestamp, symbol=self.symbol)
            
            # Calculate returns
            if idx >= 1:
                features.r_1m = np.log(closes[idx] / closes[idx - 1]) if closes[idx - 1] > 0 else 0
            
            if idx >= 5:
                features.r_5m = np.log(closes[idx] / closes[idx - 5]) if closes[idx - 5] > 0 else 0
            
            if idx >= 60:
                features.r_1h = np.log(closes[idx] / closes[idx - 60]) if closes[idx - 60] > 0 else 0
            
            # Z-score (20-period)
            if idx >= 19:
                window_closes = closes[max(0, idx - 19):idx + 1]
                if len(window_closes) >= 20:
                    mean_price = np.mean(window_closes)
                    std_price = np.std(window_closes, ddof=1)
                    if std_price > 0:
                        features.zscore_20 = (closes[idx] - mean_price) / std_price
            
            # ATR percentage
            if idx >= 14:
                atr_values = self.indicators.calculate_atr(
                    highs[:idx + 1], lows[:idx + 1], closes[:idx + 1], period=14
                )
                if len(atr_values) > 0 and not np.isnan(atr_values[-1]) and closes[idx] > 0:
                    features.atr_pct = atr_values[-1] / closes[idx] * 100
            
            # Realized volatility (1-hour window)
            if idx >= 60:
                returns_1m = np.diff(np.log(closes[max(0, idx - 60):idx + 1]))
                if len(returns_1m) >= 60:
                    features.rv_1h = np.sqrt(np.sum(returns_1m ** 2) * 525600)  # Annualized
            
            # Volume-weighted volatility
            if idx >= 60:
                returns_1m = np.diff(np.log(closes[max(0, idx - 59):idx + 1]))
                vol_window = volumes[max(0, idx - 59):idx + 1]
                if len(returns_1m) >= 59 and len(vol_window) >= 60:
                    vwv = self.indicators.calculate_volume_weighted_volatility(
                        returns_1m, vol_window[1:], window=59
                    )
                    if len(vwv) > 0 and not np.isnan(vwv[-1]):
                        features.vol_sigma_1h = vwv[-1] * np.sqrt(525600)  # Annualized
            
            # Momentum (14-period)
            if idx >= 14:
                features.mom_14 = closes[idx] / closes[idx - 14] - 1 if closes[idx - 14] > 0 else 0
            
            # RSI (14-period)
            if idx >= 14:
                rsi_values = talib.RSI(closes[:idx + 1], timeperiod=14)
                if len(rsi_values) > 0 and not np.isnan(rsi_values[-1]):
                    features.rsi_14 = rsi_values[-1]
            
            # Volume features
            if idx >= 19:
                vol_sma = talib.SMA(volumes[:idx + 1], timeperiod=20)
                if len(vol_sma) > 0 and not np.isnan(vol_sma[-1]):
                    features.vol_sma_20 = vol_sma[-1]
                    if vol_sma[-1] > 0:
                        features.vol_ratio = volumes[idx] / vol_sma[-1]
            
            # Moving averages
            if idx >= 19:
                sma_values = talib.SMA(closes[:idx + 1], timeperiod=20)
                if len(sma_values) > 0 and not np.isnan(sma_values[-1]):
                    features.sma_20 = sma_values[-1]
            
            if idx >= 11:
                ema_values = talib.EMA(closes[:idx + 1], timeperiod=12)
                if len(ema_values) > 0 and not np.isnan(ema_values[-1]):
                    features.ema_12 = ema_values[-1]
            
            # Bollinger Bands
            if idx >= 19:
                bb_upper, bb_lower, bb_middle = self.indicators.calculate_bollinger_bands(
                    closes[:idx + 1], period=20, std_dev=2.0
                )
                if (len(bb_upper) > 0 and not np.isnan(bb_upper[-1]) and 
                    len(bb_lower) > 0 and not np.isnan(bb_lower[-1])):
                    features.bb_upper = bb_upper[-1]
                    features.bb_lower = bb_lower[-1]
                    
                    # Position within bands
                    bb_range = bb_upper[-1] - bb_lower[-1]
                    if bb_range > 0:
                        features.bb_position = (closes[idx] - bb_lower[-1]) / bb_range
            
            # Cache the result
            self.feature_cache[cache_key] = features
            self.last_feature_timestamp = timestamp
            
            # Limit cache size
            if len(self.feature_cache) > 100:
                # Remove oldest entries
                old_keys = sorted(self.feature_cache.keys())[:50]
                for key in old_keys:
                    del self.feature_cache[key]
            
            # Record metrics
            computation_time = time.time() - start_time
            FEATURE_COMPUTATION_TIME.labels(feature_type='full').observe(computation_time)
            FEATURES_COMPUTED.labels(symbol=self.symbol, feature_type='full').inc()
            
            return features
            
        except Exception as e:
            logger.error(f"Feature computation error for {self.symbol}: {e}")
            FEATURE_ERRORS.labels(symbol=self.symbol, error_type=type(e).__name__).inc()
            return None


class FeatureEngine:
    """Main feature extraction engine"""
    
    def __init__(self):
        self.redis_client = None
        self.buffers = {}  # {symbol: FeatureBuffer}
        self.running = False
        
        # Configuration
        self.symbols = self._get_symbols()
        self.buffer_size = int(os.getenv('FEATURE_BUFFER_SIZE', '1440'))
        self.feature_interval = int(os.getenv('FEATURE_COMPUTATION_INTERVAL', '60'))  # seconds
        self.consumer_group = os.getenv('FEATURE_CONSUMER_GROUP', 'featurizers')
        self.consumer_name = os.getenv('FEATURE_CONSUMER_NAME', f'featurizer_{os.getpid()}')
        
        # Initialize buffers
        for symbol in self.symbols:
            self.buffers[symbol] = FeatureBuffer(symbol, self.buffer_size)
    
    def _get_symbols(self) -> List[str]:
        """Get symbols from environment"""
        symbols_env = os.getenv('AI_SYMBOLS', 'BTCUSDT,ETHUSDT,SOLUSDT,ADAUSDT')
        return [s.strip() for s in symbols_env.split(',')]
    
    async def start(self):
        """Start feature extraction engine"""
        # Connect to Redis
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        self.redis_client = redis.from_url(redis_url)
        
        self.running = True
        logger.info(f"Starting feature engine for {len(self.symbols)} symbols")
        
        # Start data ingestion and feature computation tasks
        tasks = [
            asyncio.create_task(self.ohlcv_consumer()),
            asyncio.create_task(self.feature_computation_loop()),
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def ohlcv_consumer(self):
        """Consume OHLCV data from Redis streams"""
        logger.info("Starting OHLCV consumer for feature extraction")
        
        while self.running:
            try:
                # Discover OHLCV streams
                ohlcv_streams = {}
                async for key in self.redis_client.scan_iter(match="ohlcv.*"):
                    key_str = key.decode()
                    ohlcv_streams[key_str] = '>'
                
                if not ohlcv_streams:
                    await asyncio.sleep(1)
                    continue
                
                # Create consumer groups
                for stream_key in ohlcv_streams.keys():
                    try:
                        await self.redis_client.xgroup_create(
                            stream_key, self.consumer_group, '$', mkstream=True
                        )
                    except redis.RedisError:
                        pass  # Group already exists
                
                # Read from streams
                stream_list = [(k, '>') for k in ohlcv_streams.keys()]
                messages = await self.redis_client.xreadgroup(
                    self.consumer_group,
                    self.consumer_name,
                    streams=dict(stream_list),
                    count=50,
                    block=1000
                )
                
                for stream, msgs in messages:
                    stream_str = stream.decode()
                    
                    for msg_id, fields in msgs:
                        try:
                            await self.process_ohlcv_message(stream_str, fields)
                            
                            # Acknowledge message
                            await self.redis_client.xack(stream, self.consumer_group, msg_id)
                            
                        except Exception as e:
                            logger.error(f"OHLCV processing error: {e}")
                
            except Exception as e:
                logger.error(f"OHLCV consumer error: {e}")
                await asyncio.sleep(1)
    
    async def process_ohlcv_message(self, stream: str, fields: Dict[bytes, bytes]):
        """Process OHLCV message"""
        try:
            # Parse OHLCV data
            data = {k.decode(): v.decode() for k, v in fields.items()}
            
            # Extract symbol from stream or data
            symbol = data.get('symbol', 'UNKNOWN')
            if symbol == 'UNKNOWN':
                # Try to extract from stream name
                stream_parts = stream.split('.')
                if len(stream_parts) >= 3:
                    symbol = stream_parts[2]
            
            # Skip if symbol not in our list
            if symbol not in self.symbols:
                return
            
            # Create OHLCV bar
            ohlcv_bar = OHLCV(
                timestamp=float(data.get('timestamp', time.time())),
                open=float(data.get('open', 0)),
                high=float(data.get('high', 0)),
                low=float(data.get('low', 0)),
                close=float(data.get('close', 0)),
                volume=float(data.get('volume', 0)),
                vwap=float(data.get('vwap', 0)) if data.get('vwap') else None
            )
            
            # Add to buffer
            if symbol in self.buffers:
                self.buffers[symbol].add_ohlcv(ohlcv_bar)
            
        except Exception as e:
            logger.error(f"OHLCV message processing error: {e}")
    
    async def feature_computation_loop(self):
        """Periodic feature computation"""
        logger.info("Starting feature computation loop")
        
        while self.running:
            try:
                start_time = time.time()
                current_timestamp = start_time
                
                # Compute features for all symbols
                feature_tasks = []
                for symbol in self.symbols:
                    if symbol in self.buffers:
                        task = asyncio.create_task(
                            self.compute_and_publish_features(symbol, current_timestamp)
                        )
                        feature_tasks.append(task)
                
                # Wait for all computations
                if feature_tasks:
                    await asyncio.gather(*feature_tasks, return_exceptions=True)
                
                # Calculate sleep time
                elapsed = time.time() - start_time
                sleep_time = max(0, self.feature_interval - elapsed)
                
                logger.debug(f"Feature computation cycle completed in {elapsed:.1f}s, sleeping for {sleep_time:.1f}s")
                
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                    
            except Exception as e:
                logger.error(f"Feature computation loop error: {e}")
                await asyncio.sleep(30)
    
    async def compute_and_publish_features(self, symbol: str, timestamp: float):
        """Compute and publish features for a symbol"""
        try:
            buffer = self.buffers[symbol]
            features = buffer.compute_features(timestamp)
            
            if features:
                # Publish to Redis stream
                await self.publish_features(features)
                logger.debug(f"Published features for {symbol}")
            
        except Exception as e:
            logger.error(f"Feature computation/publishing error for {symbol}: {e}")
    
    async def publish_features(self, features: FeatureVector):
        """Publish features to Redis stream"""
        try:
            stream_key = f"features.{features.symbol.lower()}"
            feature_data = features.to_dict()
            
            # Add to Redis Stream
            max_len = int(os.getenv('FEATURES_STREAM_MAXLEN', '10000'))
            await self.redis_client.xadd(
                stream_key, 
                feature_data, 
                maxlen=max_len,
                approximate=True
            )
            
            # Also publish to general features stream
            await self.redis_client.xadd(
                "features.all",
                feature_data,
                maxlen=max_len,
                approximate=True
            )
            
        except Exception as e:
            logger.error(f"Feature publishing error: {e}")
    
    async def stop(self):
        """Stop feature engine"""
        self.running = False
        
        if self.redis_client:
            await self.redis_client.close()
        
        logger.info("Stopped feature extraction engine")
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get engine health status"""
        status = {
            'running': self.running,
            'symbols': self.symbols,
            'buffers': {}
        }
        
        for symbol, buffer in self.buffers.items():
            status['buffers'][symbol] = {
                'buffer_size': len(buffer.ohlcv_buffer),
                'cache_size': len(buffer.feature_cache),
                'last_feature_timestamp': buffer.last_feature_timestamp
            }
        
        return status
    
    async def get_latest_features(self, symbol: str) -> Optional[FeatureVector]:
        """Get latest features for a symbol"""
        if symbol in self.buffers:
            return self.buffers[symbol].compute_features(time.time())
        return None


async def main():
    """Main entry point"""
    logger.info("Starting AI Feature Extraction Engine")
    
    engine = FeatureEngine()
    
    try:
        await engine.start()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        await engine.stop()


if __name__ == "__main__":
    asyncio.run(main())