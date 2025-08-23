"""
Advanced Strategy Engine for Sofia V2
Multi-strategy support with ML capabilities
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass
import logging
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

class SignalType(Enum):
    STRONG_BUY = 2
    BUY = 1
    NEUTRAL = 0
    SELL = -1
    STRONG_SELL = -2

class StrategyType(Enum):
    SCALPING = "scalping"
    ARBITRAGE = "arbitrage"
    TREND_FOLLOWING = "trend_following"
    MEAN_REVERSION = "mean_reversion"
    MOMENTUM = "momentum"
    DCA = "dollar_cost_averaging"
    ML_PREDICTION = "ml_prediction"

@dataclass
class TradingSignal:
    symbol: str
    strategy: StrategyType
    signal: SignalType
    confidence: float  # 0-1
    price_target: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    position_size: Optional[float] = None
    metadata: Dict = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.metadata is None:
            self.metadata = {}

class StrategyEngine:
    """
    Multi-strategy trading engine with risk management
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or self._default_config()
        self.active_strategies = []
        self.risk_manager = RiskManager(self.config.get('risk', {}))
        self.performance_tracker = PerformanceTracker()
        
    def _default_config(self) -> Dict:
        return {
            'strategies': {
                'scalping': {'enabled': True, 'weight': 0.2},
                'trend_following': {'enabled': True, 'weight': 0.3},
                'mean_reversion': {'enabled': True, 'weight': 0.2},
                'momentum': {'enabled': True, 'weight': 0.2},
                'arbitrage': {'enabled': True, 'weight': 0.1}
            },
            'risk': {
                'max_position_size': 0.1,  # 10% of portfolio
                'max_daily_loss': 0.02,     # 2% daily loss limit
                'stop_loss_percentage': 0.02, # 2% stop loss
                'take_profit_percentage': 0.05, # 5% take profit
                'max_open_positions': 5
            },
            'indicators': {
                'sma_short': 5,
                'sma_long': 20,
                'rsi_period': 14,
                'bb_period': 20,
                'bb_std': 2
            }
        }
    
    def analyze(self, market_data: Dict, news_sentiment: Optional[Dict] = None) -> List[TradingSignal]:
        """
        Analyze market data and generate trading signals
        """
        signals = []
        
        # Run each enabled strategy
        for strategy_name, strategy_config in self.config['strategies'].items():
            if not strategy_config.get('enabled', False):
                continue
                
            try:
                strategy_type = StrategyType(strategy_name)
                strategy_signals = self._run_strategy(strategy_type, market_data, news_sentiment)
                
                # Apply strategy weight
                for signal in strategy_signals:
                    signal.confidence *= strategy_config.get('weight', 1.0)
                    signals.append(signal)
                    
            except Exception as e:
                logger.error(f"Strategy {strategy_name} failed: {str(e)}")
                
        # Combine and filter signals
        combined_signals = self._combine_signals(signals)
        
        # Apply risk management
        filtered_signals = self.risk_manager.filter_signals(combined_signals, market_data)
        
        # Track performance
        for signal in filtered_signals:
            self.performance_tracker.record_signal(signal)
            
        return filtered_signals
    
    def _run_strategy(self, strategy_type: StrategyType, market_data: Dict, 
                     news_sentiment: Optional[Dict]) -> List[TradingSignal]:
        """
        Execute specific strategy
        """
        if strategy_type == StrategyType.SCALPING:
            return self._scalping_strategy(market_data)
        elif strategy_type == StrategyType.TREND_FOLLOWING:
            return self._trend_following_strategy(market_data)
        elif strategy_type == StrategyType.MEAN_REVERSION:
            return self._mean_reversion_strategy(market_data)
        elif strategy_type == StrategyType.MOMENTUM:
            return self._momentum_strategy(market_data, news_sentiment)
        elif strategy_type == StrategyType.ARBITRAGE:
            return self._arbitrage_strategy(market_data)
        else:
            return []
    
    def _scalping_strategy(self, market_data: Dict) -> List[TradingSignal]:
        """
        High-frequency scalping for quick profits
        """
        signals = []
        
        if 'prices' not in market_data or len(market_data['prices']) < 10:
            return signals
            
        prices = pd.Series(market_data['prices'])
        
        # Look for micro price movements
        recent_change = (prices.iloc[-1] - prices.iloc[-2]) / prices.iloc[-2]
        volatility = prices.pct_change().std()
        
        # Quick reversal detection
        if abs(recent_change) > volatility * 2:
            if recent_change < 0:  # Sharp drop, potential bounce
                signal = TradingSignal(
                    symbol=market_data['symbol'],
                    strategy=StrategyType.SCALPING,
                    signal=SignalType.BUY,
                    confidence=0.7,
                    price_target=prices.iloc[-1] * 1.005,  # 0.5% profit target
                    stop_loss=prices.iloc[-1] * 0.997,     # 0.3% stop loss
                    position_size=0.05  # Small position for scalping
                )
                signals.append(signal)
                
        return signals
    
    def _trend_following_strategy(self, market_data: Dict) -> List[TradingSignal]:
        """
        Follow the trend with moving averages
        """
        signals = []
        
        if 'prices' not in market_data or len(market_data['prices']) < 20:
            return signals
            
        prices = pd.Series(market_data['prices'])
        
        # Calculate moving averages
        sma_short = prices.rolling(self.config['indicators']['sma_short']).mean()
        sma_long = prices.rolling(self.config['indicators']['sma_long']).mean()
        
        # Check for crossover
        if len(sma_short) >= 2 and len(sma_long) >= 2:
            current_short = sma_short.iloc[-1]
            current_long = sma_long.iloc[-1]
            prev_short = sma_short.iloc[-2]
            prev_long = sma_long.iloc[-2]
            
            # Golden cross (bullish)
            if prev_short <= prev_long and current_short > current_long:
                signal = TradingSignal(
                    symbol=market_data['symbol'],
                    strategy=StrategyType.TREND_FOLLOWING,
                    signal=SignalType.STRONG_BUY,
                    confidence=0.85,
                    stop_loss=prices.iloc[-1] * 0.97,
                    take_profit=prices.iloc[-1] * 1.10
                )
                signals.append(signal)
                
            # Death cross (bearish)
            elif prev_short >= prev_long and current_short < current_long:
                signal = TradingSignal(
                    symbol=market_data['symbol'],
                    strategy=StrategyType.TREND_FOLLOWING,
                    signal=SignalType.STRONG_SELL,
                    confidence=0.85
                )
                signals.append(signal)
                
        return signals
    
    def _mean_reversion_strategy(self, market_data: Dict) -> List[TradingSignal]:
        """
        Trade on assumption that price will revert to mean
        """
        signals = []
        
        if 'prices' not in market_data or len(market_data['prices']) < 20:
            return signals
            
        prices = pd.Series(market_data['prices'])
        
        # Bollinger Bands
        sma = prices.rolling(self.config['indicators']['bb_period']).mean()
        std = prices.rolling(self.config['indicators']['bb_period']).std()
        
        if pd.notna(sma.iloc[-1]) and pd.notna(std.iloc[-1]):
            upper_band = sma.iloc[-1] + (std.iloc[-1] * self.config['indicators']['bb_std'])
            lower_band = sma.iloc[-1] - (std.iloc[-1] * self.config['indicators']['bb_std'])
            current_price = prices.iloc[-1]
            
            # Oversold - potential buy
            if current_price < lower_band:
                signal = TradingSignal(
                    symbol=market_data['symbol'],
                    strategy=StrategyType.MEAN_REVERSION,
                    signal=SignalType.BUY,
                    confidence=0.75,
                    price_target=sma.iloc[-1],  # Target is the mean
                    stop_loss=current_price * 0.98
                )
                signals.append(signal)
                
            # Overbought - potential sell
            elif current_price > upper_band:
                signal = TradingSignal(
                    symbol=market_data['symbol'],
                    strategy=StrategyType.MEAN_REVERSION,
                    signal=SignalType.SELL,
                    confidence=0.75,
                    price_target=sma.iloc[-1]
                )
                signals.append(signal)
                
        return signals
    
    def _momentum_strategy(self, market_data: Dict, news_sentiment: Optional[Dict]) -> List[TradingSignal]:
        """
        Momentum based on price action and news
        """
        signals = []
        
        if 'prices' not in market_data or len(market_data['prices']) < 14:
            return signals
            
        prices = pd.Series(market_data['prices'])
        
        # RSI calculation
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        
        if loss.iloc[-1] != 0:
            rs = gain.iloc[-1] / loss.iloc[-1]
            rsi = 100 - (100 / (1 + rs))
        else:
            rsi = 100
            
        # Combine with sentiment if available
        sentiment_boost = 0
        if news_sentiment and 'score' in news_sentiment:
            sentiment_boost = news_sentiment['score'] * 0.2
            
        # Generate signals based on RSI + sentiment
        if rsi < 30:  # Oversold
            signal = TradingSignal(
                symbol=market_data['symbol'],
                strategy=StrategyType.MOMENTUM,
                signal=SignalType.BUY,
                confidence=min(0.8 + sentiment_boost, 1.0),
                metadata={'rsi': rsi, 'sentiment': news_sentiment}
            )
            signals.append(signal)
            
        elif rsi > 70:  # Overbought
            signal = TradingSignal(
                symbol=market_data['symbol'],
                strategy=StrategyType.MOMENTUM,
                signal=SignalType.SELL,
                confidence=min(0.8 - sentiment_boost, 1.0),
                metadata={'rsi': rsi, 'sentiment': news_sentiment}
            )
            signals.append(signal)
            
        return signals
    
    def _arbitrage_strategy(self, market_data: Dict) -> List[TradingSignal]:
        """
        Look for arbitrage opportunities across exchanges
        """
        signals = []
        
        # This would need multi-exchange data
        # Placeholder for now
        if 'exchanges' in market_data:
            prices_by_exchange = market_data['exchanges']
            
            if len(prices_by_exchange) >= 2:
                min_price = min(prices_by_exchange.values())
                max_price = max(prices_by_exchange.values())
                spread_percentage = (max_price - min_price) / min_price
                
                # If spread > 1% after fees, arbitrage opportunity
                if spread_percentage > 0.015:  # 1.5% to cover fees
                    signal = TradingSignal(
                        symbol=market_data['symbol'],
                        strategy=StrategyType.ARBITRAGE,
                        signal=SignalType.STRONG_BUY,
                        confidence=0.95,
                        metadata={
                            'buy_exchange': min(prices_by_exchange, key=prices_by_exchange.get),
                            'sell_exchange': max(prices_by_exchange, key=prices_by_exchange.get),
                            'spread': spread_percentage
                        }
                    )
                    signals.append(signal)
                    
        return signals
    
    def _combine_signals(self, signals: List[TradingSignal]) -> List[TradingSignal]:
        """
        Combine signals from multiple strategies
        """
        # Group by symbol
        symbol_signals = {}
        for signal in signals:
            if signal.symbol not in symbol_signals:
                symbol_signals[signal.symbol] = []
            symbol_signals[signal.symbol].append(signal)
            
        combined = []
        for symbol, symbol_signal_list in symbol_signals.items():
            if not symbol_signal_list:
                continue
                
            # Calculate weighted average signal
            total_weight = sum(s.confidence for s in symbol_signal_list)
            if total_weight == 0:
                continue
                
            weighted_signal = sum(s.signal.value * s.confidence for s in symbol_signal_list) / total_weight
            avg_confidence = total_weight / len(symbol_signal_list)
            
            # Determine final signal type
            if weighted_signal > 1.5:
                final_signal = SignalType.STRONG_BUY
            elif weighted_signal > 0.5:
                final_signal = SignalType.BUY
            elif weighted_signal < -1.5:
                final_signal = SignalType.STRONG_SELL
            elif weighted_signal < -0.5:
                final_signal = SignalType.SELL
            else:
                final_signal = SignalType.NEUTRAL
                
            if final_signal != SignalType.NEUTRAL:
                combined_signal = TradingSignal(
                    symbol=symbol,
                    strategy=StrategyType.ML_PREDICTION,  # Combined strategy
                    signal=final_signal,
                    confidence=avg_confidence,
                    metadata={'component_signals': len(symbol_signal_list)}
                )
                combined.append(combined_signal)
                
        return combined


