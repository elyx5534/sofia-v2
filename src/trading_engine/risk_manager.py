"""Risk management module."""

from typing import Optional, Dict
from pydantic import BaseModel, Field
from datetime import datetime, timezone


class RiskParameters(BaseModel):
    """Risk management parameters."""
    
    max_position_size: float = Field(default=0.1, description="Max position size as % of portfolio")
    max_daily_loss: float = Field(default=0.02, description="Max daily loss as % of portfolio")
    max_drawdown: float = Field(default=0.1, description="Max drawdown as % of portfolio")
    stop_loss_percentage: float = Field(default=0.02, description="Default stop loss %")
    take_profit_percentage: float = Field(default=0.05, description="Default take profit %")
    max_leverage: float = Field(default=1.0, description="Maximum leverage allowed")
    max_open_positions: int = Field(default=10, description="Maximum number of open positions")
    min_risk_reward_ratio: float = Field(default=2.0, description="Minimum risk/reward ratio")


class RiskMetrics(BaseModel):
    """Risk metrics."""
    
    current_drawdown: float = 0
    daily_pnl: float = 0
    sharpe_ratio: float = 0
    win_rate: float = 0
    avg_win: float = 0
    avg_loss: float = 0
    risk_reward_ratio: float = 0
    var_95: float = 0  # Value at Risk 95%
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RiskManager:
    """Manages trading risks."""
    
    def __init__(self, parameters: Optional[RiskParameters] = None):
        """Initialize risk manager."""
        self.parameters = parameters or RiskParameters()
        self.metrics = RiskMetrics()
        self.daily_losses: float = 0
        self.peak_value: float = 0
        self.current_value: float = 0
        self.trades_today: int = 0
        self.winning_trades: int = 0
        self.losing_trades: int = 0
        self.total_wins: float = 0
        self.total_losses: float = 0
    
    def check_position_size(
        self,
        position_value: float,
        portfolio_value: float,
    ) -> tuple[bool, str]:
        """Check if position size is within limits."""
        if portfolio_value == 0:
            return False, "Portfolio value is zero"
        
        position_ratio = position_value / portfolio_value
        max_size = self.parameters.max_position_size
        
        if position_ratio > max_size:
            return False, f"Position size {position_ratio:.2%} exceeds max {max_size:.2%}"
        
        return True, "Position size OK"
    
    def check_daily_loss_limit(self) -> tuple[bool, str]:
        """Check if daily loss limit is exceeded."""
        if self.current_value == 0:
            return True, "No portfolio value set"
        
        daily_loss_ratio = abs(self.daily_losses / self.current_value)
        max_loss = self.parameters.max_daily_loss
        
        if daily_loss_ratio >= max_loss:
            return False, f"Daily loss {daily_loss_ratio:.2%} exceeds limit {max_loss:.2%}"
        
        return True, f"Daily loss within limits ({daily_loss_ratio:.2%})"
    
    def check_drawdown(self) -> tuple[bool, str]:
        """Check if drawdown exceeds limit."""
        if self.peak_value == 0:
            return True, "No peak value set"
        
        drawdown = (self.peak_value - self.current_value) / self.peak_value
        max_dd = self.parameters.max_drawdown
        
        if drawdown >= max_dd:
            return False, f"Drawdown {drawdown:.2%} exceeds limit {max_dd:.2%}"
        
        self.metrics.current_drawdown = drawdown
        return True, f"Drawdown within limits ({drawdown:.2%})"
    
    def check_open_positions(self, current_positions: int) -> tuple[bool, str]:
        """Check if number of open positions is within limit."""
        max_positions = self.parameters.max_open_positions
        
        if current_positions >= max_positions:
            return False, f"Open positions {current_positions} at limit {max_positions}"
        
        return True, f"Can open {max_positions - current_positions} more positions"
    
    def calculate_position_size(
        self,
        portfolio_value: float,
        risk_per_trade: float = 0.01,
        stop_loss_distance: float = 0.02,
    ) -> float:
        """Calculate optimal position size using Kelly Criterion."""
        # Risk amount
        risk_amount = portfolio_value * risk_per_trade
        
        # Position size based on stop loss
        position_size = risk_amount / stop_loss_distance
        
        # Apply max position size limit
        max_position = portfolio_value * self.parameters.max_position_size
        
        return min(position_size, max_position)
    
    def update_metrics(self, trade_pnl: float) -> None:
        """Update risk metrics after a trade."""
        self.daily_losses += min(0, trade_pnl)
        
        if trade_pnl > 0:
            self.winning_trades += 1
            self.total_wins += trade_pnl
        else:
            self.losing_trades += 1
            self.total_losses += abs(trade_pnl)
        
        # Update win rate
        total_trades = self.winning_trades + self.losing_trades
        if total_trades > 0:
            self.metrics.win_rate = self.winning_trades / total_trades
        
        # Update average win/loss
        if self.winning_trades > 0:
            self.metrics.avg_win = self.total_wins / self.winning_trades
        
        if self.losing_trades > 0:
            self.metrics.avg_loss = self.total_losses / self.losing_trades
        
        # Update risk/reward ratio
        if self.metrics.avg_loss > 0:
            self.metrics.risk_reward_ratio = self.metrics.avg_win / self.metrics.avg_loss
        
        self.metrics.updated_at = datetime.now(timezone.utc)
    
    def update_portfolio_value(self, value: float) -> None:
        """Update current portfolio value."""
        self.current_value = value
        
        # Update peak value for drawdown calculation
        if value > self.peak_value:
            self.peak_value = value
    
    def reset_daily_metrics(self) -> None:
        """Reset daily metrics."""
        self.daily_losses = 0
        self.trades_today = 0
        self.metrics.daily_pnl = 0
    
    def get_stop_loss_price(self, entry_price: float, side: str) -> float:
        """Calculate stop loss price."""
        stop_percentage = self.parameters.stop_loss_percentage
        
        if side == "buy":
            return entry_price * (1 - stop_percentage)
        else:
            return entry_price * (1 + stop_percentage)
    
    def get_take_profit_price(self, entry_price: float, side: str) -> float:
        """Calculate take profit price."""
        tp_percentage = self.parameters.take_profit_percentage
        
        if side == "buy":
            return entry_price * (1 + tp_percentage)
        else:
            return entry_price * (1 - tp_percentage)
