"""
MM-Lite: Maker-only Micro Scalper
Paper/Shadow trading only - NEVER for live trading
"""

import time
import numpy as np
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass
class MakerOrder:
    """Maker order representation"""
    id: str
    symbol: str
    side: OrderSide
    price: Decimal
    quantity: Decimal
    timestamp: datetime
    filled: bool = False
    fill_price: Optional[Decimal] = None
    fill_time: Optional[datetime] = None


class MMLite:
    """Maker-only micro scalping strategy (PAPER ONLY)"""
    
    def __init__(self, config: Dict = None):
        if config is None:
            config = self.default_config()
        
        # Strategy parameters
        self.symbol = config.get("symbol", "BTCUSDT")
        self.tick_size = Decimal(str(config.get("tick_size", 0.01)))
        self.min_spread_ticks = config.get("min_spread_ticks", 2)
        self.step_in_ticks = config.get("step_in_ticks", 1)
        
        # Position management
        self.max_position = Decimal(str(config.get("max_position", 0.1)))
        self.inventory_band = Decimal(str(config.get("inventory_band", 0.05)))
        self.base_quantity = Decimal(str(config.get("base_quantity", 0.001)))
        
        # Timing
        self.order_timeout_ms = config.get("order_timeout_ms", 5000)
        self.neutralization_interval_s = config.get("neutralization_interval_s", 60)
        
        # State
        self.current_position = Decimal("0")
        self.orders = {}
        self.filled_orders = []
        self.last_neutralization = datetime.now()
        
        # Metrics
        self.total_volume = Decimal("0")
        self.total_pnl = Decimal("0")
        self.fill_count = 0
        self.order_count = 0
        
        # Paper trading state
        self.paper_balance = Decimal("100000")  # Starting balance
        self.paper_position = Decimal("0")
        
        logger.warning("MM-Lite initialized - PAPER TRADING ONLY")
    
    def default_config(self) -> Dict:
        """Default configuration"""
        return {
            "symbol": "BTCUSDT",
            "tick_size": 0.01,
            "min_spread_ticks": 2,
            "step_in_ticks": 1,
            "max_position": 0.1,
            "inventory_band": 0.05,
            "base_quantity": 0.001,
            "order_timeout_ms": 5000,
            "neutralization_interval_s": 60
        }
    
    def get_orderbook_snapshot(self) -> Tuple[Decimal, Decimal, Decimal]:
        """Get current orderbook snapshot (mocked for paper trading)"""
        
        # Mock orderbook data
        mid_price = Decimal("50000") + Decimal(str(np.random.uniform(-100, 100)))
        spread_ticks = np.random.randint(1, 10)
        
        best_bid = mid_price - (self.tick_size * spread_ticks / 2)
        best_ask = mid_price + (self.tick_size * spread_ticks / 2)
        
        return best_bid, best_ask, mid_price
    
    def calculate_order_prices(
        self,
        best_bid: Decimal,
        best_ask: Decimal
    ) -> Tuple[Decimal, Decimal]:
        """Calculate maker order prices"""
        
        # Check spread
        spread_ticks = int((best_ask - best_bid) / self.tick_size)
        
        if spread_ticks < self.min_spread_ticks:
            # Spread too tight, step in
            buy_price = best_bid - (self.tick_size * self.step_in_ticks)
            sell_price = best_ask + (self.tick_size * self.step_in_ticks)
        else:
            # Join best prices
            buy_price = best_bid
            sell_price = best_ask
        
        return buy_price, sell_price
    
    def calculate_order_size(self, side: OrderSide) -> Decimal:
        """Calculate order size based on inventory"""
        
        base_size = self.base_quantity
        
        # Adjust for inventory
        if side == OrderSide.BUY:
            if self.current_position > self.inventory_band:
                # Long heavy, reduce buy size
                return base_size * Decimal("0.5")
            elif self.current_position < -self.inventory_band:
                # Short heavy, increase buy size
                return base_size * Decimal("1.5")
        else:  # SELL
            if self.current_position < -self.inventory_band:
                # Short heavy, reduce sell size
                return base_size * Decimal("0.5")
            elif self.current_position > self.inventory_band:
                # Long heavy, increase sell size
                return base_size * Decimal("1.5")
        
        return base_size
    
    def should_neutralize(self) -> bool:
        """Check if position needs neutralization"""
        
        # Time-based neutralization
        time_since_neutral = (datetime.now() - self.last_neutralization).total_seconds()
        if time_since_neutral > self.neutralization_interval_s:
            if abs(self.current_position) > self.inventory_band / 2:
                return True
        
        # Position limit neutralization
        if abs(self.current_position) > self.max_position * Decimal("0.8"):
            return True
        
        return False
    
    def place_maker_orders(self) -> List[MakerOrder]:
        """Place maker orders on both sides"""
        
        # Get orderbook
        best_bid, best_ask, mid_price = self.get_orderbook_snapshot()
        
        # Calculate prices
        buy_price, sell_price = self.calculate_order_prices(best_bid, best_ask)
        
        # Calculate sizes
        buy_size = self.calculate_order_size(OrderSide.BUY)
        sell_size = self.calculate_order_size(OrderSide.SELL)
        
        orders_placed = []
        
        # Place buy order if not at max position
        if self.current_position < self.max_position:
            buy_order = MakerOrder(
                id=f"buy_{int(time.time()*1000)}",
                symbol=self.symbol,
                side=OrderSide.BUY,
                price=buy_price,
                quantity=buy_size,
                timestamp=datetime.now()
            )
            self.orders[buy_order.id] = buy_order
            orders_placed.append(buy_order)
            self.order_count += 1
        
        # Place sell order if not at min position
        if self.current_position > -self.max_position:
            sell_order = MakerOrder(
                id=f"sell_{int(time.time()*1000)}",
                symbol=self.symbol,
                side=OrderSide.SELL,
                price=sell_price,
                quantity=sell_size,
                timestamp=datetime.now()
            )
            self.orders[sell_order.id] = sell_order
            orders_placed.append(sell_order)
            self.order_count += 1
        
        return orders_placed
    
    def simulate_fills(self) -> List[MakerOrder]:
        """Simulate order fills (paper trading)"""
        
        filled = []
        current_time = datetime.now()
        
        # Get current market
        best_bid, best_ask, mid_price = self.get_orderbook_snapshot()
        
        for order_id, order in list(self.orders.items()):
            if order.filled:
                continue
            
            # Check timeout
            age_ms = (current_time - order.timestamp).total_seconds() * 1000
            if age_ms > self.order_timeout_ms:
                # Cancel old order
                del self.orders[order_id]
                continue
            
            # Simulate fill probability
            fill_prob = 0.4  # Base fill rate
            
            # Adjust probability based on price distance
            if order.side == OrderSide.BUY:
                distance = (best_bid - order.price) / self.tick_size
                if distance <= 0:
                    fill_prob = 0.7  # At or better than best bid
                elif distance <= 2:
                    fill_prob = 0.3
                else:
                    fill_prob = 0.1
            else:  # SELL
                distance = (order.price - best_ask) / self.tick_size
                if distance <= 0:
                    fill_prob = 0.7  # At or better than best ask
                elif distance <= 2:
                    fill_prob = 0.3
                else:
                    fill_prob = 0.1
            
            # Random fill
            if np.random.random() < fill_prob:
                order.filled = True
                order.fill_price = order.price
                order.fill_time = current_time
                
                # Update position
                if order.side == OrderSide.BUY:
                    self.current_position += order.quantity
                    self.paper_position += order.quantity
                    self.paper_balance -= order.price * order.quantity
                else:
                    self.current_position -= order.quantity
                    self.paper_position -= order.quantity
                    self.paper_balance += order.price * order.quantity
                
                # Update metrics
                self.fill_count += 1
                self.total_volume += order.quantity * order.price
                
                filled.append(order)
                self.filled_orders.append(order)
        
        return filled
    
    def neutralize_position(self) -> Optional[MakerOrder]:
        """Neutralize inventory drift"""
        
        if abs(self.current_position) < self.inventory_band / 2:
            return None
        
        # Get market
        best_bid, best_ask, mid_price = self.get_orderbook_snapshot()
        
        # Create neutralization order
        if self.current_position > 0:
            # Long, need to sell
            neutral_order = MakerOrder(
                id=f"neutral_{int(time.time()*1000)}",
                symbol=self.symbol,
                side=OrderSide.SELL,
                price=best_ask - self.tick_size,  # Aggressive price
                quantity=min(self.current_position, self.base_quantity * 2),
                timestamp=datetime.now()
            )
        else:
            # Short, need to buy
            neutral_order = MakerOrder(
                id=f"neutral_{int(time.time()*1000)}",
                symbol=self.symbol,
                side=OrderSide.BUY,
                price=best_bid + self.tick_size,  # Aggressive price
                quantity=min(abs(self.current_position), self.base_quantity * 2),
                timestamp=datetime.now()
            )
        
        self.orders[neutral_order.id] = neutral_order
        self.last_neutralization = datetime.now()
        
        logger.info(f"Neutralizing position: {self.current_position:.4f}")
        
        return neutral_order
    
    def calculate_pnl(self) -> Decimal:
        """Calculate realized P&L"""
        
        pnl = Decimal("0")
        buy_volume = Decimal("0")
        sell_volume = Decimal("0")
        
        for order in self.filled_orders:
            if order.side == OrderSide.BUY:
                buy_volume += order.fill_price * order.quantity
            else:
                sell_volume += order.fill_price * order.quantity
        
        # Simple P&L: sell revenue - buy cost
        pnl = sell_volume - buy_volume
        
        # Add unrealized P&L if position not flat
        if self.current_position != 0:
            _, _, mid_price = self.get_orderbook_snapshot()
            unrealized = self.current_position * mid_price
            
            # Estimate cost basis
            avg_fill = buy_volume / max(sum(o.quantity for o in self.filled_orders 
                                           if o.side == OrderSide.BUY), Decimal("0.001"))
            cost_basis = self.current_position * avg_fill
            
            unrealized_pnl = unrealized - cost_basis if self.current_position > 0 else cost_basis - unrealized
            pnl += unrealized_pnl
        
        return pnl
    
    def get_metrics(self) -> Dict:
        """Get strategy metrics"""
        
        fill_rate = self.fill_count / max(self.order_count, 1)
        pnl = self.calculate_pnl()
        pnl_pct = (pnl / self.paper_balance) * 100 if self.paper_balance > 0 else Decimal("0")
        
        # Calculate inventory variance
        if self.filled_orders:
            positions = []
            temp_pos = Decimal("0")
            for order in self.filled_orders:
                if order.side == OrderSide.BUY:
                    temp_pos += order.quantity
                else:
                    temp_pos -= order.quantity
                positions.append(float(temp_pos))
            
            inventory_var = np.var(positions) if positions else 0
        else:
            inventory_var = 0
        
        return {
            "symbol": self.symbol,
            "current_position": float(self.current_position),
            "total_volume": float(self.total_volume),
            "fill_count": self.fill_count,
            "order_count": self.order_count,
            "fill_rate": fill_rate,
            "pnl": float(pnl),
            "pnl_pct": float(pnl_pct),
            "inventory_var": inventory_var,
            "paper_balance": float(self.paper_balance),
            "paper_position": float(self.paper_position)
        }
    
    def check_pass_criteria(self) -> Tuple[bool, Dict]:
        """Check if strategy passes criteria"""
        
        metrics = self.get_metrics()
        
        criteria = {
            "pnl_positive": metrics["pnl_pct"] > 0,
            "inventory_controlled": metrics["inventory_var"] < 0.01,  # Variance limit
            "fill_rate_good": metrics["fill_rate"] > 0.4
        }
        
        pass_all = all(criteria.values())
        
        return pass_all, criteria
    
    def run_cycle(self) -> Dict:
        """Run one MM cycle"""
        
        cycle_report = {
            "timestamp": datetime.now().isoformat(),
            "actions": []
        }
        
        # Check for neutralization
        if self.should_neutralize():
            neutral_order = self.neutralize_position()
            if neutral_order:
                cycle_report["actions"].append({
                    "type": "neutralize",
                    "order_id": neutral_order.id,
                    "side": neutral_order.side.value,
                    "price": float(neutral_order.price),
                    "quantity": float(neutral_order.quantity)
                })
        
        # Place new maker orders
        new_orders = self.place_maker_orders()
        for order in new_orders:
            cycle_report["actions"].append({
                "type": "place_order",
                "order_id": order.id,
                "side": order.side.value,
                "price": float(order.price),
                "quantity": float(order.quantity)
            })
        
        # Simulate fills
        filled_orders = self.simulate_fills()
        for order in filled_orders:
            cycle_report["actions"].append({
                "type": "fill",
                "order_id": order.id,
                "side": order.side.value,
                "price": float(order.fill_price),
                "quantity": float(order.quantity)
            })
        
        # Add metrics
        cycle_report["metrics"] = self.get_metrics()
        
        return cycle_report
    
    def reset(self):
        """Reset strategy state"""
        self.current_position = Decimal("0")
        self.orders = {}
        self.filled_orders = []
        self.total_volume = Decimal("0")
        self.total_pnl = Decimal("0")
        self.fill_count = 0
        self.order_count = 0
        self.paper_balance = Decimal("100000")
        self.paper_position = Decimal("0")
        self.last_neutralization = datetime.now()


