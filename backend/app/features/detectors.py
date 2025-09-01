"""
Sofia V2 Realtime DataHub - Anomaly Detectors
Statistical anomaly detection for big trades, liquidation spikes, etc.
"""

import asyncio
from collections import defaultdict, deque
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Deque
import statistics

import structlog

from ..bus import EventBus, EventType
from ..config import Settings

logger = structlog.get_logger(__name__)

class BigTradeDetector:
    """
    Detects unusually large trades using USD value and z-score analysis
    """
    
    def __init__(self, event_bus: EventBus, settings: Settings):
        self.event_bus = event_bus
        self.settings = settings
        
        # Configuration from YAML
        features_config = settings.yaml_config.get('features', {})
        big_trade_config = features_config.get('big_trade', {})
        
        self.enabled = big_trade_config.get('enabled', True)
        self.window_seconds = big_trade_config.get('window_seconds', 5)
        self.min_usd_notional = big_trade_config.get('min_usd_notional', 250000)
        self.z_score_threshold = big_trade_config.get('z_score_threshold', 3.0)
        
        # Rolling window for trade sizes per symbol
        self.trade_windows: Dict[str, Deque[float]] = defaultdict(lambda: deque(maxlen=1000))
        self.last_cleanup = datetime.now(timezone.utc)
        
        if self.enabled:
            event_bus.subscribe(EventType.TRADE, self._process_trade)
            logger.info("Big trade detector initialized",
                       min_usd=self.min_usd_notional,
                       z_threshold=self.z_score_threshold)
    
    async def _process_trade(self, trade_data: Dict[str, Any]):
        """Process incoming trade for big trade detection"""
        try:
            symbol = trade_data.get('symbol')
            usd_value = trade_data.get('usd_value', 0)
            
            if not symbol or usd_value <= 0:
                return
            
            # Basic threshold check
            if usd_value >= self.min_usd_notional:
                # Add to rolling window
                self.trade_windows[symbol].append(usd_value)
                
                # Check for statistical anomaly
                if len(self.trade_windows[symbol]) >= 10:  # Need minimum sample
                    await self._check_statistical_anomaly(symbol, usd_value, trade_data)
                else:
                    # For initial trades, use simple threshold
                    await self._emit_big_trade_alert(symbol, usd_value, trade_data, 'threshold')
            else:
                # Add normal trades to rolling window for baseline
                self.trade_windows[symbol].append(usd_value)
            
            # Periodic cleanup
            await self._periodic_cleanup()
            
        except Exception as e:
            logger.error("Error in big trade detection", error=str(e))
    
    async def _check_statistical_anomaly(self, symbol: str, usd_value: float, trade_data: Dict[str, Any]):
        """Check if trade is statistical anomaly using z-score"""
        try:
            trades = list(self.trade_windows[symbol])
            
            if len(trades) < 10:
                return
            
            # Calculate z-score
            mean_value = statistics.mean(trades[:-1])  # Exclude current trade
            if len(trades) > 1:
                stdev_value = statistics.stdev(trades[:-1])
            else:
                stdev_value = 0
            
            if stdev_value > 0:
                z_score = (usd_value - mean_value) / stdev_value
                
                if z_score >= self.z_score_threshold:
                    await self._emit_big_trade_alert(symbol, usd_value, trade_data, 'z_score', z_score)
            
        except Exception as e:
            logger.error("Error in statistical anomaly check", symbol=symbol, error=str(e))
    
    async def _emit_big_trade_alert(self, symbol: str, usd_value: float, trade_data: Dict[str, Any], 
                                   detection_type: str, z_score: float = None):
        """Emit big trade alert event"""
        alert_data = {
            'symbol': symbol,
            'exchange': trade_data.get('exchange'),
            'usd_value': usd_value,
            'price': trade_data.get('price'),
            'quantity': trade_data.get('quantity'),
            'side': trade_data.get('side'),
            'detection_type': detection_type,
            'z_score': z_score,
            'timestamp': trade_data.get('timestamp'),
            'trade_id': trade_data.get('trade_id')
        }
        
        await self.event_bus.publish(EventType.BIG_TRADE, alert_data)
        
        logger.info("Big trade detected",
                   symbol=symbol,
                   usd_value=usd_value,
                   detection_type=detection_type,
                   z_score=z_score)
    
    async def _periodic_cleanup(self):
        """Clean up old data periodically"""
        now = datetime.now(timezone.utc)
        if (now - self.last_cleanup).seconds > 300:  # Every 5 minutes
            # Remove symbols with no recent activity
            symbols_to_remove = []
            for symbol in self.trade_windows:
                if len(self.trade_windows[symbol]) == 0:
                    symbols_to_remove.append(symbol)
            
            for symbol in symbols_to_remove:
                del self.trade_windows[symbol]
            
            self.last_cleanup = now


