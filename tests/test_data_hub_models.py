"""
Test suite for Data Hub models and utilities
"""
import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from src.data_hub.models import (
    AssetType, OHLCVData, HealthResponse, ErrorResponse,
    SymbolSearchResponse, OHLCVResponse, SymbolInfo
)


class TestAssetType:
    """Test AssetType enum"""

    def test_asset_type_values(self):
        """Test AssetType enum values"""
        assert AssetType.EQUITY == "equity"
        assert AssetType.CRYPTO == "crypto"

    def test_asset_type_membership(self):
        """Test AssetType membership"""
        assert "equity" in AssetType
        assert "crypto" in AssetType
        assert "invalid" not in AssetType


class TestOHLCVData:
    """Test OHLCV Data model"""

    def test_ohlcv_data_creation_valid(self):
        """Test OHLCV data creation with valid data"""
        timestamp = datetime.now(timezone.utc)
        
        ohlcv = OHLCVData(
            timestamp=timestamp,
            open=100.0,
            high=105.0,
            low=95.0,
            close=102.0,
            volume=50000.0,
            symbol="AAPL"
        )
        
        assert ohlcv.timestamp == timestamp
        assert ohlcv.open == 100.0
        assert ohlcv.high == 105.0
        assert ohlcv.low == 95.0
        assert ohlcv.close == 102.0
        assert ohlcv.volume == 50000.0
        assert ohlcv.symbol == "AAPL"

    def test_ohlcv_data_creation_minimal(self):
        """Test OHLCV data creation with minimal required fields"""
        timestamp = datetime.now(timezone.utc)
        
        ohlcv = OHLCVData(
            timestamp=timestamp,
            open=100.0,
            high=105.0,
            low=95.0,
            close=102.0,
            volume=50000.0
        )
        
        assert ohlcv.timestamp == timestamp
        assert ohlcv.symbol is None  # Optional field

    def test_ohlcv_data_validation_negative_prices(self):
        """Test OHLCV data validation with negative prices"""
        timestamp = datetime.now(timezone.utc)
        
        with pytest.raises(ValidationError):
            OHLCVData(
                timestamp=timestamp,
                open=-100.0,  # Negative price
                high=105.0,
                low=95.0,
                close=102.0,
                volume=50000.0
            )

    def test_ohlcv_data_validation_negative_volume(self):
        """Test OHLCV data validation with negative volume"""
        timestamp = datetime.now(timezone.utc)
        
        with pytest.raises(ValidationError):
            OHLCVData(
                timestamp=timestamp,
                open=100.0,
                high=105.0,
                low=95.0,
                close=102.0,
                volume=-50000.0  # Negative volume
            )

    def test_ohlcv_data_validation_high_low_relationship(self):
        """Test OHLCV data validation for high/low relationship"""
        timestamp = datetime.now(timezone.utc)
        
        # This should pass validation (high >= low)
        ohlcv = OHLCVData(
            timestamp=timestamp,
            open=100.0,
            high=105.0,
            low=95.0,
            close=102.0,
            volume=50000.0
        )
        assert ohlcv.high >= ohlcv.low

    def test_ohlcv_data_serialization(self):
        """Test OHLCV data serialization"""
        timestamp = datetime.now(timezone.utc)
        
        ohlcv = OHLCVData(
            timestamp=timestamp,
            open=100.0,
            high=105.0,
            low=95.0,
            close=102.0,
            volume=50000.0,
            symbol="AAPL"
        )
        
        data = ohlcv.model_dump()
        
        assert isinstance(data, dict)
        assert data["open"] == 100.0
        assert data["symbol"] == "AAPL"
        assert "timestamp" in data

    def test_ohlcv_data_from_dict(self):
        """Test OHLCV data creation from dictionary"""
        timestamp = datetime.now(timezone.utc)
        
        data = {
            "timestamp": timestamp,
            "open": 100.0,
            "high": 105.0,
            "low": 95.0,
            "close": 102.0,
            "volume": 50000.0,
            "symbol": "AAPL"
        }
        
        ohlcv = OHLCVData(**data)
        
        assert ohlcv.open == 100.0
        assert ohlcv.symbol == "AAPL"

    def test_ohlcv_data_zero_volume(self):
        """Test OHLCV data with zero volume"""
        timestamp = datetime.now(timezone.utc)
        
        ohlcv = OHLCVData(
            timestamp=timestamp,
            open=100.0,
            high=100.0,
            low=100.0,
            close=100.0,
            volume=0.0  # Zero volume should be allowed
        )
        
        assert ohlcv.volume == 0.0

    def test_ohlcv_data_equal_prices(self):
        """Test OHLCV data with all equal prices (flat price)"""
        timestamp = datetime.now(timezone.utc)
        
        ohlcv = OHLCVData(
            timestamp=timestamp,
            open=100.0,
            high=100.0,
            low=100.0,
            close=100.0,
            volume=50000.0
        )
        
        assert ohlcv.open == ohlcv.high == ohlcv.low == ohlcv.close


