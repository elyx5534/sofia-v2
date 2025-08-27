"""
Unified Portfolio Memory System
Single source of truth for all portfolio data across Sofia V2
"""

import asyncio
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
import logging
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

@dataclass
class PortfolioState:
    """Unified portfolio state"""
    user_id: str = "demo"
    total_balance: float = 100000.0
    available_cash: float = 50000.0
    positions_value: float = 50000.0
    daily_pnl: float = 0.0
    total_pnl: float = 0.0
    daily_pnl_percentage: float = 0.0
    total_pnl_percentage: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    active_positions: int = 0
    last_updated: datetime = None
    
    def __post_init__(self):
        if self.last_updated is None:
            self.last_updated = datetime.now(timezone.utc)
    
    def to_dict(self):
        return {
            **asdict(self),
            'last_updated': self.last_updated.isoformat()
        }
    
    def update_totals(self):
        """Update calculated fields"""
        self.positions_value = self.total_balance - self.available_cash
        self.daily_pnl_percentage = (self.daily_pnl / self.total_balance) * 100 if self.total_balance > 0 else 0
        self.total_pnl_percentage = ((self.total_balance - 100000) / 100000) * 100  # Assuming $100k start
        self.win_rate = (self.winning_trades / self.total_trades) if self.total_trades > 0 else 0
        self.last_updated = datetime.now(timezone.utc)

class UnifiedPortfolioSystem:
    """Single source of truth for portfolio data"""
    
    def __init__(self):
        self.portfolio_state = PortfolioState()
        self.is_running = False
        self.update_interval = 30  # Update every 30 seconds
        
        # Try to integrate with AI engines
        self.ai_integration_enabled = False
        self.paper_engine = None
        self.portfolio_manager = None
        
    async def start(self):
        """Start the unified portfolio system"""
        if self.is_running:
            return
            
        self.is_running = True
        
        # Try to connect to AI engines
        try:
            import sys
            import os
            sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
            
            from src.trading.paper_trading_engine import paper_engine
            from src.portfolio.advanced_portfolio_manager import portfolio_manager
            
            self.paper_engine = paper_engine
            self.portfolio_manager = portfolio_manager
            self.ai_integration_enabled = True
            
            logger.info("AI engine integration enabled")
            
        except ImportError:
            logger.info("AI engines not available, using simulation")
            self.ai_integration_enabled = False
        
        # Start update loop
        asyncio.create_task(self._update_loop())
        
        logger.info("Unified Portfolio System started")
        
    async def stop(self):
        """Stop the system"""
        self.is_running = False
        logger.info("Unified Portfolio System stopped")
        
    async def get_portfolio_data(self, user_id: str = "demo") -> Dict:
        """Get current portfolio data"""
        if self.ai_integration_enabled and self.paper_engine:
            # Try to get data from AI engines
            try:
                ai_portfolio = self.paper_engine.get_portfolio_summary(user_id)
                if ai_portfolio:
                    # Update our state with AI data
                    self.portfolio_state.total_balance = ai_portfolio["total_value"]
                    self.portfolio_state.available_cash = ai_portfolio["balance"]
                    self.portfolio_state.daily_pnl = ai_portfolio["total_pnl"] 
                    self.portfolio_state.total_pnl = ai_portfolio["total_pnl"]
                    self.portfolio_state.total_trades = ai_portfolio["total_trades"]
                    self.portfolio_state.winning_trades = ai_portfolio["winning_trades"]
                    self.portfolio_state.active_positions = len(ai_portfolio.get("positions", []))
                    
                    self.portfolio_state.update_totals()
                    
                    logger.info(f"Updated portfolio from AI: ${self.portfolio_state.total_balance}")
            except Exception as e:
                logger.error(f"Error getting AI portfolio data: {e}")
        
        # Return current state
        return self.portfolio_state.to_dict()
    
    async def _update_loop(self):
        """Background update loop"""
        while self.is_running:
            try:
                if not self.ai_integration_enabled:
                    # Simulate realistic portfolio changes
                    self._simulate_portfolio_changes()
                
                await asyncio.sleep(self.update_interval)
                
            except Exception as e:
                logger.error(f"Error in portfolio update loop: {e}")
                await asyncio.sleep(60)
    
    def _simulate_portfolio_changes(self):
        """Simulate realistic portfolio changes for demo"""
        import random
        
        # Small realistic changes
        change_percent = random.uniform(-0.5, 1.0)  # -0.5% to +1% change
        balance_change = self.portfolio_state.total_balance * (change_percent / 100)
        
        self.portfolio_state.total_balance += balance_change
        self.portfolio_state.daily_pnl += balance_change * 0.7  # Not all change is today
        
        # Simulate some trading activity
        if random.random() < 0.3:  # 30% chance of new trade
            self.portfolio_state.total_trades += 1
            if random.random() < 0.75:  # 75% win rate
                self.portfolio_state.winning_trades += 1
        
        self.portfolio_state.update_totals()
        
        logger.info(f"Portfolio simulated: ${self.portfolio_state.total_balance:.2f}, P&L: ${self.portfolio_state.daily_pnl:.2f}")

# Global unified portfolio system
unified_portfolio = UnifiedPortfolioSystem()