"""
Whale trade monitoring system for large cryptocurrency trades ≥100k USDT
Monitors trade streams and triggers alerts for whale movements
"""

import asyncio
import logging
import os
import time
import json
from dataclasses import dataclass, asdict
from typing import Dict, Optional, Any, List, Set
from datetime import datetime, timedelta
import aiohttp
import redis.asyncio as redis
from prometheus_client import Counter, Histogram, Gauge
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import websockets

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Prometheus metrics
WHALE_TRADES_DETECTED = Counter('whale_trades_detected_total', 'Whale trades detected', ['exchange', 'symbol', 'side'])
ALERT_NOTIFICATIONS_SENT = Counter('whale_alert_notifications_sent_total', 'Alert notifications sent', ['channel'])
TRADE_VOLUME_HISTOGRAM = Histogram('whale_trade_volume_usdt', 'Whale trade volumes in USDT', ['exchange', 'symbol'])
WHALE_ALERT_LATENCY = Histogram('whale_alert_latency_seconds', 'Time from trade to alert', ['exchange'])
ACTIVE_WHALES = Gauge('whale_traders_active', 'Number of active whale traders', ['exchange'])


@dataclass
class WhaleTrade:
    """Whale trade data structure"""
    exchange: str
    symbol: str
    side: str  # 'buy' or 'sell'
    price: float
    quantity: float
    volume_usdt: float
    timestamp: float
    trade_id: Optional[str] = None
    trader_id: Optional[str] = None
    
    def __post_init__(self):
        if self.volume_usdt == 0:
            self.volume_usdt = self.price * self.quantity


@dataclass
class WhaleAlert:
    """Whale alert structure"""
    trade: WhaleTrade
    alert_type: str  # 'single_trade', 'accumulation', 'unusual_activity'
    severity: str  # 'low', 'medium', 'high', 'critical'
    message: str
    additional_context: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.additional_context is None:
            self.additional_context = {}


