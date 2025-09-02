"""
Live Portfolio Management System
Real-time trading with actual cryptocurrency prices
"""

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx


@dataclass
class Position:
    """Trading position"""

    id: str
    symbol: str
    side: str  # 'long' or 'short'
    size: float
    entry_price: float
    current_price: float
    entry_time: datetime
    unrealized_pnl: float
    pnl_percentage: float
    value: float


@dataclass
class Trade:
    """Completed trade"""

    id: str
    symbol: str
    side: str
    size: float
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime
    realized_pnl: float
    pnl_percentage: float
    reason: str


class LivePortfolio:
    """Live portfolio management with real prices"""

    def __init__(self, initial_balance: float = 100000):
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.available_balance = initial_balance
        self.positions: Dict[str, Position] = {}
        self.trade_history: List[Trade] = []
        self.daily_pnl = 0.0
        self.total_pnl = 0.0
        self.last_update = datetime.now()

    async def fetch_current_price(self, symbol: str) -> float:
        """Fetch current price from CoinGecko API"""
        try:
            # Convert symbol to CoinGecko format
            coin_id = self.symbol_to_coingecko_id(symbol)

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.coingecko.com/api/v3/simple/price",
                    params={"ids": coin_id, "vs_currencies": "usd"},
                )

                if response.status_code == 200:
                    data = response.json()
                    return data.get(coin_id, {}).get("usd", 0)

        except Exception as e:
            print(f"Error fetching price for {symbol}: {e}")

        # Fallback to mock prices
        return self.get_mock_price(symbol)

    def symbol_to_coingecko_id(self, symbol: str) -> str:
        """Convert trading symbol to CoinGecko ID"""
        symbol_map = {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SOL": "solana",
            "ADA": "cardano",
            "DOT": "polkadot",
            "LINK": "chainlink",
            "UNI": "uniswap",
            "MATIC": "polygon",
            "AVAX": "avalanche-2",
            "DOGE": "dogecoin",
        }
        return symbol_map.get(symbol.replace("/USDT", "").replace("-USD", ""), "bitcoin")

    def get_mock_price(self, symbol: str) -> float:
        """Fallback mock prices"""
        base_prices = {
            "BTC": 96000,
            "ETH": 3300,
            "SOL": 240,
            "ADA": 1.1,
            "DOT": 7.5,
            "LINK": 23,
            "UNI": 6.5,
            "MATIC": 0.67,
            "AVAX": 42,
            "DOGE": 0.38,
        }

        base_symbol = symbol.replace("/USDT", "").replace("-USD", "")
        return base_prices.get(base_symbol, 100)

    async def open_position(
        self, symbol: str, side: str, size_usd: float, reason: str = "Manual"
    ) -> Optional[Position]:
        """Open a new trading position"""

        current_price = await self.fetch_current_price(symbol)

        if current_price <= 0:
            return None

        # Check if we have enough balance
        if size_usd > self.available_balance:
            raise ValueError(f"Insufficient balance: ${self.available_balance:.2f} available")

        # Calculate position size in coins
        coin_size = size_usd / current_price

        # Create position
        position = Position(
            id=str(uuid.uuid4())[:8],
            symbol=symbol,
            side=side,
            size=coin_size,
            entry_price=current_price,
            current_price=current_price,
            entry_time=datetime.now(),
            unrealized_pnl=0.0,
            pnl_percentage=0.0,
            value=size_usd,
        )

        # Update balances
        self.available_balance -= size_usd
        self.positions[position.id] = position

        print(f"Position opened: {side.upper()} {coin_size:.6f} {symbol} @ ${current_price:.4f}")

        return position

    async def close_position(self, position_id: str, reason: str = "Manual") -> Optional[Trade]:
        """Close an existing position"""

        if position_id not in self.positions:
            return None

        position = self.positions[position_id]
        current_price = await self.fetch_current_price(position.symbol)

        if current_price <= 0:
            return None

        # Calculate P&L
        if position.side == "long":
            pnl = (current_price - position.entry_price) * position.size
        else:  # short
            pnl = (position.entry_price - current_price) * position.size

        pnl_percentage = (pnl / position.value) * 100

        # Create trade record
        trade = Trade(
            id=str(uuid.uuid4())[:8],
            symbol=position.symbol,
            side=position.side,
            size=position.size,
            entry_price=position.entry_price,
            exit_price=current_price,
            entry_time=position.entry_time,
            exit_time=datetime.now(),
            realized_pnl=pnl,
            pnl_percentage=pnl_percentage,
            reason=reason,
        )

        # Update balances
        exit_value = position.size * current_price
        self.available_balance += exit_value
        self.total_pnl += pnl

        # Remove position
        del self.positions[position_id]
        self.trade_history.append(trade)

        print(
            f"Position closed: {trade.side.upper()} {trade.symbol} P&L: ${pnl:.2f} ({pnl_percentage:.2f}%)"
        )

        return trade

    async def update_positions(self):
        """Update all positions with current prices"""

        if not self.positions:
            return

        for position in self.positions.values():
            current_price = await self.fetch_current_price(position.symbol)

            if current_price > 0:
                position.current_price = current_price
                position.value = position.size * current_price

                # Calculate unrealized P&L
                if position.side == "long":
                    position.unrealized_pnl = (current_price - position.entry_price) * position.size
                else:  # short
                    position.unrealized_pnl = (position.entry_price - current_price) * position.size

                position.pnl_percentage = (
                    position.unrealized_pnl / (position.entry_price * position.size)
                ) * 100

        # Update daily P&L
        total_unrealized = sum(p.unrealized_pnl for p in self.positions.values())
        self.daily_pnl = (
            (self.available_balance + sum(p.value for p in self.positions.values()))
            / self.initial_balance
            - 1
        ) * 100

        self.last_update = datetime.now()

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get current portfolio summary"""

        total_positions_value = sum(p.value for p in self.positions.values())
        total_portfolio_value = self.available_balance + total_positions_value
        total_unrealized_pnl = sum(p.unrealized_pnl for p in self.positions.values())

        return {
            "total_balance": total_portfolio_value,
            "available_balance": self.available_balance,
            "in_positions": total_positions_value,
            "daily_pnl": self.daily_pnl,
            "total_pnl": self.total_pnl + total_unrealized_pnl,
            "unrealized_pnl": total_unrealized_pnl,
            "realized_pnl": self.total_pnl,
            "position_count": len(self.positions),
            "last_update": self.last_update.isoformat(),
            "currency": "USD",
        }

    def get_positions_list(self) -> List[Dict]:
        """Get list of current positions"""
        return [
            {
                "id": pos.id,
                "symbol": pos.symbol,
                "side": pos.side,
                "size": pos.size,
                "entry_price": pos.entry_price,
                "current_price": pos.current_price,
                "unrealized_pnl": pos.unrealized_pnl,
                "pnl_percentage": pos.pnl_percentage,
                "value": pos.value,
                "entry_time": pos.entry_time.isoformat(),
            }
            for pos in self.positions.values()
        ]

    def get_trade_history(self, limit: int = 50) -> List[Dict]:
        """Get recent trade history"""
        return [
            {
                "id": trade.id,
                "symbol": trade.symbol,
                "side": trade.side,
                "size": trade.size,
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
                "realized_pnl": trade.realized_pnl,
                "pnl_percentage": trade.pnl_percentage,
                "entry_time": trade.entry_time.isoformat(),
                "exit_time": trade.exit_time.isoformat(),
                "reason": trade.reason,
            }
            for trade in sorted(self.trade_history, key=lambda x: x.exit_time, reverse=True)[:limit]
        ]

    async def execute_alert_signal(self, alert: Dict):
        """Execute trading based on alert signal"""

        action = alert.get("action", "")
        symbol = self.extract_symbol_from_alert(alert)

        if not symbol:
            return None

        # Determine position size based on confidence
        confidence = alert.get("confidence", 50)
        base_size = self.available_balance * 0.05  # 5% of available balance
        position_size = base_size * (confidence / 100)

        try:
            if action == "momentum_long":
                return await self.open_position(symbol, "long", position_size, "Alert Signal")
            elif action == "short":
                return await self.open_position(symbol, "short", position_size, "Alert Signal")
            elif action == "hedge":
                # Close profitable positions
                for pos_id, pos in list(self.positions.items()):
                    if pos.unrealized_pnl > 0:
                        await self.close_position(pos_id, "Hedge Signal")
            elif action == "close_position":
                # Close all positions
                for pos_id in list(self.positions.keys()):
                    await self.close_position(pos_id, "Close Signal")

        except Exception as e:
            print(f"Error executing alert signal: {e}")
            return None

    def extract_symbol_from_alert(self, alert: Dict) -> Optional[str]:
        """Extract symbol from alert message"""
        message = alert.get("message", "").upper()

        # Common symbols
        symbols = ["BTC", "ETH", "SOL", "ADA", "DOT", "LINK", "UNI", "MATIC", "AVAX", "DOGE"]

        for symbol in symbols:
            if symbol in message:
                return symbol

        return "BTC"  # Default to Bitcoin


# Global portfolio instance
live_portfolio = LivePortfolio()


async def start_portfolio_updates():
    """Start live portfolio update loop"""
    while True:
        try:
            await live_portfolio.update_positions()
        except Exception as e:
            print(f"Error updating portfolio: {e}")

        await asyncio.sleep(30)  # Update every 30 seconds


if __name__ == "__main__":
    asyncio.run(start_portfolio_updates())
