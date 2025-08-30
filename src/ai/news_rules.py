"""
News-Driven Trading Rules and Execution Hooks
"""

import os
import logging
import yaml
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from decimal import Decimal
import numpy as np

from .news_sentiment import SentimentScore, NewsSentimentAnalyzer
from .news_features import NewsFeatureEngine

logger = logging.getLogger(__name__)


class NewsTradeRule:
    """Individual news-based trading rule"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.enabled = config.get('enabled', True)
        
        # Rule conditions
        self.sentiment_threshold_pos = config.get('sentiment_threshold_pos', 0.5)
        self.sentiment_threshold_neg = config.get('sentiment_threshold_neg', -0.5)
        self.confidence_min = config.get('confidence_min', 0.6)
        self.volume_min = config.get('volume_min', 5)
        
        # Actions
        self.k_factor_adjustment = config.get('k_factor_adjustment', 0.1)
        self.strategy_bias_strength = config.get('strategy_bias_strength', 0.1)
        self.execution_override = config.get('execution_override', {})
    
    def evaluate(self, symbol: str, sentiment_score: SentimentScore, 
                features: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate rule and return actions"""
        
        if not self.enabled:
            return {'triggered': False}
        
        actions = {'triggered': False, 'adjustments': {}}
        
        # Check conditions
        conditions_met = self._check_conditions(sentiment_score, features)
        
        if conditions_met['triggered']:
            actions['triggered'] = True
            actions['rule_name'] = self.name
            actions['conditions'] = conditions_met
            
            # Generate adjustments
            actions['adjustments'] = self._generate_adjustments(
                sentiment_score, features, conditions_met
            )
        
        return actions
    
    def _check_conditions(self, sentiment_score: SentimentScore, 
                         features: Dict[str, Any]) -> Dict[str, Any]:
        """Check if rule conditions are met"""
        
        conditions = {
            'triggered': False,
            'sentiment_positive': False,
            'sentiment_negative': False,
            'high_confidence': False,
            'sufficient_volume': False,
            'event_detected': False,
            'anomaly_detected': False
        }
        
        # Sentiment conditions
        if sentiment_score.score_1h > self.sentiment_threshold_pos:
            conditions['sentiment_positive'] = True
        elif sentiment_score.score_1h < self.sentiment_threshold_neg:
            conditions['sentiment_negative'] = True
        
        # Confidence condition
        if sentiment_score.confidence_1h >= self.confidence_min:
            conditions['high_confidence'] = True
        
        # Volume condition
        if sentiment_score.volume_1h >= self.volume_min:
            conditions['sufficient_volume'] = True
        
        # Event detection
        if features.get('dominant_event_type') != 'none':
            conditions['event_detected'] = True
        
        # Anomaly detection
        if features.get('anomaly_score', 0) > 1.0:
            conditions['anomaly_detected'] = True
        
        # Rule-specific logic
        rule_triggered = self._evaluate_rule_logic(conditions, sentiment_score, features)
        conditions['triggered'] = rule_triggered
        
        return conditions
    
    def _evaluate_rule_logic(self, conditions: Dict[str, bool], 
                           sentiment_score: SentimentScore, 
                           features: Dict[str, Any]) -> bool:
        """Evaluate rule-specific logic"""
        
        # Default rule: strong sentiment + confidence + volume
        if self.name == 'sentiment_k_adjustment':
            return ((conditions['sentiment_positive'] or conditions['sentiment_negative']) and
                   conditions['high_confidence'] and conditions['sufficient_volume'])
        
        # Event-driven rule
        elif self.name == 'event_execution_override':
            return (conditions['event_detected'] and 
                   conditions['high_confidence'])
        
        # Regulatory/earnings rule
        elif self.name == 'regulatory_earnings_caution':
            event_type = features.get('dominant_event_type', '')
            return (event_type in ['regulatory', 'earnings'] and
                   conditions['sufficient_volume'])
        
        # Anomaly rule
        elif self.name == 'news_anomaly_twap':
            return (conditions['anomaly_detected'] and
                   sentiment_score.volume_1h > self.volume_min * 2)
        
        return False
    
    def _generate_adjustments(self, sentiment_score: SentimentScore, 
                            features: Dict[str, Any], 
                            conditions: Dict[str, bool]) -> Dict[str, Any]:
        """Generate trading adjustments based on rule"""
        
        adjustments = {}
        
        if self.name == 'sentiment_k_adjustment':
            # K-factor adjustment based on sentiment direction
            if conditions['sentiment_positive']:
                adjustments['k_factor_delta'] = self.k_factor_adjustment
                adjustments['strategy_bias'] = 'trend_following'
                adjustments['bias_strength'] = abs(sentiment_score.score_1h)
            elif conditions['sentiment_negative']:
                adjustments['k_factor_delta'] = self.k_factor_adjustment  # Also increase for vol opportunity
                adjustments['strategy_bias'] = 'mean_reversion'
                adjustments['bias_strength'] = abs(sentiment_score.score_1h)
        
        elif self.name == 'event_execution_override':
            # Override execution for events
            adjustments['execution_override'] = {
                'force_twap': True,
                'max_order_size_usd': 1000,
                'slippage_band_tightening': 0.5
            }
            
        elif self.name == 'regulatory_earnings_caution':
            # Caution for regulatory/earnings events
            adjustments['execution_override'] = {
                'maker_first_only': True,
                'order_size_cap_usd': 500,
                'post_only_timeout_extend': 2.0
            }
            
        elif self.name == 'news_anomaly_twap':
            # Force TWAP for news anomalies
            adjustments['execution_override'] = {
                'force_twap': True,
                'twap_slots_increase': 2.0,
                'slippage_band_tightening': 0.3
            }
        
        return adjustments


