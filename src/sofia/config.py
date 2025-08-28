from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if it exists
env_path = Path(".env")
if env_path.exists():
    load_dotenv(env_path)

def env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")

def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except:
        return default

def env_str(name: str, default: str) -> str:
    return os.getenv(name, default)

# WebSocket and REST configuration
WS_ENABLED = env_bool("SOFIA_WS_ENABLED", True)
REST_FALLBACK = env_bool("SOFIA_REST_FALLBACK", True)
STALE_TTL_SEC = env_int("SOFIA_STALE_TTL_SEC", 15)
CACHE_TTL_SEC = env_int("SOFIA_CACHE_TTL_SEC", 5)
REST_TIMEOUT_SEC = env_int("SOFIA_REST_TIMEOUT_SEC", 5)
WS_PING_SEC = env_int("SOFIA_WS_PING_SEC", 20)
WS_COMBINED = env_bool("SOFIA_WS_COMBINED", True)

# Symbols configuration
SYMBOLS_RAW = env_str("SOFIA_SYMBOLS", "BTC/USDT,ETH/USDT,SOL/USDT")
SYMBOLS = [s.strip() for s in SYMBOLS_RAW.split(",") if s.strip()]

# UI and environment
UI_LIVE = env_bool("SOFIA_UI_LIVE", False)
ENV = env_str("SOFIA_ENV", "dev")