"""
Sofia V2 Realtime DataHub - Parquet Storage
High-performance columnar storage for market data
"""

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import structlog

from ..bus import EventBus, EventType
from ..config import Settings

logger = structlog.get_logger(__name__)


class ParquetStore:
    """
    Parquet-based storage with automatic rotation and compression
    Optimized for time-series market data
    """

    def __init__(self, event_bus: EventBus, settings: Settings):
        self.event_bus = event_bus
        self.settings = settings

        # Storage configuration
        storage_config = settings.get_storage_config()
        parquet_config = storage_config.get("parquet", {})

        self.enabled = parquet_config.get("enabled", True)
        self.data_dir = Path(settings.data_dir)
        self.rotation_hours = parquet_config.get("rotation_hours", 24)
        self.max_retention_days = parquet_config.get("max_retention_days", 30)
        self.compression = parquet_config.get("compression", "snappy")
        self.partition_cols = parquet_config.get("partition_cols", ["date", "exchange"])

        # Buffer management
        self.buffer_size = 1000  # Records before flush
        self.flush_interval = 300  # Seconds between forced flushes

        # Data buffers
        self.trade_buffer: List[Dict[str, Any]] = []
        self.orderbook_buffer: List[Dict[str, Any]] = []
        self.liquidation_buffer: List[Dict[str, Any]] = []
        self.news_buffer: List[Dict[str, Any]] = []
        self.alert_buffer: List[Dict[str, Any]] = []

        # Rotation tracking
        self.current_rotation = self._get_current_rotation()
        self.last_flush = datetime.now(timezone.utc)

        if self.enabled:
            self._setup_directories()
            self._setup_event_subscriptions()
            logger.info(
                "Parquet store initialized",
                data_dir=str(self.data_dir),
                rotation_hours=self.rotation_hours,
                compression=self.compression,
            )

    def _setup_directories(self):
        """Create directory structure"""
        directories = ["trades", "orderbook", "liquidations", "news", "alerts"]

        for directory in directories:
            dir_path = self.data_dir / directory
            dir_path.mkdir(parents=True, exist_ok=True)

    def _setup_event_subscriptions(self):
        """Subscribe to relevant events"""
        self.event_bus.subscribe(EventType.TRADE, self._store_trade)
        self.event_bus.subscribe(EventType.ORDERBOOK, self._store_orderbook)
        self.event_bus.subscribe(EventType.LIQUIDATION, self._store_liquidation)
        self.event_bus.subscribe(EventType.NEWS, self._store_news)
        self.event_bus.subscribe(EventType.BIG_TRADE, self._store_alert)
        self.event_bus.subscribe(EventType.LIQ_SPIKE, self._store_alert)
        self.event_bus.subscribe(EventType.VOLUME_SURGE, self._store_alert)

    def _get_current_rotation(self) -> str:
        """Get current rotation identifier"""
        now = datetime.now(timezone.utc)
        rotation_timestamp = now.replace(minute=0, second=0, microsecond=0)

        # Round down to rotation boundary
        hours_since_epoch = int(rotation_timestamp.timestamp()) // 3600
        rotation_boundary = (hours_since_epoch // self.rotation_hours) * self.rotation_hours
        rotation_time = datetime.fromtimestamp(rotation_boundary * 3600, tz=timezone.utc)

        return rotation_time.strftime("%Y%m%d_%H")

    def _should_rotate(self) -> bool:
        """Check if rotation is needed"""
        return self.current_rotation != self._get_current_rotation()

    async def _store_trade(self, trade_data: Dict[str, Any]):
        """Store trade data"""
        if not self.enabled:
            return

        # Normalize and enrich trade data
        enriched_trade = {
            **trade_data,
            "date": datetime.now(timezone.utc).date().isoformat(),
            "hour": datetime.now(timezone.utc).hour,
            "data_type": "trade",
        }

        self.trade_buffer.append(enriched_trade)

        if len(self.trade_buffer) >= self.buffer_size:
            await self._flush_trades()

    async def _store_orderbook(self, orderbook_data: Dict[str, Any]):
        """Store orderbook data (sampled to reduce volume)"""
        if not self.enabled:
            return

        # Sample orderbook data (e.g., every 10th update)
        if len(self.orderbook_buffer) % 10 == 0:
            enriched_orderbook = {
                **orderbook_data,
                "date": datetime.now(timezone.utc).date().isoformat(),
                "hour": datetime.now(timezone.utc).hour,
                "data_type": "orderbook",
                "bid_count": len(orderbook_data.get("bids", [])),
                "ask_count": len(orderbook_data.get("asks", [])),
                "spread": self._calculate_spread(orderbook_data),
            }

            self.orderbook_buffer.append(enriched_orderbook)

        if len(self.orderbook_buffer) >= self.buffer_size // 10:  # Less frequent flush
            await self._flush_orderbooks()

    async def _store_liquidation(self, liquidation_data: Dict[str, Any]):
        """Store liquidation data"""
        if not self.enabled:
            return

        enriched_liquidation = {
            **liquidation_data,
            "date": datetime.now(timezone.utc).date().isoformat(),
            "hour": datetime.now(timezone.utc).hour,
            "data_type": "liquidation",
        }

        self.liquidation_buffer.append(enriched_liquidation)

        if len(self.liquidation_buffer) >= self.buffer_size // 2:  # More frequent flush
            await self._flush_liquidations()

    async def _store_news(self, news_data: Dict[str, Any]):
        """Store news data"""
        if not self.enabled:
            return

        enriched_news = {
            **news_data,
            "date": datetime.now(timezone.utc).date().isoformat(),
            "hour": datetime.now(timezone.utc).hour,
            "data_type": "news",
        }

        self.news_buffer.append(enriched_news)

        if len(self.news_buffer) >= self.buffer_size // 5:
            await self._flush_news()

    async def _store_alert(self, alert_data: Dict[str, Any]):
        """Store alert data (big trades, liquidation spikes, etc.)"""
        if not self.enabled:
            return

        enriched_alert = {
            **alert_data,
            "date": datetime.now(timezone.utc).date().isoformat(),
            "hour": datetime.now(timezone.utc).hour,
            "data_type": "alert",
        }

        self.alert_buffer.append(enriched_alert)

        if len(self.alert_buffer) >= self.buffer_size // 10:
            await self._flush_alerts()

    def _calculate_spread(self, orderbook_data: Dict[str, Any]) -> Optional[float]:
        """Calculate bid-ask spread"""
        try:
            bids = orderbook_data.get("bids", [])
            asks = orderbook_data.get("asks", [])

            if bids and asks:
                best_bid = float(bids[0][0])
                best_ask = float(asks[0][0])
                return best_ask - best_bid

            return None
        except (IndexError, ValueError, TypeError):
            return None

    async def _flush_trades(self):
        """Flush trade buffer to parquet file"""
        if not self.trade_buffer:
            return

        try:
            df = pd.DataFrame(self.trade_buffer)

            # Check for rotation
            if self._should_rotate():
                await self._rotate_files()

            file_path = self.data_dir / "trades" / f"trades_{self.current_rotation}.parquet"

            if file_path.exists():
                # Append to existing file
                existing_df = pd.read_parquet(file_path)
                df = pd.concat([existing_df, df], ignore_index=True)

            df.to_parquet(file_path, compression=self.compression, index=False)

            logger.debug(
                "Flushed trades to parquet", count=len(self.trade_buffer), file=str(file_path)
            )
            self.trade_buffer.clear()

        except Exception as e:
            logger.error("Failed to flush trades", error=str(e))

    async def _flush_orderbooks(self):
        """Flush orderbook buffer to parquet file"""
        if not self.orderbook_buffer:
            return

        try:
            # Flatten orderbook data for parquet storage
            flattened_data = []
            for ob in self.orderbook_buffer:
                # Store summary instead of full book
                flattened_data.append(
                    {
                        "symbol": ob.get("symbol"),
                        "exchange": ob.get("exchange"),
                        "timestamp": ob.get("timestamp"),
                        "date": ob.get("date"),
                        "hour": ob.get("hour"),
                        "best_bid": ob.get("bids", [[0, 0]])[0][0] if ob.get("bids") else None,
                        "best_ask": ob.get("asks", [[0, 0]])[0][0] if ob.get("asks") else None,
                        "bid_volume": sum(bid[1] for bid in ob.get("bids", [])[:5]),  # Top 5 levels
                        "ask_volume": sum(ask[1] for ask in ob.get("asks", [])[:5]),
                        "spread": ob.get("spread"),
                        "data_type": "orderbook",
                    }
                )

            df = pd.DataFrame(flattened_data)

            if self._should_rotate():
                await self._rotate_files()

            file_path = self.data_dir / "orderbook" / f"orderbook_{self.current_rotation}.parquet"

            if file_path.exists():
                existing_df = pd.read_parquet(file_path)
                df = pd.concat([existing_df, df], ignore_index=True)

            df.to_parquet(file_path, compression=self.compression, index=False)

            logger.debug(
                "Flushed orderbooks to parquet",
                count=len(self.orderbook_buffer),
                file=str(file_path),
            )
            self.orderbook_buffer.clear()

        except Exception as e:
            logger.error("Failed to flush orderbooks", error=str(e))

    async def _flush_liquidations(self):
        """Flush liquidation buffer to parquet file"""
        if not self.liquidation_buffer:
            return

        try:
            df = pd.DataFrame(self.liquidation_buffer)

            if self._should_rotate():
                await self._rotate_files()

            file_path = (
                self.data_dir / "liquidations" / f"liquidations_{self.current_rotation}.parquet"
            )

            if file_path.exists():
                existing_df = pd.read_parquet(file_path)
                df = pd.concat([existing_df, df], ignore_index=True)

            df.to_parquet(file_path, compression=self.compression, index=False)

            logger.debug(
                "Flushed liquidations to parquet",
                count=len(self.liquidation_buffer),
                file=str(file_path),
            )
            self.liquidation_buffer.clear()

        except Exception as e:
            logger.error("Failed to flush liquidations", error=str(e))

    async def _flush_news(self):
        """Flush news buffer to parquet file"""
        if not self.news_buffer:
            return

        try:
            df = pd.DataFrame(self.news_buffer)

            if self._should_rotate():
                await self._rotate_files()

            file_path = self.data_dir / "news" / f"news_{self.current_rotation}.parquet"

            if file_path.exists():
                existing_df = pd.read_parquet(file_path)
                df = pd.concat([existing_df, df], ignore_index=True)

            df.to_parquet(file_path, compression=self.compression, index=False)

            logger.debug(
                "Flushed news to parquet", count=len(self.news_buffer), file=str(file_path)
            )
            self.news_buffer.clear()

        except Exception as e:
            logger.error("Failed to flush news", error=str(e))

    async def _flush_alerts(self):
        """Flush alert buffer to parquet file"""
        if not self.alert_buffer:
            return

        try:
            df = pd.DataFrame(self.alert_buffer)

            if self._should_rotate():
                await self._rotate_files()

            file_path = self.data_dir / "alerts" / f"alerts_{self.current_rotation}.parquet"

            if file_path.exists():
                existing_df = pd.read_parquet(file_path)
                df = pd.concat([existing_df, df], ignore_index=True)

            df.to_parquet(file_path, compression=self.compression, index=False)

            logger.debug(
                "Flushed alerts to parquet", count=len(self.alert_buffer), file=str(file_path)
            )
            self.alert_buffer.clear()

        except Exception as e:
            logger.error("Failed to flush alerts", error=str(e))

    async def _rotate_files(self):
        """Rotate to new time-based partition"""
        old_rotation = self.current_rotation
        self.current_rotation = self._get_current_rotation()

        logger.info(
            "Rotating parquet files", old_rotation=old_rotation, new_rotation=self.current_rotation
        )

        # Clean up old files
        await self._cleanup_old_files()

    async def _cleanup_old_files(self):
        """Remove files older than retention period"""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.max_retention_days)

            for data_type in ["trades", "orderbook", "liquidations", "news", "alerts"]:
                data_dir = self.data_dir / data_type

                if not data_dir.exists():
                    continue

                for file_path in data_dir.glob("*.parquet"):
                    # Extract date from filename (format: type_YYYYMMDD_HH.parquet)
                    try:
                        filename = file_path.stem
                        date_part = filename.split("_")[-2]  # Get YYYYMMDD part
                        file_date = datetime.strptime(date_part, "%Y%m%d").replace(
                            tzinfo=timezone.utc
                        )

                        if file_date < cutoff_date:
                            file_path.unlink()
                            logger.info("Deleted old parquet file", file=str(file_path))

                    except (ValueError, IndexError):
                        # Skip files that don't match expected format
                        continue

        except Exception as e:
            logger.error("Failed to cleanup old files", error=str(e))

    async def flush_all_buffers(self):
        """Force flush all buffers"""
        await asyncio.gather(
            self._flush_trades(),
            self._flush_orderbooks(),
            self._flush_liquidations(),
            self._flush_news(),
            self._flush_alerts(),
            return_exceptions=True,
        )

        logger.info("Force flushed all parquet buffers")

    async def periodic_flush(self):
        """Periodic flush task"""
        while True:
            try:
                await asyncio.sleep(self.flush_interval)

                now = datetime.now(timezone.utc)
                time_since_last_flush = (now - self.last_flush).seconds

                if time_since_last_flush >= self.flush_interval:
                    await self.flush_all_buffers()
                    self.last_flush = now

            except asyncio.CancelledError:
                logger.info("Periodic flush cancelled")
                break
            except Exception as e:
                logger.error("Error in periodic flush", error=str(e))
                await asyncio.sleep(60)  # Back off on error

    def get_status(self) -> Dict[str, Any]:
        """Get storage status"""
        return {
            "enabled": self.enabled,
            "data_directory": str(self.data_dir),
            "current_rotation": self.current_rotation,
            "buffer_sizes": {
                "trades": len(self.trade_buffer),
                "orderbooks": len(self.orderbook_buffer),
                "liquidations": len(self.liquidation_buffer),
                "news": len(self.news_buffer),
                "alerts": len(self.alert_buffer),
            },
            "compression": self.compression,
            "rotation_hours": self.rotation_hours,
            "max_retention_days": self.max_retention_days,
        }
