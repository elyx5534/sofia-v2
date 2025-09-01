"""
Real-time Trade Simulator
Generates realistic price movements and executes trades
"""

import asyncio
import random
import time
from datetime import datetime
from typing import Dict, List, Optional
import numpy as np

class PriceSimulator:
    """Simulates realistic price movements for cryptocurrencies"""
    
    def __init__(self):
        # Base prices for different coins (in USD)
        self.base_prices = {
            "BTC/USDT": 64000 + random.uniform(-5000, 5000),
            "ETH/USDT": 3200 + random.uniform(-300, 300),
            "BNB/USDT": 580 + random.uniform(-50, 50),
            "SOL/USDT": 145 + random.uniform(-20, 20),
            "XRP/USDT": 0.62 + random.uniform(-0.1, 0.1),
            "ADA/USDT": 0.58 + random.uniform(-0.1, 0.1),
            "AVAX/USDT": 38 + random.uniform(-5, 5),
            "DOGE/USDT": 0.085 + random.uniform(-0.02, 0.02),
            "DOT/USDT": 7.2 + random.uniform(-1, 1),
            "MATIC/USDT": 0.95 + random.uniform(-0.2, 0.2),
            "SHIB/USDT": 0.0000095 + random.uniform(-0.000002, 0.000002),
            "PEPE/USDT": 0.00000125 + random.uniform(-0.0000003, 0.0000003),
            "FLOKI/USDT": 0.000035 + random.uniform(-0.00001, 0.00001),
            "BONK/USDT": 0.0000012 + random.uniform(-0.0000003, 0.0000003),
            "WIF/USDT": 2.8 + random.uniform(-0.5, 0.5),
            "MEME/USDT": 0.028 + random.uniform(-0.005, 0.005),
            "ARB/USDT": 1.12 + random.uniform(-0.2, 0.2),
            "OP/USDT": 2.35 + random.uniform(-0.3, 0.3),
            "INJ/USDT": 24.5 + random.uniform(-3, 3),
            "SEI/USDT": 0.52 + random.uniform(-0.1, 0.1),
            "JTO/USDT": 3.2 + random.uniform(-0.5, 0.5),
            "FET/USDT": 0.68 + random.uniform(-0.1, 0.1),
            "RNDR/USDT": 8.5 + random.uniform(-1, 1),
            "GRT/USDT": 0.28 + random.uniform(-0.05, 0.05),
            "OCEAN/USDT": 0.72 + random.uniform(-0.1, 0.1),
            "AGIX/USDT": 0.35 + random.uniform(-0.05, 0.05),
        }
        
        # Current prices (will fluctuate)
        self.current_prices = self.base_prices.copy()
        
        # Price history for each coin
        self.price_history = {symbol: [price] * 100 for symbol, price in self.base_prices.items()}
        
        # Volume data
        self.volumes = {symbol: [] for symbol in self.base_prices.keys()}
        
        # Volatility factors for different coins
        self.volatility = {
            "BTC/USDT": 0.02,
            "ETH/USDT": 0.025,
            "PEPE/USDT": 0.15,  # Meme coins are more volatile
            "FLOKI/USDT": 0.12,
            "BONK/USDT": 0.13,
            "WIF/USDT": 0.10,
            "MEME/USDT": 0.11,
            "SHIB/USDT": 0.08,
        }
        
        # Market trends
        self.market_trend = 0  # -1 bearish, 0 neutral, 1 bullish
        self.trend_strength = 0.5
        
    def update_market_trend(self):
        """Randomly update market trend"""
        # Small chance of trend change
        if random.random() < 0.1:
            self.market_trend = random.choice([-1, 0, 1])
            self.trend_strength = random.uniform(0.3, 1.0)
    
    def generate_price_movement(self, symbol: str) -> float:
        """Generate realistic price movement for a symbol"""
        current_price = self.current_prices.get(symbol, 100)
        base_volatility = self.volatility.get(symbol, 0.03)
        
        # Add some randomness
        random_factor = np.random.normal(0, base_volatility)
        
        # Apply market trend
        trend_factor = self.market_trend * self.trend_strength * 0.001
        
        # Occasionally add bigger movements (whale trades, news, etc.)
        if random.random() < 0.05:  # 5% chance of bigger move
            random_factor *= random.uniform(2, 5)
        
        # Calculate new price
        price_change = current_price * (random_factor + trend_factor)
        new_price = current_price + price_change
        
        # Prevent negative prices
        new_price = max(new_price, current_price * 0.5)
        
        # Mean reversion tendency
        base_price = self.base_prices.get(symbol, current_price)
        reversion_factor = (base_price - new_price) / base_price * 0.01
        new_price += new_price * reversion_factor
        
        return new_price
    
    def generate_volume(self, symbol: str) -> float:
        """Generate realistic volume data"""
        base_volume = 1000000  # Base volume in USD
        
        # Popular coins have higher volume
        if "BTC" in symbol:
            base_volume *= 100
        elif "ETH" in symbol:
            base_volume *= 50
        elif "PEPE" in symbol or "SHIB" in symbol:
            base_volume *= 10
        
        # Add randomness
        volume = base_volume * random.uniform(0.5, 2.0)
        
        # Spike volume occasionally
        if random.random() < 0.1:
            volume *= random.uniform(2, 5)
        
        return volume
    
    def update_all_prices(self):
        """Update prices for all tracked symbols"""
        self.update_market_trend()
        
        for symbol in self.current_prices.keys():
            # Generate new price
            new_price = self.generate_price_movement(symbol)
            self.current_prices[symbol] = new_price
            
            # Update history
            if symbol in self.price_history:
                self.price_history[symbol].append(new_price)
                # Keep only last 200 prices
                if len(self.price_history[symbol]) > 200:
                    self.price_history[symbol] = self.price_history[symbol][-200:]
            
            # Generate volume
            volume = self.generate_volume(symbol)
            if symbol in self.volumes:
                self.volumes[symbol].append(volume)
                # Keep only last 200 volumes
                if len(self.volumes[symbol]) > 200:
                    self.volumes[symbol] = self.volumes[symbol][-200:]
    
    def get_price_data(self, symbol: str) -> Dict:
        """Get current price data for a symbol"""
        return {
            "symbol": symbol,
            "price": self.current_prices.get(symbol, 0),
            "prices": self.price_history.get(symbol, [])[-50:],  # Last 50 prices
            "volumes": self.volumes.get(symbol, [])[-50:],  # Last 50 volumes
            "change_24h": self._calculate_change(symbol, 24),
            "change_1h": self._calculate_change(symbol, 1),
        }
    
    def _calculate_change(self, symbol: str, hours: int) -> float:
        """Calculate price change percentage"""
        history = self.price_history.get(symbol, [])
        if len(history) < hours:
            return 0
        
        old_price = history[-hours]
        current_price = self.current_prices.get(symbol, old_price)
        
        if old_price == 0:
            return 0
        
        return ((current_price - old_price) / old_price) * 100