class RiskManager:
    """
    Risk management and position sizing
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.daily_loss = 0
        self.open_positions = []
        
    def filter_signals(self, signals: List[TradingSignal], market_data: Dict) -> List[TradingSignal]:
        """
        Filter signals based on risk parameters
        """
        filtered = []
        
        for signal in signals:
            # Check daily loss limit
            if self.daily_loss >= self.config.get('max_daily_loss', 0.02):
                logger.warning(f"Daily loss limit reached: {self.daily_loss:.2%}")
                break
                
            # Check max open positions
            if len(self.open_positions) >= self.config.get('max_open_positions', 5):
                if signal.signal not in [SignalType.SELL, SignalType.STRONG_SELL]:
                    continue
                    
            # Calculate position size based on Kelly Criterion
            signal.position_size = self._calculate_position_size(signal)
            
            # Add stop loss and take profit if not set
            if signal.signal in [SignalType.BUY, SignalType.STRONG_BUY]:
                if not signal.stop_loss:
                    current_price = market_data.get('last_price', 0)
                    signal.stop_loss = current_price * (1 - self.config.get('stop_loss_percentage', 0.02))
                if not signal.take_profit:
                    current_price = market_data.get('last_price', 0)
                    signal.take_profit = current_price * (1 + self.config.get('take_profit_percentage', 0.05))
                    
            filtered.append(signal)
            
        return filtered
    
    def _calculate_position_size(self, signal: TradingSignal) -> float:
        """
        Calculate optimal position size using Kelly Criterion
        """
        # Simplified Kelly: f = (p*b - q) / b
        # where p = probability of win, q = probability of loss, b = odds
        
        confidence = signal.confidence
        win_probability = 0.5 + (confidence * 0.2)  # Convert confidence to probability
        loss_probability = 1 - win_probability
        
        # Assume 2:1 reward/risk ratio
        odds = 2
        
        kelly_fraction = (win_probability * odds - loss_probability) / odds
        
        # Apply safety factor (never use full Kelly)
        safety_factor = 0.25
        position_size = kelly_fraction * safety_factor
        
        # Cap at max position size
        max_size = self.config.get('max_position_size', 0.1)
        position_size = min(max(position_size, 0), max_size)
        
        return position_size
    
    def update_daily_loss(self, pnl: float):
        """
        Update daily P&L tracking
        """
        self.daily_loss = min(0, self.daily_loss + pnl)
        
    def reset_daily_metrics(self):
        """
        Reset daily metrics (call at day start)
        """
        self.daily_loss = 0


class PerformanceTracker:
    """
    Track strategy performance for optimization
    """
    
    def __init__(self):
        self.signals_history = []
        self.trades_history = []
        self.metrics = {
            'total_signals': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_pnl': 0,
            'sharpe_ratio': 0,
            'max_drawdown': 0,
            'win_rate': 0
        }
        
    def record_signal(self, signal: TradingSignal):
        """
        Record a generated signal
        """
        self.signals_history.append({
            'timestamp': signal.timestamp,
            'symbol': signal.symbol,
            'strategy': signal.strategy.value,
            'signal': signal.signal.value,
            'confidence': signal.confidence
        })
        self.metrics['total_signals'] += 1
        
    def record_trade(self, entry_price: float, exit_price: float, 
                    position_size: float, symbol: str):
        """
        Record completed trade for performance analysis
        """
        pnl = (exit_price - entry_price) / entry_price * position_size
        
        self.trades_history.append({
            'timestamp': datetime.now(),
            'symbol': symbol,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'position_size': position_size,
            'pnl': pnl
        })
        
        self.metrics['total_pnl'] += pnl
        if pnl > 0:
            self.metrics['winning_trades'] += 1
        else:
            self.metrics['losing_trades'] += 1
            
        total_trades = self.metrics['winning_trades'] + self.metrics['losing_trades']
        if total_trades > 0:
            self.metrics['win_rate'] = self.metrics['winning_trades'] / total_trades
            
    def calculate_sharpe_ratio(self) -> float:
        """
        Calculate Sharpe ratio from trade history
        """
        if len(self.trades_history) < 2:
            return 0
            
        returns = [t['pnl'] for t in self.trades_history]
        return_series = pd.Series(returns)
        
        if return_series.std() == 0:
            return 0
            
        # Annualized Sharpe (assuming daily returns)
        sharpe = (return_series.mean() / return_series.std()) * np.sqrt(365)
        self.metrics['sharpe_ratio'] = sharpe
        
        return sharpe
    
    def calculate_max_drawdown(self) -> float:
        """
        Calculate maximum drawdown
        """
        if len(self.trades_history) < 2:
            return 0
            
        cumulative_returns = []
        cumsum = 0
        
        for trade in self.trades_history:
            cumsum += trade['pnl']
            cumulative_returns.append(cumsum)
            
        peak = cumulative_returns[0]
        max_dd = 0
        
        for value in cumulative_returns:
            if value > peak:
                peak = value
            dd = (peak - value) / peak if peak != 0 else 0
            max_dd = max(max_dd, dd)
            
        self.metrics['max_drawdown'] = max_dd
        return max_dd
    
    def get_performance_summary(self) -> Dict:
        """
        Get comprehensive performance metrics
        """
        self.calculate_sharpe_ratio()
        self.calculate_max_drawdown()
        
        return self.metrics