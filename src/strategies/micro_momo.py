"""
Micro Momentum (MoMo) Strategy
Quick momentum scalping on 5-minute timeframes
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class MicroMomoStrategy:
    """
    Micro Momentum strategy for quick scalps
    - Uses 5-min EMA crossovers
    - RSI for momentum confirmation  
    - Volume spike detection
    - Quick in/out trades
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        
        # EMA periods
        self.fast_ema = self.config.get('fast_ema', 8)
        self.slow_ema = self.config.get('slow_ema', 21)
        
        # RSI settings
        self.rsi_period = self.config.get('rsi_period', 14)
        self.rsi_overbought = self.config.get('rsi_overbought', 70)
        self.rsi_oversold = self.config.get('rsi_oversold', 30)
        
        # Volume settings
        self.volume_multiplier = self.config.get('volume_multiplier', 1.5)
        self.volume_lookback = self.config.get('volume_lookback', 20)
        
        # Risk management
        self.stop_loss_pct = self.config.get('stop_loss_pct', 0.5)  # 0.5%
        self.take_profit_pct = self.config.get('take_profit_pct', 1.0)  # 1%
        
        # State
        self.position = None
        self.entry_price = 0
        
    def calculate_ema(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate Exponential Moving Average"""
        return prices.ewm(span=period, adjust=False).mean()
    
    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def detect_volume_spike(self, volumes: pd.Series) -> bool:
        """Detect if current volume is a spike"""
        if len(volumes) < self.volume_lookback:
            return False
        
        avg_volume = volumes[-self.volume_lookback:-1].mean()
        current_volume = volumes.iloc[-1]
        
        return current_volume > (avg_volume * self.volume_multiplier)
    
    def generate_signal(self, data: pd.DataFrame) -> str:
        """
        Generate trading signal
        Returns: 'buy', 'sell', or 'hold'
        """
        if len(data) < max(self.slow_ema, self.rsi_period, self.volume_lookback):
            return 'hold'
        
        # Calculate indicators
        close_prices = data['close']
        volumes = data['volume']
        
        ema_fast = self.calculate_ema(close_prices, self.fast_ema)
        ema_slow = self.calculate_ema(close_prices, self.slow_ema)
        rsi = self.calculate_rsi(close_prices, self.rsi_period)
        
        # Current values
        current_price = close_prices.iloc[-1]
        current_ema_fast = ema_fast.iloc[-1]
        current_ema_slow = ema_slow.iloc[-1]
        current_rsi = rsi.iloc[-1]
        
        # Previous values for crossover detection
        prev_ema_fast = ema_fast.iloc[-2]
        prev_ema_slow = ema_slow.iloc[-2]
        
        # Volume spike
        volume_spike = self.detect_volume_spike(volumes)
        
        # Check position for exit conditions
        if self.position == 'long':
            # Check stop loss or take profit
            pnl_pct = ((current_price - self.entry_price) / self.entry_price) * 100
            
            if pnl_pct <= -self.stop_loss_pct or pnl_pct >= self.take_profit_pct:
                return 'sell'
            
            # Exit on bearish crossover
            if prev_ema_fast > prev_ema_slow and current_ema_fast <= current_ema_slow:
                return 'sell'
        
        # Entry signals (only if no position)
        if self.position is None:
            # Bullish crossover with momentum confirmation
            bullish_cross = prev_ema_fast <= prev_ema_slow and current_ema_fast > current_ema_slow
            
            if bullish_cross and current_rsi < self.rsi_overbought and volume_spike:
                return 'buy'
            
            # Oversold bounce with volume
            if current_rsi < self.rsi_oversold and volume_spike and current_ema_fast > prev_ema_fast:
                return 'buy'
        
        return 'hold'
    
    def execute_signal(self, signal: str, price: float, timestamp: float) -> Optional[Dict]:
        """Execute trading signal"""
        if signal == 'buy' and self.position is None:
            self.position = 'long'
            self.entry_price = price
            return {
                'action': 'buy',
                'price': price,
                'timestamp': timestamp,
                'reason': 'Micro momentum entry'
            }
        
        elif signal == 'sell' and self.position == 'long':
            pnl_pct = ((price - self.entry_price) / self.entry_price) * 100
            self.position = None
            self.entry_price = 0
            
            return {
                'action': 'sell',
                'price': price,
                'timestamp': timestamp,
                'pnl_pct': pnl_pct,
                'reason': 'Exit signal'
            }
        
        return None
    
    def backtest(self, data: pd.DataFrame) -> Dict:
        """Run backtest on historical data"""
        trades = []
        equity_curve = []
        initial_capital = 10000
        capital = initial_capital
        
        for i in range(max(self.slow_ema, self.rsi_period, self.volume_lookback), len(data)):
            window = data.iloc[:i+1]
            signal = self.generate_signal(window)
            
            price = data['close'].iloc[i]
            timestamp = data.index[i] if hasattr(data.index, '__iter__') else i
            
            trade = self.execute_signal(signal, price, timestamp)
            
            if trade:
                trades.append(trade)
                
                if trade['action'] == 'sell':
                    # Update capital based on PnL
                    capital *= (1 + trade['pnl_pct'] / 100)
            
            equity_curve.append(capital)
        
        # Calculate metrics
        total_trades = len([t for t in trades if t['action'] == 'buy'])
        winning_trades = len([t for t in trades if t.get('pnl_pct', 0) > 0])
        
        results = {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'win_rate': (winning_trades / total_trades * 100) if total_trades > 0 else 0,
            'final_capital': capital,
            'total_return': ((capital - initial_capital) / initial_capital * 100),
            'trades': trades,
            'equity_curve': equity_curve
        }
        
        return results

# Global instance
micro_momo = MicroMomoStrategy()