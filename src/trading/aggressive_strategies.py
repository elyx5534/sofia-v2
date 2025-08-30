"""
Aggressive Trading Strategies for Quick Profits
More volatile and rapid trading approaches
"""

from typing import List, Dict, Optional, Tuple
import numpy as np
from enum import Enum

class AggressiveStrategyType(Enum):
    SCALPING = "scalping"
    MOMENTUM_BURST = "momentum_burst"
    BREAKOUT = "breakout"
    REVERSAL = "reversal"
    VOLUME_SPIKE = "volume_spike"

class AggressiveStrategies:
    """Ultra aggressive trading strategies for quick trades"""
    
    @staticmethod
    def scalping_signal(prices: List[float], volumes: List[float]) -> Tuple[Optional[str], float]:
        """
        Scalping strategy - very quick in/out trades
        Target: 0.5-1% profit per trade
        """
        if len(prices) < 5:
            return None, 0.0
            
        # Check for micro movements
        last_price = prices[-1]
        avg_5 = np.mean(prices[-5:])
        
        # Quick momentum check
        momentum = (last_price - avg_5) / avg_5
        
        # Volume confirmation
        recent_vol = volumes[-1] if volumes else 0
        avg_vol = np.mean(volumes[-10:]) if len(volumes) >= 10 else recent_vol
        
        confidence = 0.0
        signal = None
        
        if momentum > 0.002:  # 0.2% up movement
            if recent_vol > avg_vol * 1.2:  # Volume spike
                signal = "BUY"
                confidence = min(0.9, momentum * 100)
        elif momentum < -0.002:  # 0.2% down movement
            if recent_vol > avg_vol * 1.2:
                signal = "SELL"
                confidence = min(0.9, abs(momentum) * 100)
                
        return signal, confidence
    
    @staticmethod
    def momentum_burst(prices: List[float]) -> Tuple[Optional[str], float]:
        """
        Catch sudden momentum bursts
        Target: 2-5% profit per trade
        """
        if len(prices) < 20:
            return None, 0.0
            
        # Calculate rate of change
        roc_5 = (prices[-1] - prices[-5]) / prices[-5]
        roc_10 = (prices[-1] - prices[-10]) / prices[-10]
        roc_20 = (prices[-1] - prices[-20]) / prices[-20]
        
        confidence = 0.0
        signal = None
        
        # Strong momentum detection
        if roc_5 > 0.01 and roc_10 > 0.015 and roc_20 > 0.02:
            signal = "BUY"
            confidence = min(0.95, roc_5 * 50)
        elif roc_5 < -0.01 and roc_10 < -0.015 and roc_20 < -0.02:
            # Potential reversal opportunity
            signal = "BUY"  # Counter-trend
            confidence = min(0.7, abs(roc_5) * 30)
            
        return signal, confidence
    
    @staticmethod
    def breakout_detector(prices: List[float], volumes: List[float]) -> Tuple[Optional[str], float]:
        """
        Detect price breakouts from consolidation
        Target: 3-8% profit per trade
        """
        if len(prices) < 50:
            return None, 0.0
            
        # Find resistance and support levels
        recent_high = max(prices[-20:])
        recent_low = min(prices[-20:])
        current_price = prices[-1]
        
        # Calculate price range
        price_range = recent_high - recent_low
        range_pct = price_range / recent_low
        
        confidence = 0.0
        signal = None
        
        # Breakout conditions
        if current_price > recent_high * 1.002:  # Break above resistance
            if range_pct < 0.03:  # Was in tight range
                signal = "BUY"
                confidence = 0.85
            else:
                signal = "BUY"
                confidence = 0.65
        elif current_price < recent_low * 0.998:  # Break below support
            signal = "SELL"
            confidence = 0.75
            
        # Volume confirmation
        if signal and volumes:
            recent_vol = volumes[-1]
            avg_vol = np.mean(volumes[-20:])
            if recent_vol > avg_vol * 1.5:
                confidence = min(0.95, confidence + 0.2)
                
        return signal, confidence
    
    @staticmethod
    def reversal_catcher(prices: List[float]) -> Tuple[Optional[str], float]:
        """
        Catch trend reversals for quick profits
        Target: 2-4% profit per trade
        """
        if len(prices) < 30:
            return None, 0.0
            
        # Calculate RSI for oversold/overbought
        gains = []
        losses = []
        for i in range(1, min(15, len(prices))):
            diff = prices[-i] - prices[-i-1]
            if diff > 0:
                gains.append(diff)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(diff))
        
        avg_gain = np.mean(gains) if gains else 0
        avg_loss = np.mean(losses) if losses else 0.001
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        # Check for divergence
        price_trend = (prices[-1] - prices[-10]) / prices[-10]
        
        confidence = 0.0
        signal = None
        
        if rsi < 25:  # Extremely oversold
            signal = "BUY"
            confidence = 0.8
        elif rsi > 75:  # Extremely overbought
            signal = "SELL"
            confidence = 0.8
        elif rsi < 35 and price_trend < -0.02:  # Oversold + downtrend
            signal = "BUY"
            confidence = 0.65
        elif rsi > 65 and price_trend > 0.02:  # Overbought + uptrend
            signal = "SELL"
            confidence = 0.65
            
        return signal, confidence
    
    @staticmethod
    def volume_spike_trader(prices: List[float], volumes: List[float]) -> Tuple[Optional[str], float]:
        """
        Trade on unusual volume spikes
        Target: 1-3% profit per trade
        """
        if len(prices) < 10 or len(volumes) < 10:
            return None, 0.0
            
        current_vol = volumes[-1]
        avg_vol = np.mean(volumes[-20:]) if len(volumes) >= 20 else np.mean(volumes)
        vol_ratio = current_vol / avg_vol if avg_vol > 0 else 1
        
        # Price movement
        price_change = (prices[-1] - prices[-2]) / prices[-2]
        
        confidence = 0.0  
        signal = None
        
        if vol_ratio > 3:  # Massive volume spike
            if price_change > 0.001:
                signal = "BUY"
                confidence = min(0.9, vol_ratio / 5)
            elif price_change < -0.001:
                signal = "BUY"  # Potential reversal on high volume
                confidence = min(0.7, vol_ratio / 6)
        elif vol_ratio > 2:  # Significant volume
            if price_change > 0.003:
                signal = "BUY"
                confidence = 0.6
                
        return signal, confidence
    
    @staticmethod
    def combined_aggressive(prices: List[float], volumes: List[float]) -> Tuple[Optional[str], Dict]:
        """
        Combine all aggressive strategies for maximum opportunity
        """
        strategies = {}
        signals = []
        confidences = []
        
        # Run all strategies
        scalp_signal, scalp_conf = AggressiveStrategies.scalping_signal(prices, volumes)
        if scalp_signal:
            strategies["scalping"] = {"signal": scalp_signal, "confidence": scalp_conf}
            signals.append(scalp_signal)
            confidences.append(scalp_conf)
        
        momentum_signal, momentum_conf = AggressiveStrategies.momentum_burst(prices)
        if momentum_signal:
            strategies["momentum"] = {"signal": momentum_signal, "confidence": momentum_conf}
            signals.append(momentum_signal)
            confidences.append(momentum_conf)
        
        breakout_signal, breakout_conf = AggressiveStrategies.breakout_detector(prices, volumes)
        if breakout_signal:
            strategies["breakout"] = {"signal": breakout_signal, "confidence": breakout_conf}
            signals.append(breakout_signal)
            confidences.append(breakout_conf)
        
        reversal_signal, reversal_conf = AggressiveStrategies.reversal_catcher(prices)
        if reversal_signal:
            strategies["reversal"] = {"signal": reversal_signal, "confidence": reversal_conf}
            signals.append(reversal_signal)
            confidences.append(reversal_conf)
        
        volume_signal, volume_conf = AggressiveStrategies.volume_spike_trader(prices, volumes)
        if volume_signal:
            strategies["volume_spike"] = {"signal": volume_signal, "confidence": volume_conf}
            signals.append(volume_signal)
            confidences.append(volume_conf)
        
        # Determine final signal
        if not signals:
            return None, {"strategies": strategies}
        
        # Count buy/sell signals
        buy_count = sum(1 for s in signals if s == "BUY")
        sell_count = sum(1 for s in signals if s == "SELL")
        
        # Calculate weighted confidence
        buy_confidence = np.mean([c for s, c in zip(signals, confidences) if s == "BUY"]) if buy_count > 0 else 0
        sell_confidence = np.mean([c for s, c in zip(signals, confidences) if s == "SELL"]) if sell_count > 0 else 0
        
        final_signal = None
        if buy_count >= 2 and buy_confidence > 0.5:
            final_signal = "BUY"
        elif sell_count >= 2 and sell_confidence > 0.5:
            final_signal = "SELL"
        elif buy_count >= 3:
            final_signal = "BUY"
        elif sell_count >= 3:
            final_signal = "SELL"
        
        return final_signal, {
            "strategies": strategies,
            "buy_signals": buy_count,
            "sell_signals": sell_count,
            "avg_confidence": np.mean(confidences) if confidences else 0
        }