"""Portfolio management module."""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class Asset(BaseModel):
    """Asset in portfolio."""

    symbol: str
    quantity: float
    average_cost: float
    current_price: float
    market_value: float = 0
    unrealized_pnl: float = 0
    realized_pnl: float = 0
    weight: float = 0  # Portfolio weight percentage

    def update_price(self, price: float) -> None:
        """Update asset price and calculations."""
        self.current_price = price
        self.market_value = self.quantity * price
        self.unrealized_pnl = (price - self.average_cost) * self.quantity


class Portfolio(BaseModel):
    """Portfolio model."""

    id: str = Field(default="main")
    cash_balance: float = Field(default=100000.0)
    initial_capital: float = Field(default=100000.0)
    assets: Dict[str, Asset] = Field(default_factory=dict)
    total_value: float = Field(default=100000.0)
    total_pnl: float = Field(default=0.0)
    total_return: float = Field(default=0.0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def add_asset(
        self,
        symbol: str,
        quantity: float,
        price: float,
    ) -> bool:
        """Add asset to portfolio."""
        cost = quantity * price

        if cost > self.cash_balance:
            return False  # Insufficient funds

        if symbol in self.assets:
            # Update existing position
            asset = self.assets[symbol]
            total_quantity = asset.quantity + quantity
            total_cost = (asset.average_cost * asset.quantity) + cost
            asset.quantity = total_quantity
            asset.average_cost = total_cost / total_quantity if total_quantity > 0 else 0
            asset.update_price(price)
        else:
            # Create new position
            self.assets[symbol] = Asset(
                symbol=symbol,
                quantity=quantity,
                average_cost=price,
                current_price=price,
                market_value=cost,
            )

        self.cash_balance -= cost
        self.update_portfolio_metrics()
        return True

    def remove_asset(
        self,
        symbol: str,
        quantity: float,
        price: float,
    ) -> Optional[float]:
        """Remove asset from portfolio."""
        if symbol not in self.assets:
            return None

        asset = self.assets[symbol]

        if quantity > asset.quantity:
            return None  # Insufficient quantity

        # Calculate realized PnL
        realized_pnl = (price - asset.average_cost) * quantity
        asset.realized_pnl += realized_pnl

        # Update position
        asset.quantity -= quantity
        proceeds = quantity * price
        self.cash_balance += proceeds

        # Remove if position is closed
        if asset.quantity == 0:
            del self.assets[symbol]
        else:
            asset.update_price(price)

        self.update_portfolio_metrics()
        return realized_pnl

    def update_prices(self, prices: Dict[str, float]) -> None:
        """Update asset prices."""
        for symbol, price in prices.items():
            if symbol in self.assets:
                self.assets[symbol].update_price(price)

        self.update_portfolio_metrics()

    def update_portfolio_metrics(self) -> None:
        """Update portfolio metrics."""
        # Calculate total market value of assets
        assets_value = sum(asset.market_value for asset in self.assets.values())

        # Total portfolio value
        self.total_value = self.cash_balance + assets_value

        # Calculate weights
        if self.total_value > 0:
            for asset in self.assets.values():
                asset.weight = (asset.market_value / self.total_value) * 100

        # Calculate total PnL
        unrealized = sum(asset.unrealized_pnl for asset in self.assets.values())
        realized = sum(asset.realized_pnl for asset in self.assets.values())
        self.total_pnl = unrealized + realized

        # Calculate total return
        if self.initial_capital > 0:
            self.total_return = (
                (self.total_value - self.initial_capital) / self.initial_capital
            ) * 100

        self.updated_at = datetime.utcnow()

    def get_asset(self, symbol: str) -> Optional[Asset]:
        """Get asset by symbol."""
        return self.assets.get(symbol)

    def get_allocation(self) -> Dict[str, float]:
        """Get portfolio allocation."""
        allocation = {
            "cash": (self.cash_balance / self.total_value * 100) if self.total_value > 0 else 0
        }

        for symbol, asset in self.assets.items():
            allocation[symbol] = asset.weight

        return allocation

    def get_performance_metrics(self) -> Dict[str, float]:
        """Get portfolio performance metrics."""
        return {
            "total_value": self.total_value,
            "cash_balance": self.cash_balance,
            "assets_value": self.total_value - self.cash_balance,
            "total_pnl": self.total_pnl,
            "total_return": self.total_return,
            "num_positions": len(self.assets),
        }

    def rebalance(self, target_weights: Dict[str, float], prices: Dict[str, float]) -> List[Dict]:
        """Calculate rebalancing trades."""
        trades = []

        # Calculate target values
        for symbol, target_weight in target_weights.items():
            target_value = self.total_value * (target_weight / 100)
            current_value = self.assets[symbol].market_value if symbol in self.assets else 0

            difference = target_value - current_value

            if abs(difference) > 10:  # Minimum trade threshold
                price = prices.get(symbol, 0)
                if price > 0:
                    quantity = difference / price
                    trades.append(
                        {
                            "symbol": symbol,
                            "action": "buy" if quantity > 0 else "sell",
                            "quantity": abs(quantity),
                            "price": price,
                        }
                    )

        return trades
