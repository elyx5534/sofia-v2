"""
Turkish Cryptocurrency Arbitrage System
Specialized for BTCTurk, Binance TR, and Paribu

STATUS: SKELETON READY - To be activated tomorrow
Fee parameters configured, spread calculation ready
"""

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class TurkishExchange(Enum):
    BTCTURK = "btcturk"
    BINANCE_TR = "binance_tr"
    PARIBU = "paribu"


class ArbitrageType(Enum):
    TWO_WAY = "two_way"
    THREE_WAY = "three_way"
    TRIANGULAR = "triangular"


@dataclass
class ExchangeConfig:
    """Exchange configuration"""

    name: TurkishExchange
    api_key: str
    api_secret: str
    maker_fee: Decimal
    taker_fee: Decimal
    withdrawal_fee: Decimal
    min_order_size: Dict[str, Decimal]
    api_url: str
    ws_url: Optional[str] = None


@dataclass
class OrderBookSnapshot:
    """Order book snapshot"""

    exchange: TurkishExchange
    symbol: str
    bids: List[Tuple[Decimal, Decimal]]
    asks: List[Tuple[Decimal, Decimal]]
    timestamp: float

    @property
    def best_bid(self) -> Optional[Decimal]:
        return self.bids[0][0] if self.bids else None

    @property
    def best_ask(self) -> Optional[Decimal]:
        return self.asks[0][0] if self.asks else None

    @property
    def spread(self) -> Optional[Decimal]:
        if self.best_bid and self.best_ask:
            return self.best_ask - self.best_bid
        return None

    def get_liquidity(self, side: str, depth: int = 5) -> Decimal:
        """Get total liquidity at given depth"""
        orders = self.bids if side == "bid" else self.asks
        total = Decimal(0)
        for i, (price, amount) in enumerate(orders):
            if i >= depth:
                break
            total += amount * price
        return total


@dataclass
class ArbitrageOpportunity:
    """Arbitrage opportunity"""

    type: ArbitrageType
    buy_exchange: TurkishExchange
    sell_exchange: TurkishExchange
    symbol: str
    buy_price: Decimal
    sell_price: Decimal
    max_amount: Decimal
    spread_percentage: Decimal
    gross_profit: Decimal
    net_profit: Decimal
    slippage_risk: Decimal
    timestamp: float = field(default_factory=time.time)

    @property
    def is_profitable(self) -> bool:
        return self.net_profit > 0


@dataclass
class ExecutionResult:
    """Trade execution result"""

    opportunity: ArbitrageOpportunity
    buy_order_id: Optional[str]
    sell_order_id: Optional[str]
    buy_filled: Decimal
    sell_filled: Decimal
    actual_profit: Decimal
    execution_time: float
    success: bool
    error: Optional[str] = None
    rollback_needed: bool = False


