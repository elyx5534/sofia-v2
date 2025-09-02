from datetime import timezone

"""Cache management for the data-hub module."""

import hashlib
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, select

from .models import CandleCache, OHLCVData, SymbolCache, SymbolInfo
from .settings import settings


class CacheManager:
    """Manages caching operations for OHLCV and symbol data."""

    def __init__(self) -> None:
        """Initialize the cache manager."""
        self.engine = create_async_engine(
            settings.database_url,
            echo=False,
            future=True,
        )
        self.async_session = sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)
        self.ttl_seconds = settings.cache_ttl

    async def init_db(self) -> None:
        """Initialize database tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    async def close(self) -> None:
        """Close database connections."""
        await self.engine.dispose()

    def _generate_cache_key(self, **kwargs: str) -> str:
        """Generate a unique cache key from parameters."""
        key_parts = [f"{k}={v}" for k, v in sorted(kwargs.items()) if v is not None]
        key_string = "|".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()

    def _is_expired(self, created_at: datetime) -> bool:
        """Check if cached data has expired."""
        age = datetime.now(timezone.utc) - created_at
        return age > timedelta(seconds=self.ttl_seconds)

    async def get_ohlcv_cache(
        self,
        symbol: str,
        asset_type: str,
        timeframe: str,
        exchange: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[OHLCVData] | None:
        """Retrieve OHLCV data from cache if valid."""
        cache_key = self._generate_cache_key(
            symbol=symbol,
            asset_type=asset_type,
            timeframe=timeframe,
            exchange=exchange,
            start_date=start_date.isoformat() if start_date else None,
            end_date=end_date.isoformat() if end_date else None,
        )

        async with self.async_session() as session:
            # Query cached candles
            statement = select(CandleCache).where(CandleCache.cache_key == cache_key)
            results = await session.execute(statement)
            candles = results.scalars().all()

            if not candles:
                return None

            # Check if any candle has expired
            if any(self._is_expired(candle.created_at) for candle in candles):
                # Delete expired cache entries
                for candle in candles:
                    await session.delete(candle)
                await session.commit()
                return None

            # Convert to OHLCVData models
            return [
                OHLCVData(
                    timestamp=candle.timestamp,
                    open=candle.open,
                    high=candle.high,
                    low=candle.low,
                    close=candle.close,
                    volume=candle.volume,
                )
                for candle in sorted(candles, key=lambda x: x.timestamp)
            ]

    async def set_ohlcv_cache(
        self,
        symbol: str,
        asset_type: str,
        timeframe: str,
        data: list[OHLCVData],
        exchange: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> None:
        """Store OHLCV data in cache."""
        cache_key = self._generate_cache_key(
            symbol=symbol,
            asset_type=asset_type,
            timeframe=timeframe,
            exchange=exchange,
            start_date=start_date.isoformat() if start_date else None,
            end_date=end_date.isoformat() if end_date else None,
        )

        async with self.async_session() as session:
            # Delete existing cache entries with same key
            statement = select(CandleCache).where(CandleCache.cache_key == cache_key)
            results = await session.execute(statement)
            existing = results.scalars().all()
            for candle in existing:
                await session.delete(candle)

            # Insert new cache entries
            for ohlcv in data:
                candle = CandleCache(
                    symbol=symbol,
                    asset_type=asset_type,
                    timeframe=timeframe,
                    exchange=exchange,
                    timestamp=ohlcv.timestamp,
                    open=ohlcv.open,
                    high=ohlcv.high,
                    low=ohlcv.low,
                    close=ohlcv.close,
                    volume=ohlcv.volume,
                    cache_key=cache_key,
                )
                session.add(candle)

            await session.commit()

    async def get_symbol_cache(self, symbol: str, asset_type: str) -> SymbolInfo | None:
        """Retrieve symbol information from cache if valid."""
        async with self.async_session() as session:
            statement = (
                select(SymbolCache)
                .where(SymbolCache.symbol == symbol)
                .where(SymbolCache.asset_type == asset_type)
            )
            result = await session.execute(statement)
            cached_symbol = result.scalar_one_or_none()

            if not cached_symbol:
                return None

            if self._is_expired(cached_symbol.updated_at):
                await session.delete(cached_symbol)
                await session.commit()
                return None

            return SymbolInfo(
                symbol=cached_symbol.symbol,
                name=cached_symbol.name,
                asset_type=asset_type,  # type: ignore
                exchange=cached_symbol.exchange,
                currency=cached_symbol.currency,
                active=cached_symbol.active,
            )

    async def set_symbol_cache(self, symbol_info: SymbolInfo) -> None:
        """Store symbol information in cache."""
        async with self.async_session() as session:
            # Check if symbol exists
            statement = (
                select(SymbolCache)
                .where(SymbolCache.symbol == symbol_info.symbol)
                .where(SymbolCache.asset_type == symbol_info.asset_type)
            )
            result = await session.execute(statement)
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing
                existing.name = symbol_info.name
                existing.exchange = symbol_info.exchange
                existing.currency = symbol_info.currency
                existing.active = symbol_info.active
                existing.updated_at = datetime.now(timezone.utc)
            else:
                # Create new
                new_symbol = SymbolCache(
                    symbol=symbol_info.symbol,
                    name=symbol_info.name,
                    asset_type=symbol_info.asset_type,
                    exchange=symbol_info.exchange,
                    currency=symbol_info.currency,
                    active=symbol_info.active,
                )
                session.add(new_symbol)

            await session.commit()

    async def clear_expired_cache(self) -> int:
        """Clear all expired cache entries. Returns number of deleted entries."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(seconds=self.ttl_seconds)
        deleted_count = 0

        async with self.async_session() as session:
            # Clear expired candles
            statement = select(CandleCache).where(CandleCache.created_at < cutoff_time)
            results = await session.execute(statement)
            expired_candles = results.scalars().all()
            for candle in expired_candles:
                await session.delete(candle)
                deleted_count += 1

            # Clear expired symbols
            statement = select(SymbolCache).where(SymbolCache.updated_at < cutoff_time)
            results = await session.execute(statement)
            expired_symbols = results.scalars().all()
            for symbol in expired_symbols:
                await session.delete(symbol)
                deleted_count += 1

            await session.commit()

        return deleted_count


# Global cache manager instance
cache_manager = CacheManager()
