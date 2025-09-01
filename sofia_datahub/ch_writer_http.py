"""
ClickHouse writer using HTTP API (no driver needed)
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, UTC
from typing import Dict, List, Optional

import httpx
import orjson
from dotenv import load_dotenv
from nats.aio.client import Client as NATS

logger = logging.getLogger(__name__)

class ClickHouseHTTPWriter:
    """Writes to ClickHouse using HTTP API"""
    
    def __init__(self, config: Dict, nats_client: NATS):
        self.config = config
        self.nats = nats_client
        self.base_url = config.get("url", "http://localhost:8123")
        self.running = False
        
        self.tick_buffer: List[Dict] = []
        self.last_flush = time.time()
        
        self.stats = {
            "ticks_received": 0,
            "ticks_written": 0,
            "errors": 0,
            "start_time": time.time()
        }
    
    async def execute_query(self, query: str) -> bool:
        """Execute a query via HTTP"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    params={"query": query},
                    timeout=10.0
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return False
    
    async def insert_batch(self, table: str, data: List[Dict]) -> bool:
        """Insert batch of data"""
        if not data:
            return True
            
        try:
            # Format as TSV for bulk insert
            values = []
            for row in data:
                values.append("\t".join(str(v) for v in row.values()))
            
            query = f"INSERT INTO {table} FORMAT TabSeparated"
            body = "\n".join(values)
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    params={"query": query},
                    content=body,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    self.stats["ticks_written"] += len(data)
                    return True
                else:
                    logger.error(f"Insert failed: {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Batch insert failed: {e}")
            self.stats["errors"] += 1
            return False
    
    async def process_tick(self, msg):
        """Process incoming tick"""
        try:
            data = orjson.loads(msg.data)
            
            tick = {
                "ts": datetime.fromtimestamp(data["ts"] / 1000, UTC).isoformat(),
                "symbol": data["symbol"],
                "price": data["price"],
                "volume": data.get("volume", 0),
                "bid": data.get("bid", 0),
                "ask": data.get("ask", 0),
                "src": data.get("src", "binance")
            }
            
            self.tick_buffer.append(tick)
            self.stats["ticks_received"] += 1
            
            # Flush if buffer is full
            if len(self.tick_buffer) >= 100:
                await self.flush_ticks()
                
        except Exception as e:
            logger.error(f"Error processing tick: {e}")
    
    async def flush_ticks(self):
        """Flush tick buffer"""
        if not self.tick_buffer:
            return
            
        await self.insert_batch("market_ticks", self.tick_buffer)
        self.tick_buffer.clear()
        self.last_flush = time.time()
    
    async def run(self):
        """Main run loop"""
        self.running = True
        
        # Create tables if needed
        await self.execute_query("""
            CREATE TABLE IF NOT EXISTS market_ticks (
                ts DateTime64(3),
                symbol String,
                price Float64,
                volume Float64,
                bid Float64,
                ask Float64,
                src String
            ) ENGINE = MergeTree() ORDER BY (symbol, ts)
        """)
        
        # Subscribe to ticks
        subscription = await self.nats.subscribe("ticks.*", cb=self.process_tick)
        logger.info("HTTP Writer started")
        
        try:
            while self.running:
                await asyncio.sleep(1)
                
                # Periodic flush
                if time.time() - self.last_flush > 5:
                    await self.flush_ticks()
                    
        finally:
            await subscription.unsubscribe()
            await self.flush_ticks()
    
    async def stop(self):
        """Stop the writer"""
        self.running = False