class WhaleDetectionEngine:
    """Engine for detecting whale trades and patterns"""
    
    def __init__(self):
        # Configuration
        self.min_whale_threshold = float(os.getenv('WHALE_MIN_THRESHOLD_USDT', '100000'))  # 100k USDT
        self.large_whale_threshold = float(os.getenv('WHALE_LARGE_THRESHOLD_USDT', '500000'))  # 500k USDT
        self.mega_whale_threshold = float(os.getenv('WHALE_MEGA_THRESHOLD_USDT', '1000000'))  # 1M USDT
        
        # Pattern detection parameters
        self.accumulation_window = int(os.getenv('WHALE_ACCUMULATION_WINDOW_SEC', '300'))  # 5 minutes
        self.accumulation_threshold = float(os.getenv('WHALE_ACCUMULATION_THRESHOLD_USDT', '200000'))  # 200k USDT
        self.unusual_activity_threshold = int(os.getenv('WHALE_UNUSUAL_ACTIVITY_THRESHOLD', '3'))  # 3 trades in window
        
        # Trade tracking
        self.recent_trades = {}  # {symbol: [trades]}
        self.trader_patterns = {}  # {trader_id: pattern_data}
        self.symbol_volumes = {}  # {symbol: volume_data}
        
        # Cleanup parameters
        self.cleanup_interval = 3600  # 1 hour
        self.max_trade_history = 1000
    
    def is_whale_trade(self, trade_volume_usdt: float) -> bool:
        """Check if trade qualifies as whale trade"""
        return trade_volume_usdt >= self.min_whale_threshold
    
    def get_severity(self, trade_volume_usdt: float) -> str:
        """Determine alert severity based on volume"""
        if trade_volume_usdt >= self.mega_whale_threshold:
            return 'critical'
        elif trade_volume_usdt >= self.large_whale_threshold:
            return 'high'
        elif trade_volume_usdt >= self.min_whale_threshold * 2:
            return 'medium'
        else:
            return 'low'
    
    def detect_patterns(self, trade: WhaleTrade) -> List[WhaleAlert]:
        """Detect whale trading patterns"""
        alerts = []
        current_time = time.time()
        
        # Add to recent trades
        if trade.symbol not in self.recent_trades:
            self.recent_trades[trade.symbol] = []
        
        self.recent_trades[trade.symbol].append(trade)
        
        # Clean old trades
        cutoff_time = current_time - self.accumulation_window
        self.recent_trades[trade.symbol] = [
            t for t in self.recent_trades[trade.symbol] 
            if t.timestamp > cutoff_time
        ]
        
        # Single large trade alert
        if self.is_whale_trade(trade.volume_usdt):
            severity = self.get_severity(trade.volume_usdt)
            message = f"🐋 Large {trade.side} order: {trade.quantity:,.2f} {trade.symbol} (${trade.volume_usdt:,.0f}) on {trade.exchange}"
            
            alert = WhaleAlert(
                trade=trade,
                alert_type='single_trade',
                severity=severity,
                message=message,
                additional_context={
                    'price_impact': self._estimate_price_impact(trade),
                    'market_context': self._get_market_context(trade.symbol)
                }
            )
            alerts.append(alert)
        
        # Accumulation pattern detection
        recent_same_side = [
            t for t in self.recent_trades[trade.symbol]
            if t.side == trade.side and t.exchange == trade.exchange
        ]
        
        if len(recent_same_side) >= 2:
            total_volume = sum(t.volume_usdt for t in recent_same_side)
            
            if total_volume >= self.accumulation_threshold:
                avg_price = sum(t.price * t.quantity for t in recent_same_side) / sum(t.quantity for t in recent_same_side)
                total_quantity = sum(t.quantity for t in recent_same_side)
                
                message = f"📈 Accumulation detected: {len(recent_same_side)} {trade.side} orders totaling {total_quantity:,.2f} {trade.symbol} (${total_volume:,.0f}) on {trade.exchange}"
                
                alert = WhaleAlert(
                    trade=trade,
                    alert_type='accumulation',
                    severity='medium' if total_volume < self.large_whale_threshold else 'high',
                    message=message,
                    additional_context={
                        'trade_count': len(recent_same_side),
                        'total_volume_usdt': total_volume,
                        'avg_price': avg_price,
                        'time_window_sec': self.accumulation_window
                    }
                )
                alerts.append(alert)
        
        # Unusual activity detection (high frequency trading)
        if len(self.recent_trades[trade.symbol]) >= self.unusual_activity_threshold:
            total_volume = sum(t.volume_usdt for t in self.recent_trades[trade.symbol])
            
            if total_volume >= self.min_whale_threshold:
                message = f"⚡ Unusual activity: {len(self.recent_trades[trade.symbol])} trades in {self.accumulation_window}s totaling ${total_volume:,.0f} for {trade.symbol} on {trade.exchange}"
                
                alert = WhaleAlert(
                    trade=trade,
                    alert_type='unusual_activity',
                    severity='medium',
                    message=message,
                    additional_context={
                        'trade_frequency': len(self.recent_trades[trade.symbol]) / (self.accumulation_window / 60),  # trades per minute
                        'total_volume_usdt': total_volume
                    }
                )
                alerts.append(alert)
        
        return alerts
    
    def _estimate_price_impact(self, trade: WhaleTrade) -> Optional[float]:
        """Estimate potential price impact of trade"""
        # Simple heuristic based on trade size
        # In reality, this would require order book depth analysis
        volume_millions = trade.volume_usdt / 1_000_000
        
        # Rough estimate: larger trades have exponentially higher impact
        estimated_impact = min(volume_millions ** 0.5 * 0.01, 0.1)  # Max 10% impact
        return estimated_impact
    
    def _get_market_context(self, symbol: str) -> Dict[str, Any]:
        """Get market context for the symbol"""
        # This would typically fetch current market data
        # For now, return placeholder context
        return {
            'symbol': symbol,
            'context_timestamp': time.time()
        }


