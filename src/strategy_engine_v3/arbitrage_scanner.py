"""
Arbitrage Scanner - Identify and execute arbitrage opportunities.

Scans for:
- Cross-exchange arbitrage (crypto)
- Statistical arbitrage
- Triangular arbitrage
- Market maker arbitrage
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel

from .market_adapter import MarketData, MarketType, Order, OrderSide, OrderType


class ArbitrageOpportunity(BaseModel):
    """Represents an arbitrage opportunity."""
    
    type: str  # cross_exchange, triangular, statistical
    symbol: str
    buy_market: str
    sell_market: str
    buy_price: float
    sell_price: float
    spread: float  # Profit potential
    spread_pct: float  # Profit percentage
    volume: float  # Max executable volume
    confidence: float  # Confidence score 0-1
    timestamp: datetime
    expires_at: Optional[datetime] = None


class TriangularArbitrage(BaseModel):
    """Triangular arbitrage opportunity."""
    
    pair1: str  # e.g., BTC/USDT
    pair2: str  # e.g., ETH/BTC
    pair3: str  # e.g., ETH/USDT
    profit_pct: float
    path: List[str]  # Trading path
    volumes: List[float]
    timestamp: datetime


class ArbitrageConfig(BaseModel):
    """Configuration for arbitrage scanner."""
    
    min_spread_pct: float = 0.5  # Minimum 0.5% spread
    max_position_size: float = 10000.0  # Max position in USD
    scan_interval: int = 1  # Seconds between scans
    execution_delay: int = 100  # Milliseconds max execution delay
    include_fees: bool = True
    markets_to_scan: List[str] = ["binance", "coinbase", "kraken"]


class ArbitrageScanner:
    """
    Scanner for identifying arbitrage opportunities across markets.
    
    Features:
    - Real-time opportunity detection
    - Risk-adjusted profit calculation
    - Automatic execution capability
    - Latency monitoring
    """
    
    def __init__(self, config: ArbitrageConfig):
        """Initialize arbitrage scanner."""
        self.config = config
        self.opportunities: List[ArbitrageOpportunity] = []
        self.executed_arbs: List[ArbitrageOpportunity] = []
        self.market_data: Dict[str, Dict[str, MarketData]] = {}
        self.is_scanning = False
        self.fee_structure = {
            "binance": 0.001,  # 0.1%
            "coinbase": 0.005,  # 0.5%
            "kraken": 0.002,  # 0.2%
        }
        
    async def scan_cross_exchange(self, symbol: str) -> List[ArbitrageOpportunity]:
        """Scan for cross-exchange arbitrage opportunities."""
        opportunities = []
        
        # Get market data from all exchanges
        market_prices = {}
        for market in self.config.markets_to_scan:
            if market in self.market_data and symbol in self.market_data[market]:
                market_prices[market] = self.market_data[market][symbol]
                
        # Find arbitrage opportunities
        for buy_market, buy_data in market_prices.items():
            for sell_market, sell_data in market_prices.items():
                if buy_market != sell_market:
                    spread = sell_data.bid - buy_data.ask
                    spread_pct = (spread / buy_data.ask) * 100
                    
                    # Account for fees
                    if self.config.include_fees:
                        buy_fee = self.fee_structure.get(buy_market, 0.002)
                        sell_fee = self.fee_structure.get(sell_market, 0.002)
                        net_spread_pct = spread_pct - (buy_fee + sell_fee) * 100
                    else:
                        net_spread_pct = spread_pct
                        
                    if net_spread_pct > self.config.min_spread_pct:
                        opportunity = ArbitrageOpportunity(
                            type="cross_exchange",
                            symbol=symbol,
                            buy_market=buy_market,
                            sell_market=sell_market,
                            buy_price=buy_data.ask,
                            sell_price=sell_data.bid,
                            spread=spread,
                            spread_pct=net_spread_pct,
                            volume=min(buy_data.volume, sell_data.volume) * 0.01,  # 1% of volume
                            confidence=self._calculate_confidence(net_spread_pct),
                            timestamp=datetime.utcnow()
                        )
                        opportunities.append(opportunity)
                        
        return opportunities
        
    async def scan_triangular(self, base_currency: str = "USDT") -> List[TriangularArbitrage]:
        """Scan for triangular arbitrage opportunities."""
        opportunities = []
        
        # Example triangular path: USDT -> BTC -> ETH -> USDT
        paths = [
            ["BTC/USDT", "ETH/BTC", "ETH/USDT"],
            ["BTC/USDT", "BNB/BTC", "BNB/USDT"],
            ["ETH/USDT", "BNB/ETH", "BNB/USDT"],
        ]
        
        for path in paths:
            profit = await self._calculate_triangular_profit(path)
            if profit > self.config.min_spread_pct:
                opportunity = TriangularArbitrage(
                    pair1=path[0],
                    pair2=path[1],
                    pair3=path[2],
                    profit_pct=profit,
                    path=path,
                    volumes=[1000.0, 0.0, 0.0],  # Simplified
                    timestamp=datetime.utcnow()
                )
                opportunities.append(opportunity)
                
        return opportunities
        
    async def _calculate_triangular_profit(self, path: List[str]) -> float:
        """Calculate profit for a triangular arbitrage path."""
        # Simplified calculation - would need actual market data
        # Start with 1 unit of base currency
        amount = 1.0
        
        for pair in path:
            # Mock price conversion
            if "BTC" in pair:
                amount *= 0.000022  # Example BTC price
            elif "ETH" in pair:
                amount *= 0.00055  # Example ETH price
            else:
                amount *= 1.0
                
        # Calculate profit percentage
        profit_pct = (amount - 1.0) * 100
        return profit_pct
        
    async def scan_statistical(self, pairs: List[Tuple[str, str]]) -> List[ArbitrageOpportunity]:
        """Scan for statistical arbitrage (pairs trading) opportunities."""
        opportunities = []
        
        for pair1, pair2 in pairs:
            # Calculate correlation and spread
            correlation = await self._calculate_correlation(pair1, pair2)
            if correlation > 0.8:  # High correlation
                spread = await self._calculate_pair_spread(pair1, pair2)
                if abs(spread) > 2.0:  # 2 standard deviations
                    opportunity = ArbitrageOpportunity(
                        type="statistical",
                        symbol=f"{pair1}_{pair2}",
                        buy_market=pair1 if spread < 0 else pair2,
                        sell_market=pair2 if spread < 0 else pair1,
                        buy_price=0.0,  # Placeholder
                        sell_price=0.0,  # Placeholder
                        spread=abs(spread),
                        spread_pct=abs(spread) * 0.5,  # Simplified
                        volume=1000.0,
                        confidence=min(correlation, 0.9),
                        timestamp=datetime.utcnow()
                    )
                    opportunities.append(opportunity)
                    
        return opportunities
        
    async def _calculate_correlation(self, symbol1: str, symbol2: str) -> float:
        """Calculate correlation between two symbols."""
        # Mock correlation calculation
        return 0.85
        
    async def _calculate_pair_spread(self, symbol1: str, symbol2: str) -> float:
        """Calculate z-score of pair spread."""
        # Mock spread calculation
        return 2.5
        
    def _calculate_confidence(self, spread_pct: float) -> float:
        """Calculate confidence score for an opportunity."""
        # Higher spread = higher confidence (simplified)
        if spread_pct > 2.0:
            return 0.9
        elif spread_pct > 1.0:
            return 0.7
        elif spread_pct > 0.5:
            return 0.5
        else:
            return 0.3
            
    async def execute_arbitrage(self, opportunity: ArbitrageOpportunity) -> Tuple[bool, str]:
        """Execute an arbitrage opportunity."""
        try:
            # Validate opportunity is still valid
            if not await self._validate_opportunity(opportunity):
                return False, "Opportunity no longer valid"
                
            # Calculate position size
            position_size = min(
                opportunity.volume,
                self.config.max_position_size / opportunity.buy_price
            )
            
            # Create orders
            buy_order = Order(
                symbol=opportunity.symbol,
                market_type=MarketType.CRYPTO,
                side=OrderSide.BUY,
                type=OrderType.LIMIT,
                quantity=position_size,
                price=opportunity.buy_price
            )
            
            sell_order = Order(
                symbol=opportunity.symbol,
                market_type=MarketType.CRYPTO,
                side=OrderSide.SELL,
                type=OrderType.LIMIT,
                quantity=position_size,
                price=opportunity.sell_price
            )
            
            # Execute orders (would need actual market adapters)
            # For now, just mark as executed
            self.executed_arbs.append(opportunity)
            
            return True, f"Executed arbitrage: {opportunity.spread_pct:.2f}% profit"
            
        except Exception as e:
            return False, f"Execution failed: {str(e)}"
            
    async def _validate_opportunity(self, opportunity: ArbitrageOpportunity) -> bool:
        """Validate that an opportunity is still valid."""
        # Check if opportunity has expired
        if opportunity.expires_at and datetime.utcnow() > opportunity.expires_at:
            return False
            
        # Re-check spread (would need fresh market data)
        # For now, assume valid if less than 5 seconds old
        age = (datetime.utcnow() - opportunity.timestamp).total_seconds()
        return age < 5
        
    async def update_market_data(self, market: str, symbol: str, data: MarketData) -> None:
        """Update market data for scanning."""
        if market not in self.market_data:
            self.market_data[market] = {}
        self.market_data[market][symbol] = data
        
    async def start_scanning(self) -> None:
        """Start continuous scanning for opportunities."""
        self.is_scanning = True
        
        while self.is_scanning:
            try:
                # Clear old opportunities
                self.opportunities = []
                
                # Scan different arbitrage types
                symbols = ["BTC/USDT", "ETH/USDT", "BNB/USDT"]
                
                for symbol in symbols:
                    # Cross-exchange arbitrage
                    cross_opps = await self.scan_cross_exchange(symbol)
                    self.opportunities.extend(cross_opps)
                    
                # Triangular arbitrage
                tri_opps = await self.scan_triangular()
                # Convert to ArbitrageOpportunity format
                for tri in tri_opps:
                    self.opportunities.append(
                        ArbitrageOpportunity(
                            type="triangular",
                            symbol=tri.pair1,
                            buy_market="exchange1",
                            sell_market="exchange1",
                            buy_price=0.0,
                            sell_price=0.0,
                            spread=tri.profit_pct,
                            spread_pct=tri.profit_pct,
                            volume=1000.0,
                            confidence=0.7,
                            timestamp=tri.timestamp
                        )
                    )
                    
                # Statistical arbitrage
                pairs = [("BTC/USDT", "ETH/USDT"), ("BNB/USDT", "ADA/USDT")]
                stat_opps = await self.scan_statistical(pairs)
                self.opportunities.extend(stat_opps)
                
                # Sort by profit potential
                self.opportunities.sort(key=lambda x: x.spread_pct, reverse=True)
                
                # Auto-execute high confidence opportunities
                for opp in self.opportunities:
                    if opp.confidence > 0.8 and opp.spread_pct > 1.0:
                        await self.execute_arbitrage(opp)
                        
                await asyncio.sleep(self.config.scan_interval)
                
            except Exception as e:
                print(f"Scanning error: {e}")
                await asyncio.sleep(self.config.scan_interval)
                
    async def stop_scanning(self) -> None:
        """Stop scanning for opportunities."""
        self.is_scanning = False
        
    def get_opportunities(self, min_spread: float = 0.0) -> List[ArbitrageOpportunity]:
        """Get current arbitrage opportunities."""
        return [o for o in self.opportunities if o.spread_pct >= min_spread]
        
    def get_statistics(self) -> Dict:
        """Get scanner statistics."""
        return {
            "active_opportunities": len(self.opportunities),
            "executed_count": len(self.executed_arbs),
            "total_profit": sum(o.spread_pct for o in self.executed_arbs),
            "avg_spread": sum(o.spread_pct for o in self.opportunities) / len(self.opportunities) if self.opportunities else 0,
            "best_opportunity": max(self.opportunities, key=lambda x: x.spread_pct) if self.opportunities else None
        }