class LiquidationSpikeDetector:
    """
    Detects spikes in liquidation activity using z-score analysis
    """
    
    def __init__(self, event_bus: EventBus, settings: Settings):
        self.event_bus = event_bus
        self.settings = settings
        
        # Configuration from YAML
        features_config = settings.yaml_config.get('features', {})
        liq_spike_config = features_config.get('liq_spike', {})
        
        self.enabled = liq_spike_config.get('enabled', True)
        self.window_seconds = liq_spike_config.get('window_seconds', 60)
        self.z_score_threshold = liq_spike_config.get('z_score_threshold', 3.0)
        self.min_liquidation_usd = liq_spike_config.get('min_liquidation_usd', 100000)
        
        # Rolling window for liquidations per symbol per time window
        self.liquidation_windows: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.last_cleanup = datetime.now(timezone.utc)
        
        if self.enabled:
            event_bus.subscribe(EventType.LIQUIDATION, self._process_liquidation)
            logger.info("Liquidation spike detector initialized",
                       window_seconds=self.window_seconds,
                       z_threshold=self.z_score_threshold)
    
    async def _process_liquidation(self, liquidation_data: Dict[str, Any]):
        """Process incoming liquidation for spike detection"""
        try:
            symbol = liquidation_data.get('symbol')
            usd_value = liquidation_data.get('usd_value', 0)
            timestamp_str = liquidation_data.get('timestamp')
            
            if not symbol or usd_value < self.min_liquidation_usd or not timestamp_str:
                return
            
            # Parse timestamp
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            
            # Add to rolling window
            liquidation_entry = {
                'usd_value': usd_value,
                'timestamp': timestamp,
                'data': liquidation_data
            }
            
            self.liquidation_windows[symbol].append(liquidation_entry)
            
            # Clean up old entries outside time window
            cutoff_time = timestamp - timedelta(seconds=self.window_seconds)
            self.liquidation_windows[symbol] = [
                entry for entry in self.liquidation_windows[symbol]
                if entry['timestamp'] > cutoff_time
            ]
            
            # Check for spike
            await self._check_liquidation_spike(symbol, timestamp)
            
            # Periodic cleanup
            await self._periodic_cleanup()
            
        except Exception as e:
            logger.error("Error in liquidation spike detection", error=str(e))
    
    async def _check_liquidation_spike(self, symbol: str, current_time: datetime):
        """Check for liquidation spike using volume and frequency analysis"""
        try:
            recent_liquidations = self.liquidation_windows[symbol]
            
            if len(recent_liquidations) < 3:  # Need minimum sample
                return
            
            # Calculate metrics for current window
            current_window_start = current_time - timedelta(seconds=self.window_seconds)
            current_window_liquidations = [
                liq for liq in recent_liquidations
                if liq['timestamp'] > current_window_start
            ]
            
            if len(current_window_liquidations) < 2:
                return
            
            # Calculate total volume and count in current window
            current_volume = sum(liq['usd_value'] for liq in current_window_liquidations)
            current_count = len(current_window_liquidations)
            
            # Get historical data for comparison (last 10 windows)
            historical_volumes = []
            historical_counts = []
            
            for i in range(1, 11):  # Look back 10 windows
                window_start = current_time - timedelta(seconds=self.window_seconds * (i + 1))
                window_end = current_time - timedelta(seconds=self.window_seconds * i)
                
                window_liquidations = [
                    liq for liq in recent_liquidations
                    if window_start < liq['timestamp'] <= window_end
                ]
                
                if window_liquidations:
                    window_volume = sum(liq['usd_value'] for liq in window_liquidations)
                    window_count = len(window_liquidations)
                    historical_volumes.append(window_volume)
                    historical_counts.append(window_count)
            
            # Check for volume spike
            if len(historical_volumes) >= 3:
                await self._check_volume_spike(symbol, current_volume, historical_volumes, current_window_liquidations[0]['data'])
            
            # Check for frequency spike
            if len(historical_counts) >= 3:
                await self._check_frequency_spike(symbol, current_count, historical_counts, current_window_liquidations[0]['data'])
                
        except Exception as e:
            logger.error("Error checking liquidation spike", symbol=symbol, error=str(e))
    
    async def _check_volume_spike(self, symbol: str, current_volume: float, historical_volumes: List[float], sample_data: Dict[str, Any]):
        """Check for volume-based spike"""
        if len(historical_volumes) < 3:
            return
        
        mean_volume = statistics.mean(historical_volumes)
        if len(historical_volumes) > 1 and mean_volume > 0:
            stdev_volume = statistics.stdev(historical_volumes)
            if stdev_volume > 0:
                z_score = (current_volume - mean_volume) / stdev_volume
                
                if z_score >= self.z_score_threshold:
                    await self._emit_liquidation_spike_alert(symbol, 'volume', current_volume, z_score, sample_data)
    
    async def _check_frequency_spike(self, symbol: str, current_count: int, historical_counts: List[int], sample_data: Dict[str, Any]):
        """Check for frequency-based spike"""
        if len(historical_counts) < 3:
            return
        
        mean_count = statistics.mean(historical_counts)
        if len(historical_counts) > 1 and mean_count > 0:
            stdev_count = statistics.stdev(historical_counts)
            if stdev_count > 0:
                z_score = (current_count - mean_count) / stdev_count
                
                if z_score >= self.z_score_threshold:
                    await self._emit_liquidation_spike_alert(symbol, 'frequency', current_count, z_score, sample_data)
    
    async def _emit_liquidation_spike_alert(self, symbol: str, spike_type: str, value: float, z_score: float, sample_data: Dict[str, Any]):
        """Emit liquidation spike alert"""
        alert_data = {
            'symbol': symbol,
            'exchange': sample_data.get('exchange'),
            'spike_type': spike_type,  # 'volume' or 'frequency'
            'spike_value': value,
            'z_score': z_score,
            'window_seconds': self.window_seconds,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'sample_liquidation': sample_data
        }
        
        await self.event_bus.publish(EventType.LIQ_SPIKE, alert_data)
        
        logger.info("Liquidation spike detected",
                   symbol=symbol,
                   spike_type=spike_type,
                   value=value,
                   z_score=z_score)
    
    async def _periodic_cleanup(self):
        """Clean up old data periodically"""
        now = datetime.now(timezone.utc)
        if (now - self.last_cleanup).seconds > 300:  # Every 5 minutes
            cutoff_time = now - timedelta(seconds=self.window_seconds * 20)  # Keep 20 windows of history
            
            for symbol in list(self.liquidation_windows.keys()):
                self.liquidation_windows[symbol] = [
                    entry for entry in self.liquidation_windows[symbol]
                    if entry['timestamp'] > cutoff_time
                ]
                
                # Remove empty symbols
                if not self.liquidation_windows[symbol]:
                    del self.liquidation_windows[symbol]
            
            self.last_cleanup = now