class TradingSimulator:
    """Simulates the complete trading bot with realistic data"""
    
    def __init__(self, bot):
        self.bot = bot
        self.price_simulator = PriceSimulator()
        self.running = False
        self.update_interval = 2  # Update every 2 seconds
        
        # Add more coins to price simulator
        for symbol in bot.ALL_COINS[:100]:  # Add first 100 coins
            if symbol not in self.price_simulator.base_prices:
                # Generate random base price
                self.price_simulator.base_prices[symbol] = random.uniform(0.0001, 100)
                self.price_simulator.current_prices[symbol] = self.price_simulator.base_prices[symbol]
                self.price_simulator.price_history[symbol] = [self.price_simulator.base_prices[symbol]] * 100
                self.price_simulator.volumes[symbol] = []
                self.price_simulator.volatility[symbol] = random.uniform(0.03, 0.15)
    
    async def run_simulation(self):
        """Run the trading simulation"""
        self.running = True
        iteration = 0
        
        while self.running:
            iteration += 1
            
            # Update all prices
            self.price_simulator.update_all_prices()
            
            # Update bot indicators for each coin in watchlist
            for symbol in list(self.bot.watchlist)[:50]:  # Process first 50 coins
                price_data = self.price_simulator.get_price_data(symbol)
                
                # Update bot's indicators
                prices = price_data["prices"]
                volumes = price_data["volumes"]
                
                if len(prices) >= 20:
                    # Calculate indicators
                    from .strategies import TradingStrategies
                    strategies = TradingStrategies()
                    
                    indicators = {}
                    
                    # RSI
                    if len(prices) >= 14:
                        indicators["rsi"] = strategies.calculate_rsi(prices)
                    
                    # MACD
                    if len(prices) >= 26:
                        macd_data = strategies.calculate_macd(prices)
                        indicators["macd"] = macd_data
                    
                    # Bollinger Bands
                    if len(prices) >= 20:
                        bb_data = strategies.calculate_bollinger_bands(prices)
                        indicators["bollinger"] = bb_data
                    
                    # Moving averages
                    indicators["sma_10"] = np.mean(prices[-10:]) if len(prices) >= 10 else prices[-1]
                    indicators["sma_20"] = np.mean(prices[-20:]) if len(prices) >= 20 else prices[-1]
                    
                    # Store indicators
                    self.bot.indicators[symbol] = indicators
                    
                    # Update position prices
                    if symbol in self.bot.positions:
                        self.bot.positions[symbol].update_pnl(
                            price_data["price"], 
                            self.bot.usd_to_try
                        )
            
            # Execute trading logic every 5 iterations (10 seconds)
            if iteration % 5 == 0 and self.bot.status.value == "running":
                await self._execute_trades()
            
            # Wait before next update
            await asyncio.sleep(self.update_interval)
    
    async def _execute_trades(self):
        """Execute trades based on current signals"""
        # Import aggressive strategies
        from .aggressive_strategies import AggressiveStrategies
        
        # Track coins to trade
        coins_to_trade = []
        
        # Analyze each coin in watchlist
        for symbol in list(self.bot.watchlist)[:self.bot.max_coins_to_trade]:
            if symbol not in self.bot.indicators:
                continue
            
            price_data = self.price_simulator.get_price_data(symbol)
            prices = price_data["prices"]
            volumes = price_data["volumes"]
            current_price = price_data["price"]
            
            # Skip if not enough data
            if len(prices) < 20:
                continue
            
            # Get signals from different strategies
            signal = None
            confidence = 0
            
            # Use aggressive strategies
            aggressive_signal, aggressive_data = AggressiveStrategies.combined_aggressive(prices, volumes)
            
            if aggressive_signal:
                signal = aggressive_signal
                confidence = aggressive_data.get("avg_confidence", 0.5)
            else:
                # Fall back to regular strategies
                from .strategies import TradingStrategies
                regular_signal, regular_data = TradingStrategies.get_combined_signal(prices)
                if regular_signal:
                    signal = regular_signal
                    confidence = regular_data.get("confidence", 0.5)
            
            # Execute trade if signal is strong enough
            if signal and confidence > 0.25:  # Low threshold for aggressive trading
                # Determine confidence level
                if confidence > 0.7:
                    conf_level = "high"
                elif confidence > 0.4:
                    conf_level = "medium"
                else:
                    conf_level = "low"
                
                # Execute the trade
                trade = self.bot.execute_trade(symbol, signal, current_price, conf_level)
                
                if trade and trade.get("amount", 0) > 0:
                    coins_to_trade.append({
                        "symbol": symbol,
                        "signal": signal,
                        "price": current_price,
                        "confidence": confidence,
                        "trade": trade
                    })
        
        # Log trading activity
        if coins_to_trade:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Executed {len(coins_to_trade)} trades:")
            for ct in coins_to_trade:
                print(f"  {ct['symbol']}: {ct['signal']} @ ${ct['price']:.6f} (conf: {ct['confidence']:.2%})")
    
    def stop(self):
        """Stop the simulation"""
        self.running = False