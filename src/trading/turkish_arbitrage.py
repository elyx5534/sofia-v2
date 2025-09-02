"""
Turkish Arbitrage Trading System
Arbitrage between Binance and BTCTurk with TL gateway
"""

import asyncio
import ccxt.async_support as ccxt
from decimal import Decimal
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class TurkishArbitrage:
    """Turkish Lira arbitrage between Binance and BTCTurk"""
    
    def __init__(self, paper_mode: bool = True):
        self.paper_mode = paper_mode
        self.logger = logging.getLogger(f"{__name__}.TurkishArbitrage")
        
        # Exchange connections
        self.binance = None
        self.btcturk = None
        
        # Arbitrage parameters
        self.min_profit_threshold = Decimal("0.3")  # 0.3% minimum profit
        self.tl_gateway_fee = Decimal("0.1")  # 0.1% TL transfer fee
        self.min_volume_usd = 50000  # Minimum liquidity
        self.max_position_size = Decimal("1000")  # Max $1000 per trade
        
        # State tracking
        self.opportunities = []
        self.executed_trades = []
        self.total_profit = Decimal("0")
        self._running = False
        self._monitor_task = None
        
    async def initialize(self):
        """Initialize exchange connections"""
        try:
            # Initialize Binance
            self.binance = ccxt.binance({
                'enableRateLimit': True,
                'options': {'defaultType': 'spot'}
            })
            
            # Initialize BTCTurk
            self.btcturk = ccxt.btcturk({
                'enableRateLimit': True
            })
            
            # Load markets
            await self.binance.load_markets()
            await self.btcturk.load_markets()
            
            self.logger.info("Turkish arbitrage system initialized")
            
        except Exception as e:
            self.logger.error(f"Initialization failed: {e}")
            raise
            
    async def start(self):
        """Start arbitrage monitoring"""
        if not self.binance or not self.btcturk:
            await self.initialize()
            
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        self.logger.info("Turkish arbitrage monitoring started")
        
    async def stop(self):
        """Stop arbitrage monitoring"""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
                
        # Close exchange connections
        if self.binance:
            await self.binance.close()
        if self.btcturk:
            await self.btcturk.close()
            
        self.logger.info("Turkish arbitrage monitoring stopped")
        
    async def _monitor_loop(self):
        """Main monitoring loop"""
        while self._running:
            try:
                # Find arbitrage opportunities
                opportunities = await self._find_opportunities()
                
                # Execute profitable trades
                for opp in opportunities:
                    if await self._should_execute(opp):
                        await self._execute_arbitrage(opp)
                        
                # Save state
                self._save_state()
                
                # Wait before next scan
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                self.logger.error(f"Monitor loop error: {e}")
                await asyncio.sleep(10)
                
    async def _find_opportunities(self) -> List[Dict]:
        """Find arbitrage opportunities between exchanges"""
        opportunities = []
        
        # Target pairs for arbitrage
        target_pairs = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT']
        
        for symbol in target_pairs:
            try:
                # Get prices from both exchanges
                binance_ticker = await self.binance.fetch_ticker(symbol)
                
                # Convert symbol for BTCTurk (uses TRY pairs)
                base = symbol.split('/')[0]
                btcturk_symbol = f"{base}/TRY"
                
                if btcturk_symbol in self.btcturk.markets:
                    btcturk_ticker = await self.btcturk.fetch_ticker(btcturk_symbol)
                    
                    # Get USDT/TRY rate
                    usdt_try = await self._get_usdt_try_rate()
                    
                    if usdt_try:
                        # Calculate arbitrage opportunity
                        opp = self._calculate_opportunity(
                            symbol,
                            binance_ticker,
                            btcturk_ticker,
                            usdt_try
                        )
                        
                        if opp and opp['profit_pct'] > float(self.min_profit_threshold):
                            opportunities.append(opp)
                            self.logger.info(f"Found opportunity: {symbol} - {opp['profit_pct']:.2f}% profit")
                            
            except Exception as e:
                self.logger.warning(f"Error checking {symbol}: {e}")
                
        self.opportunities = opportunities
        return opportunities
        
    async def _get_usdt_try_rate(self) -> Optional[float]:
        """Get USDT/TRY exchange rate"""
        try:
            # Try from Binance
            if 'USDT/TRY' in self.binance.markets:
                ticker = await self.binance.fetch_ticker('USDT/TRY')
                return ticker['last']
                
            # Fallback to fixed rate for simulation
            return 34.5  # Approximate USDT/TRY rate
            
        except Exception as e:
            self.logger.warning(f"Failed to get USDT/TRY rate: {e}")
            return 34.5  # Fallback rate
            
    def _calculate_opportunity(self, symbol: str, binance_ticker: Dict, 
                              btcturk_ticker: Dict, usdt_try: float) -> Optional[Dict]:
        """Calculate arbitrage opportunity"""
        try:
            # Binance price in USDT
            binance_bid = binance_ticker['bid']
            binance_ask = binance_ticker['ask']
            
            # BTCTurk price in TRY
            btcturk_bid = btcturk_ticker['bid']
            btcturk_ask = btcturk_ticker['ask']
            
            # Convert BTCTurk prices to USDT
            btcturk_bid_usdt = btcturk_bid / usdt_try
            btcturk_ask_usdt = btcturk_ask / usdt_try
            
            # Calculate both directions
            # Direction 1: Buy on Binance, Sell on BTCTurk
            profit1 = (btcturk_bid_usdt - binance_ask) / binance_ask * 100
            profit1_after_fees = profit1 - float(self.tl_gateway_fee) - 0.2  # Exchange fees
            
            # Direction 2: Buy on BTCTurk, Sell on Binance
            profit2 = (binance_bid - btcturk_ask_usdt) / btcturk_ask_usdt * 100
            profit2_after_fees = profit2 - float(self.tl_gateway_fee) - 0.2
            
            # Choose best direction
            if profit1_after_fees > profit2_after_fees:
                return {
                    'symbol': symbol,
                    'direction': 'binance_to_btcturk',
                    'buy_exchange': 'binance',
                    'sell_exchange': 'btcturk',
                    'buy_price': binance_ask,
                    'sell_price': btcturk_bid_usdt,
                    'profit_pct': profit1_after_fees,
                    'usdt_try_rate': usdt_try,
                    'timestamp': datetime.now().isoformat()
                }
            elif profit2_after_fees > 0:
                return {
                    'symbol': symbol,
                    'direction': 'btcturk_to_binance',
                    'buy_exchange': 'btcturk',
                    'sell_exchange': 'binance',
                    'buy_price': btcturk_ask_usdt,
                    'sell_price': binance_bid,
                    'profit_pct': profit2_after_fees,
                    'usdt_try_rate': usdt_try,
                    'timestamp': datetime.now().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Opportunity calculation error: {e}")
            
        return None
        
    async def _should_execute(self, opportunity: Dict) -> bool:
        """Check if opportunity should be executed"""
        # Check profit threshold
        if opportunity['profit_pct'] < float(self.min_profit_threshold):
            return False
            
        # Check liquidity (simplified for paper trading)
        symbol = opportunity['symbol']
        
        try:
            # Get order book depth
            if opportunity['buy_exchange'] == 'binance':
                orderbook = await self.binance.fetch_order_book(symbol, 5)
            else:
                base = symbol.split('/')[0]
                orderbook = await self.btcturk.fetch_order_book(f"{base}/TRY", 5)
                
            # Check if there's enough liquidity
            total_bid_volume = sum(bid[1] for bid in orderbook['bids'])
            total_ask_volume = sum(ask[1] for ask in orderbook['asks'])
            
            min_volume = float(self.max_position_size) / opportunity['buy_price']
            
            if total_bid_volume < min_volume or total_ask_volume < min_volume:
                self.logger.warning(f"Insufficient liquidity for {symbol}")
                return False
                
        except Exception as e:
            self.logger.error(f"Liquidity check failed: {e}")
            return False
            
        return True
        
    async def _execute_arbitrage(self, opportunity: Dict):
        """Execute arbitrage trade (paper or live)"""
        try:
            trade_size = float(self.max_position_size)
            quantity = trade_size / opportunity['buy_price']
            
            if self.paper_mode:
                # Simulate execution
                trade = {
                    'id': f"arb_{len(self.executed_trades)+1}",
                    'opportunity': opportunity,
                    'quantity': quantity,
                    'trade_size_usdt': trade_size,
                    'executed_at': datetime.now().isoformat(),
                    'status': 'filled',
                    'profit_usdt': trade_size * opportunity['profit_pct'] / 100
                }
                
                self.executed_trades.append(trade)
                self.total_profit += Decimal(str(trade['profit_usdt']))
                
                self.logger.info(
                    f"PAPER TRADE: {opportunity['symbol']} "
                    f"{opportunity['direction']} "
                    f"Profit: ${trade['profit_usdt']:.2f}"
                )
                
            else:
                # Live execution would go here
                self.logger.warning("Live trading not implemented yet")
                
        except Exception as e:
            self.logger.error(f"Execution failed: {e}")
            
    def _save_state(self):
        """Save current state to file"""
        state_file = Path("logs/turkish_arbitrage_state.json")
        state_file.parent.mkdir(exist_ok=True)
        
        state = {
            'opportunities': self.opportunities[-10:],  # Last 10 opportunities
            'executed_trades': self.executed_trades[-50:],  # Last 50 trades
            'total_profit': float(self.total_profit),
            'last_update': datetime.now().isoformat()
        }
        
        with open(state_file, 'w') as f:
            json.dump(state, f, indent=2)
            
    def get_status(self) -> Dict:
        """Get current arbitrage status"""
        return {
            'running': self._running,
            'mode': 'paper' if self.paper_mode else 'live',
            'opportunities_found': len(self.opportunities),
            'trades_executed': len(self.executed_trades),
            'total_profit_usdt': float(self.total_profit),
            'current_opportunities': self.opportunities[:5],  # Top 5
            'recent_trades': self.executed_trades[-5:]  # Last 5
        }


# Global instance
turkish_arbitrage = TurkishArbitrage(paper_mode=True)