class WhaleTradeStream:
    """Stream processor for trade data from exchanges"""
    
    def __init__(self, detection_engine: WhaleDetectionEngine):
        self.detection_engine = detection_engine
        self.redis_client = None
        self.running = False
        
        # Stream configuration
        self.consumer_group = os.getenv('WHALE_CONSUMER_GROUP', 'whale_monitors')
        self.consumer_name = os.getenv('WHALE_CONSUMER_NAME', f'whale_{os.getpid()}')
        self.batch_size = int(os.getenv('WHALE_BATCH_SIZE', '10'))
    
    async def start(self):
        """Start processing trade streams"""
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        self.redis_client = redis.from_url(redis_url)
        
        self.running = True
        logger.info("Starting whale trade stream processor")
        
        # Start stream consumer
        await self.consume_trade_streams()
    
    async def consume_trade_streams(self):
        """Consume trade data from Redis streams"""
        while self.running:
            try:
                # Discover trade streams
                trade_streams = {}
                async for key in self.redis_client.scan_iter(match="trades.*"):
                    key_str = key.decode()
                    trade_streams[key_str] = '>'
                
                if not trade_streams:
                    await asyncio.sleep(1)
                    continue
                
                # Create consumer groups
                for stream_key in trade_streams.keys():
                    try:
                        await self.redis_client.xgroup_create(
                            stream_key, self.consumer_group, '$', mkstream=True
                        )
                    except redis.RedisError:
                        pass  # Group already exists
                
                # Read from streams
                stream_list = [(k, '>') for k in trade_streams.keys()]
                messages = await self.redis_client.xreadgroup(
                    self.consumer_group,
                    self.consumer_name,
                    streams=dict(stream_list),
                    count=self.batch_size,
                    block=1000
                )
                
                for stream, msgs in messages:
                    stream_str = stream.decode()
                    
                    for msg_id, fields in msgs:
                        try:
                            await self.process_trade_message(stream_str, fields)
                            
                            # Acknowledge message
                            await self.redis_client.xack(stream, self.consumer_group, msg_id)
                            
                        except Exception as e:
                            logger.error(f"Trade processing error: {e}")
                
            except Exception as e:
                logger.error(f"Stream consumer error: {e}")
                await asyncio.sleep(1)
    
    async def process_trade_message(self, stream: str, fields: Dict[bytes, bytes]):
        """Process individual trade message"""
        try:
            # Parse trade data
            trade_data = {k.decode(): v.decode() for k, v in fields.items()}
            
            # Extract exchange and symbol from stream name (e.g., "trades.binance.BTCUSDT")
            stream_parts = stream.split('.')
            if len(stream_parts) >= 3:
                exchange = stream_parts[1]
                symbol = stream_parts[2]
            else:
                exchange = trade_data.get('exchange', 'unknown')
                symbol = trade_data.get('symbol', 'UNKNOWN')
            
            # Create whale trade object
            trade = WhaleTrade(
                exchange=exchange,
                symbol=symbol,
                side=trade_data.get('side', 'unknown'),
                price=float(trade_data.get('price', 0)),
                quantity=float(trade_data.get('quantity', 0)),
                volume_usdt=float(trade_data.get('volume_usdt', 0)),
                timestamp=float(trade_data.get('timestamp', time.time())),
                trade_id=trade_data.get('trade_id'),
                trader_id=trade_data.get('trader_id')
            )
            
            # Skip if not a significant trade
            if trade.volume_usdt < self.detection_engine.min_whale_threshold:
                return
            
            # Detect patterns and generate alerts
            alerts = self.detection_engine.detect_patterns(trade)
            
            # Record metrics
            WHALE_TRADES_DETECTED.labels(
                exchange=trade.exchange, 
                symbol=trade.symbol, 
                side=trade.side
            ).inc()
            
            TRADE_VOLUME_HISTOGRAM.labels(
                exchange=trade.exchange, 
                symbol=trade.symbol
            ).observe(trade.volume_usdt)
            
            # Process alerts
            for alert in alerts:
                await self.handle_alert(alert)
            
        except Exception as e:
            logger.error(f"Trade message processing error: {e}")
    
    async def handle_alert(self, alert: WhaleAlert):
        """Handle whale alert"""
        try:
            # Record alert latency
            alert_latency = time.time() - alert.trade.timestamp
            WHALE_ALERT_LATENCY.labels(exchange=alert.trade.exchange).observe(alert_latency)
            
            logger.info(f"Whale alert [{alert.severity}]: {alert.message}")
            
            # Store alert in Redis
            await self.store_alert(alert)
            
            # Send notifications based on severity
            await self.send_notifications(alert)
            
        except Exception as e:
            logger.error(f"Alert handling error: {e}")
    
    async def store_alert(self, alert: WhaleAlert):
        """Store alert in Redis for persistence"""
        try:
            alert_data = {
                'trade': asdict(alert.trade),
                'alert_type': alert.alert_type,
                'severity': alert.severity,
                'message': alert.message,
                'additional_context': alert.additional_context,
                'timestamp': time.time()
            }
            
            # Store in alerts stream
            await self.redis_client.xadd(
                'alerts.whale_trades',
                alert_data,
                maxlen=int(os.getenv('WHALE_ALERTS_MAXLEN', '1000')),
                approximate=True
            )
            
            # Store in severity-specific stream
            severity_stream = f'alerts.whale_trades.{alert.severity}'
            await self.redis_client.xadd(
                severity_stream,
                alert_data,
                maxlen=500,
                approximate=True
            )
            
        except Exception as e:
            logger.error(f"Alert storage error: {e}")
    
    async def send_notifications(self, alert: WhaleAlert):
        """Send notifications based on alert severity"""
        try:
            # Only send notifications for medium+ severity
            if alert.severity in ['medium', 'high', 'critical']:
                # Send webhook notification
                await self.send_webhook_notification(alert)
                
                # Send email for high/critical severity
                if alert.severity in ['high', 'critical']:
                    await self.send_email_notification(alert)
                
                # Send Telegram for critical severity
                if alert.severity == 'critical':
                    await self.send_telegram_notification(alert)
            
        except Exception as e:
            logger.error(f"Notification sending error: {e}")
    
    async def send_webhook_notification(self, alert: WhaleAlert):
        """Send webhook notification"""
        webhook_url = os.getenv('WHALE_WEBHOOK_URL')
        if not webhook_url:
            return
        
        try:
            payload = {
                'alert_type': 'whale_trade',
                'severity': alert.severity,
                'message': alert.message,
                'trade': asdict(alert.trade),
                'timestamp': time.time()
            }
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(webhook_url, json=payload) as response:
                    if response.status == 200:
                        ALERT_NOTIFICATIONS_SENT.labels(channel='webhook').inc()
                    else:
                        logger.error(f"Webhook notification failed: HTTP {response.status}")
            
        except Exception as e:
            logger.error(f"Webhook notification error: {e}")
    
    async def send_email_notification(self, alert: WhaleAlert):
        """Send email notification"""
        smtp_server = os.getenv('SMTP_SERVER')
        smtp_port = int(os.getenv('SMTP_PORT', '587'))
        smtp_username = os.getenv('SMTP_USERNAME')
        smtp_password = os.getenv('SMTP_PASSWORD')
        email_recipients = os.getenv('WHALE_EMAIL_RECIPIENTS', '').split(',')
        
        if not all([smtp_server, smtp_username, smtp_password]) or not email_recipients[0]:
            return
        
        try:
            # Create email
            msg = MIMEMultipart()
            msg['From'] = smtp_username
            msg['To'] = ', '.join(email_recipients)
            msg['Subject'] = f"🐋 Whale Alert [{alert.severity.upper()}] - {alert.trade.symbol}"
            
            # Email body
            body = f"""
            Whale Trade Alert
            
            Severity: {alert.severity.upper()}
            Message: {alert.message}
            
            Trade Details:
            - Exchange: {alert.trade.exchange}
            - Symbol: {alert.trade.symbol}
            - Side: {alert.trade.side}
            - Price: ${alert.trade.price:,.4f}
            - Quantity: {alert.trade.quantity:,.4f}
            - Volume (USDT): ${alert.trade.volume_usdt:,.2f}
            - Time: {datetime.fromtimestamp(alert.trade.timestamp).isoformat()}
            
            Additional Context:
            {json.dumps(alert.additional_context, indent=2)}
            
            ---
            Sofia V2 Whale Monitoring System
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._send_email_sync, msg, smtp_server, smtp_port, smtp_username, smtp_password)
            
            ALERT_NOTIFICATIONS_SENT.labels(channel='email').inc()
            
        except Exception as e:
            logger.error(f"Email notification error: {e}")
    
    def _send_email_sync(self, msg, server, port, username, password):
        """Send email synchronously"""
        with smtplib.SMTP(server, port) as smtp:
            smtp.starttls()
            smtp.login(username, password)
            smtp.send_message(msg)
    
    async def send_telegram_notification(self, alert: WhaleAlert):
        """Send Telegram notification"""
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        if not bot_token or not chat_id:
            return
        
        try:
            message = f"""