class TurkishArbitrageSystem:
    """Turkish cryptocurrency arbitrage system"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.exchanges: Dict[TurkishExchange, ExchangeConfig] = {}
        self._setup_exchanges()
        self.min_profit_tl = Decimal(str(config.get("min_profit_tl", 100)))
        self.max_position_tl = Decimal(str(config.get("max_position_tl", 20000)))
        self.max_daily_trades = config.get("max_daily_trades", 50)
        self.cooldown_seconds = config.get("cooldown_seconds", 30)
        self.min_spread_percentage = Decimal(str(config.get("min_spread_percentage", 0.003)))
        self.execution_timeout = config.get("execution_timeout", 10)
        self.max_slippage = Decimal(str(config.get("max_slippage", 0.002)))
        self.min_liquidity = Decimal(str(config.get("min_liquidity", 10000)))
        self.partial_fill_threshold = Decimal(str(config.get("partial_fill_threshold", 0.95)))
        self.orderbooks: Dict[Tuple[TurkishExchange, str], OrderBookSnapshot] = {}
        self.balances: Dict[TurkishExchange, Dict[str, Decimal]] = {}
        self.daily_trades_count = 0
        self.total_profit = Decimal(0)
        self.last_trade_time: Optional[datetime] = None
        self.spread_history: Dict[str, deque] = {}
        self.execution_history: List[ExecutionResult] = []
        self.opportunities_found = 0
        self.trades_executed = 0
        self.trades_successful = 0
        self.total_volume = Decimal(0)
        self.monitor_task = None
        self.balance_task = None
        self.cleanup_task = None

    def _setup_exchanges(self):
        """Setup exchange configurations"""
        self.exchanges[TurkishExchange.BTCTURK] = ExchangeConfig(
            name=TurkishExchange.BTCTURK,
            api_key=self.config.get("btcturk_api_key", ""),
            api_secret=self.config.get("btcturk_api_secret", ""),
            maker_fee=Decimal("0.0018"),
            taker_fee=Decimal("0.0025"),
            withdrawal_fee=Decimal("0.0005"),
            min_order_size={
                "BTCTRY": Decimal("0.0001"),
                "ETHTRY": Decimal("0.001"),
                "USDTTRY": Decimal("10"),
            },
            api_url="https://api.btcturk.com",
            ws_url="wss://ws-feed-pro.btcturk.com",
        )
        self.exchanges[TurkishExchange.BINANCE_TR] = ExchangeConfig(
            name=TurkishExchange.BINANCE_TR,
            api_key=self.config.get("binance_tr_api_key", ""),
            api_secret=self.config.get("binance_tr_api_secret", ""),
            maker_fee=Decimal("0.001"),
            taker_fee=Decimal("0.001"),
            withdrawal_fee=Decimal("0.0005"),
            min_order_size={
                "BTCTRY": Decimal("0.0001"),
                "ETHTRY": Decimal("0.001"),
                "USDTTRY": Decimal("10"),
            },
            api_url="https://trbinance.com/api",
            ws_url="wss://stream.binance.com:9443/ws",
        )
        self.exchanges[TurkishExchange.PARIBU] = ExchangeConfig(
            name=TurkishExchange.PARIBU,
            api_key=self.config.get("paribu_api_key", ""),
            api_secret=self.config.get("paribu_api_secret", ""),
            maker_fee=Decimal("0.0015"),
            taker_fee=Decimal("0.0025"),
            withdrawal_fee=Decimal("0.0005"),
            min_order_size={
                "BTCTRY": Decimal("0.0001"),
                "ETHTRY": Decimal("0.001"),
                "USDTTRY": Decimal("10"),
            },
            api_url="https://v4.paribu.com",
            ws_url=None,
        )

    async def initialize(self):
        """Initialize arbitrage system"""
        logger.info("Initializing Turkish Arbitrage System")
        self.monitor_task = asyncio.create_task(self._monitor_spreads())
        self.balance_task = asyncio.create_task(self._update_balances())
        self.cleanup_task = asyncio.create_task(self._cleanup_old_data())
        await self._connect_exchanges()
        logger.info("Turkish Arbitrage System initialized")

    async def shutdown(self):
        """Shutdown arbitrage system"""
        if self.monitor_task:
            self.monitor_task.cancel()
        if self.balance_task:
            self.balance_task.cancel()
        if self.cleanup_task:
            self.cleanup_task.cancel()

    async def _connect_exchanges(self):
        """Connect to all exchanges"""
        pass

    async def fetch_orderbook(
        self, exchange: TurkishExchange, symbol: str
    ) -> Optional[OrderBookSnapshot]:
        """Fetch order book from exchange"""
        try:
            base_price = Decimal("2000000") if "BTC" in symbol else Decimal("130000")
            spread_factor = {
                TurkishExchange.BTCTURK: Decimal("1.001"),
                TurkishExchange.BINANCE_TR: Decimal("1.000"),
                TurkishExchange.PARIBU: Decimal("1.002"),
            }[exchange]
            price = base_price * spread_factor
            bids = [(price - Decimal(i * 100), Decimal(f"0.{10 - i}")) for i in range(10)]
            asks = [(price + Decimal(i * 100), Decimal(f"0.{10 - i}")) for i in range(10)]
            snapshot = OrderBookSnapshot(
                exchange=exchange, symbol=symbol, bids=bids, asks=asks, timestamp=time.time()
            )
            self.orderbooks[exchange, symbol] = snapshot
            return snapshot
        except Exception as e:
            logger.error(f"Error fetching orderbook from {exchange.value}: {e}")
            return None

    def calculate_arbitrage(
        self, symbol: str, orderbooks: Dict[TurkishExchange, OrderBookSnapshot]
    ) -> List[ArbitrageOpportunity]:
        """Calculate arbitrage opportunities"""
        opportunities = []
        exchanges = list(orderbooks.keys())
        for i, ex1 in enumerate(exchanges):
            for ex2 in exchanges[i + 1 :]:
                book1 = orderbooks[ex1]
                book2 = orderbooks[ex2]
                if not (book1.best_bid and book1.best_ask and book2.best_bid and book2.best_ask):
                    continue
                if book1.best_ask < book2.best_bid:
                    opp = self._create_opportunity(
                        buy_exchange=ex1,
                        sell_exchange=ex2,
                        buy_book=book1,
                        sell_book=book2,
                        symbol=symbol,
                    )
                    if opp and opp.is_profitable:
                        opportunities.append(opp)
                if book2.best_ask < book1.best_bid:
                    opp = self._create_opportunity(
                        buy_exchange=ex2,
                        sell_exchange=ex1,
                        buy_book=book2,
                        sell_book=book1,
                        symbol=symbol,
                    )
                    if opp and opp.is_profitable:
                        opportunities.append(opp)
        return opportunities

    def _create_opportunity(
        self,
        buy_exchange: TurkishExchange,
        sell_exchange: TurkishExchange,
        buy_book: OrderBookSnapshot,
        sell_book: OrderBookSnapshot,
        symbol: str,
    ) -> Optional[ArbitrageOpportunity]:
        """Create arbitrage opportunity with fee calculations"""
        buy_price = buy_book.best_ask
        sell_price = sell_book.best_bid
        if not (buy_price and sell_price):
            return None
        spread = sell_price - buy_price
        spread_percentage = spread / buy_price * 100
        if spread_percentage < self.min_spread_percentage * 100:
            return None
        buy_fee = self.exchanges[buy_exchange].taker_fee
        sell_fee = self.exchanges[sell_exchange].taker_fee
        buy_liquidity = buy_book.get_liquidity("ask", 3)
        sell_liquidity = sell_book.get_liquidity("bid", 3)
        max_amount_tl = min(buy_liquidity, sell_liquidity, self.max_position_tl)
        if max_amount_tl < self.min_liquidity:
            return None
        max_amount = max_amount_tl / buy_price
        gross_profit = max_amount * spread
        buy_cost = max_amount * buy_price * buy_fee
        sell_cost = max_amount * sell_price * sell_fee
        net_profit = gross_profit - buy_cost - sell_cost
        slippage_risk = self._estimate_slippage(buy_book, sell_book, max_amount)
        return ArbitrageOpportunity(
            type=ArbitrageType.TWO_WAY,
            buy_exchange=buy_exchange,
            sell_exchange=sell_exchange,
            symbol=symbol,
            buy_price=buy_price,
            sell_price=sell_price,
            max_amount=max_amount,
            spread_percentage=spread_percentage,
            gross_profit=gross_profit,
            net_profit=net_profit,
            slippage_risk=slippage_risk,
        )

    def _estimate_slippage(
        self, buy_book: OrderBookSnapshot, sell_book: OrderBookSnapshot, amount: Decimal
    ) -> Decimal:
        """Estimate slippage for given amount"""
        buy_slippage = self._calculate_weighted_price(buy_book.asks, amount) - buy_book.best_ask
        sell_slippage = sell_book.best_bid - self._calculate_weighted_price(sell_book.bids, amount)
        total_slippage = buy_slippage + sell_slippage
        if buy_book.best_ask > 0:
            return total_slippage / buy_book.best_ask * 100
        return Decimal(0)

    def _calculate_weighted_price(
        self, orders: List[Tuple[Decimal, Decimal]], target_amount: Decimal
    ) -> Decimal:
        """Calculate weighted average price for target amount"""
        remaining = target_amount
        total_cost = Decimal(0)
        total_amount = Decimal(0)
        for price, amount in orders:
            if remaining <= 0:
                break
            fill_amount = min(remaining, amount)
            total_cost += price * fill_amount
            total_amount += fill_amount
            remaining -= fill_amount
        if total_amount > 0:
            return total_cost / total_amount
        return orders[0][0] if orders else Decimal(0)

    async def execute_arbitrage(self, opportunity: ArbitrageOpportunity) -> ExecutionResult:
        """Execute arbitrage trade"""
        start_time = time.time()
        if not self._check_cooldown():
            return ExecutionResult(
                opportunity=opportunity,
                buy_order_id=None,
                sell_order_id=None,
                buy_filled=Decimal(0),
                sell_filled=Decimal(0),
                actual_profit=Decimal(0),
                execution_time=0,
                success=False,
                error="Cooldown period active",
            )
        if self.daily_trades_count >= self.max_daily_trades:
            return ExecutionResult(
                opportunity=opportunity,
                buy_order_id=None,
                sell_order_id=None,
                buy_filled=Decimal(0),
                sell_filled=Decimal(0),
                actual_profit=Decimal(0),
                execution_time=0,
                success=False,
                error="Daily trade limit reached",
            )
        if not await self._check_balances(opportunity):
            return ExecutionResult(
                opportunity=opportunity,
                buy_order_id=None,
                sell_order_id=None,
                buy_filled=Decimal(0),
                sell_filled=Decimal(0),
                actual_profit=Decimal(0),
                execution_time=0,
                success=False,
                error="Insufficient balance",
            )
        try:
            buy_task = asyncio.create_task(
                self._place_order(
                    opportunity.buy_exchange,
                    opportunity.symbol,
                    "buy",
                    opportunity.max_amount,
                    opportunity.buy_price,
                )
            )
            sell_task = asyncio.create_task(
                self._place_order(
                    opportunity.sell_exchange,
                    opportunity.symbol,
                    "sell",
                    opportunity.max_amount,
                    opportunity.sell_price,
                )
            )
            done, pending = await asyncio.wait(
                [buy_task, sell_task], timeout=self.execution_timeout
            )
            for task in pending:
                task.cancel()
            buy_result = await buy_task if buy_task.done() else None
            sell_result = await sell_task if sell_task.done() else None
            if buy_result and sell_result:
                buy_filled = buy_result.get("filled", Decimal(0))
                sell_filled = sell_result.get("filled", Decimal(0))
                fill_ratio = min(buy_filled, sell_filled) / opportunity.max_amount
                if fill_ratio >= self.partial_fill_threshold:
                    actual_buy_cost = buy_filled * buy_result.get(
                        "avg_price", opportunity.buy_price
                    )
                    actual_sell_revenue = sell_filled * sell_result.get(
                        "avg_price", opportunity.sell_price
                    )
                    buy_fee = actual_buy_cost * self.exchanges[opportunity.buy_exchange].taker_fee
                    sell_fee = (
                        actual_sell_revenue * self.exchanges[opportunity.sell_exchange].taker_fee
                    )
                    actual_profit = actual_sell_revenue - actual_buy_cost - buy_fee - sell_fee
                    self.daily_trades_count += 1
                    self.total_profit += actual_profit
                    self.trades_executed += 1
                    self.trades_successful += 1
                    self.total_volume += actual_buy_cost
                    self.last_trade_time = datetime.now()
                    return ExecutionResult(
                        opportunity=opportunity,
                        buy_order_id=buy_result.get("order_id"),
                        sell_order_id=sell_result.get("order_id"),
                        buy_filled=buy_filled,
                        sell_filled=sell_filled,
                        actual_profit=actual_profit,
                        execution_time=time.time() - start_time,
                        success=True,
                    )
                else:
                    await self._rollback_orders(buy_result, sell_result)
                    return ExecutionResult(
                        opportunity=opportunity,
                        buy_order_id=buy_result.get("order_id"),
                        sell_order_id=sell_result.get("order_id"),
                        buy_filled=buy_filled,
                        sell_filled=sell_filled,
                        actual_profit=Decimal(0),
                        execution_time=time.time() - start_time,
                        success=False,
                        error="Insufficient fill",
                        rollback_needed=True,
                    )
            else:
                if buy_result:
                    await self._cancel_order(opportunity.buy_exchange, buy_result.get("order_id"))
                if sell_result:
                    await self._cancel_order(opportunity.sell_exchange, sell_result.get("order_id"))
                return ExecutionResult(
                    opportunity=opportunity,
                    buy_order_id=buy_result.get("order_id") if buy_result else None,
                    sell_order_id=sell_result.get("order_id") if sell_result else None,
                    buy_filled=Decimal(0),
                    sell_filled=Decimal(0),
                    actual_profit=Decimal(0),
                    execution_time=time.time() - start_time,
                    success=False,
                    error="Order execution failed",
                )
        except asyncio.TimeoutError:
            return ExecutionResult(
                opportunity=opportunity,
                buy_order_id=None,
                sell_order_id=None,
                buy_filled=Decimal(0),
                sell_filled=Decimal(0),
                actual_profit=Decimal(0),
                execution_time=self.execution_timeout,
                success=False,
                error="Execution timeout",
            )
        except Exception as e:
            logger.error(f"Arbitrage execution error: {e}")
            return ExecutionResult(
                opportunity=opportunity,
                buy_order_id=None,
                sell_order_id=None,
                buy_filled=Decimal(0),
                sell_filled=Decimal(0),
                actual_profit=Decimal(0),
                execution_time=time.time() - start_time,
                success=False,
                error=str(e),
            )

    async def _place_order(
        self, exchange: TurkishExchange, symbol: str, side: str, amount: Decimal, price: Decimal
    ) -> Dict[str, Any]:
        """Place order on exchange"""
        await asyncio.sleep(0.1)
        fill_percentage = Decimal(str(np.random.uniform(0.95, 1.0)))
        return {
            "order_id": f"{exchange.value}_{int(time.time() * 1000)}",
            "symbol": symbol,
            "side": side,
            "amount": amount,
            "price": price,
            "filled": amount * fill_percentage,
            "avg_price": price * Decimal(str(np.random.uniform(0.999, 1.001))),
            "status": "filled",
        }

    async def _cancel_order(self, exchange: TurkishExchange, order_id: str):
        """Cancel order on exchange"""
        logger.info(f"Cancelling order {order_id} on {exchange.value}")

    async def _rollback_orders(self, buy_result: Dict, sell_result: Dict):
        """Rollback partially filled orders"""
        logger.warning("Rolling back partial fills")

    def _check_cooldown(self) -> bool:
        """Check if cooldown period has passed"""
        if not self.last_trade_time:
            return True
        elapsed = (datetime.now() - self.last_trade_time).total_seconds()
        return elapsed >= self.cooldown_seconds

    async def _check_balances(self, opportunity: ArbitrageOpportunity) -> bool:
        """Check if sufficient balance exists"""
        return True

    async def _update_balances(self):
        """Update balance information periodically"""
        while True:
            try:
                await asyncio.sleep(30)
                for exchange in self.exchanges:
                    self.balances[exchange] = {
                        "TRY": Decimal("50000"),
                        "BTC": Decimal("0.1"),
                        "ETH": Decimal("1"),
                        "USDT": Decimal("1000"),
                    }
            except Exception as e:
                logger.error(f"Balance update error: {e}")

    async def _monitor_spreads(self):
        """Monitor spreads continuously"""
        symbols = ["BTCTRY", "ETHTRY", "USDTTRY"]
        while True:
            try:
                for symbol in symbols:
                    orderbooks = {}
                    for exchange in self.exchanges:
                        book = await self.fetch_orderbook(exchange, symbol)
                        if book:
                            orderbooks[exchange] = book
                    if len(orderbooks) >= 2:
                        opportunities = self.calculate_arbitrage(symbol, orderbooks)
                        for opp in opportunities:
                            self.opportunities_found += 1
                            logger.info(
                                f"Arbitrage opportunity: {opp.symbol} Buy {opp.buy_exchange.value} @ {opp.buy_price:.2f} Sell {opp.sell_exchange.value} @ {opp.sell_price:.2f} Profit: {opp.net_profit:.2f} TL ({opp.spread_percentage:.3f}%)"
                            )
                            if opp.net_profit >= self.min_profit_tl:
                                result = await self.execute_arbitrage(opp)
                                self.execution_history.append(result)
                                if result.success:
                                    logger.info(
                                        f"Arbitrage executed successfully! Profit: {result.actual_profit:.2f} TL"
                                    )
                                else:
                                    logger.warning(f"Arbitrage execution failed: {result.error}")
                    if symbol not in self.spread_history:
                        self.spread_history[symbol] = deque(maxlen=1000)
                    if len(orderbooks) >= 2:
                        spreads = []
                        for ex1, book1 in orderbooks.items():
                            for ex2, book2 in orderbooks.items():
                                if ex1 != ex2 and book1.best_ask and book2.best_bid:
                                    spread = (
                                        (book2.best_bid - book1.best_ask) / book1.best_ask * 100
                                    )
                                    spreads.append(float(spread))
                        if spreads:
                            self.spread_history[symbol].append(
                                {
                                    "timestamp": time.time(),
                                    "max_spread": max(spreads),
                                    "avg_spread": sum(spreads) / len(spreads),
                                }
                            )
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Spread monitoring error: {e}")
                await asyncio.sleep(5)

    async def _cleanup_old_data(self):
        """Clean up old data periodically"""
        while True:
            try:
                await asyncio.sleep(3600)
                now = datetime.now()
                if now.hour == 0 and now.minute < 1:
                    self.daily_trades_count = 0
                    logger.info("Daily trade counter reset")
                if len(self.execution_history) > 1000:
                    self.execution_history = self.execution_history[-500:]
            except Exception as e:
                logger.error(f"Cleanup error: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        """Get system statistics"""
        success_rate = 0
        if self.trades_executed > 0:
            success_rate = self.trades_successful / self.trades_executed * 100
        avg_spread = {}
        for symbol, history in self.spread_history.items():
            if history:
                recent = list(history)[-100:]
                avg_spread[symbol] = sum(h["max_spread"] for h in recent) / len(recent)
        return {
            "opportunities_found": self.opportunities_found,
            "trades_executed": self.trades_executed,
            "trades_successful": self.trades_successful,
            "success_rate": success_rate,
            "total_profit": float(self.total_profit),
            "total_volume": float(self.total_volume),
            "daily_trades": self.daily_trades_count,
            "avg_spreads": avg_spread,
            "last_trade": self.last_trade_time.isoformat() if self.last_trade_time else None,
        }

    async def backtest(
        self, historical_data: Optional[List[Dict]] = None, num_opportunities: int = 1000
    ) -> Dict[str, Any]:
        """Backtest arbitrage strategy"""
        logger.info(f"Starting backtest with {num_opportunities} opportunities")
        if not historical_data:
            historical_data = self._generate_fake_opportunities(num_opportunities)
        results = {
            "total_opportunities": 0,
            "profitable_opportunities": 0,
            "executed_trades": 0,
            "successful_trades": 0,
            "total_profit": Decimal(0),
            "max_profit": Decimal(0),
            "min_profit": Decimal(999999),
            "avg_profit": Decimal(0),
            "total_volume": Decimal(0),
        }
        for data in historical_data:
            opp = ArbitrageOpportunity(
                type=ArbitrageType.TWO_WAY,
                buy_exchange=data["buy_exchange"],
                sell_exchange=data["sell_exchange"],
                symbol=data["symbol"],
                buy_price=Decimal(str(data["buy_price"])),
                sell_price=Decimal(str(data["sell_price"])),
                max_amount=Decimal(str(data["amount"])),
                spread_percentage=Decimal(str(data["spread"])),
                gross_profit=Decimal(str(data["gross_profit"])),
                net_profit=Decimal(str(data["net_profit"])),
                slippage_risk=Decimal(str(data.get("slippage", 0))),
            )
            results["total_opportunities"] += 1
            if opp.is_profitable:
                results["profitable_opportunities"] += 1
                if opp.net_profit >= self.min_profit_tl:
                    success_probability = 0.95 - float(opp.slippage_risk) / 100
                    if np.random.random() < success_probability:
                        results["successful_trades"] += 1
                        results["total_profit"] += opp.net_profit
                        results["max_profit"] = max(results["max_profit"], opp.net_profit)
                        results["min_profit"] = min(results["min_profit"], opp.net_profit)
                        results["total_volume"] += opp.max_amount * opp.buy_price
                    results["executed_trades"] += 1
        if results["successful_trades"] > 0:
            results["avg_profit"] = results["total_profit"] / results["successful_trades"]
            results["success_rate"] = (
                results["successful_trades"] / results["executed_trades"] * 100
            )
        else:
            results["avg_profit"] = Decimal(0)
            results["success_rate"] = 0
        results["total_profit"] = float(results["total_profit"])
        results["max_profit"] = float(results["max_profit"])
        results["min_profit"] = (
            float(results["min_profit"]) if results["min_profit"] < 999999 else 0
        )
        results["avg_profit"] = float(results["avg_profit"])
        results["total_volume"] = float(results["total_volume"])
        logger.info(f"Backtest complete: {results['success_rate']:.2f}% success rate")
        return results

    def _generate_fake_opportunities(self, count: int) -> List[Dict]:
        """Generate fake arbitrage opportunities for testing"""
        opportunities = []
        exchanges = list(self.exchanges.keys())
        symbols = ["BTCTRY", "ETHTRY", "USDTTRY"]
        for _ in range(count):
            symbol = np.random.choice(symbols)
            buy_exchange = np.random.choice(exchanges)
            sell_exchange = np.random.choice([e for e in exchanges if e != buy_exchange])
            if np.random.random() < 0.1:
                spread = np.random.uniform(0.5, 2.0)
            else:
                spread = np.random.uniform(-0.5, 0.5)
            base_price = {"BTCTRY": 2000000, "ETHTRY": 130000, "USDTTRY": 32}[symbol]
            buy_price = base_price * (1 - spread / 200)
            sell_price = base_price * (1 + spread / 200)
            amount = (
                np.random.uniform(0.001, 0.1) if "BTC" in symbol else np.random.uniform(0.01, 1)
            )
            buy_fee = float(self.exchanges[buy_exchange].taker_fee)
            sell_fee = float(self.exchanges[sell_exchange].taker_fee)
            gross_profit = amount * (sell_price - buy_price)
            fee_cost = amount * (buy_price * buy_fee + sell_price * sell_fee)
            net_profit = gross_profit - fee_cost
            opportunities.append(
                {
                    "buy_exchange": buy_exchange,
                    "sell_exchange": sell_exchange,
                    "symbol": symbol,
                    "buy_price": buy_price,
                    "sell_price": sell_price,
                    "amount": amount,
                    "spread": spread,
                    "gross_profit": gross_profit,
                    "net_profit": net_profit,
                    "slippage": np.random.uniform(0, 0.5),
                }
            )
        return opportunities