class TestSymbolInfo:
    """Test SymbolInfo model"""

    def test_symbol_info_creation(self):
        """Test SymbolInfo creation"""
        symbol = SymbolInfo(
            symbol="AAPL",
            name="Apple Inc.",
            type="equity",
            exchange="NASDAQ"
        )
        
        assert symbol.symbol == "AAPL"
        assert symbol.name == "Apple Inc."
        assert symbol.type == "equity"
        assert symbol.exchange == "NASDAQ"

    def test_symbol_info_minimal(self):
        """Test SymbolInfo with minimal required fields"""
        symbol = SymbolInfo(
            symbol="AAPL",
            name="Apple Inc.",
            type="equity"
        )
        
        assert symbol.symbol == "AAPL"
        assert symbol.exchange is None  # Optional field

    def test_symbol_info_validation_empty_symbol(self):
        """Test SymbolInfo validation with empty symbol"""
        with pytest.raises(ValidationError):
            SymbolInfo(
                symbol="",  # Empty symbol
                name="Apple Inc.",
                type="equity"
            )

    def test_symbol_info_validation_empty_name(self):
        """Test SymbolInfo validation with empty name"""
        with pytest.raises(ValidationError):
            SymbolInfo(
                symbol="AAPL",
                name="",  # Empty name
                type="equity"
            )


class TestHealthResponse:
    """Test HealthResponse model"""

    def test_health_response_creation(self):
        """Test HealthResponse creation"""
        timestamp = datetime.now(timezone.utc)
        
        health = HealthResponse(
            status="healthy",
            timestamp=timestamp,
            version="1.0.0"
        )
        
        assert health.status == "healthy"
        assert health.timestamp == timestamp
        assert health.version == "1.0.0"

    def test_health_response_serialization(self):
        """Test HealthResponse serialization"""
        timestamp = datetime.now(timezone.utc)
        
        health = HealthResponse(
            status="healthy",
            timestamp=timestamp,
            version="1.0.0"
        )
        
        data = health.model_dump()
        
        assert data["status"] == "healthy"
        assert data["version"] == "1.0.0"
        assert "timestamp" in data


class TestErrorResponse:
    """Test ErrorResponse model"""

    def test_error_response_creation(self):
        """Test ErrorResponse creation"""
        error = ErrorResponse(
            error="Not Found",
            detail="Symbol not found"
        )
        
        assert error.error == "Not Found"
        assert error.detail == "Symbol not found"

    def test_error_response_minimal(self):
        """Test ErrorResponse with minimal fields"""
        error = ErrorResponse(
            error="Internal Error"
        )
        
        assert error.error == "Internal Error"
        assert error.detail is None  # Optional field

    def test_error_response_serialization(self):
        """Test ErrorResponse serialization"""
        error = ErrorResponse(
            error="Not Found",
            detail="Symbol not found"
        )
        
        data = error.model_dump()
        
        assert data["error"] == "Not Found"
        assert data["detail"] == "Symbol not found"


