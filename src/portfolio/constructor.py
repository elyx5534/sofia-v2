"""
Portfolio Construction with HRP/VolTarget/Kelly
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import leaves_list, linkage
from scipy.spatial.distance import squareform
from sklearn.covariance import LedoitWolf

logger = logging.getLogger(__name__)


class PortfolioConstructor:
    """Build risk-adjusted portfolios from strategy returns"""

    def __init__(self, method: str = "hrp"):
        self.method = method.lower()
        self.vol_target = float(os.getenv("VOLATILITY_TARGET", "10.0")) / 100  # 10% annual
        self.kelly_cap = float(os.getenv("KELLY_CAP", "0.5"))
        self.max_symbol_weight = float(os.getenv("MAX_SYMBOL_WEIGHT", "30")) / 100
        self.max_strategy_weight = float(os.getenv("MAX_STRATEGY_WEIGHT", "20")) / 100
        self.turnover_penalty = 0.01  # 1% penalty for turnover

        # Risk-free rate (annualized)
        self.risk_free_rate = 0.02

        # Minimum periods for estimation
        self.min_periods = 30

    def build_portfolio(
        self, returns_data: Dict[str, pd.Series], current_weights: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """Build portfolio weights using specified method"""

        if not returns_data:
            return {"error": "No returns data provided"}

        # Convert to DataFrame
        returns_df = pd.DataFrame(returns_data)
        returns_df = returns_df.fillna(0)  # Fill missing with 0 return

        if len(returns_df) < self.min_periods:
            logger.warning(f"Insufficient data: {len(returns_df)} periods, need {self.min_periods}")
            return {"error": f"Need at least {self.min_periods} periods, have {len(returns_df)}"}

        logger.info(f"Building portfolio with {self.method} method, {len(returns_df)} periods")

        try:
            if self.method == "hrp":
                weights = self._hierarchical_risk_parity(returns_df)
            elif self.method == "voltarget":
                weights = self._volatility_targeting(returns_df)
            elif self.method == "kelly":
                weights = self._kelly_optimal(returns_df)
            elif self.method == "equal":
                weights = self._equal_weight(returns_df)
            else:
                raise ValueError(f"Unknown portfolio method: {self.method}")

            # Apply constraints
            weights = self._apply_constraints(weights, returns_df)

            # Apply turnover penalty if current weights provided
            if current_weights:
                weights = self._apply_turnover_penalty(weights, current_weights)

            # Calculate portfolio metrics
            metrics = self._calculate_portfolio_metrics(weights, returns_df)

            return {
                "method": self.method,
                "weights": weights,
                "metrics": metrics,
                "n_assets": len(weights),
                "n_periods": len(returns_df),
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Portfolio construction failed: {e}")
            return {"error": str(e)}

    def _hierarchical_risk_parity(self, returns: pd.DataFrame) -> Dict[str, float]:
        """Hierarchical Risk Parity (HRP) allocation"""

        # Calculate correlation matrix
        corr_matrix = returns.corr()

        # Handle missing correlations
        corr_matrix = corr_matrix.fillna(0)
        np.fill_diagonal(corr_matrix.values, 1.0)

        # Convert correlation to distance
        distance_matrix = np.sqrt((1 - corr_matrix) / 2)

        # Hierarchical clustering
        condensed_distances = squareform(distance_matrix.values)
        linkage_matrix = linkage(condensed_distances, method="single")

        # Get clustered order
        sorted_indices = leaves_list(linkage_matrix)
        sorted_assets = [returns.columns[i] for i in sorted_indices]

        # Calculate HRP weights recursively
        weights = self._hrp_recursive(sorted_assets, corr_matrix, returns)

        return {asset: weights.get(asset, 0) for asset in returns.columns}

    def _hrp_recursive(
        self, assets: List[str], corr_matrix: pd.DataFrame, returns: pd.DataFrame
    ) -> Dict[str, float]:
        """Recursive HRP weight calculation"""

        if len(assets) == 1:
            return {assets[0]: 1.0}

        # Split assets into two clusters
        mid_point = len(assets) // 2
        cluster1 = assets[:mid_point]
        cluster2 = assets[mid_point:]

        # Calculate cluster volatilities
        vol1 = self._cluster_variance(cluster1, corr_matrix, returns)
        vol2 = self._cluster_variance(cluster2, corr_matrix, returns)

        # Allocate between clusters (inverse volatility)
        total_vol = vol1 + vol2
        if total_vol > 0:
            alpha1 = vol2 / total_vol
            alpha2 = vol1 / total_vol
        else:
            alpha1 = alpha2 = 0.5

        # Recursive allocation within clusters
        weights1 = self._hrp_recursive(cluster1, corr_matrix, returns)
        weights2 = self._hrp_recursive(cluster2, corr_matrix, returns)

        # Scale by cluster allocation
        final_weights = {}
        for asset, weight in weights1.items():
            final_weights[asset] = weight * alpha1
        for asset, weight in weights2.items():
            final_weights[asset] = weight * alpha2

        return final_weights

    def _cluster_variance(
        self, assets: List[str], corr_matrix: pd.DataFrame, returns: pd.DataFrame
    ) -> float:
        """Calculate variance of equally weighted cluster"""
        if not assets:
            return 0

        cluster_corr = corr_matrix.loc[assets, assets]
        cluster_vols = returns[assets].std(ddof=1)

        # Equal weight assumption
        n = len(assets)
        weight = 1.0 / n

        # Portfolio variance
        variance = 0
        for i, asset_i in enumerate(assets):
            for j, asset_j in enumerate(assets):
                vol_i = cluster_vols.get(asset_i, 0.01)
                vol_j = cluster_vols.get(asset_j, 0.01)
                corr_ij = (
                    cluster_corr.loc[asset_i, asset_j]
                    if not pd.isna(cluster_corr.loc[asset_i, asset_j])
                    else 0
                )
                variance += weight * weight * vol_i * vol_j * corr_ij

        return max(variance, 1e-6)

    def _volatility_targeting(self, returns: pd.DataFrame) -> Dict[str, float]:
        """Volatility targeting allocation"""

        # Calculate individual volatilities (annualized)
        vols = returns.std(ddof=1) * np.sqrt(252)

        # Inverse volatility weights
        inv_vols = 1.0 / (vols + 1e-6)  # Add small constant to avoid division by zero
        weights = inv_vols / inv_vols.sum()

        # Scale to target volatility
        current_vol = np.sqrt(np.dot(weights, np.dot(returns.cov() * 252, weights)))
        if current_vol > 0:
            scale_factor = self.vol_target / current_vol
            weights *= scale_factor

        # Normalize
        weights /= weights.sum()

        return weights.to_dict()

    def _kelly_optimal(self, returns: pd.DataFrame) -> Dict[str, float]:
        """Kelly optimal allocation (capped)"""

        # Calculate expected returns (annualized)
        mu = returns.mean() * 252

        # Covariance matrix (annualized) with Ledoit-Wolf shrinkage
        try:
            lw = LedoitWolf()
            cov_shrunk = lw.fit(returns.values).covariance_ * 252
            sigma = pd.DataFrame(cov_shrunk, index=returns.columns, columns=returns.columns)
        except:
            sigma = returns.cov() * 252

        # Risk-free rate adjustment
        excess_returns = mu - self.risk_free_rate

        try:
            # Kelly weights: w = Σ^-1 * μ
            inv_sigma = pd.DataFrame(
                np.linalg.pinv(sigma.values), index=sigma.index, columns=sigma.columns
            )

            kelly_weights = inv_sigma.dot(excess_returns)

            # Cap weights
            kelly_weights = kelly_weights.clip(-self.kelly_cap, self.kelly_cap)

            # Handle negative weights (convert to 0)
            kelly_weights = kelly_weights.clip(0, None)

            # Normalize
            if kelly_weights.sum() > 0:
                kelly_weights /= kelly_weights.sum()
            else:
                # Fallback to equal weights
                kelly_weights = pd.Series(1.0 / len(returns.columns), index=returns.columns)

            return kelly_weights.to_dict()

        except np.linalg.LinAlgError:
            logger.warning("Singular covariance matrix, using equal weights")
            return self._equal_weight(returns)

    def _equal_weight(self, returns: pd.DataFrame) -> Dict[str, float]:
        """Equal weight allocation"""
        n_assets = len(returns.columns)
        weight = 1.0 / n_assets
        return {asset: weight for asset in returns.columns}

    def _apply_constraints(
        self, weights: Dict[str, float], returns: pd.DataFrame
    ) -> Dict[str, float]:
        """Apply portfolio constraints"""

        # Convert to series for easier manipulation
        w = pd.Series(weights)

        # Non-negative constraint
        w = w.clip(0, None)

        # Maximum weight constraints
        # Parse symbol and strategy from keys (format: "strategy_symbol")
        symbol_weights = {}
        strategy_weights = {}

        for key in w.index:
            parts = key.split("_", 1)
            if len(parts) == 2:
                strategy, symbol = parts
                symbol_weights[symbol] = symbol_weights.get(symbol, 0) + w[key]
                strategy_weights[strategy] = strategy_weights.get(strategy, 0) + w[key]

        # Apply symbol weight constraints
        for key in w.index:
            parts = key.split("_", 1)
            if len(parts) == 2:
                strategy, symbol = parts
                if symbol_weights[symbol] > self.max_symbol_weight:
                    scale_factor = self.max_symbol_weight / symbol_weights[symbol]
                    w[key] *= scale_factor

        # Apply strategy weight constraints
        for key in w.index:
            parts = key.split("_", 1)
            if len(parts) == 2:
                strategy, symbol = parts
                if strategy_weights[strategy] > self.max_strategy_weight:
                    scale_factor = self.max_strategy_weight / strategy_weights[strategy]
                    w[key] *= scale_factor

        # Normalize to sum to 1
        if w.sum() > 0:
            w /= w.sum()
        else:
            # Fallback to equal weights
            w = pd.Series(1.0 / len(w), index=w.index)

        return w.to_dict()

    def _apply_turnover_penalty(
        self, new_weights: Dict[str, float], current_weights: Dict[str, float]
    ) -> Dict[str, float]:
        """Apply turnover penalty to reduce excessive rebalancing"""

        # Calculate turnover
        turnover = 0
        for asset in set(new_weights.keys()) | set(current_weights.keys()):
            new_w = new_weights.get(asset, 0)
            current_w = current_weights.get(asset, 0)
            turnover += abs(new_w - current_w)

        # If turnover is high, blend with current weights
        if turnover > 0.2:  # 20% turnover threshold
            blend_factor = min(turnover * self.turnover_penalty, 0.5)

            blended_weights = {}
            for asset in set(new_weights.keys()) | set(current_weights.keys()):
                new_w = new_weights.get(asset, 0)
                current_w = current_weights.get(asset, 0)
                blended_weights[asset] = (1 - blend_factor) * new_w + blend_factor * current_w

            # Normalize
            total = sum(blended_weights.values())
            if total > 0:
                blended_weights = {k: v / total for k, v in blended_weights.items()}

            return blended_weights

        return new_weights

    def _calculate_portfolio_metrics(
        self, weights: Dict[str, float], returns: pd.DataFrame
    ) -> Dict[str, Any]:
        """Calculate portfolio performance metrics"""

        # Convert weights to series
        w = pd.Series(weights)

        # Align with returns
        w = w.reindex(returns.columns, fill_value=0)

        # Portfolio returns
        port_returns = returns.dot(w)

        # Performance metrics (annualized)
        mean_return = port_returns.mean() * 252
        volatility = port_returns.std(ddof=1) * np.sqrt(252)
        sharpe = (mean_return - self.risk_free_rate) / volatility if volatility > 0 else 0

        # Maximum drawdown
        cumulative = (1 + port_returns).cumprod()
        rolling_max = cumulative.expanding().max()
        drawdown = (cumulative - rolling_max) / rolling_max
        max_drawdown = drawdown.min()

        # Diversification metrics
        effective_assets = 1 / (w**2).sum() if (w**2).sum() > 0 else 0
        concentration = (w**2).sum()

        # Risk decomposition
        risk_contrib = self._calculate_risk_contributions(w, returns)

        return {
            "expected_return": float(mean_return),
            "volatility": float(volatility),
            "sharpe_ratio": float(sharpe),
            "max_drawdown": float(max_drawdown),
            "effective_n_assets": float(effective_assets),
            "concentration_hhi": float(concentration),
            "risk_contributions": risk_contrib,
            "total_weight": float(w.sum()),
            "n_positions": int((w > 0.001).sum()),  # Positions > 0.1%
        }

    def _calculate_risk_contributions(
        self, weights: pd.Series, returns: pd.DataFrame
    ) -> Dict[str, float]:
        """Calculate risk contributions of each asset"""

        # Covariance matrix
        cov_matrix = returns.cov() * 252

        # Portfolio variance
        port_var = np.dot(weights, np.dot(cov_matrix, weights))

        if port_var <= 0:
            return {asset: 0.0 for asset in weights.index}

        # Marginal risk contributions
        marginal_contrib = np.dot(cov_matrix, weights)

        # Risk contributions = weight * marginal contribution / portfolio volatility
        risk_contrib = weights * marginal_contrib / port_var

        return risk_contrib.to_dict()

    def generate_portfolio_report(
        self, portfolio_result: Dict[str, Any], returns_data: Dict[str, pd.Series]
    ) -> str:
        """Generate HTML portfolio construction report"""

        if "error" in portfolio_result:
            return (
                f"<p class='error'>Portfolio construction failed: {portfolio_result['error']}</p>"
            )

        weights = portfolio_result["weights"]
        metrics = portfolio_result["metrics"]

        # Sort weights by value
        sorted_weights = sorted(weights.items(), key=lambda x: x[1], reverse=True)

        # Create weights table
        weights_table = """
        <table class="weights-table">
            <thead>
                <tr><th>Strategy-Symbol</th><th>Weight (%)</th><th>Risk Contrib (%)</th></tr>
            </thead>
            <tbody>
        """

        risk_contribs = metrics.get("risk_contributions", {})
        for strategy_symbol, weight in sorted_weights:
            if weight > 0.001:  # Only show > 0.1%
                risk_contrib = risk_contribs.get(strategy_symbol, 0) * 100
                weights_table += f"""
                    <tr>
                        <td>{strategy_symbol}</td>
                        <td>{weight*100:.1f}%</td>
                        <td>{risk_contrib:.1f}%</td>
                    </tr>
                """

        weights_table += "</tbody></table>"

        # Portfolio metrics
        metrics_html = f"""
        <div class="metrics-grid">
            <div class="metric-card">
                <h4>Expected Return</h4>
                <div class="metric-value">{metrics['expected_return']*100:.1f}%</div>
            </div>
            <div class="metric-card">
                <h4>Volatility</h4>
                <div class="metric-value">{metrics['volatility']*100:.1f}%</div>
            </div>
            <div class="metric-card">
                <h4>Sharpe Ratio</h4>
                <div class="metric-value">{metrics['sharpe_ratio']:.2f}</div>
            </div>
            <div class="metric-card">
                <h4>Max Drawdown</h4>
                <div class="metric-value">{metrics['max_drawdown']*100:.1f}%</div>
            </div>
            <div class="metric-card">
                <h4>Effective Assets</h4>
                <div class="metric-value">{metrics['effective_n_assets']:.1f}</div>
            </div>
            <div class="metric-card">
                <h4>Concentration</h4>
                <div class="metric-value">{metrics['concentration_hhi']:.3f}</div>
            </div>
        </div>
        """

        # Full HTML report
        html = f"""
        <div class="portfolio-report">
            <h2>Portfolio Construction Report - {portfolio_result['method'].upper()}</h2>
            <p>Generated: {portfolio_result['timestamp']}</p>
            <p>Assets: {portfolio_result['n_assets']}, Periods: {portfolio_result['n_periods']}</p>

            <h3>Portfolio Metrics</h3>
            {metrics_html}

            <h3>Asset Weights</h3>
            {weights_table}
        </div>
        """

        return html
