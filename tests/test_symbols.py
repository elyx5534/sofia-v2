import pytest
from src.sofia.symbols import to_ui, to_binance, is_valid_symbol

def test_roundtrip():
    """Test symbol conversion roundtrip"""
    for ui in ["BTC/USDT", "ETH/USDT", "SOL/USDT"]:
        assert to_ui(to_binance(ui)) == ui

def test_binance_to_ui():
    """Test Binance to UI conversion"""
    assert to_ui("BTCUSDT") == "BTC/USDT"
    assert to_ui("ETHUSDT") == "ETH/USDT"
    assert to_ui("btcusdt") == "BTC/USDT"  # Case insensitive

def test_ui_to_binance():
    """Test UI to Binance conversion"""
    assert to_binance("BTC/USDT") == "BTCUSDT"
    assert to_binance("ETH/USDT") == "ETHUSDT"
    assert to_binance("BTC-USDT") == "BTCUSDT"  # Handle dashes

def test_invalid_passthrough():
    """Test invalid symbols pass through with reasonable defaults"""
    assert to_binance("ABC/XYZ") == "ABCXYZ"
    assert to_ui("ABCUSDT") == "ABC/USDT"

def test_is_valid_symbol():
    """Test symbol validation"""
    assert is_valid_symbol("BTCUSDT") is True
    assert is_valid_symbol("BTC/USDT") is True
    assert is_valid_symbol("INVALID") is False