class NewsRulesEngine:
    """Engine for applying news-driven trading rules"""
    
    def __init__(self, rules_file: str = "config/news_rules.yaml"):
        self.rules_file = rules_file
        self.rules: List[NewsTradeRule] = []
        self.enabled = os.getenv('AI_NEWS_ENABLED', 'true').lower() == 'true'
        
        # Load rules
        self._load_rules()
        
        # Components
        self.sentiment_analyzer = NewsSentimentAnalyzer()
        self.feature_engine = NewsFeatureEngine()
        
        # State tracking
        self.active_adjustments: Dict[str, Dict[str, Any]] = {}
        self.adjustment_history: List[Dict[str, Any]] = []
        
        logger.info(f"News rules engine initialized with {len(self.rules)} rules")
    
    def _load_rules(self):
        """Load trading rules from YAML configuration"""
        
        # Default rules if file doesn't exist
        default_rules = {
            'sentiment_k_adjustment': {
                'enabled': True,
                'description': 'Adjust K-factor based on sentiment',
                'sentiment_threshold_pos': 0.5,
                'sentiment_threshold_neg': -0.5,
                'confidence_min': 0.6,
                'volume_min': 5,
                'k_factor_adjustment': 0.1
            },
            'event_execution_override': {
                'enabled': True,
                'description': 'Override execution for major events',
                'confidence_min': 0.7,
                'volume_min': 10,
                'execution_override': {
                    'force_twap': True,
                    'max_order_size_usd': 1000
                }
            },
            'regulatory_earnings_caution': {
                'enabled': True,
                'description': 'Cautious execution for regulatory/earnings',
                'event_types': ['regulatory', 'earnings'],
                'volume_min': 3,
                'execution_override': {
                    'maker_first_only': True,
                    'order_size_cap_usd': 500
                }
            },
            'news_anomaly_twap': {
                'enabled': True,
                'description': 'Force TWAP for news volume anomalies',
                'anomaly_threshold': 1.5,
                'volume_multiplier': 2.0,
                'execution_override': {
                    'force_twap': True,
                    'twap_slots_increase': 2.0
                }
            }
        }
        
        try:
            # Try to load from file
            if os.path.exists(self.rules_file):
                with open(self.rules_file, 'r') as f:
                    rules_config = yaml.safe_load(f)
            else:
                rules_config = default_rules
                # Save default rules
                os.makedirs(os.path.dirname(self.rules_file), exist_ok=True)
                with open(self.rules_file, 'w') as f:
                    yaml.dump(default_rules, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to load rules file: {e}, using defaults")
            rules_config = default_rules
        
        # Create rule objects
        self.rules = []
        for rule_name, rule_config in rules_config.items():
            rule = NewsTradeRule(rule_name, rule_config)
            self.rules.append(rule)
    
    async def apply_news_rules(self, symbol: str) -> Dict[str, Any]:
        """Apply all news rules for symbol and return adjustments"""
        
        if not self.enabled:
            return {'enabled': False}
        
        try:
            # Get sentiment data
            sentiment_scores = await self.sentiment_analyzer.update_news_sentiment([symbol])
            sentiment_score = sentiment_scores.get(symbol)
            
            if not sentiment_score:
                return {'no_sentiment_data': True}
            
            # Get news features
            news_items = self.sentiment_analyzer.news_cache.get(symbol, [])
            features = self.feature_engine.extract_features(symbol, news_items, sentiment_score)
            
            # Apply each rule
            rule_results = []
            combined_adjustments = {
                'k_factor_delta': 0.0,
                'strategy_bias': 'neutral',
                'bias_strength': 0.0,
                'execution_overrides': {}
            }
            
            for rule in self.rules:
                result = rule.evaluate(symbol, sentiment_score, features)
                
                if result['triggered']:
                    rule_results.append({
                        'rule_name': rule.name,
                        'conditions': result['conditions'],
                        'adjustments': result['adjustments']
                    })
                    
                    # Combine adjustments
                    adjustments = result['adjustments']
                    
                    # K-factor adjustments (additive)
                    if 'k_factor_delta' in adjustments:
                        combined_adjustments['k_factor_delta'] += adjustments['k_factor_delta']
                    
                    # Strategy bias (strongest wins)
                    if 'strategy_bias' in adjustments:
                        bias_strength = adjustments.get('bias_strength', 0)
                        if bias_strength > combined_adjustments['bias_strength']:
                            combined_adjustments['strategy_bias'] = adjustments['strategy_bias']
                            combined_adjustments['bias_strength'] = bias_strength
                    
                    # Execution overrides (merge)
                    if 'execution_override' in adjustments:
                        combined_adjustments['execution_overrides'].update(adjustments['execution_override'])
            
            # Cap K-factor adjustment
            combined_adjustments['k_factor_delta'] = np.clip(
                combined_adjustments['k_factor_delta'], -0.2, 0.2
            )
            
            # Store active adjustments
            if rule_results:
                self.active_adjustments[symbol] = {
                    'timestamp': datetime.now(),
                    'sentiment_score': sentiment_score,
                    'triggered_rules': rule_results,
                    'combined_adjustments': combined_adjustments
                }
            
            return {
                'symbol': symbol,
                'rules_triggered': len(rule_results),
                'triggered_rules': rule_results,
                'combined_adjustments': combined_adjustments,
                'sentiment_summary': {
                    'score_1h': sentiment_score.score_1h,
                    'score_24h': sentiment_score.score_24h,
                    'confidence_1h': sentiment_score.confidence_1h,
                    'volume_1h': sentiment_score.volume_1h
                },
                'news_features': features
            }
            
        except Exception as e:
            logger.error(f"Failed to apply news rules for {symbol}: {e}")
            return {'error': str(e)}
    
    def get_execution_overrides(self, symbol: str) -> Dict[str, Any]:
        """Get execution overrides for symbol"""
        
        if symbol not in self.active_adjustments:
            return {}
        
        adjustments = self.active_adjustments[symbol]
        
        # Check if adjustments are still fresh (within 1 hour)
        age_hours = (datetime.now() - adjustments['timestamp']).total_seconds() / 3600
        if age_hours > 1.0:
            # Remove stale adjustments
            del self.active_adjustments[symbol]
            return {}
        
        return adjustments['combined_adjustments'].get('execution_overrides', {})
    
    def get_k_factor_adjustment(self, symbol: str, base_k_factor: float) -> float:
        """Get K-factor adjustment for symbol"""
        
        if symbol not in self.active_adjustments:
            return base_k_factor
        
        adjustments = self.active_adjustments[symbol]
        
        # Check freshness
        age_hours = (datetime.now() - adjustments['timestamp']).total_seconds() / 3600
        if age_hours > 1.0:
            del self.active_adjustments[symbol]
            return base_k_factor
        
        k_delta = adjustments['combined_adjustments'].get('k_factor_delta', 0.0)
        
        # Apply with hysteresis to prevent whipsawing
        hysteresis_threshold = float(os.getenv('HYSTERESIS_THRESHOLD', '0.02'))
        
        if abs(k_delta) > hysteresis_threshold:
            adjusted_k = base_k_factor + k_delta
            
            # Respect min/max bounds
            k_min = float(os.getenv('K_FACTOR_MIN', '0.05'))
            k_max = float(os.getenv('K_FACTOR_MAX', '1.0'))
            
            return np.clip(adjusted_k, k_min, k_max)
        
        return base_k_factor
    
    def get_strategy_bias(self, symbol: str) -> Tuple[str, float]:
        """Get strategy bias and strength for symbol"""
        
        if symbol not in self.active_adjustments:
            return 'neutral', 0.0
        
        adjustments = self.active_adjustments[symbol]
        
        # Check freshness
        age_hours = (datetime.now() - adjustments['timestamp']).total_seconds() / 3600
        if age_hours > 1.0:
            del self.active_adjustments[symbol]
            return 'neutral', 0.0
        
        combined = adjustments['combined_adjustments']
        bias = combined.get('strategy_bias', 'neutral')
        strength = combined.get('bias_strength', 0.0)
        
        return bias, strength
    
    def should_force_twap(self, symbol: str, order_size_usd: float) -> bool:
        """Check if TWAP should be forced for symbol"""
        
        execution_overrides = self.get_execution_overrides(symbol)
        
        # Check rule-based TWAP forcing
        if execution_overrides.get('force_twap', False):
            return True
        
        # Check order size cap
        max_order_size = execution_overrides.get('max_order_size_usd')
        if max_order_size and order_size_usd > max_order_size:
            return True
        
        return False
    
    def get_slippage_band_adjustment(self, symbol: str) -> float:
        """Get slippage band tightening factor"""
        
        execution_overrides = self.get_execution_overrides(symbol)
        
        return execution_overrides.get('slippage_band_tightening', 1.0)
    
    def should_use_maker_only(self, symbol: str) -> bool:
        """Check if should use maker-only execution"""
        
        execution_overrides = self.get_execution_overrides(symbol)
        
        return execution_overrides.get('maker_first_only', False)
    
    def get_active_adjustments_summary(self) -> Dict[str, Any]:
        """Get summary of all active adjustments"""
        
        summary = {
            'total_symbols_with_adjustments': len(self.active_adjustments),
            'adjustments_by_symbol': {},
            'rule_trigger_counts': defaultdict(int),
            'last_update': datetime.now().isoformat()
        }
        
        for symbol, adjustment_data in self.active_adjustments.items():
            summary['adjustments_by_symbol'][symbol] = {
                'k_factor_delta': adjustment_data['combined_adjustments'].get('k_factor_delta', 0),
                'strategy_bias': adjustment_data['combined_adjustments'].get('strategy_bias', 'neutral'),
                'execution_overrides': len(adjustment_data['combined_adjustments'].get('execution_overrides', {})),
                'triggered_rules': [r['rule_name'] for r in adjustment_data['triggered_rules']],
                'age_minutes': (datetime.now() - adjustment_data['timestamp']).total_seconds() / 60
            }
            
            # Count rule triggers
            for rule_result in adjustment_data['triggered_rules']:
                summary['rule_trigger_counts'][rule_result['rule_name']] += 1
        
        return summary
    
    def cleanup_stale_adjustments(self):
        """Remove stale adjustments"""
        
        cutoff_time = datetime.now() - timedelta(hours=2)
        
        stale_symbols = [
            symbol for symbol, data in self.active_adjustments.items()
            if data['timestamp'] < cutoff_time
        ]
        
        for symbol in stale_symbols:
            del self.active_adjustments[symbol]
        
        if stale_symbols:
            logger.info(f"Cleaned up {len(stale_symbols)} stale news adjustments")