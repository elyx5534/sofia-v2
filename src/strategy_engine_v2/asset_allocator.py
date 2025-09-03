"""
Asset Allocator

Implements various portfolio allocation strategies:
- Equal Weight
- Risk Parity
- Momentum-based allocation
- Volatility-weighted allocation
- Market Cap weighted allocation
"""

import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from .portfolio_manager import AllocationMethod

logger = logging.getLogger(__name__)


class AssetAllocator:
    """
    Implements various asset allocation strategies for multi-asset portfolios
    """

    def __init__(self, lookback_period: int = 60):
        """
        Initialize Asset Allocator

        Args:
            lookback_period: Number of periods to look back for calculations
        """
        self.lookback_period = lookback_period

    def calculate_allocation(
        self, price_data: Dict[str, List[float]], method: AllocationMethod, **kwargs
    ) -> Dict[str, float]:
        """
        Calculate optimal asset allocation based on method

        Args:
            price_data: Dict mapping symbol to price history
            method: Allocation method to use
            **kwargs: Additional parameters for specific methods

        Returns:
            Dict mapping symbol to allocation weight (0-1)
        """
        if not price_data:
            return {}
        symbols = list(price_data.keys())
        if method == AllocationMethod.EQUAL_WEIGHT:
            return self._equal_weight_allocation(symbols)
        elif method == AllocationMethod.RISK_PARITY:
            return self._risk_parity_allocation(price_data)
        elif method == AllocationMethod.MOMENTUM_WEIGHT:
            return self._momentum_allocation(price_data, **kwargs)
        elif method == AllocationMethod.VOLATILITY_WEIGHT:
            return self._volatility_allocation(price_data, **kwargs)
        elif method == AllocationMethod.MARKET_CAP_WEIGHT:
            market_caps = kwargs.get("market_caps", {})
            return self._market_cap_allocation(symbols, market_caps)
        else:
            logger.warning(f"Unknown allocation method: {method}, using equal weight")
            return self._equal_weight_allocation(symbols)

    def _equal_weight_allocation(self, symbols: List[str]) -> Dict[str, float]:
        """Equal weight allocation"""
        if not symbols:
            return {}
        weight = 1.0 / len(symbols)
        return {symbol: weight for symbol in symbols}

    def _risk_parity_allocation(self, price_data: Dict[str, List[float]]) -> Dict[str, float]:
        """
        Risk parity allocation - allocate based on inverse volatility
        Each asset contributes equally to portfolio risk
        """
        volatilities = self._calculate_volatilities(price_data)
        if not volatilities or all(vol == 0 for vol in volatilities.values()):
            return self._equal_weight_allocation(list(price_data.keys()))
        inv_vol = {symbol: 1 / vol if vol > 0 else 0 for symbol, vol in volatilities.items()}
        total_inv_vol = sum(inv_vol.values())
        if total_inv_vol == 0:
            return self._equal_weight_allocation(list(price_data.keys()))
        return {symbol: weight / total_inv_vol for symbol, weight in inv_vol.items()}

    def _momentum_allocation(
        self, price_data: Dict[str, List[float]], momentum_period: int = 30, **kwargs
    ) -> Dict[str, float]:
        """
        Momentum-based allocation - overweight assets with positive momentum
        """
        momentum_scores = {}
        for symbol, prices in price_data.items():
            if len(prices) >= momentum_period:
                momentum = (prices[-1] - prices[-momentum_period]) / prices[-momentum_period]
                momentum_scores[symbol] = max(0, momentum)
            else:
                momentum_scores[symbol] = 0
        total_momentum = sum(momentum_scores.values())
        if total_momentum == 0:
            return self._equal_weight_allocation(list(price_data.keys()))
        base_weight = 0.1 / len(momentum_scores)
        adjusted_scores = {
            symbol: base_weight + 0.9 * (score / total_momentum)
            for symbol, score in momentum_scores.items()
        }
        return adjusted_scores

    def _volatility_allocation(
        self, price_data: Dict[str, List[float]], inverse: bool = True, **kwargs
    ) -> Dict[str, float]:
        """
        Volatility-based allocation

        Args:
            inverse: If True, allocate inversely to volatility (less to volatile assets)
        """
        volatilities = self._calculate_volatilities(price_data)
        if not volatilities or all(vol == 0 for vol in volatilities.values()):
            return self._equal_weight_allocation(list(price_data.keys()))
        if inverse:
            weights = {symbol: 1 / vol if vol > 0 else 0 for symbol, vol in volatilities.items()}
        else:
            weights = volatilities.copy()
        total_weight = sum(weights.values())
        if total_weight == 0:
            return self._equal_weight_allocation(list(price_data.keys()))
        return {symbol: weight / total_weight for symbol, weight in weights.items()}

    def _market_cap_allocation(
        self, symbols: List[str], market_caps: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Market cap weighted allocation

        Args:
            symbols: List of symbols
            market_caps: Dict mapping symbol to market cap value
        """
        if not market_caps:
            return self._equal_weight_allocation(symbols)
        valid_caps = {symbol: market_caps[symbol] for symbol in symbols if symbol in market_caps}
        if not valid_caps:
            return self._equal_weight_allocation(symbols)
        total_cap = sum(valid_caps.values())
        allocation = {}
        for symbol in symbols:
            if symbol in valid_caps:
                allocation[symbol] = valid_caps[symbol] / total_cap
            else:
                allocation[symbol] = 0
        return allocation

    def _calculate_volatilities(self, price_data: Dict[str, List[float]]) -> Dict[str, float]:
        """Calculate annualized volatility for each asset"""
        volatilities = {}
        for symbol, prices in price_data.items():
            if len(prices) < 2:
                volatilities[symbol] = 0
                continue
            returns = [prices[i] / prices[i - 1] - 1 for i in range(1, len(prices))]
            if not returns:
                volatilities[symbol] = 0
                continue
            vol = np.std(returns) * np.sqrt(252)
            volatilities[symbol] = vol
        return volatilities

    def optimize_allocation(
        self,
        price_data: Dict[str, List[float]],
        target_return: Optional[float] = None,
        max_volatility: Optional[float] = None,
        max_weight: float = 0.4,
        min_weight: float = 0.05,
    ) -> Dict[str, float]:
        """
        Optimize allocation using Modern Portfolio Theory

        Args:
            price_data: Historical price data
            target_return: Target portfolio return (annualized)
            max_volatility: Maximum allowed portfolio volatility
            max_weight: Maximum weight per asset
            min_weight: Minimum weight per asset

        Returns:
            Optimal allocation weights
        """
        symbols = list(price_data.keys())
        n_assets = len(symbols)
        if n_assets == 0:
            return {}
        if n_assets == 1:
            return {symbols[0]: 1.0}
        returns_data = self._prepare_returns_data(price_data)
        if returns_data is None or returns_data.empty:
            return self._equal_weight_allocation(symbols)
        expected_returns = returns_data.mean() * 252
        cov_matrix = returns_data.cov() * 252

        def objective(weights):
            portfolio_var = np.dot(weights, np.dot(cov_matrix.values, weights))
            return portfolio_var

        constraints = [{"type": "eq", "fun": lambda x: np.sum(x) - 1}]
        if target_return is not None:
            constraints.append(
                {"type": "eq", "fun": lambda x: np.dot(x, expected_returns.values) - target_return}
            )
        if max_volatility is not None:
            constraints.append(
                {
                    "type": "ineq",
                    "fun": lambda x: max_volatility**2 - np.dot(x, np.dot(cov_matrix.values, x)),
                }
            )
        bounds = [(min_weight, max_weight) for _ in range(n_assets)]
        initial_weights = np.array([1.0 / n_assets] * n_assets)
        try:
            result = minimize(
                objective, initial_weights, method="SLSQP", bounds=bounds, constraints=constraints
            )
            if result.success:
                optimal_weights = result.x
                return {symbol: weight for symbol, weight in zip(symbols, optimal_weights)}
            else:
                logger.warning("Optimization failed, using equal weights")
                return self._equal_weight_allocation(symbols)
        except Exception as e:
            logger.error(f"Optimization error: {e}")
            return self._equal_weight_allocation(symbols)

    def _prepare_returns_data(self, price_data: Dict[str, List[float]]) -> Optional[pd.DataFrame]:
        """Prepare returns data for optimization"""
        returns_data = {}
        min_length = float("inf")
        for symbol, prices in price_data.items():
            if len(prices) > 1:
                returns = [prices[i] / prices[i - 1] - 1 for i in range(1, len(prices))]
                returns_data[symbol] = returns
                min_length = min(min_length, len(returns))
        if min_length == float("inf") or min_length < 2:
            return None
        for symbol in returns_data:
            returns_data[symbol] = returns_data[symbol][-min_length:]
        return pd.DataFrame(returns_data)

    def calculate_efficient_frontier(
        self, price_data: Dict[str, List[float]], num_points: int = 50
    ) -> List[Dict[str, float]]:
        """
        Calculate efficient frontier portfolios

        Args:
            price_data: Historical price data
            num_points: Number of points on frontier

        Returns:
            List of portfolio allocations along efficient frontier
        """
        returns_data = self._prepare_returns_data(price_data)
        if returns_data is None or returns_data.empty:
            return [self._equal_weight_allocation(list(price_data.keys()))]
        expected_returns = returns_data.mean() * 252
        min_return = expected_returns.min()
        max_return = expected_returns.max()
        target_returns = np.linspace(min_return, max_return, num_points)
        efficient_portfolios = []
        for target_return in target_returns:
            allocation = self.optimize_allocation(
                price_data, target_return=target_return, max_weight=1.0, min_weight=0.0
            )
            efficient_portfolios.append(allocation)
        return efficient_portfolios

    def calculate_sharpe_optimal(
        self, price_data: Dict[str, List[float]], risk_free_rate: float = 0.02
    ) -> Dict[str, float]:
        """
        Calculate portfolio with maximum Sharpe ratio

        Args:
            price_data: Historical price data
            risk_free_rate: Annual risk-free rate

        Returns:
            Optimal allocation weights
        """
        returns_data = self._prepare_returns_data(price_data)
        if returns_data is None or returns_data.empty:
            return self._equal_weight_allocation(list(price_data.keys()))
        expected_returns = returns_data.mean() * 252
        cov_matrix = returns_data.cov() * 252

        def objective(weights):
            portfolio_return = np.dot(weights, expected_returns.values)
            portfolio_var = np.dot(weights, np.dot(cov_matrix.values, weights))
            portfolio_vol = np.sqrt(portfolio_var)
            if portfolio_vol == 0:
                return -np.inf
            sharpe_ratio = (portfolio_return - risk_free_rate) / portfolio_vol
            return -sharpe_ratio

        symbols = list(price_data.keys())
        n_assets = len(symbols)
        constraints = [{"type": "eq", "fun": lambda x: np.sum(x) - 1}]
        bounds = [(0, 1) for _ in range(n_assets)]
        initial_weights = np.array([1.0 / n_assets] * n_assets)
        try:
            result = minimize(
                objective, initial_weights, method="SLSQP", bounds=bounds, constraints=constraints
            )
            if result.success:
                optimal_weights = result.x
                return {symbol: weight for symbol, weight in zip(symbols, optimal_weights)}
            else:
                logger.warning("Sharpe optimization failed, using equal weights")
                return self._equal_weight_allocation(symbols)
        except Exception as e:
            logger.error(f"Sharpe optimization error: {e}")
            return self._equal_weight_allocation(symbols)