class VolumeSurgeDetector:
    """
    Detects sudden volume surges in trading
    """
    
    def __init__(self, event_bus: EventBus, settings: Settings):
        self.event_bus = event_bus
        self.settings = settings
        
        # Configuration from YAML
        features_config = settings.yaml_config.get('features', {})
        volume_config = features_config.get('volume_surge', {})
        
        self.enabled = volume_config.get('enabled', True)
        self.window_seconds = volume_config.get('window_seconds', 30)
        self.surge_threshold = volume_config.get('surge_threshold', 2.0)  # 2x normal volume
        
        # Rolling windows for volume tracking
        self.volume_windows: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.last_cleanup = datetime.now(timezone.utc)
        
        if self.enabled:
            event_bus.subscribe(EventType.TRADE, self._process_trade_volume)
            logger.info("Volume surge detector initialized",
                       window_seconds=self.window_seconds,
                       surge_threshold=self.surge_threshold)
    
    async def _process_trade_volume(self, trade_data: Dict[str, Any]):
        """Process trade for volume surge detection"""
        try:
            symbol = trade_data.get('symbol')
            usd_value = trade_data.get('usd_value', 0)
            timestamp_str = trade_data.get('timestamp')
            
            if not symbol or usd_value <= 0 or not timestamp_str:
                return
            
            # Parse timestamp
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            
            # Add to volume window
            volume_entry = {
                'usd_value': usd_value,
                'timestamp': timestamp
            }
            
            self.volume_windows[symbol].append(volume_entry)
            
            # Clean up old entries
            cutoff_time = timestamp - timedelta(seconds=self.window_seconds * 10)  # Keep 10 windows
            self.volume_windows[symbol] = [
                entry for entry in self.volume_windows[symbol]
                if entry['timestamp'] > cutoff_time
            ]
            
            # Check for volume surge
            await self._check_volume_surge(symbol, timestamp, trade_data)
            
        except Exception as e:
            logger.error("Error in volume surge detection", error=str(e))
    
    async def _check_volume_surge(self, symbol: str, current_time: datetime, trade_data: Dict[str, Any]):
        """Check for volume surge"""
        try:
            volumes = self.volume_windows[symbol]
            
            if len(volumes) < 20:  # Need sufficient history
                return
            
            # Current window volume
            current_window_start = current_time - timedelta(seconds=self.window_seconds)
            current_volume = sum(
                entry['usd_value'] for entry in volumes
                if entry['timestamp'] > current_window_start
            )
            
            # Historical windows for comparison
            historical_volumes = []
            for i in range(1, 6):  # Compare with last 5 windows
                window_start = current_time - timedelta(seconds=self.window_seconds * (i + 1))
                window_end = current_time - timedelta(seconds=self.window_seconds * i)
                
                window_volume = sum(
                    entry['usd_value'] for entry in volumes
                    if window_start < entry['timestamp'] <= window_end
                )
                
                if window_volume > 0:
                    historical_volumes.append(window_volume)
            
            if len(historical_volumes) >= 3:
                avg_historical_volume = statistics.mean(historical_volumes)
                
                if avg_historical_volume > 0:
                    surge_ratio = current_volume / avg_historical_volume
                    
                    if surge_ratio >= self.surge_threshold:
                        await self._emit_volume_surge_alert(symbol, current_volume, avg_historical_volume, surge_ratio, trade_data)
        
        except Exception as e:
            logger.error("Error checking volume surge", symbol=symbol, error=str(e))
    
    async def _emit_volume_surge_alert(self, symbol: str, current_volume: float, avg_volume: float, surge_ratio: float, trade_data: Dict[str, Any]):
        """Emit volume surge alert"""
        alert_data = {
            'symbol': symbol,
            'exchange': trade_data.get('exchange'),
            'current_volume': current_volume,
            'average_volume': avg_volume,
            'surge_ratio': surge_ratio,
            'window_seconds': self.window_seconds,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        await self.event_bus.publish(EventType.VOLUME_SURGE, alert_data)
        
        logger.info("Volume surge detected",
                   symbol=symbol,
                   surge_ratio=surge_ratio,
                   current_volume=current_volume)


class DetectorManager:
    """
    Manager for all anomaly detectors
    """
    
    def __init__(self, event_bus: EventBus, settings: Settings):
        self.event_bus = event_bus
        self.settings = settings
        
        # Initialize detectors
        self.big_trade_detector = BigTradeDetector(event_bus, settings)
        self.liquidation_spike_detector = LiquidationSpikeDetector(event_bus, settings)
        self.volume_surge_detector = VolumeSurgeDetector(event_bus, settings)
        
        logger.info("Detector manager initialized with all detectors")
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of all detectors"""
        return {
            'big_trade_detector': {
                'enabled': self.big_trade_detector.enabled,
                'symbols_tracked': len(self.big_trade_detector.trade_windows)
            },
            'liquidation_spike_detector': {
                'enabled': self.liquidation_spike_detector.enabled,
                'symbols_tracked': len(self.liquidation_spike_detector.liquidation_windows)
            },
            'volume_surge_detector': {
                'enabled': self.volume_surge_detector.enabled,
                'symbols_tracked': len(self.volume_surge_detector.volume_windows)
            }
        }