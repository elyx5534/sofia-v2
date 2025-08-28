"""
Prometheus metrics server for Sofia V2
Exposes all system metrics on /metrics endpoint
"""

import asyncio
import logging
import os
from typing import Dict, Any
import time
from prometheus_client import start_http_server, generate_latest, CONTENT_TYPE_LATEST
from prometheus_client import Counter, Histogram, Gauge, Summary, CollectorRegistry
import redis.asyncio as redis
from fastapi import FastAPI, Response
import uvicorn

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Custom metrics for system health
SYSTEM_HEALTH = Gauge('sofia_system_health', 'Overall system health (0-1)', ['component'])
COMPONENT_STATUS = Gauge('sofia_component_status', 'Component status (0=down, 1=up)', ['component', 'instance'])
REDIS_CONNECTION_STATUS = Gauge('sofia_redis_connection_status', 'Redis connection status')
UPTIME_SECONDS = Gauge('sofia_uptime_seconds', 'System uptime in seconds')


class MetricsCollector:
    """Collects system metrics from various components"""
    
    def __init__(self):
        self.redis_client = None
        self.start_time = time.time()
        self.components = [
            'crypto_ws',
            'ts_writer', 
            'equities_pull',
            'news_rss',
            'whale_monitor',
            'ai_featurizer',
            'ai_model',
            'paper_trading'
        ]
    
    async def start(self):
        """Initialize metrics collector"""
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        try:
            self.redis_client = redis.from_url(redis_url)
            await self.redis_client.ping()
            REDIS_CONNECTION_STATUS.set(1)
            logger.info("Connected to Redis for metrics collection")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            REDIS_CONNECTION_STATUS.set(0)
    
    async def collect_component_health(self):
        """Collect health status from all components"""
        try:
            # Update uptime
            uptime = time.time() - self.start_time
            UPTIME_SECONDS.set(uptime)
            
            if not self.redis_client:
                return
            
            overall_health = 1.0
            healthy_components = 0
            
            for component in self.components:
                try:
                    # Check for component health status in Redis
                    health_key = f"health:{component}"
                    health_data = await self.redis_client.get(health_key)
                    
                    if health_data:
                        health_info = eval(health_data.decode())  # Simple eval for demo
                        component_health = health_info.get('healthy', False)
                        
                        COMPONENT_STATUS.labels(component=component, instance='default').set(1 if component_health else 0)
                        
                        if component_health:
                            healthy_components += 1
                            SYSTEM_HEALTH.labels(component=component).set(1.0)
                        else:
                            SYSTEM_HEALTH.labels(component=component).set(0.0)
                            overall_health *= 0.8  # Reduce overall health
                    else:
                        # Component not reporting
                        COMPONENT_STATUS.labels(component=component, instance='default').set(0)
                        SYSTEM_HEALTH.labels(component=component).set(0.0)
                        overall_health *= 0.7
                        
                except Exception as e:
                    logger.error(f"Error collecting health for {component}: {e}")
                    COMPONENT_STATUS.labels(component=component, instance='default').set(0)
                    SYSTEM_HEALTH.labels(component=component).set(0.0)
            
            # Set overall system health
            SYSTEM_HEALTH.labels(component='overall').set(overall_health)
            
        except Exception as e:
            logger.error(f"Health collection error: {e}")
    
    async def run_collector(self):
        """Run metrics collection loop"""
        while True:
            try:
                await self.collect_component_health()
                await asyncio.sleep(30)  # Collect every 30 seconds
            except Exception as e:
                logger.error(f"Metrics collection loop error: {e}")
                await asyncio.sleep(60)


# FastAPI app for metrics endpoint
app = FastAPI(title="Sofia V2 Metrics Server")
metrics_collector = MetricsCollector()


@app.on_event("startup")
async def startup_event():
    """Initialize metrics collector on startup"""
    await metrics_collector.start()
    
    # Start collector task
    asyncio.create_task(metrics_collector.run_collector())


@app.get("/metrics")
async def get_metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "uptime": time.time() - metrics_collector.start_time,
        "redis_connected": metrics_collector.redis_client is not None
    }


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Sofia V2 Metrics Server",
        "endpoints": {
            "metrics": "/metrics",
            "health": "/health"
        }
    }


if __name__ == "__main__":
    # Start Prometheus HTTP server on separate port for direct access
    prometheus_port = int(os.getenv('PROMETHEUS_PORT', '8000'))
    start_http_server(prometheus_port)
    logger.info(f"Prometheus metrics server started on port {prometheus_port}")
    
    # Start FastAPI server for additional endpoints
    fastapi_port = int(os.getenv('METRICS_API_PORT', '8001'))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=fastapi_port,
        log_level="info"
    )