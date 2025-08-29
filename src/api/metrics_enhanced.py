"""
Enhanced Metrics Collection for Sofia V2
Tracks all required metrics for observability
"""

import time
import asyncio
from typing import Dict, Any
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
import statistics

@dataclass
class SystemMetrics:
    """System-wide metrics"""
    bus_lag_ms: float = 0.0
    writer_queue: int = 0
    reconnects_total: int = 0
    stale_ratio: float = 0.0
    api_p95_ms: float = 0.0
    auc: float = 0.55  # Default AUC
    paper_pnl: float = 0.0
    fallback_hits_total: int = 0
    provider_latency_ms: Dict[str, float] = None
    ws_connections: int = 0
    
    def __post_init__(self):
        if self.provider_latency_ms is None:
            self.provider_latency_ms = {}

class MetricsCollector:
    """Collects and aggregates system metrics"""
    
    def __init__(self):
        self.metrics = SystemMetrics()
        self.api_latencies = deque(maxlen=1000)
        self.symbol_freshness = {}
        self.tick_counts = defaultdict(int)
        self.fallback_counts = defaultdict(int)
        self.provider_latencies = defaultdict(list)
        self.last_update = time.time()
        
    def record_api_latency(self, latency_ms: float):
        """Record API call latency"""
        self.api_latencies.append(latency_ms)
        
    def record_tick(self, symbol: str):
        """Record price tick"""
        self.tick_counts[symbol] += 1
        self.symbol_freshness[symbol] = time.time()
        
    def record_fallback(self, provider: str):
        """Record fallback usage"""
        self.fallback_counts[provider] += 1
        self.metrics.fallback_hits_total += 1
        
    def record_provider_latency(self, provider: str, latency_ms: float):
        """Record provider latency"""
        if len(self.provider_latencies[provider]) > 100:
            self.provider_latencies[provider].pop(0)
        self.provider_latencies[provider].append(latency_ms)
        
    def update_paper_pnl(self, pnl: float):
        """Update paper trading PnL"""
        self.metrics.paper_pnl = pnl
        
    def update_ws_connections(self, count: int):
        """Update WebSocket connection count"""
        self.metrics.ws_connections = count
        
    def update_auc(self, auc: float):
        """Update model AUC"""
        self.metrics.auc = auc
        
    def increment_reconnects(self):
        """Increment reconnection counter"""
        self.metrics.reconnects_total += 1
        
    def calculate_metrics(self) -> Dict[str, Any]:
        """Calculate current metrics"""
        current_time = time.time()
        
        # Calculate API P95 latency
        if self.api_latencies:
            sorted_latencies = sorted(self.api_latencies)
            p95_index = int(len(sorted_latencies) * 0.95)
            self.metrics.api_p95_ms = sorted_latencies[p95_index] if sorted_latencies else 0
        
        # Calculate stale ratio (symbols not updated in last 15s)
        stale_count = 0
        total_symbols = len(self.symbol_freshness)
        
        for symbol, last_update in self.symbol_freshness.items():
            if current_time - last_update > 15:  # 15 second stale threshold
                stale_count += 1
                
        self.metrics.stale_ratio = stale_count / total_symbols if total_symbols > 0 else 0
        
        # Calculate average provider latencies
        for provider, latencies in self.provider_latencies.items():
            if latencies:
                self.metrics.provider_latency_ms[provider] = statistics.mean(latencies)
        
        # Calculate bus lag (mock for now, should come from actual data pipeline)
        self.metrics.bus_lag_ms = 50 + (hash(str(current_time)) % 100)  # Mock: 50-150ms
        
        # Mock writer queue (should come from actual writer)
        self.metrics.writer_queue = hash(str(current_time)) % 100
        
        return {
            **asdict(self.metrics),
            "tick_counts": dict(self.tick_counts),
            "symbol_freshness": {
                symbol: current_time - last_update 
                for symbol, last_update in self.symbol_freshness.items()
            },
            "fallback_usage_pct": (
                (self.metrics.fallback_hits_total / sum(self.tick_counts.values()) * 100)
                if sum(self.tick_counts.values()) > 0 else 0
            ),
            "timestamp": current_time
        }

# Global metrics collector instance
metrics_collector = MetricsCollector()