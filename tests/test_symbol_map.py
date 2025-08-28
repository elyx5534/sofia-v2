"""
Test symbol mapping configuration
"""

import pytest
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.symbols import get_ws_sym, get_rest_sym, symbol_mapper


def test_symbol_mapping_exists():
    """Test that symbol mappings exist for configured symbols"""
    
    # Test UI to WS mapping
    test_cases = [
        ('BTC/USDT', 'BTCUSDT'),
        ('ETH/USDT', 'ETHUSDT'),
        ('SOL/USDT', 'SOLUSDT'),
    ]
    
    for ui_sym, expected_ws in test_cases:
        ws_sym = get_ws_sym(ui_sym)
        assert ws_sym == expected_ws, f"UI symbol {ui_sym} should map to WS {expected_ws}, got {ws_sym}"
        print(f"OK: {ui_sym} -> WS: {ws_sym}")
    
    # Test UI to REST mapping
    for ui_sym, expected_rest in test_cases:
        rest_sym = get_rest_sym(ui_sym)
        assert rest_sym == expected_rest, f"UI symbol {ui_sym} should map to REST {expected_rest}, got {rest_sym}"
        print(f"OK: {ui_sym} -> REST: {rest_sym}")


def test_reverse_mapping():
    """Test reverse mapping from WS/REST to UI"""
    
    test_cases = [
        ('BTCUSDT', 'BTC/USDT'),
        ('ETHUSDT', 'ETH/USDT'),
        ('SOLUSDT', 'SOL/USDT'),
    ]
    
    for ws_sym, expected_ui in test_cases:
        ui_sym = symbol_mapper.get_ui_sym(ws_sym)
        assert ui_sym == expected_ui, f"WS symbol {ws_sym} should map to UI {expected_ui}, got {ui_sym}"
        print(f"OK: {ws_sym} -> UI: {ui_sym}")


def test_unknown_symbol():
    """Test handling of unknown symbols"""
    
    unknown = 'UNKNOWN/PAIR'
    assert get_ws_sym(unknown) is None
    assert get_rest_sym(unknown) is None
    print(f"OK: Unknown symbol {unknown} returns None")


if __name__ == "__main__":
    test_symbol_mapping_exists()
    test_reverse_mapping()
    test_unknown_symbol()
    print("\nAll symbol mapping tests passed!")