🚨 <b>CRITICAL WHALE ALERT</b> 🚨

{alert.message}

💰 <b>Volume:</b> ${alert.trade.volume_usdt:,.0f}
📊 <b>Price:</b> ${alert.trade.price:,.4f}
📈 <b>Side:</b> {alert.trade.side.upper()}
🏢 <b>Exchange:</b> {alert.trade.exchange}
⏰ <b>Time:</b> {datetime.fromtimestamp(alert.trade.timestamp).strftime('%Y-%m-%d %H:%M:%S')}
            """.strip()
            
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                'chat_id': chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        ALERT_NOTIFICATIONS_SENT.labels(channel='telegram').inc()
                    else:
                        logger.error(f"Telegram notification failed: HTTP {response.status}")
            
        except Exception as e:
            logger.error(f"Telegram notification error: {e}")
    
    async def stop(self):
        """Stop stream processing"""
        self.running = False
        
        if self.redis_client:
            await self.redis_client.close()


class WhaleMonitor:
    """Main whale monitoring system"""
    
    def __init__(self):
        self.detection_engine = WhaleDetectionEngine()
        self.trade_stream = WhaleTradeStream(self.detection_engine)
        self.running = False
    
    async def start(self):
        """Start whale monitoring"""
        self.running = True
        logger.info("Starting whale monitoring system")
        
        # Start trade stream processor
        stream_task = asyncio.create_task(self.trade_stream.start())
        
        # Start cleanup task
        cleanup_task = asyncio.create_task(self.cleanup_loop())
        
        await asyncio.gather(stream_task, cleanup_task, return_exceptions=True)
    
    async def cleanup_loop(self):
        """Periodic cleanup of old data"""
        while self.running:
            try:
                await asyncio.sleep(self.detection_engine.cleanup_interval)
                
                current_time = time.time()
                cutoff_time = current_time - (24 * 3600)  # 24 hours
                
                # Clean old trades
                for symbol in list(self.detection_engine.recent_trades.keys()):
                    self.detection_engine.recent_trades[symbol] = [
                        trade for trade in self.detection_engine.recent_trades[symbol]
                        if trade.timestamp > cutoff_time
                    ]
                    
                    # Remove empty lists
                    if not self.detection_engine.recent_trades[symbol]:
                        del self.detection_engine.recent_trades[symbol]
                
                logger.info("Completed whale data cleanup")
                
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
    
    async def stop(self):
        """Stop monitoring"""
        self.running = False
        await self.trade_stream.stop()
        logger.info("Stopped whale monitoring system")
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get monitoring system health status"""
        return {
            'running': self.running,
            'detection_engine': {
                'min_whale_threshold': self.detection_engine.min_whale_threshold,
                'tracked_symbols': len(self.detection_engine.recent_trades),
                'total_recent_trades': sum(len(trades) for trades in self.detection_engine.recent_trades.values())
            },
            'stream_processor': {
                'running': self.trade_stream.running,
                'consumer_group': self.trade_stream.consumer_group,
                'consumer_name': self.trade_stream.consumer_name
            }
        }


async def main():
    """Main entry point"""
    logger.info("Starting Whale Trade Monitor")
    
    monitor = WhaleMonitor()
    
    try:
        await monitor.start()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        await monitor.stop()


if __name__ == "__main__":
    asyncio.run(main())