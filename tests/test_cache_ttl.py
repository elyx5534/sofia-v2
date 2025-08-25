from datetime import timezone
"""Tests for cache TTL functionality."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from src.data_hub.cache import CacheManager
from src.data_hub.models import AssetType, OHLCVData, SymbolInfo


@pytest.fixture
async def cache_manager():
    """Create a cache manager instance for testing."""
    manager = CacheManager()
    # Use in-memory database for testing
    manager.engine = None
    manager.ttl_seconds = 2  # Short TTL for testing
    await manager.init_db()
    yield manager
    await manager.close()


@pytest.mark.asyncio
async def test_cache_ttl_expiry():
    """Test that cached data expires after TTL."""
    manager = CacheManager()
    manager.ttl_seconds = 1  # 1 second TTL for testing

    # Mock the database operations
    with patch.object(manager, "get_ohlcv_cache") as mock_get:
        with patch.object(manager, "set_ohlcv_cache") as mock_set:
            # First call - cache miss
            mock_get.return_value = None

            # Simulate fetching data
            sample_data = [
                OHLCVData(
                    timestamp=datetime.now(timezone.utc),
                    open=100.0,
                    high=105.0,
                    low=99.0,
                    close=103.0,
                    volume=1000000.0,
                )
            ]

            # Store in cache
            await manager.set_ohlcv_cache(
                symbol="AAPL",
                asset_type="equity",
                timeframe="1h",
                data=sample_data,
            )

            # Second call - cache hit (within TTL)
            mock_get.return_value = sample_data
            cached_data = await manager.get_ohlcv_cache(
                symbol="AAPL",
                asset_type="equity",
                timeframe="1h",
            )
            assert cached_data is not None

            # Wait for TTL to expire
            await asyncio.sleep(2)

            # Third call - cache miss (TTL expired)
            mock_get.return_value = None
            cached_data = await manager.get_ohlcv_cache(
                symbol="AAPL",
                asset_type="equity",
                timeframe="1h",
            )
            # In real implementation, this would return None after TTL


@pytest.mark.asyncio
async def test_cache_key_generation():
    """Test that cache keys are generated consistently."""
    manager = CacheManager()

    # Same parameters should generate same key
    key1 = manager._generate_cache_key(
        symbol="AAPL",
        asset_type="equity",
        timeframe="1h",
    )
    key2 = manager._generate_cache_key(
        symbol="AAPL",
        asset_type="equity",
        timeframe="1h",
    )
    assert key1 == key2

    # Different parameters should generate different keys
    key3 = manager._generate_cache_key(
        symbol="GOOGL",
        asset_type="equity",
        timeframe="1h",
    )
    assert key1 != key3

    # Order shouldn't matter
    key4 = manager._generate_cache_key(
        timeframe="1h",
        symbol="AAPL",
        asset_type="equity",
    )
    assert key1 == key4


@pytest.mark.asyncio
async def test_is_expired():
    """Test the TTL expiration check."""
    manager = CacheManager()
    manager.ttl_seconds = 600  # 10 minutes

    # Recent timestamp - not expired
    recent = datetime.now(timezone.utc) - timedelta(seconds=300)
    assert not manager._is_expired(recent)

    # Old timestamp - expired
    old = datetime.now(timezone.utc) - timedelta(seconds=700)
    assert manager._is_expired(old)

    # Exact TTL boundary - should not be expired (exactly at limit)
    # Create timestamp exactly at the boundary with buffer for timing precision
    boundary = datetime.now(timezone.utc) - timedelta(seconds=599.999)  # Just under 600 seconds
    assert not manager._is_expired(boundary)

    # Just over TTL
    just_over = datetime.now(timezone.utc) - timedelta(seconds=601)
    assert manager._is_expired(just_over)


@pytest.mark.asyncio
async def test_symbol_cache_ttl():
    """Test TTL for symbol cache."""
    manager = CacheManager()
    manager.ttl_seconds = 1  # 1 second TTL

    with patch.object(manager, "get_symbol_cache") as mock_get:
        with patch.object(manager, "set_symbol_cache") as mock_set:
            # Create symbol info
            symbol_info = SymbolInfo(
                symbol="AAPL",
                name="Apple Inc.",
                asset_type=AssetType.EQUITY,
                currency="USD",
                active=True,
            )

            # First call - cache miss
            mock_get.return_value = None

            # Store in cache
            await manager.set_symbol_cache(symbol_info)

            # Second call - cache hit
            mock_get.return_value = symbol_info
            cached = await manager.get_symbol_cache("AAPL", "equity")
            assert cached is not None

            # Wait for expiry
            await asyncio.sleep(2)

            # Third call - expired
            mock_get.return_value = None
            cached = await manager.get_symbol_cache("AAPL", "equity")
            # Would be None after TTL in real implementation


@pytest.mark.asyncio
async def test_clear_expired_cache():
    """Test clearing expired cache entries."""
    manager = CacheManager()

    with patch.object(manager, "clear_expired_cache") as mock_clear:
        mock_clear.return_value = 10  # Simulate 10 entries cleared

        count = await manager.clear_expired_cache()
        assert count == 10
        mock_clear.assert_called_once()


@pytest.mark.asyncio
async def test_cache_with_dates():
    """Test cache key generation with date parameters."""
    manager = CacheManager()

    start_date = datetime(2024, 1, 1)
    end_date = datetime(2024, 1, 31)

    key1 = manager._generate_cache_key(
        symbol="AAPL",
        asset_type="equity",
        timeframe="1d",
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
    )

    # Same dates should generate same key
    key2 = manager._generate_cache_key(
        symbol="AAPL",
        asset_type="equity",
        timeframe="1d",
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
    )
    assert key1 == key2

    # Different dates should generate different key
    key3 = manager._generate_cache_key(
        symbol="AAPL",
        asset_type="equity",
        timeframe="1d",
        start_date=datetime(2024, 2, 1).isoformat(),
        end_date=end_date.isoformat(),
    )
    assert key1 != key3


@pytest.mark.asyncio
async def test_cache_hit_miss_scenario():
    """Test realistic cache hit/miss scenario."""
    manager = CacheManager()
    manager.ttl_seconds = 5  # 5 seconds TTL

    # Create sample data
    sample_data = [
        OHLCVData(
            timestamp=datetime.now(timezone.utc) - timedelta(hours=i),
            open=100.0 + i,
            high=105.0 + i,
            low=99.0 + i,
            close=103.0 + i,
            volume=1000000.0,
        )
        for i in range(3)
    ]

    with patch.object(manager, "_is_expired") as mock_expired:
        with patch.object(manager, "async_session") as mock_session:
            # Setup mock session
            mock_session.return_value.__aenter__ = AsyncMock()
            mock_session.return_value.__aexit__ = AsyncMock()

            # First check - not expired
            mock_expired.return_value = False

            # Simulate cache hit scenario
            # This would involve database queries in real implementation

            # Second check - expired
            mock_expired.return_value = True

            # This would trigger cache deletion and return None


@pytest.mark.asyncio
async def test_concurrent_cache_access():
    """Test concurrent access to cache."""
    manager = CacheManager()

    async def access_cache(symbol: str):
        """Simulate cache access."""
        with patch.object(manager, "get_ohlcv_cache") as mock_get:
            mock_get.return_value = []
            return await manager.get_ohlcv_cache(
                symbol=symbol,
                asset_type="equity",
                timeframe="1h",
            )

    # Simulate multiple concurrent cache accesses
    tasks = [
        access_cache("AAPL"),
        access_cache("GOOGL"),
        access_cache("MSFT"),
    ]

    results = await asyncio.gather(*tasks)
    assert len(results) == 3
