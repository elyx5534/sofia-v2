"""
FX Rate Provider with caching and fallback
Provides live USDTRY rates for Turkish arbitrage
"""

import json
import logging
import time
from pathlib import Path
from typing import Dict, Optional

import ccxt

logger = logging.getLogger(__name__)


class FXProvider:
    """Foreign exchange rate provider"""

    def __init__(self):
        self.cache = {}
        self.cache_ttl = 30
        self.cache_file = Path("logs/fx_cache.json")
        self.fallback_rate = 34.5
        self._load_cache()

    def _load_cache(self):
        """Load cache from file"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file) as f:
                    self.cache = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load FX cache: {e}")
                self.cache = {}

    def _save_cache(self):
        """Save cache to file"""
        self.cache_file.parent.mkdir(exist_ok=True)
        try:
            with open(self.cache_file, "w") as f:
                json.dump(self.cache, f)
        except Exception as e:
            logger.warning(f"Failed to save FX cache: {e}")

    def get_usdtry(self, use_cache: bool = True) -> float:
        """Get USDTRY exchange rate"""
        pair = "USDTTRY"
        if use_cache and pair in self.cache:
            cached = self.cache[pair]
            if time.time() - cached.get("ts", 0) < self.cache_ttl:
                logger.debug(f"Using cached USDTRY: {cached['rate']}")
                return cached["rate"]
        rate = self._fetch_live_rate()
        if rate:
            self.cache[pair] = {"ts": time.time(), "rate": rate, "source": "live"}
            self._save_cache()
            logger.info(f"Live USDTRY: {rate}")
            return rate
        else:
            rate = self._get_fallback_rate()
            self.cache[pair] = {"ts": time.time(), "rate": rate, "source": "fallback"}
            self._save_cache()
            logger.warning(f"Using fallback USDTRY: {rate}")
            return rate

    def _fetch_live_rate(self) -> Optional[float]:
        """Fetch live rate from exchange"""
        try:
            exchange = ccxt.btcturk()
            ticker = exchange.fetch_ticker("USDT/TRY")
            return ticker["last"]
        except Exception as e1:
            logger.debug(f"BTCTurk USDTRY failed: {e1}")
            try:
                exchange = ccxt.binance()
                ticker = exchange.fetch_ticker("USDT/TRY")
                return ticker["last"]
            except Exception as e2:
                logger.debug(f"Binance USDTRY failed: {e2}")
        return None

    def _get_fallback_rate(self) -> float:
        """Get fallback rate from config or default"""
        try:
            config_file = Path("config/strategies/turkish_arbitrage.yaml")
            if config_file.exists():
                import yaml

                with open(config_file) as f:
                    config = yaml.safe_load(f)
                    return config.get("usdtry_rate", self.fallback_rate)
        except:
            pass
        return self.fallback_rate

    def get_rate_info(self) -> Dict:
        """Get detailed rate information"""
        pair = "USDTTRY"
        if pair in self.cache:
            cached = self.cache[pair]
            age = time.time() - cached.get("ts", 0)
            return {
                "rate": cached["rate"],
                "source": cached["source"],
                "age_seconds": age,
                "is_stale": age > self.cache_ttl,
            }
        else:
            return {
                "rate": self.fallback_rate,
                "source": "default",
                "age_seconds": 0,
                "is_stale": True,
            }


fx_provider = FXProvider()