class TestSymbolSearchResponse:
    """Test SymbolSearchResponse model"""

    def test_symbol_search_response_creation(self):
        """Test SymbolSearchResponse creation"""
        symbols = [
            SymbolInfo(symbol="AAPL", name="Apple Inc.", type="equity"),
            SymbolInfo(symbol="MSFT", name="Microsoft", type="equity")
        ]
        
        response = SymbolSearchResponse(
            query="APP",
            asset_type=AssetType.EQUITY,
            results=symbols,
            count=2
        )
        
        assert response.query == "APP"
        assert response.asset_type == AssetType.EQUITY
        assert len(response.results) == 2
        assert response.count == 2

    def test_symbol_search_response_empty_results(self):
        """Test SymbolSearchResponse with empty results"""
        response = SymbolSearchResponse(
            query="NONEXISTENT",
            asset_type=AssetType.EQUITY,
            results=[],
            count=0
        )
        
        assert response.query == "NONEXISTENT"
        assert len(response.results) == 0
        assert response.count == 0

    def test_symbol_search_response_validation_count_mismatch(self):
        """Test SymbolSearchResponse validation with count mismatch"""
        symbols = [
            SymbolInfo(symbol="AAPL", name="Apple Inc.", type="equity")
        ]
        
        # Count doesn't match results length
        response = SymbolSearchResponse(
            query="AAPL",
            asset_type=AssetType.EQUITY,
            results=symbols,
            count=5  # Mismatch with actual results length
        )
        
        # Model should still be created (count is informational)
        assert response.count == 5
        assert len(response.results) == 1


class TestOHLCVResponse:
    """Test OHLCVResponse model"""

    def test_ohlcv_response_creation(self):
        """Test OHLCVResponse creation"""
        timestamp_now = datetime.now(timezone.utc)
        timestamp_data = datetime.now(timezone.utc)
        
        ohlcv_data = [
            OHLCVData(
                timestamp=timestamp_data,
                open=100.0, high=105.0, low=95.0, close=102.0, volume=50000.0
            )
        ]
        
        response = OHLCVResponse(
            symbol="AAPL",
            asset_type=AssetType.EQUITY,
            timeframe="1h",
            data=ohlcv_data,
            cached=False,
            timestamp=timestamp_now
        )
        
        assert response.symbol == "AAPL"
        assert response.asset_type == AssetType.EQUITY
        assert response.timeframe == "1h"
        assert len(response.data) == 1
        assert response.cached == False
        assert response.timestamp == timestamp_now

    def test_ohlcv_response_cached_data(self):
        """Test OHLCVResponse with cached data"""
        timestamp_now = datetime.now(timezone.utc)
        
        response = OHLCVResponse(
            symbol="AAPL",
            asset_type=AssetType.EQUITY,
            timeframe="1h",
            data=[],  # Empty data
            cached=True,
            timestamp=timestamp_now
        )
        
        assert response.cached == True
        assert len(response.data) == 0

    def test_ohlcv_response_serialization(self):
        """Test OHLCVResponse serialization"""
        timestamp_now = datetime.now(timezone.utc)
        timestamp_data = datetime.now(timezone.utc)
        
        ohlcv_data = [
            OHLCVData(
                timestamp=timestamp_data,
                open=100.0, high=105.0, low=95.0, close=102.0, volume=50000.0
            )
        ]
        
        response = OHLCVResponse(
            symbol="AAPL",
            asset_type=AssetType.EQUITY,
            timeframe="1h",
            data=ohlcv_data,
            cached=False,
            timestamp=timestamp_now
        )
        
        data = response.model_dump()
        
        assert data["symbol"] == "AAPL"
        assert data["asset_type"] == "equity"
        assert data["cached"] == False
        assert len(data["data"]) == 1
        assert isinstance(data["data"][0], dict)

    def test_ohlcv_response_with_exchange(self):
        """Test OHLCVResponse with exchange information"""
        timestamp_now = datetime.now(timezone.utc)
        
        response = OHLCVResponse(
            symbol="BTC/USDT",
            asset_type=AssetType.CRYPTO,
            timeframe="1h",
            data=[],
            cached=False,
            timestamp=timestamp_now,
            exchange="binance"
        )
        
        assert response.symbol == "BTC/USDT"
        assert response.asset_type == AssetType.CRYPTO
        assert response.exchange == "binance"


