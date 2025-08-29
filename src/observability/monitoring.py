"""
Observability with Sentry and Prometheus
"""

import os
import time
import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from functools import wraps
from contextlib import contextmanager

# Conditional imports
try:
    import sentry_sdk
    from sentry_sdk import capture_exception, capture_message, set_tag, set_context
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False
    
try:
    from prometheus_client import Counter, Histogram, Gauge, Summary, generate_latest
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

logger = logging.getLogger(__name__)


# Prometheus metrics (if available)
if PROMETHEUS_AVAILABLE:
    # Counters
    order_counter = Counter('trading_orders_total', 'Total number of orders', ['symbol', 'side', 'type', 'status'])
    error_counter = Counter('trading_errors_total', 'Total number of errors', ['error_type', 'component'])
    risk_check_counter = Counter('risk_checks_total', 'Total risk checks', ['check_name', 'action'])
    kill_switch_counter = Counter('kill_switch_activations_total', 'Kill switch activations', ['trigger'])
    
    # Histograms
    order_latency = Histogram('order_latency_seconds', 'Order execution latency', ['exchange'])
    api_latency = Histogram('api_latency_seconds', 'API request latency', ['endpoint', 'method'])
    
    # Gauges
    position_gauge = Gauge('trading_position_usd', 'Current position in USD', ['symbol'])
    pnl_gauge = Gauge('trading_pnl_usd', 'Current P&L in USD')
    ws_downtime_gauge = Gauge('websocket_downtime_seconds', 'WebSocket downtime')
    
    # Summary
    backtest_summary = Summary('backtest_duration_seconds', 'Backtest execution time')


class ObservabilityManager:
    """Centralized observability management"""
    
    def __init__(self):
        self.sentry_enabled = False
        self.prometheus_enabled = os.getenv('PROMETHEUS_ENABLED', 'true').lower() == 'true'
        
        # Initialize Sentry
        if SENTRY_AVAILABLE:
            sentry_dsn = os.getenv('SENTRY_DSN')
            if sentry_dsn:
                try:
                    sentry_sdk.init(
                        dsn=sentry_dsn,
                        traces_sample_rate=0.1,
                        environment=os.getenv('ENVIRONMENT', 'development'),
                        release=os.getenv('RELEASE_VERSION', 'v0.2.0')
                    )
                    self.sentry_enabled = True
                    logger.info("Sentry initialized successfully")
                except Exception as e:
                    logger.error(f"Failed to initialize Sentry: {e}")
        
        # Check Prometheus
        if self.prometheus_enabled and not PROMETHEUS_AVAILABLE:
            logger.warning("Prometheus enabled but prometheus_client not installed")
            self.prometheus_enabled = False
        
        logger.info(f"ObservabilityManager initialized: sentry={self.sentry_enabled}, prometheus={self.prometheus_enabled}")
    
    def capture_exception(self, error: Exception, context: Dict[str, Any] = None):
        """Capture exception to Sentry"""
        if self.sentry_enabled and SENTRY_AVAILABLE:
            if context:
                for key, value in context.items():
                    set_tag(key, value)
            capture_exception(error)
        else:
            logger.error(f"Exception captured: {error}", extra=context)
    
    def capture_message(self, message: str, level: str = "info", context: Dict[str, Any] = None):
        """Capture message to Sentry"""
        if self.sentry_enabled and SENTRY_AVAILABLE:
            if context:
                set_context("additional", context)
            capture_message(message, level=level)
        else:
            log_func = getattr(logger, level, logger.info)
            log_func(message, extra=context)
    
    def track_order(self, symbol: str, side: str, order_type: str, status: str):
        """Track order metrics"""
        if self.prometheus_enabled and PROMETHEUS_AVAILABLE:
            order_counter.labels(symbol=symbol, side=side, type=order_type, status=status).inc()
    
    def track_error(self, error_type: str, component: str):
        """Track error metrics"""
        if self.prometheus_enabled and PROMETHEUS_AVAILABLE:
            error_counter.labels(error_type=error_type, component=component).inc()
    
    def track_risk_check(self, check_name: str, action: str):
        """Track risk check metrics"""
        if self.prometheus_enabled and PROMETHEUS_AVAILABLE:
            risk_check_counter.labels(check_name=check_name, action=action).inc()
    
    def track_kill_switch(self, trigger: str):
        """Track kill switch activation"""
        if self.prometheus_enabled and PROMETHEUS_AVAILABLE:
            kill_switch_counter.labels(trigger=trigger).inc()
    
    def update_position(self, symbol: str, position_usd: float):
        """Update position gauge"""
        if self.prometheus_enabled and PROMETHEUS_AVAILABLE:
            position_gauge.labels(symbol=symbol).set(position_usd)
    
    def update_pnl(self, pnl: float):
        """Update P&L gauge"""
        if self.prometheus_enabled and PROMETHEUS_AVAILABLE:
            pnl_gauge.set(pnl)
    
    def update_ws_downtime(self, downtime_seconds: float):
        """Update WebSocket downtime"""
        if self.prometheus_enabled and PROMETHEUS_AVAILABLE:
            ws_downtime_gauge.set(downtime_seconds)
    
    @contextmanager
    def track_latency(self, metric_name: str, **labels):
        """Context manager to track latency"""
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            
            if self.prometheus_enabled and PROMETHEUS_AVAILABLE:
                if metric_name == 'order':
                    order_latency.labels(**labels).observe(duration)
                elif metric_name == 'api':
                    api_latency.labels(**labels).observe(duration)
                elif metric_name == 'backtest':
                    backtest_summary.observe(duration)
    
    def get_metrics(self) -> bytes:
        """Get Prometheus metrics in text format"""
        if self.prometheus_enabled and PROMETHEUS_AVAILABLE:
            return generate_latest()
        return b""
    
    def get_status(self) -> Dict[str, Any]:
        """Get observability status"""
        return {
            'sentry_enabled': self.sentry_enabled,
            'prometheus_enabled': self.prometheus_enabled,
            'environment': os.getenv('ENVIRONMENT', 'development'),
            'release': os.getenv('RELEASE_VERSION', 'v0.2.0')
        }


# Decorators for automatic tracking
def track_execution(component: str):
    """Decorator to track function execution"""
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            error_occurred = False
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                error_occurred = True
                if 'observability' in kwargs:
                    obs: ObservabilityManager = kwargs['observability']
                    obs.capture_exception(e, {'component': component, 'function': func.__name__})
                    obs.track_error(type(e).__name__, component)
                raise
            finally:
                duration = time.time() - start_time
                logger.debug(f"{component}.{func.__name__} executed in {duration:.3f}s (error={error_occurred})")
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            error_occurred = False
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                error_occurred = True
                if 'observability' in kwargs:
                    obs: ObservabilityManager = kwargs['observability']
                    obs.capture_exception(e, {'component': component, 'function': func.__name__})
                    obs.track_error(type(e).__name__, component)
                raise
            finally:
                duration = time.time() - start_time
                logger.debug(f"{component}.{func.__name__} executed in {duration:.3f}s (error={error_occurred})")
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def track_api_endpoint(endpoint: str, method: str = "GET"):
    """Decorator to track API endpoint latency"""
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            if PROMETHEUS_AVAILABLE:
                with api_latency.labels(endpoint=endpoint, method=method).time():
                    return await func(*args, **kwargs)
            else:
                return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            if PROMETHEUS_AVAILABLE:
                with api_latency.labels(endpoint=endpoint, method=method).time():
                    return func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# Singleton instance
observability = ObservabilityManager()