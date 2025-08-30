"""
Portfolio Weights to K-Factor Mapping with Sentiment Overlay
"""

import os
import json
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
import numpy as np

from src.ai.news_rules import NewsRulesEngine

logger = logging.getLogger(__name__)


class KFactorMapper:
    """Map portfolio weights to per-strategy K-factors with sentiment overlay"""
    
    def __init__(self):
        self.config = {
            'BASE_K_FACTOR': float(os.getenv('BASE_K_FACTOR', '0.25')),
            'K_FACTOR_MIN': float(os.getenv('K_FACTOR_MIN', '0.05')),
            'K_FACTOR_MAX': float(os.getenv('K_FACTOR_MAX', '1.0')),
            'HYSTERESIS_THRESHOLD': float(os.getenv('HYSTERESIS_THRESHOLD', '0.02')),
            'PORTFOLIO_ALPHA': float(os.getenv('PORTFOLIO_ALPHA', '1.0'))  # Portfolio weight scaling
        }
        
        # News rules integration
        self.news_rules_engine = NewsRulesEngine()
        
        # Current K-factor state
        self.current_k_factors: Dict[str, float] = {}
        self.portfolio_weights: Dict[str, float] = {}
        self.last_portfolio_update: Optional[datetime] = None
        
        # Hysteresis state to prevent whipsawing
        self.previous_adjustments: Dict[str, float] = {}
        
    async def load_portfolio_weights(self) -> bool:
        """Load latest portfolio weights"""
        
        try:
            # Try latest weights file
            weights_file = "reports/portfolio/weights_latest.json"
            
            if os.path.exists(weights_file):
                with open(weights_file, 'r') as f:
                    data = json.load(f)
                
                self.portfolio_weights = data.get('weights', {})
                self.last_portfolio_update = datetime.fromisoformat(data['timestamp'])
                
                logger.info(f"Loaded portfolio weights: {len(self.portfolio_weights)} strategies")
                return True
            
            else:
                logger.warning("No portfolio weights file found")
                return False
                
        except Exception as e:
            logger.error(f"Failed to load portfolio weights: {e}")
            return False
    
    async def calculate_k_factors(self, symbol: str, strategy_name: str, 
                                capital_pct: float = 1.0) -> float:
        """Calculate K-factor for strategy-symbol combination"""
        
        # Load portfolio weights if needed
        if not self.portfolio_weights or not self.last_portfolio_update:
            await self.load_portfolio_weights()
        
        # Create strategy-symbol key
        strategy_key = f"{strategy_name}_{symbol}"
        
        # Get base weight from portfolio
        portfolio_weight = self.portfolio_weights.get(strategy_key, 0.0)
        
        if portfolio_weight == 0.0:
            # Not in portfolio - use base K-factor
            base_k_factor = self.config['BASE_K_FACTOR']
        else:
            # Map portfolio weight to K-factor
            base_k_factor = portfolio_weight * self.config['PORTFOLIO_ALPHA']
        
        # Apply capital scaling (for canary mode)
        scaled_k_factor = base_k_factor * capital_pct
        
        # Apply news sentiment adjustments
        sentiment_adjusted_k = await self._apply_news_adjustments(symbol, scaled_k_factor)
        
        # Apply hysteresis to prevent excessive changes
        final_k_factor = self._apply_hysteresis(strategy_key, sentiment_adjusted_k)
        
        # Respect bounds
        final_k_factor = np.clip(final_k_factor, 
                               self.config['K_FACTOR_MIN'], 
                               self.config['K_FACTOR_MAX'])
        
        # Update state
        self.current_k_factors[strategy_key] = final_k_factor
        
        logger.debug(f"K-factor for {strategy_key}: portfolio={portfolio_weight:.3f} → "
                    f"base={base_k_factor:.3f} → scaled={scaled_k_factor:.3f} → "
                    f"sentiment={sentiment_adjusted_k:.3f} → final={final_k_factor:.3f}")
        
        return final_k_factor
    
    async def _apply_news_adjustments(self, symbol: str, base_k_factor: float) -> float:
        """Apply news sentiment adjustments to K-factor"""
        
        try:
            # Get K-factor adjustment from news rules
            adjusted_k = self.news_rules_engine.get_k_factor_adjustment(symbol, base_k_factor)
            
            return adjusted_k
            
        except Exception as e:
            logger.error(f"Failed to apply news adjustments for {symbol}: {e}")
            return base_k_factor
    
    def _apply_hysteresis(self, strategy_key: str, new_k_factor: float) -> float:
        """Apply hysteresis to prevent K-factor whipsawing"""
        
        current_k = self.current_k_factors.get(strategy_key, new_k_factor)
        
        # Calculate change magnitude
        change = abs(new_k_factor - current_k)
        
        # Only apply change if it exceeds hysteresis threshold
        if change > self.config['HYSTERESIS_THRESHOLD']:
            return new_k_factor
        else:
            # Keep current value (no change)
            return current_k
    
    async def get_strategy_bias_for_symbol(self, symbol: str) -> Tuple[str, float]:
        """Get strategy bias and strength for symbol"""
        
        return self.news_rules_engine.get_strategy_bias(symbol)
    
    async def bulk_calculate_k_factors(self, symbols: List[str], 
                                     strategies: List[str],
                                     capital_pct: float = 1.0) -> Dict[str, Dict[str, float]]:
        """Calculate K-factors for multiple symbol-strategy combinations"""
        
        k_factor_matrix = {}
        
        for symbol in symbols:
            k_factor_matrix[symbol] = {}
            
            for strategy in strategies:
                k_factor = await self.calculate_k_factors(symbol, strategy, capital_pct)
                k_factor_matrix[symbol][strategy] = k_factor
        
        return k_factor_matrix
    
    def get_portfolio_attribution(self) -> Dict[str, Any]:
        """Get current portfolio attribution and K-factor breakdown"""
        
        attribution = {
            'portfolio_weights': self.portfolio_weights.copy(),
            'current_k_factors': self.current_k_factors.copy(),
            'news_adjustments': {},
            'total_portfolio_weight': sum(self.portfolio_weights.values()),
            'total_k_factor_allocated': sum(self.current_k_factors.values()),
            'last_portfolio_update': self.last_portfolio_update.isoformat() if self.last_portfolio_update else None
        }
        
        # Get news adjustments
        news_summary = self.news_rules_engine.get_active_adjustments_summary()
        attribution['news_adjustments'] = news_summary['adjustments_by_symbol']
        
        # Calculate strategy attribution
        strategy_attribution = {}
        for strategy_key, k_factor in self.current_k_factors.items():
            parts = strategy_key.split('_', 1)
            if len(parts) == 2:
                strategy, symbol = parts
                
                if strategy not in strategy_attribution:
                    strategy_attribution[strategy] = {
                        'total_k_factor': 0.0,
                        'symbol_count': 0,
                        'symbols': []
                    }
                
                strategy_attribution[strategy]['total_k_factor'] += k_factor
                strategy_attribution[strategy]['symbol_count'] += 1
                strategy_attribution[strategy]['symbols'].append({
                    'symbol': symbol,
                    'k_factor': k_factor,
                    'portfolio_weight': self.portfolio_weights.get(strategy_key, 0.0)
                })
        
        attribution['strategy_attribution'] = strategy_attribution
        
        return attribution
    
    async def refresh_all_k_factors(self, capital_pct: float = 1.0) -> Dict[str, float]:
        """Refresh all K-factors with current portfolio and sentiment"""
        
        logger.info("Refreshing all K-factors...")
        
        # Reload portfolio weights
        await self.load_portfolio_weights()
        
        refreshed_k_factors = {}
        
        # Update all current K-factors
        for strategy_key in self.portfolio_weights.keys():
            parts = strategy_key.split('_', 1)
            if len(parts) == 2:
                strategy, symbol = parts
                
                k_factor = await self.calculate_k_factors(symbol, strategy, capital_pct)
                refreshed_k_factors[strategy_key] = k_factor
        
        logger.info(f"Refreshed {len(refreshed_k_factors)} K-factors")
        
        return refreshed_k_factors
    
    def get_symbol_k_factor_summary(self, symbol: str) -> Dict[str, Any]:
        """Get K-factor summary for specific symbol"""
        
        symbol_strategies = {}
        total_k_factor = 0.0
        
        for strategy_key, k_factor in self.current_k_factors.items():
            if strategy_key.endswith(f'_{symbol}'):
                strategy = strategy_key.replace(f'_{symbol}', '')
                symbol_strategies[strategy] = {
                    'k_factor': k_factor,
                    'portfolio_weight': self.portfolio_weights.get(strategy_key, 0.0)
                }
                total_k_factor += k_factor
        
        # Get news adjustments
        news_adjustments = self.news_rules_engine.active_adjustments.get(symbol, {})
        
        return {
            'symbol': symbol,
            'strategies': symbol_strategies,
            'total_k_factor': total_k_factor,
            'news_adjustments': {
                'k_factor_delta': news_adjustments.get('combined_adjustments', {}).get('k_factor_delta', 0.0),
                'strategy_bias': news_adjustments.get('combined_adjustments', {}).get('strategy_bias', 'neutral'),
                'active_rules': len(news_adjustments.get('triggered_rules', [])),
                'last_update': news_adjustments.get('timestamp', datetime.min).isoformat() if news_adjustments else None
            },
            'effective_exposure': total_k_factor,
            'last_calculation': datetime.now().isoformat()
        }