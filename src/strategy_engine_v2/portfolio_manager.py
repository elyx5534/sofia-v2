"""
Multi-Asset Portfolio Manager

Manages a portfolio of multiple assets across different markets (crypto, equity, etc.)
Provides unified interface for portfolio operations, risk management, and performance tracking.
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import pandas as pd
import numpy as np

from src.data_hub.models import AssetType, OHLCVData
from src.backtester.strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


class AllocationMethod(str, Enum):
    """Portfolio allocation methods"""
    EQUAL_WEIGHT = "equal_weight"
    MARKET_CAP_WEIGHT = "market_cap_weight" 
    RISK_PARITY = "risk_parity"
    MOMENTUM_WEIGHT = "momentum_weight"
    VOLATILITY_WEIGHT = "volatility_weight"
    CUSTOM = "custom"


@dataclass
class Asset:
    """Represents an asset in the portfolio"""
    symbol: str
    asset_type: AssetType
    weight: float = 0.0
    current_price: float = 0.0
    quantity: float = 0.0
    value: float = 0.0
    allocation_target: float = 0.0
    last_rebalance: Optional[datetime] = None
    
    @property
    def market_value(self) -> float:
        """Current market value of the position"""
        return self.quantity * self.current_price
    
    def update_price(self, new_price: float) -> None:
        """Update current price and recalculate value"""
        self.current_price = new_price
        self.value = self.market_value


@dataclass
class PortfolioMetrics:
    """Portfolio performance metrics"""
    total_value: float
    total_return: float
    sharpe_ratio: float
    volatility: float
    max_drawdown: float
    correlation_matrix: Optional[pd.DataFrame]
    diversification_ratio: float
    var_95: float  # Value at Risk (95% confidence)
    beta: float  # Market beta
    last_updated: datetime


class PortfolioManager:
    """
    Multi-Asset Portfolio Manager
    
    Manages a portfolio of assets across different markets with:
    - Dynamic allocation strategies
    - Risk management
    - Performance tracking
    - Rebalancing logic
    """
    
    def __init__(
        self,
        initial_capital: float = 100000.0,
        allocation_method: AllocationMethod = AllocationMethod.EQUAL_WEIGHT,
        rebalancing_threshold: float = 0.05,  # 5% drift threshold
        max_position_size: float = 0.25,  # Max 25% per asset
        risk_free_rate: float = 0.02  # 2% annual risk-free rate
    ):
        """
        Initialize Portfolio Manager
        
        Args:
            initial_capital: Starting capital
            allocation_method: How to allocate capital across assets
            rebalancing_threshold: Drift % that triggers rebalancing
            max_position_size: Maximum allocation to single asset
            risk_free_rate: Annual risk-free rate for Sharpe calculation
        """
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.allocation_method = allocation_method
        self.rebalancing_threshold = rebalancing_threshold
        self.max_position_size = max_position_size
        self.risk_free_rate = risk_free_rate
        
        # Portfolio state
        self.assets: Dict[str, Asset] = {}
        self.strategies: Dict[str, BaseStrategy] = {}
        self.price_history: Dict[str, List[float]] = {}
        self.portfolio_history: List[Dict[str, Any]] = []
        self.last_rebalance: Optional[datetime] = None
        
        # Performance tracking
        self.metrics: Optional[PortfolioMetrics] = None
        
        logger.info(f"Initialized PortfolioManager with ${initial_capital:,.2f} capital")
    
    def add_asset(
        self,
        symbol: str,
        asset_type: AssetType,
        target_allocation: float,
        strategy: Optional[BaseStrategy] = None
    ) -> None:
        """
        Add an asset to the portfolio
        
        Args:
            symbol: Asset symbol (e.g., 'AAPL', 'BTC/USDT')
            asset_type: Type of asset (equity, crypto)
            target_allocation: Target allocation percentage (0.0 to 1.0)
            strategy: Trading strategy for this asset
        """
        if symbol in self.assets:
            logger.warning(f"Asset {symbol} already in portfolio, updating allocation")
        
        # Validate allocation
        if not 0 <= target_allocation <= self.max_position_size:
            raise ValueError(f"Target allocation must be between 0 and {self.max_position_size}")
        
        # Create asset
        asset = Asset(
            symbol=symbol,
            asset_type=asset_type,
            allocation_target=target_allocation
        )
        
        self.assets[symbol] = asset
        if strategy:
            self.strategies[symbol] = strategy
        
        self.price_history[symbol] = []
        
        logger.info(f"Added asset {symbol} ({asset_type}) with {target_allocation:.1%} target allocation")
    
    def remove_asset(self, symbol: str) -> None:
        """Remove an asset from the portfolio"""
        if symbol not in self.assets:
            raise ValueError(f"Asset {symbol} not found in portfolio")
        
        # Sell all holdings first
        self._liquidate_asset(symbol)
        
        # Remove from tracking
        del self.assets[symbol]
        if symbol in self.strategies:
            del self.strategies[symbol]
        if symbol in self.price_history:
            del self.price_history[symbol]
        
        logger.info(f"Removed asset {symbol} from portfolio")
    
    def update_prices(self, price_data: Dict[str, float]) -> None:
        """
        Update current prices for all assets
        
        Args:
            price_data: Dict mapping symbol -> current price
        """
        for symbol, price in price_data.items():
            if symbol in self.assets:
                self.assets[symbol].update_price(price)
                self.price_history[symbol].append(price)
                
                # Keep only last 252 prices (1 year daily)
                if len(self.price_history[symbol]) > 252:
                    self.price_history[symbol] = self.price_history[symbol][-252:]
        
        # Update portfolio metrics
        self._calculate_metrics()
        
        # Check if rebalancing is needed
        if self._needs_rebalancing():
            logger.info("Portfolio drift detected, rebalancing recommended")
    
    def rebalance_portfolio(self, force: bool = False) -> Dict[str, float]:
        """
        Rebalance portfolio to target allocations
        
        Args:
            force: Force rebalancing even if within threshold
            
        Returns:
            Dict mapping symbol to trade amount (positive = buy, negative = sell)
        """
        if not force and not self._needs_rebalancing():
            logger.info("Portfolio within rebalancing threshold, no action needed")
            return {}
        
        total_value = self.get_total_value()
        if total_value <= 0:
            logger.warning("No portfolio value, cannot rebalance")
            return {}
        
        trades = {}
        
        # Calculate target values and current values
        for symbol, asset in self.assets.items():
            target_value = total_value * asset.allocation_target
            current_value = asset.market_value
            
            # Calculate required trade
            trade_value = target_value - current_value
            
            if abs(trade_value) > total_value * 0.01:  # Only trade if > 1% of portfolio
                trades[symbol] = trade_value
                logger.info(f"Rebalance {symbol}: {trade_value:+,.2f} (target: {target_value:,.2f}, current: {current_value:,.2f})")
        
        # Execute trades (in practice, would go to broker/exchange)
        self._execute_rebalance_trades(trades)
        
        self.last_rebalance = datetime.now(timezone.utc)
        
        return trades
    
    def get_total_value(self) -> float:
        """Get total portfolio value"""
        return sum(asset.market_value for asset in self.assets.values())
    
    def get_allocation_breakdown(self) -> Dict[str, Dict[str, float]]:
        """
        Get current allocation breakdown
        
        Returns:
            Dict mapping symbol to allocation info
        """
        total_value = self.get_total_value()
        if total_value == 0:
            return {}
        
        breakdown = {}
        for symbol, asset in self.assets.items():
            current_weight = asset.market_value / total_value
            breakdown[symbol] = {
                "current_weight": current_weight,
                "target_weight": asset.allocation_target,
                "drift": current_weight - asset.allocation_target,
                "value": asset.market_value,
                "quantity": asset.quantity,
                "price": asset.current_price
            }
        
        return breakdown
    
    def get_performance_metrics(self) -> Optional[PortfolioMetrics]:
        """Get current portfolio performance metrics"""
        return self.metrics
    
    def generate_signals(
        self,
        market_data: Dict[str, pd.DataFrame]
    ) -> Dict[str, int]:
        """
        Generate trading signals for all assets
        
        Args:
            market_data: Dict mapping symbol to OHLCV DataFrame
            
        Returns:
            Dict mapping symbol to signal (-1, 0, 1)
        """
        signals = {}
        
        for symbol, strategy in self.strategies.items():
            if symbol in market_data:
                try:
                    signal = strategy.generate_signals(market_data[symbol])
                    # Get latest signal
                    if isinstance(signal, (list, pd.Series)) and len(signal) > 0:
                        signals[symbol] = signal[-1] if isinstance(signal, list) else signal.iloc[-1]
                    else:
                        signals[symbol] = 0
                except Exception as e:
                    logger.error(f"Error generating signal for {symbol}: {e}")
                    signals[symbol] = 0
            else:
                signals[symbol] = 0
        
        return signals
    
    def _needs_rebalancing(self) -> bool:
        """Check if portfolio needs rebalancing"""
        total_value = self.get_total_value()
        if total_value == 0:
            return False
        
        for asset in self.assets.values():
            current_weight = asset.market_value / total_value
            drift = abs(current_weight - asset.allocation_target)
            
            if drift > self.rebalancing_threshold:
                return True
        
        return False
    
    def _liquidate_asset(self, symbol: str) -> None:
        """Liquidate all holdings of an asset"""
        asset = self.assets[symbol]
        if asset.quantity > 0:
            # In practice, would execute sell order
            self.current_capital += asset.market_value
            asset.quantity = 0
            asset.value = 0
            logger.info(f"Liquidated {symbol}, returned ${asset.market_value:,.2f} to cash")
    
    def _execute_rebalance_trades(self, trades: Dict[str, float]) -> None:
        """Execute rebalancing trades"""
        for symbol, trade_value in trades.items():
            asset = self.assets[symbol]
            
            if trade_value > 0:  # Buy
                quantity = trade_value / asset.current_price
                asset.quantity += quantity
                self.current_capital -= trade_value
                logger.info(f"Bought {quantity:.4f} {symbol} for ${trade_value:,.2f}")
                
            elif trade_value < 0:  # Sell
                quantity = abs(trade_value) / asset.current_price
                asset.quantity = max(0, asset.quantity - quantity)
                self.current_capital += abs(trade_value)
                logger.info(f"Sold {quantity:.4f} {symbol} for ${abs(trade_value):,.2f}")
            
            # Update asset value
            asset.value = asset.market_value
    
    def _calculate_metrics(self) -> None:
        """Calculate portfolio performance metrics"""
        if not self.assets or not any(self.price_history.values()):
            return
        
        total_value = self.get_total_value()
        if total_value == 0:
            return
        
        # Calculate returns
        total_return = (total_value - self.initial_capital) / self.initial_capital
        
        # Calculate portfolio volatility and Sharpe ratio
        portfolio_returns = self._calculate_portfolio_returns()
        if len(portfolio_returns) > 1:
            volatility = np.std(portfolio_returns) * np.sqrt(252)  # Annualized
            excess_return = np.mean(portfolio_returns) * 252 - self.risk_free_rate
            sharpe_ratio = excess_return / volatility if volatility > 0 else 0
        else:
            volatility = 0
            sharpe_ratio = 0
        
        # Calculate correlation matrix
        correlation_matrix = self._calculate_correlation_matrix()
        
        # Calculate diversification ratio
        diversification_ratio = self._calculate_diversification_ratio(correlation_matrix)
        
        # Calculate VaR
        var_95 = np.percentile(portfolio_returns, 5) if len(portfolio_returns) > 0 else 0
        
        # Calculate max drawdown
        max_drawdown = self._calculate_max_drawdown()
        
        self.metrics = PortfolioMetrics(
            total_value=total_value,
            total_return=total_return,
            sharpe_ratio=sharpe_ratio,
            volatility=volatility,
            max_drawdown=max_drawdown,
            correlation_matrix=correlation_matrix,
            diversification_ratio=diversification_ratio,
            var_95=var_95,
            beta=0.0,  # Would need market benchmark data
            last_updated=datetime.now(timezone.utc)
        )
    
    def _calculate_portfolio_returns(self) -> List[float]:
        """Calculate portfolio daily returns"""
        # Simplified calculation - would need more sophisticated approach in practice
        if not self.portfolio_history:
            return []
        
        returns = []
        for i in range(1, len(self.portfolio_history)):
            prev_value = self.portfolio_history[i-1].get('total_value', 0)
            curr_value = self.portfolio_history[i].get('total_value', 0)
            
            if prev_value > 0:
                returns.append((curr_value - prev_value) / prev_value)
        
        return returns
    
    def _calculate_correlation_matrix(self) -> Optional[pd.DataFrame]:
        """Calculate asset correlation matrix"""
        if len(self.assets) < 2:
            return None
        
        # Create returns matrix
        returns_data = {}
        min_length = float('inf')
        
        for symbol in self.assets.keys():
            if len(self.price_history[symbol]) > 1:
                prices = self.price_history[symbol]
                returns = [prices[i]/prices[i-1] - 1 for i in range(1, len(prices))]
                returns_data[symbol] = returns
                min_length = min(min_length, len(returns))
        
        if min_length == float('inf') or min_length < 2:
            return None
        
        # Truncate to same length
        for symbol in returns_data:
            returns_data[symbol] = returns_data[symbol][-min_length:]
        
        # Calculate correlation
        df = pd.DataFrame(returns_data)
        return df.corr()
    
    def _calculate_diversification_ratio(self, corr_matrix: Optional[pd.DataFrame]) -> float:
        """Calculate portfolio diversification ratio"""
        if corr_matrix is None or len(corr_matrix) < 2:
            return 1.0
        
        # Simplified calculation
        avg_correlation = corr_matrix.values[np.triu_indices_from(corr_matrix.values, k=1)].mean()
        n_assets = len(corr_matrix)
        
        # Diversification ratio approximation
        return 1 / np.sqrt(1 + (n_assets - 1) * avg_correlation)
    
    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown"""
        if len(self.portfolio_history) < 2:
            return 0.0
        
        values = [h.get('total_value', 0) for h in self.portfolio_history]
        peak = values[0]
        max_drawdown = 0.0
        
        for value in values[1:]:
            if value > peak:
                peak = value
            else:
                drawdown = (peak - value) / peak
                max_drawdown = max(max_drawdown, drawdown)
        
        return max_drawdown
    
    def save_portfolio_state(self) -> None:
        """Save current portfolio state to history"""
        state = {
            'timestamp': datetime.now(timezone.utc),
            'total_value': self.get_total_value(),
            'cash': self.current_capital,
            'assets': {
                symbol: {
                    'quantity': asset.quantity,
                    'price': asset.current_price,
                    'value': asset.market_value,
                    'weight': asset.market_value / self.get_total_value() if self.get_total_value() > 0 else 0
                }
                for symbol, asset in self.assets.items()
            }
        }
        
        self.portfolio_history.append(state)
        
        # Keep only last 252 states (1 year daily)
        if len(self.portfolio_history) > 252:
            self.portfolio_history = self.portfolio_history[-252:]