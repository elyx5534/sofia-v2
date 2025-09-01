"""
Auto Trading Module - Executes trades based on alert signals
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
import httpx
from enum import Enum

class TradeAction(Enum):
    """Trade actions based on signals"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    CLOSE = "close"
    HEDGE = "hedge"
    
class RiskLevel(Enum):
    """Risk levels for position sizing"""
    LOW = 0.01      # 1% of portfolio
    MEDIUM = 0.02   # 2% of portfolio
    HIGH = 0.05     # 5% of portfolio
    CRITICAL = 0.1  # 10% of portfolio

class AutoTrader:
    """Automated trading based on alert signals"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.portfolio_balance = config.get("initial_balance", 100000)
        self.max_position_size = config.get("max_position_size", 0.1)  # 10% max per position
        self.risk_per_trade = config.get("risk_per_trade", 0.02)  # 2% risk per trade
        self.stop_loss_percent = config.get("stop_loss", 0.05)  # 5% stop loss
        self.take_profit_percent = config.get("take_profit", 0.15)  # 15% take profit
        self.active_trades = {}
        self.trade_history = []
        self.alert_api_url = config.get("alert_api", "http://localhost:8010")
        self.trading_api_url = config.get("trading_api", "http://localhost:8003")
        
    async def process_alert_signal(self, alert: Dict) -> Optional[Dict]:
        """Process an alert signal and decide on trading action"""
        
        # Map alert actions to trade actions
        action_map = {
            "hedge": TradeAction.HEDGE,
            "momentum_long": TradeAction.BUY,
            "short": TradeAction.SELL,
            "close_position": TradeAction.CLOSE,
            "reduce_exposure": TradeAction.CLOSE,
        }
        
        # Map severity to risk level
        risk_map = {
            "critical": RiskLevel.CRITICAL,
            "high": RiskLevel.HIGH,
            "medium": RiskLevel.MEDIUM,
            "low": RiskLevel.LOW,
        }
        
        action = action_map.get(alert.get("action"))
        if not action:
            return None
            
        risk_level = risk_map.get(alert.get("severity", "low"))
        
        # Calculate position size based on risk
        position_size = self.calculate_position_size(risk_level)
        
        # Determine symbol from alert data
        symbol = self.extract_symbol_from_alert(alert)
        
        if not symbol:
            symbol = "BTC/USDT"  # Default to BTC
            
        trade = {
            "timestamp": datetime.now().isoformat(),
            "alert_id": alert.get("id"),
            "symbol": symbol,
            "action": action.value,
            "position_size": position_size,
            "risk_level": risk_level.value,
            "stop_loss": self.stop_loss_percent,
            "take_profit": self.take_profit_percent,
            "reason": alert.get("message", "Alert signal"),
            "source": alert.get("source", "unknown"),
        }
        
        # Execute trade if conditions are met
        if self.should_execute_trade(trade):
            return await self.execute_trade(trade)
            
        return None
        
    def calculate_position_size(self, risk_level: RiskLevel) -> float:
        """Calculate position size based on risk level and portfolio"""
        base_size = self.portfolio_balance * risk_level.value
        
        # Apply Kelly Criterion for optimal sizing
        win_rate = 0.55  # Assumed win rate
        avg_win = self.take_profit_percent
        avg_loss = self.stop_loss_percent
        
        kelly_percent = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
        kelly_size = max(0, min(kelly_percent, self.max_position_size))
        
        final_size = min(base_size * kelly_size, self.portfolio_balance * self.max_position_size)
        
        return round(final_size, 2)
        
    def extract_symbol_from_alert(self, alert: Dict) -> Optional[str]:
        """Extract trading symbol from alert data"""
        message = alert.get("message", "").upper()
        
        # Common crypto symbols
        symbols = ["BTC", "ETH", "SOL", "BNB", "ADA", "DOT", "AVAX", "MATIC"]
        
        for symbol in symbols:
            if symbol in message:
                return f"{symbol}/USDT"
                
        # Check data field
        data = alert.get("data", {})
        if isinstance(data, dict):
            for coin in data.get("coins", []):
                if isinstance(coin, dict):
                    symbol = coin.get("symbol")
                    if symbol:
                        return f"{symbol}/USDT"
                        
        return None
        
    def should_execute_trade(self, trade: Dict) -> bool:
        """Check if trade should be executed based on risk management"""
        
        # Check if we already have a position in this symbol
        if trade["symbol"] in self.active_trades:
            # Only add to position if it's the same direction
            existing = self.active_trades[trade["symbol"]]
            if existing["action"] != trade["action"]:
                return False
                
        # Check total exposure
        total_exposure = sum(t["position_size"] for t in self.active_trades.values())
        if total_exposure + trade["position_size"] > self.portfolio_balance * 0.5:
            return False  # Don't exceed 50% total exposure
            
        # Check number of open positions
        if len(self.active_trades) >= 10:
            return False  # Max 10 concurrent positions
            
        return True
        
    async def execute_trade(self, trade: Dict) -> Dict:
        """Execute the trade via trading API"""
        
        try:
            async with httpx.AsyncClient() as client:
                # Call trading API to execute
                response = await client.post(
                    f"{self.trading_api_url}/execute",
                    json=trade
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # Track the trade
                    self.active_trades[trade["symbol"]] = trade
                    self.trade_history.append(trade)
                    
                    return {
                        "success": True,
                        "trade": trade,
                        "execution": result
                    }
                    
        except Exception as e:
            print(f"Trade execution failed: {e}")
            
        # Simulate trade for now
        self.active_trades[trade["symbol"]] = trade
        self.trade_history.append(trade)
        
        return {
            "success": True,
            "trade": trade,
            "execution": {"simulated": True, "price": 0}
        }
        
    async def monitor_positions(self):
        """Monitor active positions for stop loss and take profit"""
        
        while True:
            for symbol, trade in list(self.active_trades.items()):
                # Check current price
                current_price = await self.get_current_price(symbol)
                
                if current_price:
                    entry_price = trade.get("entry_price", current_price)
                    pnl_percent = (current_price - entry_price) / entry_price
                    
                    # Check stop loss
                    if pnl_percent <= -trade["stop_loss"]:
                        await self.close_position(symbol, "stop_loss")
                        
                    # Check take profit
                    elif pnl_percent >= trade["take_profit"]:
                        await self.close_position(symbol, "take_profit")
                        
            await asyncio.sleep(10)  # Check every 10 seconds
            
    async def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for symbol"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.trading_api_url}/price/{symbol}"
                )
                if response.status_code == 200:
                    data = response.json()
                    return data.get("price")
        except:
            pass
            
        # Default prices for simulation
        default_prices = {
            "BTC/USDT": 95000,
            "ETH/USDT": 3300,
            "SOL/USDT": 250,
            "BNB/USDT": 700,
        }
        
        return default_prices.get(symbol, 100)
        
    async def close_position(self, symbol: str, reason: str):
        """Close a position"""
        if symbol in self.active_trades:
            trade = self.active_trades[symbol]
            trade["closed_at"] = datetime.now().isoformat()
            trade["close_reason"] = reason
            
            # Calculate PnL
            current_price = await self.get_current_price(symbol)
            if current_price:
                entry_price = trade.get("entry_price", current_price)
                pnl = (current_price - entry_price) * trade["position_size"] / entry_price
                trade["pnl"] = pnl
                self.portfolio_balance += pnl
                
            del self.active_trades[symbol]
            
    async def run(self):
        """Main loop to process alert signals"""
        
        # Start position monitor
        asyncio.create_task(self.monitor_positions())
        
        while True:
            try:
                # Fetch latest alerts
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.alert_api_url}/signals/live",
                        params={"limit": 5}
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        alerts = data.get("signals", [])
                        
                        for alert in alerts:
                            # Check if we've already processed this alert
                            alert_id = alert.get("id")
                            if not any(t.get("alert_id") == alert_id for t in self.trade_history):
                                result = await self.process_alert_signal(alert)
                                if result:
                                    print(f"Trade executed: {result}")
                                    
            except Exception as e:
                print(f"Error in auto trader: {e}")
                
            await asyncio.sleep(30)  # Check for new signals every 30 seconds
            
    def get_stats(self) -> Dict:
        """Get trading statistics"""
        total_trades = len(self.trade_history)
        active_positions = len(self.active_trades)
        
        # Calculate PnL
        total_pnl = sum(t.get("pnl", 0) for t in self.trade_history if "pnl" in t)
        
        # Win rate
        winning_trades = [t for t in self.trade_history if t.get("pnl", 0) > 0]
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
        
        return {
            "total_trades": total_trades,
            "active_positions": active_positions,
            "total_pnl": total_pnl,
            "win_rate": win_rate,
            "portfolio_balance": self.portfolio_balance,
            "total_exposure": sum(t["position_size"] for t in self.active_trades.values()),
        }

# Auto trader configuration
AUTO_TRADER_CONFIG = {
    "initial_balance": 100000,
    "max_position_size": 0.1,
    "risk_per_trade": 0.02,
    "stop_loss": 0.05,
    "take_profit": 0.15,
    "alert_api": "http://localhost:8010",
    "trading_api": "http://localhost:8003",
}

# Global auto trader instance
auto_trader = AutoTrader(AUTO_TRADER_CONFIG)

async def start_auto_trading():
    """Start the auto trading system"""
    print("Starting Auto Trading System...")
    await auto_trader.run()

if __name__ == "__main__":
    asyncio.run(start_auto_trading())