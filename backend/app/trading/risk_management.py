"""
Sofia V2 Risk Management - Professional Risk Control System
Advanced risk management competing with institutional traders
"""

import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum
import math

import structlog

from .engine import Portfolio, Position, Order, OrderSide
from .indicators import QuantitativeIndicators

logger = structlog.get_logger(__name__)

class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium" 
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class RiskMetrics:
    """Risk metrics for portfolio analysis"""
    var_95: float  # Value at Risk (95% confidence)
    cvar_95: float  # Conditional VaR
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    volatility: float
    beta: float  # Market beta
    correlation: float  # Correlation with market
    risk_level: RiskLevel
    
class RiskManager:
    """Advanced risk management system"""
    
    def __init__(self, portfolio: Portfolio, settings: Dict[str, Any] = None):
        self.portfolio = portfolio
        
        default_settings = {
            'max_portfolio_risk': 0.20,      # Max 20% portfolio risk
            'max_position_risk': 0.05,       # Max 5% per position
            'max_correlation_risk': 0.80,    # Max 80% correlation
            'max_sector_concentration': 0.30, # Max 30% in one sector
            'var_confidence': 0.95,          # 95% VaR confidence
            'lookback_days': 252,            # 1 year lookback
            'rebalance_threshold': 0.05,     # 5% drift threshold
            'max_leverage': 1.0,             # No leverage by default
            'stop_loss_multiplier': 2.0,     # ATR multiplier for stops
            'take_profit_multiplier': 3.0,   # ATR multiplier for profits
        }
        
        if settings:
            default_settings.update(settings)
        
        self.settings = default_settings
        
        # Risk tracking
        self.historical_returns = deque(maxlen=500)
        self.drawdown_history = deque(maxlen=500) 
        self.volatility_history = deque(maxlen=100)
        self.correlation_matrix = {}
        self.sector_allocation = defaultdict(float)
        
        # Performance metrics
        self.daily_returns = []
        self.benchmark_returns = []  # SPY or BTC returns for comparison
        
        # Risk alerts
        self.risk_alerts = []
        self.last_rebalance = datetime.now(timezone.utc)
        
        logger.info("Risk manager initialized", settings=default_settings)
    
    def calculate_portfolio_risk(self) -> RiskMetrics:
        """Calculate comprehensive portfolio risk metrics"""
        try:
            if len(self.historical_returns) < 30:
                return self._default_risk_metrics()
            
            returns_array = np.array(list(self.historical_returns))
            
            # Value at Risk calculations
            var_95 = QuantitativeIndicators.value_at_risk(returns_array, 0.05)
            cvar_95 = QuantitativeIndicators.conditional_value_at_risk(returns_array, 0.05)
            
            # Risk-adjusted return metrics
            sharpe_ratio = QuantitativeIndicators.sharpe_ratio(returns_array)
            sortino_ratio = self._calculate_sortino_ratio(returns_array)
            
            # Drawdown metrics
            portfolio_values = [self.portfolio.initial_balance]
            for ret in returns_array:
                portfolio_values.append(portfolio_values[-1] * (1 + ret))
            
            max_drawdown = QuantitativeIndicators.maximum_drawdown(portfolio_values)
            
            # Volatility
            volatility = np.std(returns_array) * np.sqrt(252)  # Annualized
            
            # Market correlation (if benchmark available)
            if len(self.benchmark_returns) >= len(returns_array):
                correlation = np.corrcoef(returns_array, self.benchmark_returns[-len(returns_array):])[0, 1]
                beta = self._calculate_beta(returns_array, self.benchmark_returns[-len(returns_array):])
            else:
                correlation = 0.0
                beta = 1.0
            
            # Overall risk level
            risk_level = self._assess_risk_level(var_95, max_drawdown, volatility, sharpe_ratio)
            
            return RiskMetrics(
                var_95=var_95,
                cvar_95=cvar_95,
                sharpe_ratio=sharpe_ratio,
                sortino_ratio=sortino_ratio,
                max_drawdown=max_drawdown,
                volatility=volatility,
                beta=beta,
                correlation=correlation,
                risk_level=risk_level
            )
            
        except Exception as e:
            logger.error("Risk calculation error", error=str(e))
            return self._default_risk_metrics()
    
    def _default_risk_metrics(self) -> RiskMetrics:
        """Default risk metrics when insufficient data"""
        return RiskMetrics(
            var_95=0.0, cvar_95=0.0, sharpe_ratio=0.0, sortino_ratio=0.0,
            max_drawdown=0.0, volatility=0.0, beta=1.0, correlation=0.0,
            risk_level=RiskLevel.LOW
        )
    
    def _calculate_sortino_ratio(self, returns: np.ndarray, risk_free_rate: float = 0.02) -> float:
        """Calculate Sortino ratio (downside deviation)"""
        excess_returns = returns - risk_free_rate / 252
        downside_returns = excess_returns[excess_returns < 0]
        
        if len(downside_returns) == 0:
            return float('inf') if np.mean(excess_returns) > 0 else 0.0
        
        downside_deviation = np.sqrt(np.mean(downside_returns ** 2))
        
        if downside_deviation == 0:
            return float('inf') if np.mean(excess_returns) > 0 else 0.0
        
        return np.mean(excess_returns) / downside_deviation * np.sqrt(252)
    
    def _calculate_beta(self, returns: np.ndarray, benchmark_returns: np.ndarray) -> float:
        """Calculate portfolio beta vs benchmark"""
        if len(returns) != len(benchmark_returns) or len(returns) < 2:
            return 1.0
        
        covariance = np.cov(returns, benchmark_returns)[0, 1]
        benchmark_variance = np.var(benchmark_returns)
        
        if benchmark_variance == 0:
            return 1.0
        
        return covariance / benchmark_variance
    
    def _assess_risk_level(self, var_95: float, max_drawdown: float, 
                          volatility: float, sharpe_ratio: float) -> RiskLevel:
        """Assess overall portfolio risk level"""
        risk_score = 0
        
        # VaR assessment
        if abs(var_95) > 0.05:  # >5% daily VaR
            risk_score += 2
        elif abs(var_95) > 0.03:  # >3% daily VaR
            risk_score += 1
        
        # Drawdown assessment
        if max_drawdown > 0.30:  # >30% drawdown
            risk_score += 2
        elif max_drawdown > 0.15:  # >15% drawdown
            risk_score += 1
        
        # Volatility assessment
        if volatility > 0.40:  # >40% annualized volatility
            risk_score += 2
        elif volatility > 0.25:  # >25% annualized volatility
            risk_score += 1
        
        # Sharpe ratio assessment (inverted - low Sharpe is risky)
        if sharpe_ratio < 0:
            risk_score += 2
        elif sharpe_ratio < 0.5:
            risk_score += 1
        
        # Map score to risk level
        if risk_score >= 6:
            return RiskLevel.CRITICAL
        elif risk_score >= 4:
            return RiskLevel.HIGH
        elif risk_score >= 2:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    def validate_new_position(self, symbol: str, side: OrderSide, size: float, 
                            entry_price: float, stop_loss: float) -> Tuple[bool, str, float]:
        """Validate new position against risk parameters"""
        try:
            # Calculate position risk
            position_value = size * entry_price
            position_risk = abs(entry_price - stop_loss) * size
            
            # Portfolio checks
            current_portfolio_value = self.portfolio.current_balance
            
            # 1. Position size check
            position_pct = position_value / current_portfolio_value
            if position_pct > self.settings['max_position_risk']:
                suggested_size = (current_portfolio_value * self.settings['max_position_risk']) / entry_price
                return False, f"Position too large: {position_pct:.2%} > {self.settings['max_position_risk']:.2%}", suggested_size
            
            # 2. Risk per trade check
            risk_pct = position_risk / current_portfolio_value
            if risk_pct > self.settings['max_position_risk'] * 0.5:  # Risk should be half of position size
                suggested_size = (current_portfolio_value * self.settings['max_position_risk'] * 0.5) / abs(entry_price - stop_loss)
                return False, f"Risk too high: {risk_pct:.2%} > {self.settings['max_position_risk'] * 0.5:.2%}", suggested_size
            
            # 3. Portfolio heat check (total open risk)
            total_open_risk = sum(
                abs(pos.current_price - pos.stop_loss) * pos.size 
                for pos in self.portfolio.positions.values() 
                if pos.stop_loss
            )
            total_risk_pct = (total_open_risk + position_risk) / current_portfolio_value
            
            if total_risk_pct > self.settings['max_portfolio_risk']:
                return False, f"Portfolio risk too high: {total_risk_pct:.2%} > {self.settings['max_portfolio_risk']:.2%}", size * 0.5
            
            # 4. Correlation check (if we have similar positions)
            correlation_risk = self._check_correlation_risk(symbol, position_value)
            if correlation_risk > self.settings['max_correlation_risk']:
                return False, f"Correlation risk too high: {correlation_risk:.2%} > {self.settings['max_correlation_risk']:.2%}", size * 0.7
            
            # 5. Leverage check
            total_position_value = sum(pos.size * pos.current_price for pos in self.portfolio.positions.values())
            leverage = (total_position_value + position_value) / current_portfolio_value
            
            if leverage > self.settings['max_leverage']:
                max_additional_value = (current_portfolio_value * self.settings['max_leverage']) - total_position_value
                suggested_size = max_additional_value / entry_price
                return False, f"Leverage too high: {leverage:.2f}x > {self.settings['max_leverage']:.2f}x", max(suggested_size, 0)
            
            return True, "Position approved", size
            
        except Exception as e:
            logger.error("Position validation error", error=str(e))
            return False, f"Validation error: {str(e)}", size * 0.5
    
    def _check_correlation_risk(self, symbol: str, position_value: float) -> float:
        """Check correlation risk with existing positions"""
        if not self.portfolio.positions:
            return 0.0
        
        # Simple correlation check based on symbol similarity
        # In production, this would use actual correlation data
        similar_exposure = 0.0
        
        for existing_symbol, position in self.portfolio.positions.items():
            if existing_symbol == symbol:
                continue
            
            # Check if similar asset (same base currency, etc.)
            correlation = self._estimate_correlation(symbol, existing_symbol)
            if correlation > 0.7:  # High correlation
                similar_exposure += position.size * position.current_price * correlation
        
        total_portfolio_value = self.portfolio.current_balance
        correlation_risk = (similar_exposure + position_value) / total_portfolio_value
        
        return correlation_risk
    
    def _estimate_correlation(self, symbol1: str, symbol2: str) -> float:
        """Estimate correlation between two symbols"""
        # Simple heuristic - in production use historical correlation
        if symbol1 == symbol2:
            return 1.0
        
        # Same base currency (BTC pairs)
        if symbol1.startswith('BTC') and symbol2.startswith('BTC'):
            return 0.8
        
        # Same quote currency (USDT pairs)
        if symbol1.endswith('USDT') and symbol2.endswith('USDT'):
            return 0.6
        
        # Major cryptos tend to be correlated
        major_cryptos = ['BTC', 'ETH', 'BNB', 'SOL', 'ADA']
        base1 = symbol1.replace('USDT', '').replace('USD', '')
        base2 = symbol2.replace('USDT', '').replace('USD', '')
        
        if base1 in major_cryptos and base2 in major_cryptos:
            return 0.7
        
        return 0.3  # Default correlation
    
    def calculate_optimal_position_size(self, symbol: str, entry_price: float, 
                                      stop_loss: float, confidence: float = 0.5) -> float:
        """Calculate optimal position size using Kelly Criterion and risk constraints"""
        try:
            # Get historical win rate and average win/loss for this strategy
            # For now, use portfolio statistics
            portfolio_metrics = self.portfolio.get_metrics()
            win_rate = portfolio_metrics['win_rate_pct'] / 100
            
            if self.portfolio.winning_trades > 0 and self.portfolio.losing_trades > 0:
                avg_win = abs(portfolio_metrics['largest_win'] / self.portfolio.winning_trades)
                avg_loss = abs(portfolio_metrics['largest_loss'] / self.portfolio.losing_trades)
            else:
                # Default values
                avg_win = abs(entry_price - stop_loss) * 1.5  # Assume 1.5:1 R/R
                avg_loss = abs(entry_price - stop_loss)
            
            # Kelly Criterion calculation
            if avg_loss > 0 and win_rate > 0:
                kelly_fraction = QuantitativeIndicators.kelly_criterion(win_rate, avg_win, avg_loss)
            else:
                kelly_fraction = 0.02  # 2% default
            
            # Adjust for confidence
            adjusted_kelly = kelly_fraction * confidence
            
            # Apply risk management constraints
            max_risk_per_trade = self.settings['max_position_risk'] * 0.5  # Risk should be half of position limit
            
            # Calculate position size based on risk
            portfolio_value = self.portfolio.current_balance
            max_risk_amount = portfolio_value * max_risk_per_trade
            risk_per_share = abs(entry_price - stop_loss)
            
            if risk_per_share > 0:
                risk_based_size = max_risk_amount / risk_per_share
            else:
                risk_based_size = 0
            
            # Kelly-based size
            kelly_based_size = (portfolio_value * adjusted_kelly) / entry_price
            
            # Use the minimum of risk-based and Kelly-based sizes
            optimal_size = min(risk_based_size, kelly_based_size)
            
            # Final validation against position size limits
            max_position_value = portfolio_value * self.settings['max_position_risk']
            max_size_by_value = max_position_value / entry_price
            
            final_size = min(optimal_size, max_size_by_value)
            
            return max(final_size, 0)
            
        except Exception as e:
            logger.error("Optimal position size calculation error", error=str(e))
            # Fallback to simple risk-based sizing
            portfolio_value = self.portfolio.current_balance
            max_risk = portfolio_value * 0.01  # 1% risk
            if abs(entry_price - stop_loss) > 0:
                return max_risk / abs(entry_price - stop_loss)
            return 0
    
    def should_rebalance_portfolio(self) -> bool:
        """Determine if portfolio needs rebalancing"""
        # Time-based rebalancing
        time_since_rebalance = datetime.now(timezone.utc) - self.last_rebalance
        if time_since_rebalance > timedelta(days=7):  # Weekly rebalancing
            return True
        
        # Drift-based rebalancing
        total_portfolio_value = self.portfolio.current_balance
        
        for symbol, position in self.portfolio.positions.items():
            position_value = position.size * position.current_price
            position_weight = position_value / total_portfolio_value
            
            # If any position drifted more than threshold
            if position_weight > self.settings['max_position_risk'] * (1 + self.settings['rebalance_threshold']):
                return True
        
        return False
    
    def generate_risk_report(self) -> Dict[str, Any]:
        """Generate comprehensive risk report"""
        risk_metrics = self.calculate_portfolio_risk()
        portfolio_metrics = self.portfolio.get_metrics()
        
        # Position analysis
        position_analysis = []
        total_value = self.portfolio.current_balance
        
        for symbol, position in self.portfolio.positions.items():
            position_value = position.size * position.current_price
            position_risk = abs(position.current_price - position.stop_loss) * position.size if position.stop_loss else 0
            
            position_analysis.append({
                'symbol': symbol,
                'side': position.side.value,
                'size': position.size,
                'value': position_value,
                'weight_pct': position_value / total_value * 100,
                'unrealized_pnl': position.unrealized_pnl,
                'risk_amount': position_risk,
                'risk_pct': position_risk / total_value * 100 if total_value > 0 else 0
            })
        
        # Risk alerts
        current_alerts = self._generate_risk_alerts(risk_metrics)
        
        return {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'risk_metrics': {
                'var_95_pct': risk_metrics.var_95 * 100,
                'cvar_95_pct': risk_metrics.cvar_95 * 100,
                'sharpe_ratio': risk_metrics.sharpe_ratio,
                'sortino_ratio': risk_metrics.sortino_ratio,
                'max_drawdown_pct': risk_metrics.max_drawdown * 100,
                'volatility_pct': risk_metrics.volatility * 100,
                'beta': risk_metrics.beta,
                'correlation': risk_metrics.correlation,
                'risk_level': risk_metrics.risk_level.value
            },
            'portfolio_metrics': portfolio_metrics,
            'position_analysis': position_analysis,
            'risk_alerts': current_alerts,
            'total_portfolio_risk_pct': sum(p['risk_pct'] for p in position_analysis),
            'largest_position_pct': max([p['weight_pct'] for p in position_analysis] + [0]),
            'position_count': len(position_analysis),
            'cash_pct': max(0, (total_value - sum(p['value'] for p in position_analysis)) / total_value * 100),
            'rebalance_needed': self.should_rebalance_portfolio()
        }
    
    def _generate_risk_alerts(self, risk_metrics: RiskMetrics) -> List[Dict[str, Any]]:
        """Generate risk alerts based on current metrics"""
        alerts = []
        
        # High risk level alert
        if risk_metrics.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            alerts.append({
                'type': 'risk_level',
                'severity': risk_metrics.risk_level.value,
                'message': f'Portfolio risk level is {risk_metrics.risk_level.value}',
                'recommendation': 'Consider reducing position sizes or closing some positions'
            })
        
        # High drawdown alert
        if risk_metrics.max_drawdown > 0.20:
            alerts.append({
                'type': 'drawdown',
                'severity': 'high',
                'message': f'Maximum drawdown: {risk_metrics.max_drawdown:.1%}',
                'recommendation': 'Review risk management and consider portfolio diversification'
            })
        
        # Poor Sharpe ratio alert
        if risk_metrics.sharpe_ratio < 0:
            alerts.append({
                'type': 'performance',
                'severity': 'medium',
                'message': f'Negative Sharpe ratio: {risk_metrics.sharpe_ratio:.2f}',
                'recommendation': 'Portfolio is not generating risk-adjusted returns'
            })
        
        # High VaR alert
        if abs(risk_metrics.var_95) > 0.05:
            alerts.append({
                'type': 'var',
                'severity': 'high',
                'message': f'High daily VaR: {risk_metrics.var_95:.2%}',
                'recommendation': 'Daily losses could exceed 5% with 95% confidence'
            })
        
        return alerts
    
    def update_performance_data(self, current_balance: float, benchmark_return: float = None):
        """Update performance tracking data"""
        # Calculate daily return
        if len(self.historical_returns) > 0:
            previous_balance = self.portfolio.initial_balance * (1 + sum(self.historical_returns))
            daily_return = (current_balance - previous_balance) / previous_balance
        else:
            daily_return = (current_balance - self.portfolio.initial_balance) / self.portfolio.initial_balance
        
        self.historical_returns.append(daily_return)
        
        # Add benchmark return if provided
        if benchmark_return is not None:
            self.benchmark_returns.append(benchmark_return)
        
        # Update drawdown tracking
        current_peak = max(self.portfolio.initial_balance * (1 + sum(self.historical_returns)), 
                          self.portfolio.peak_balance)
        current_drawdown = (current_peak - current_balance) / current_peak
        self.drawdown_history.append(current_drawdown)
        
        # Update volatility
        if len(self.historical_returns) >= 20:
            recent_volatility = np.std(list(self.historical_returns)[-20:])
            self.volatility_history.append(recent_volatility)
        
        logger.debug("Performance data updated",
                    daily_return=daily_return,
                    current_drawdown=current_drawdown,
                    balance=current_balance)