def test_mm_lite():
    """Test MM-Lite strategy"""
    
    print("="*60)
    print(" MM-LITE TEST (PAPER ONLY)")
    print("="*60)
    print("[WARNING] This strategy is for paper/shadow testing only")
    print("[WARNING] NEVER connect to live trading")
    print("-"*60)
    
    # Initialize strategy
    mm = MMLite({
        "symbol": "BTCUSDT",
        "max_position": 0.1,
        "inventory_band": 0.05,
        "base_quantity": 0.001
    })
    
    # Run for 15 cycles (simulating 15 seconds)
    for i in range(15):
        print(f"\nCycle {i+1}:")
        
        report = mm.run_cycle()
        
        # Print actions
        for action in report["actions"]:
            if action["type"] == "place_order":
                print(f"  [ORDER] {action['side']} {action['quantity']:.4f} @ {action['price']:.2f}")
            elif action["type"] == "fill":
                print(f"  [FILL] {action['side']} {action['quantity']:.4f} @ {action['price']:.2f}")
            elif action["type"] == "neutralize":
                print(f"  [NEUTRAL] {action['side']} {action['quantity']:.4f}")
        
        # Print metrics every 5 cycles
        if (i + 1) % 5 == 0:
            metrics = report["metrics"]
            print(f"\n  Metrics:")
            print(f"    Position: {metrics['current_position']:.4f}")
            print(f"    Fill Rate: {metrics['fill_rate']:.2%}")
            print(f"    P&L: {metrics['pnl']:.2f} ({metrics['pnl_pct']:.3f}%)")
        
        time.sleep(0.1)  # Small delay for simulation
    
    # Final results
    print("\n" + "="*60)
    print(" FINAL RESULTS")
    print("="*60)
    
    metrics = mm.get_metrics()
    pass_check, criteria = mm.check_pass_criteria()
    
    print(f"Total Volume: {metrics['total_volume']:.2f}")
    print(f"Fill Count: {metrics['fill_count']}/{metrics['order_count']}")
    print(f"Fill Rate: {metrics['fill_rate']:.2%}")
    print(f"Final Position: {metrics['current_position']:.4f}")
    print(f"P&L: {metrics['pnl']:.2f} ({metrics['pnl_pct']:.3f}%)")
    print(f"Inventory Variance: {metrics['inventory_var']:.6f}")
    
    print("\nPASS Criteria:")
    for criterion, passed in criteria.items():
        status = "[OK]" if passed else "[FAIL]"
        print(f"  {status} {criterion}")
    
    print(f"\nOverall: {'PASS' if pass_check else 'FAIL'}")
    print("="*60)


if __name__ == "__main__":
    test_mm_lite()