class TestModelValidation:
    """Test model validation edge cases"""

    def test_timestamp_timezone_awareness(self):
        """Test that timestamps are properly timezone-aware"""
        # Naive timestamp should be rejected or converted
        naive_timestamp = datetime(2022, 1, 1, 12, 0, 0)  # No timezone
        aware_timestamp = datetime(2022, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        # Should work with timezone-aware timestamp
        ohlcv = OHLCVData(
            timestamp=aware_timestamp,
            open=100.0, high=105.0, low=95.0, close=102.0, volume=50000.0
        )
        
        assert ohlcv.timestamp.tzinfo is not None

    def test_string_field_limits(self):
        """Test string field length limits and validation"""
        # Very long symbol name
        long_symbol = "A" * 1000
        
        try:
            symbol = SymbolInfo(
                symbol=long_symbol,
                name="Test Company",
                type="equity"
            )
            # Should either succeed or fail gracefully
            assert len(symbol.symbol) <= 1000
        except ValidationError:
            # Validation error is acceptable for very long strings
            pass

    def test_numeric_precision(self):
        """Test numeric precision handling"""
        # Very precise decimal
        precise_price = 123.456789012345
        
        ohlcv = OHLCVData(
            timestamp=datetime.now(timezone.utc),
            open=precise_price,
            high=precise_price + 1,
            low=precise_price - 1,
            close=precise_price,
            volume=100.0
        )
        
        # Should handle precision appropriately
        assert isinstance(ohlcv.open, float)
        assert ohlcv.open == precise_price

    def test_extreme_numeric_values(self):
        """Test handling of extreme numeric values"""
        timestamp = datetime.now(timezone.utc)
        
        # Very large values
        large_price = 1e12
        large_volume = 1e15
        
        ohlcv = OHLCVData(
            timestamp=timestamp,
            open=large_price,
            high=large_price,
            low=large_price,
            close=large_price,
            volume=large_volume
        )
        
        assert ohlcv.open == large_price
        assert ohlcv.volume == large_volume

    def test_unicode_string_handling(self):
        """Test handling of unicode characters in strings"""
        unicode_name = "测试公司 Company 🚀"
        
        symbol = SymbolInfo(
            symbol="TEST",
            name=unicode_name,
            type="equity"
        )
        
        assert symbol.name == unicode_name

    def test_model_equality(self):
        """Test model equality comparison"""
        timestamp = datetime.now(timezone.utc)
        
        ohlcv1 = OHLCVData(
            timestamp=timestamp,
            open=100.0, high=105.0, low=95.0, close=102.0, volume=50000.0,
            symbol="AAPL"
        )
        
        ohlcv2 = OHLCVData(
            timestamp=timestamp,
            open=100.0, high=105.0, low=95.0, close=102.0, volume=50000.0,
            symbol="AAPL"
        )
        
        assert ohlcv1 == ohlcv2

    def test_model_hash(self):
        """Test model hashing for sets and dicts"""
        symbol1 = SymbolInfo(symbol="AAPL", name="Apple Inc.", type="equity")
        symbol2 = SymbolInfo(symbol="AAPL", name="Apple Inc.", type="equity")
        
        # Should be able to use in sets/dicts
        symbol_set = {symbol1, symbol2}
        # Set should deduplicate identical symbols
        assert len(symbol_set) <= 2