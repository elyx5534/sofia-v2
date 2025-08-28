from __future__ import annotations
from typing import Dict

# Single source of truth for symbol mapping
BINANCE_TO_UI: Dict[str, str] = {
    "BTCUSDT": "BTC/USDT",
    "ETHUSDT": "ETH/USDT",
    "SOLUSDT": "SOL/USDT",
    "BNBUSDT": "BNB/USDT",
    "ADAUSDT": "ADA/USDT",
    "XRPUSDT": "XRP/USDT",
    "DOTUSDT": "DOT/USDT",
    "AVAXUSDT": "AVAX/USDT",
}

UI_TO_BINANCE: Dict[str, str] = {v: k for k, v in BINANCE_TO_UI.items()}

def to_ui(sym: str) -> str:
    """Convert Binance symbol to UI format"""
    s = sym.replace("-", "").replace("_", "").upper()
    return BINANCE_TO_UI.get(s, sym.upper().replace("USDT", "/USDT"))

def to_binance(sym: str) -> str:
    """Convert UI symbol to Binance format"""
    s = sym.replace("-", "/").upper()
    return UI_TO_BINANCE.get(s, s.replace("/", ""))

def is_valid_symbol(sym: str) -> bool:
    """Check if symbol is valid in either format"""
    return sym in BINANCE_TO_UI or sym in UI_TO_BINANCE