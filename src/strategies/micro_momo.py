"""
Micro momentum strategy for observable trades with real data.
"""

import asyncio
import time
import logging
from typing import Dict, Optional
from datetime import datetime, timezone
import os

from src.services.price_service_real import get_price_service
from src.trading.paper_engine import get_paper_engine

logger = logging.getLogger(__name__)

class MicroMomentumStrategy:
    """Micro momentum breakout strategy for testing with real data."""
    
    def __init__(self):
        # Thresholds from environment
        self.btc_threshold = float(os.getenv("SOFIA_MICRO_TH_PCT_BTC", "0.0008"))
        self.eth_threshold = float(os.getenv("SOFIA_MICRO_TH_PCT_ETH", "0.0008"))
        self.sol_threshold = float(os.getenv("SOFIA_MICRO_TH_PCT_SOL", "0.0015"))
        
        # Trade parameters
        self.trade_usd = float(os.getenv("SOFIA_TRADE_USD", "100"))
        self.cooldown_seconds = int(os.getenv("SOFIA_COOLDOWN_SECONDS", "20"))
        
        # State tracking
        self.last_prices = {}  # symbol -> price
        self.last_trade_times = {}  # symbol -> timestamp
        self.enabled = False
        self.running = False
        
        # Position limits
        self.max_positions_per_symbol = 1
        self.max_total_notional = 1000.0  # $1000 max total exposure
        
    async def start(self):
        """Start the strategy."""
        if self.running:
            return {"status": "already_running"}
        
        self.enabled = True
        self.running = True
        
        # Start monitoring loop
        asyncio.create_task(self._monitoring_loop())
        
        logger.info("Micro momentum strategy started")
        return {
            "status": "started",
            "thresholds": {
                "BTCUSDT": self.btc_threshold,
                "ETHUSDT": self.eth_threshold, 
                "SOLUSDT": self.sol_threshold
            },
            "trade_usd": self.trade_usd,
            "cooldown_seconds": self.cooldown_seconds
        }
    
    def stop(self):
        """Stop the strategy."""
        self.enabled = False
        self.running = False
        logger.info("Micro momentum strategy stopped")
        
        return {"status": "stopped"}
    
    async def _monitoring_loop(self):
        """Main strategy monitoring loop."""
        try:
            price_service = await get_price_service()
            symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
            
            while self.enabled:
                for symbol in symbols:
                    try:
                        await self._check_symbol_for_signal(symbol, price_service)
                    except Exception as e:
                        logger.error(f"Strategy error for {symbol}: {e}")
                
                # Wait before next check
                await asyncio.sleep(5)  # Check every 5 seconds
                
        except Exception as e:
            logger.error(f"Strategy monitoring loop error: {e}")
        finally:
            self.running = False
    
    async def _check_symbol_for_signal(self, symbol: str, price_service):
        """Check symbol for momentum signal."""
        
        # Get current price
        price_data = await price_service.get_price(symbol)
        if not price_data:
            return
        
        current_price = price_data["price"]
        
        # Check if we have previous price for comparison
        if symbol not in self.last_prices:
            self.last_prices[symbol] = current_price
            return
        
        last_price = self.last_prices[symbol]
        
        # Calculate price change percentage
        if last_price > 0:
            price_change_pct = abs((current_price - last_price) / last_price)
        else:
            price_change_pct = 0.0
        
        # Get threshold for symbol
        threshold = self._get_threshold(symbol)
        
        # Check for momentum signal
        if price_change_pct >= threshold:
            # Check cooldown
            if symbol in self.last_trade_times:
                time_since_last = time.time() - self.last_trade_times[symbol]
                if time_since_last < self.cooldown_seconds:
                    return
            
            # Check position limits
            if not await self._can_open_position(symbol):
                return
            
            # Determine trade direction (momentum following)
            side = "buy" if current_price > last_price else "sell"
            
            # Execute trade
            await self._execute_momentum_trade(symbol, side, current_price, price_change_pct)
        
        # Update last price
        self.last_prices[symbol] = current_price
    
    def _get_threshold(self, symbol: str) -> float:
        """Get momentum threshold for symbol."""
        if "BTC" in symbol:
            return self.btc_threshold
        elif "ETH" in symbol:
            return self.eth_threshold
        elif "SOL" in symbol:
            return self.sol_threshold
        else:
            return 0.001  # Default 0.1%
    
    async def _can_open_position(self, symbol: str) -> bool:
        """Check if we can open a new position."""
        # Get current positions
        engine = get_paper_engine()
        portfolio = await engine.get_portfolio_summary()
        
        positions = portfolio.get("positions", {})
        
        # Check per-symbol position limit
        if symbol in positions and positions[symbol]["quantity"] != 0:
            return False  # Already have position in this symbol
        
        # Check total notional exposure
        total_notional = sum(
            abs(pos["market_value"]) for pos in positions.values()
        )
        
        if total_notional + self.trade_usd > self.max_total_notional:
            return False  # Would exceed total exposure limit
        
        return True
    
    async def _execute_momentum_trade(self, symbol: str, side: str, price: float, momentum_pct: float):
        """Execute momentum trade."""
        try:
            engine = get_paper_engine()
            
            # Place order
            result = await engine.place_order(
                symbol=symbol,
                side=side,
                usd_amount=self.trade_usd,
                strategy="micro_momentum"
            )
            
            if result["status"] == "success":
                self.last_trade_times[symbol] = time.time()
                logger.info(f"Momentum trade: {side.upper()} ${self.trade_usd} {symbol} @ ${price:.2f} (momentum: {momentum_pct:.4f})")
            else:
                logger.warning(f"Momentum trade failed: {result['message']}")
                
        except Exception as e:
            logger.error(f"Momentum trade execution error: {e}")
    
    def get_status(self) -> Dict:
        """Get strategy status."""
        return {
            "enabled": self.enabled,
            "running": self.running,
            "thresholds": {
                "BTCUSDT": self.btc_threshold,
                "ETHUSDT": self.eth_threshold,
                "SOLUSDT": self.sol_threshold
            },
            "trade_usd": self.trade_usd,
            "cooldown_seconds": self.cooldown_seconds,
            "last_trade_times": self.last_trade_times.copy(),
            "max_total_notional": self.max_total_notional,
            "last_prices": self.last_prices.copy()
        }


# Global strategy instance
_micro_momentum = None

def get_micro_momentum_strategy() -> MicroMomentumStrategy:
    """Get or create the global micro momentum strategy."""
    global _micro_momentum
    if _micro_momentum is None:
        _micro_momentum = MicroMomentumStrategy()
    return _micro_momentum