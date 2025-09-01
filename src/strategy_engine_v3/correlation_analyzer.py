"""
Correlation Analyzer - Analyze market correlations and relationships.

Analyzes:
- Asset correlations
- Market regime detection
- Lead-lag relationships
- Sector rotations
"""

import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel


class CorrelationMatrix(BaseModel):
    """Correlation matrix for multiple assets."""
    
    symbols: List[str]
    matrix: List[List[float]]  # NxN correlation matrix
    period: str  # Time period for calculation
    timestamp: datetime
    

class MarketRegime(BaseModel):
    """Market regime classification."""
    
    regime: str  # bull, bear, sideways, volatile
    confidence: float
    indicators: Dict[str, float]
    start_date: Optional[datetime]
    duration_days: Optional[int]
    

class LeadLagRelationship(BaseModel):
    """Lead-lag relationship between assets."""
    
    leader: str
    follower: str
    lag_periods: int  # Number of periods lag
    correlation: float
    confidence: float
    

class SectorRotation(BaseModel):
    """Sector rotation analysis."""
    
    from_sector: str
    to_sector: str
    strength: float  # Rotation strength
    momentum: float
    timestamp: datetime


class CorrelationAnalyzer:
    """
    Analyzer for market correlations and relationships.
    
    Features:
    - Rolling correlation calculation
    - Regime detection
    - Lead-lag analysis
    - Sector rotation tracking
    """
    
    def __init__(self):
        """Initialize correlation analyzer."""
        self.price_data: Dict[str, List[float]] = {}
        self.correlation_cache: Dict[str, CorrelationMatrix] = {}
        self.current_regime: Optional[MarketRegime] = None
        
    def add_price_data(self, symbol: str, prices: List[float]) -> None:
        """Add price data for a symbol."""
        self.price_data[symbol] = prices
        
    def calculate_correlation_matrix(
        self, 
        symbols: List[str], 
        period: int = 30
    ) -> CorrelationMatrix:
        """Calculate correlation matrix for given symbols."""
        n = len(symbols)
        matrix = [[0.0] * n for _ in range(n)]
        
        for i, symbol1 in enumerate(symbols):
            for j, symbol2 in enumerate(symbols):
                if i == j:
                    matrix[i][j] = 1.0
                else:
                    corr = self._calculate_correlation(symbol1, symbol2, period)
                    matrix[i][j] = corr
                    matrix[j][i] = corr  # Symmetric
                    
        result = CorrelationMatrix(
            symbols=symbols,
            matrix=matrix,
            period=f"{period}d",
            timestamp=datetime.utcnow()
        )
        
        # Cache result
        cache_key = f"{'_'.join(symbols)}_{period}"
        self.correlation_cache[cache_key] = result
        
        return result
        
    def _calculate_correlation(
        self, 
        symbol1: str, 
        symbol2: str, 
        period: int
    ) -> float:
        """Calculate correlation between two symbols."""
        if symbol1 not in self.price_data or symbol2 not in self.price_data:
            return 0.0
            
        prices1 = self.price_data[symbol1][-period:]
        prices2 = self.price_data[symbol2][-period:]
        
        if len(prices1) != len(prices2) or len(prices1) < 2:
            return 0.0
            
        # Calculate returns
        returns1 = [(prices1[i] - prices1[i-1]) / prices1[i-1] 
                    for i in range(1, len(prices1))]
        returns2 = [(prices2[i] - prices2[i-1]) / prices2[i-1] 
                    for i in range(1, len(prices2))]
        
        # Calculate correlation
        if len(returns1) == 0:
            return 0.0
            
        mean1 = sum(returns1) / len(returns1)
        mean2 = sum(returns2) / len(returns2)
        
        cov = sum((r1 - mean1) * (r2 - mean2) 
                  for r1, r2 in zip(returns1, returns2)) / len(returns1)
        
        std1 = (sum((r - mean1) ** 2 for r in returns1) / len(returns1)) ** 0.5
        std2 = (sum((r - mean2) ** 2 for r in returns2) / len(returns2)) ** 0.5
        
        if std1 == 0 or std2 == 0:
            return 0.0
            
        return cov / (std1 * std2)
        
    def detect_market_regime(self) -> MarketRegime:
        """Detect current market regime."""
        indicators = {}
        
        # Calculate market indicators
        if "SPY" in self.price_data:
            spy_prices = self.price_data["SPY"]
            
            # Trend indicator (SMA comparison)
            if len(spy_prices) >= 50:
                sma20 = sum(spy_prices[-20:]) / 20
                sma50 = sum(spy_prices[-50:]) / 50
                indicators["trend"] = (sma20 - sma50) / sma50 * 100
                
            # Volatility indicator
            if len(spy_prices) >= 20:
                returns = [(spy_prices[i] - spy_prices[i-1]) / spy_prices[i-1] 
                          for i in range(-19, 0)]
                indicators["volatility"] = np.std(returns) * np.sqrt(252) * 100
                
            # Momentum indicator
            if len(spy_prices) >= 14:
                momentum = (spy_prices[-1] - spy_prices[-14]) / spy_prices[-14] * 100
                indicators["momentum"] = momentum
                
        # Classify regime
        regime = self._classify_regime(indicators)
        
        self.current_regime = regime
        return regime
        
    def _classify_regime(self, indicators: Dict[str, float]) -> MarketRegime:
        """Classify market regime based on indicators."""
        trend = indicators.get("trend", 0)
        volatility = indicators.get("volatility", 20)
        momentum = indicators.get("momentum", 0)
        
        # Simple classification logic
        if trend > 2 and volatility < 20:
            regime = "bull"
            confidence = 0.8
        elif trend < -2 and volatility > 25:
            regime = "bear"
            confidence = 0.7
        elif abs(trend) < 1 and volatility < 15:
            regime = "sideways"
            confidence = 0.6
        elif volatility > 30:
            regime = "volatile"
            confidence = 0.9
        else:
            regime = "mixed"
            confidence = 0.5
            
        return MarketRegime(
            regime=regime,
            confidence=confidence,
            indicators=indicators,
            start_date=datetime.utcnow(),
            duration_days=0
        )
        
    def find_lead_lag_relationships(
        self, 
        symbols: List[str], 
        max_lag: int = 5
    ) -> List[LeadLagRelationship]:
        """Find lead-lag relationships between symbols."""
        relationships = []
        
        for i, symbol1 in enumerate(symbols):
            for symbol2 in symbols[i+1:]:
                best_lag = 0
                best_corr = 0.0
                
                for lag in range(1, max_lag + 1):
                    corr = self._calculate_lagged_correlation(symbol1, symbol2, lag)
                    if abs(corr) > abs(best_corr):
                        best_corr = corr
                        best_lag = lag
                        
                if abs(best_corr) > 0.5:  # Significant correlation
                    rel = LeadLagRelationship(
                        leader=symbol1 if best_corr > 0 else symbol2,
                        follower=symbol2 if best_corr > 0 else symbol1,
                        lag_periods=best_lag,
                        correlation=abs(best_corr),
                        confidence=min(abs(best_corr), 0.9)
                    )
                    relationships.append(rel)
                    
        return relationships
        
    def _calculate_lagged_correlation(
        self, 
        symbol1: str, 
        symbol2: str, 
        lag: int
    ) -> float:
        """Calculate correlation with lag."""
        if symbol1 not in self.price_data or symbol2 not in self.price_data:
            return 0.0
            
        prices1 = self.price_data[symbol1]
        prices2 = self.price_data[symbol2]
        
        if len(prices1) < lag + 20 or len(prices2) < lag + 20:
            return 0.0
            
        # Align data with lag
        aligned1 = prices1[:-lag]
        aligned2 = prices2[lag:]
        
        # Use last 20 periods for correlation
        return self._calculate_correlation_from_prices(
            aligned1[-20:], 
            aligned2[-20:]
        )
        
    def _calculate_correlation_from_prices(
        self, 
        prices1: List[float], 
        prices2: List[float]
    ) -> float:
        """Calculate correlation from price lists."""
        if len(prices1) != len(prices2) or len(prices1) < 2:
            return 0.0
            
        # Convert to returns and calculate correlation
        returns1 = [(prices1[i] - prices1[i-1]) / prices1[i-1] 
                    for i in range(1, len(prices1))]
        returns2 = [(prices2[i] - prices2[i-1]) / prices2[i-1] 
                    for i in range(1, len(prices2))]
        
        if not returns1:
            return 0.0
            
        # Calculate correlation coefficient
        n = len(returns1)
        sum1 = sum(returns1)
        sum2 = sum(returns2)
        sum1_sq = sum(r**2 for r in returns1)
        sum2_sq = sum(r**2 for r in returns2)
        sum_prod = sum(r1*r2 for r1, r2 in zip(returns1, returns2))
        
        num = n * sum_prod - sum1 * sum2
        den = ((n * sum1_sq - sum1**2) * (n * sum2_sq - sum2**2)) ** 0.5
        
        if den == 0:
            return 0.0
            
        return num / den
        
    def analyze_sector_rotation(
        self, 
        sector_etfs: Dict[str, str]
    ) -> List[SectorRotation]:
        """Analyze sector rotation patterns."""
        rotations = []
        
        # Calculate relative strength for each sector
        sector_strength = {}
        for sector, etf in sector_etfs.items():
            if etf in self.price_data:
                prices = self.price_data[etf]
                if len(prices) >= 20:
                    # Simple relative strength: recent vs past performance
                    recent_return = (prices[-1] - prices[-5]) / prices[-5]
                    past_return = (prices[-5] - prices[-20]) / prices[-20]
                    sector_strength[sector] = recent_return - past_return
                    
        # Identify rotations
        sorted_sectors = sorted(sector_strength.items(), key=lambda x: x[1])
        
        if len(sorted_sectors) >= 2:
            # Weakest to strongest rotation
            weakest = sorted_sectors[0]
            strongest = sorted_sectors[-1]
            
            if strongest[1] > 0.02 and weakest[1] < -0.02:  # Significant rotation
                rotation = SectorRotation(
                    from_sector=weakest[0],
                    to_sector=strongest[0],
                    strength=abs(strongest[1] - weakest[1]),
                    momentum=strongest[1],
                    timestamp=datetime.utcnow()
                )
                rotations.append(rotation)
                
        return rotations
        
    def get_diversification_score(self, portfolio: Dict[str, float]) -> float:
        """Calculate portfolio diversification score."""
        if len(portfolio) < 2:
            return 0.0
            
        symbols = list(portfolio.keys())
        weights = list(portfolio.values())
        
        # Get correlation matrix
        corr_matrix = self.calculate_correlation_matrix(symbols)
        
        # Calculate average correlation
        total_corr = 0.0
        count = 0
        for i in range(len(symbols)):
            for j in range(i+1, len(symbols)):
                total_corr += abs(corr_matrix.matrix[i][j]) * weights[i] * weights[j]
                count += 1
                
        if count == 0:
            return 1.0
            
        avg_corr = total_corr / count
        
        # Diversification score: 1 - average correlation
        return max(0.0, min(1.0, 1.0 - avg_corr))
        
    def get_correlation_clusters(
        self, 
        symbols: List[str], 
        threshold: float = 0.7
    ) -> List[List[str]]:
        """Find clusters of highly correlated assets."""
        corr_matrix = self.calculate_correlation_matrix(symbols)
        clusters = []
        used = set()
        
        for i, symbol1 in enumerate(symbols):
            if symbol1 in used:
                continue
                
            cluster = [symbol1]
            used.add(symbol1)
            
            for j, symbol2 in enumerate(symbols):
                if i != j and symbol2 not in used:
                    if abs(corr_matrix.matrix[i][j]) >= threshold:
                        cluster.append(symbol2)
                        used.add(symbol2)
                        
            if len(cluster) > 1:
                clusters.append(cluster)
                
        return clusters