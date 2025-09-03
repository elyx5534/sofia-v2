"""
Turkish Lira Multi-Coin Trading Bot
100K TL başlangıç bakiyesi ile yüzlerce coin destekli bot
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Dict, List

from .strategies import RiskManager, StrategyType, TradingStrategies

logger = logging.getLogger(__name__)


class BotStatus(Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    ERROR = "error"


class CoinPosition:
    """Track position for a single coin"""

    def __init__(self, symbol: str):
        self.symbol = symbol
        self.amount = 0.0
        self.entry_price_try = 0.0
        self.current_price_try = 0.0
        self.highest_price_try = 0.0
        self.unrealized_pnl_try = 0.0
        self.realized_pnl_try = 0.0
        self.trades = []

    def update_pnl(self, current_price_usd: float, usd_to_try: float = 34.5):
        """Update P&L calculations in TRY"""
        self.current_price_try = current_price_usd * usd_to_try
        if self.amount > 0:
            self.unrealized_pnl_try = (self.current_price_try - self.entry_price_try) * self.amount
            self.highest_price_try = max(self.current_price_try, self.highest_price_try)


class TurkishTradingBot:
    """Advanced Turkish Lira trading bot supporting hundreds of coins"""

    POPULAR_COINS = [
        "BTC/USDT",
        "ETH/USDT",
        "BNB/USDT",
        "SOL/USDT",
        "XRP/USDT",
        "ADA/USDT",
        "AVAX/USDT",
        "DOGE/USDT",
        "DOT/USDT",
        "MATIC/USDT",
        "SHIB/USDT",
        "TRX/USDT",
        "UNI/USDT",
        "ATOM/USDT",
        "LINK/USDT",
        "LTC/USDT",
        "BCH/USDT",
        "XLM/USDT",
        "ALGO/USDT",
        "VET/USDT",
        "FIL/USDT",
        "EOS/USDT",
        "MANA/USDT",
        "SAND/USDT",
        "AXS/USDT",
        "FTM/USDT",
        "NEAR/USDT",
        "RUNE/USDT",
        "GALA/USDT",
        "ENJ/USDT",
        "APE/USDT",
        "GMT/USDT",
        "WAVES/USDT",
        "JASMY/USDT",
        "PEOPLE/USDT",
    ]
    ALL_COINS = POPULAR_COINS + [
        "CHZ/USDT",
        "THETA/USDT",
        "ONE/USDT",
        "ZIL/USDT",
        "IOTA/USDT",
        "XTZ/USDT",
        "ETC/USDT",
        "NEO/USDT",
        "WAVES/USDT",
        "MKR/USDT",
        "COMP/USDT",
        "SNX/USDT",
        "SUSHI/USDT",
        "YFI/USDT",
        "UMA/USDT",
        "REN/USDT",
        "BAL/USDT",
        "CRV/USDT",
        "INCH/USDT",
        "RSR/USDT",
        "AAVE/USDT",
        "ANKR/USDT",
        "BADGER/USDT",
        "BAND/USDT",
        "BNT/USDT",
        "CELR/USDT",
        "COTI/USDT",
        "CREAM/USDT",
        "CRO/USDT",
        "CVX/USDT",
        "DAO/USDT",
        "DEXE/USDT",
        "DODO/USDT",
        "DYDX/USDT",
        "FARM/USDT",
        "ALICE/USDT",
        "ATA/USDT",
        "ATLAS/USDT",
        "AXS/USDT",
        "BAKE/USDT",
        "BETA/USDT",
        "BICO/USDT",
        "BURGER/USDT",
        "C98/USDT",
        "CAKE/USDT",
        "CELO/USDT",
        "CELR/USDT",
        "CFX/USDT",
        "CHR/USDT",
        "CITY/USDT",
        "PEPE/USDT",
        "FLOKI/USDT",
        "BONK/USDT",
        "WIF/USDT",
        "BOME/USDT",
        "MEME/USDT",
        "LADYS/USDT",
        "BABYDOGE/USDT",
        "ELON/USDT",
        "AKITA/USDT",
        "KISHU/USDT",
        "SAITAMA/USDT",
        "VOLT/USDT",
        "DOBO/USDT",
        "SAMO/USDT",
        "ARB/USDT",
        "OP/USDT",
        "MATIC/USDT",
        "AVAX/USDT",
        "FTM/USDT",
        "ONE/USDT",
        "CELO/USDT",
        "KAVA/USDT",
        "ROSE/USDT",
        "OASIS/USDT",
        "GLMR/USDT",
        "ASTR/USDT",
        "KLAY/USDT",
        "WAXP/USDT",
        "ICX/USDT",
        "FET/USDT",
        "OCEAN/USDT",
        "AGIX/USDT",
        "NMR/USDT",
        "GRT/USDT",
        "RNDR/USDT",
        "AI/USDT",
        "PHB/USDT",
        "CTXC/USDT",
        "MDT/USDT",
        "FIL/USDT",
        "AR/USDT",
        "STORJ/USDT",
        "SC/USDT",
        "BTT/USDT",
        "ANKR/USDT",
        "BLZ/USDT",
        "TFUEL/USDT",
        "DGB/USDT",
        "RLC/USDT",
        "XMR/USDT",
        "ZEC/USDT",
        "DASH/USDT",
        "DCR/USDT",
        "ZEN/USDT",
        "BEAM/USDT",
        "GRIN/USDT",
        "XVG/USDT",
        "NAV/USDT",
        "PIVX/USDT",
        "BNB/USDT",
        "OKB/USDT",
        "HT/USDT",
        "FTT/USDT",
        "LEO/USDT",
        "KCS/USDT",
        "CRO/USDT",
        "MX/USDT",
        "GT/USDT",
        "WOO/USDT",
        "LINK/USDT",
        "BAND/USDT",
        "API3/USDT",
        "TRB/USDT",
        "DIA/USDT",
        "NEST/USDT",
        "DOS/USDT",
        "OGN/USDT",
        "TORN/USDT",
        "UMA/USDT",
        "APE/USDT",
        "MANA/USDT",
        "SAND/USDT",
        "ENJ/USDT",
        "CHZ/USDT",
        "FLOW/USDT",
        "GALA/USDT",
        "THETA/USDT",
        "WAXP/USDT",
        "ILV/USDT",
        "JTO/USDT",
        "PYTH/USDT",
        "SEI/USDT",
        "CYBER/USDT",
        "ORDI/USDT",
        "BEAMX/USDT",
        "MANTA/USDT",
        "ALT/USDT",
        "JUP/USDT",
        "DYM/USDT",
        "STRK/USDT",
        "PIXEL/USDT",
        "PORTAL/USDT",
        "PDA/USDT",
        "XAI/USDT",
        "ETHFI/USDT",
        "ENA/USDT",
        "OMNI/USDT",
        "REZ/USDT",
        "BB/USDT",
        "NOT/USDT",
        "IO/USDT",
        "ZK/USDT",
        "LISTA/USDT",
        "ZRO/USDT",
        "ACH/USDT",
        "ADX/USDT",
        "AERGO/USDT",
        "AGI/USDT",
        "AGLD/USDT",
        "AKRO/USDT",
        "ALCX/USDT",
        "ALPACA/USDT",
        "ALPHA/USDT",
        "AMB/USDT",
        "AMP/USDT",
        "ANCT/USDT",
        "ANY/USDT",
        "APM/USDT",
        "ARDR/USDT",
        "ARPA/USDT",
        "ASR/USDT",
        "AST/USDT",
        "ASTR/USDT",
        "ATM/USDT",
        "AUCTION/USDT",
        "AUDIO/USDT",
        "AUTO/USDT",
        "AVA/USDT",
        "AXS/USDT",
        "BAR/USDT",
        "BAT/USDT",
        "BCD/USDT",
        "BEAM/USDT",
        "BEL/USDT",
        "BGBP/USDT",
        "BIFI/USDT",
        "BLCT/USDT",
        "BLZ/USDT",
        "BNX/USDT",
        "BOBA/USDT",
        "BOND/USDT",
        "BORG/USDT",
        "BOSON/USDT",
        "BOUNTY/USDT",
        "BRWL/USDT",
        "BSW/USDT",
        "BTCDOM/USDT",
        "BTCST/USDT",
        "BTG/USDT",
        "BTS/USDT",
        "BTT/USDT",
        "BUILD/USDT",
        "BUL/USDT",
        "BULL/USDT",
        "BUSD/USDT",
        "BUX/USDT",
        "BXH/USDT",
        "BZZ/USDT",
        "CANTO/USDT",
    ]

    def __init__(self, initial_balance_try: float = 100000.0):
        self.status = BotStatus.STOPPED
        self.balance_try = initial_balance_try
        self.initial_balance_try = initial_balance_try
        self.usd_to_try = 34.5
        self.positions = {}
        self.active_coins = set()
        initial_coins = self.POPULAR_COINS[:20] + [
            "PEPE/USDT",
            "FLOKI/USDT",
            "BONK/USDT",
            "WIF/USDT",
            "MEME/USDT",
            "ARB/USDT",
            "OP/USDT",
            "INJ/USDT",
            "SEI/USDT",
            "JTO/USDT",
            "FET/USDT",
            "RNDR/USDT",
            "GRT/USDT",
            "OCEAN/USDT",
            "AGIX/USDT",
            "IMX/USDT",
            "BLUR/USDT",
            "MAGIC/USDT",
            "HIGH/USDT",
            "HOOK/USDT",
        ]
        self.watchlist = set(initial_coins[:50])
        self.strategy_type = StrategyType.COMBINED
        self.risk_manager = RiskManager(
            stop_loss_pct=0.05,
            take_profit_pct=0.03,
            trailing_stop_pct=0.025,
            max_position_size=0.02,
        )
        self.strategies = TradingStrategies()
        self.all_trades = []
        self.indicators = {}
        self.daily_pnl = 0.0
        self.weekly_pnl = 0.0
        self.monthly_pnl = 0.0
        self.best_trade = None
        self.worst_trade = None
        self.min_volume_usd = 100000
        self.max_coins_to_trade = 50
        self.min_price_usd = 1e-07
        logger.info(f"Turkish Trading Bot initialized with {self.initial_balance_try:,.2f} TRY")

    def add_coins_to_watchlist(self, symbols: List[str]):
        """Add multiple coins to watchlist"""
        for symbol in symbols:
            if symbol in self.ALL_COINS:
                self.watchlist.add(symbol)
                logger.info(f"Added {symbol} to watchlist")
        if len(self.watchlist) > 50:
            self.watchlist = set(list(self.watchlist)[:50])

    def scan_for_opportunities(self) -> List[str]:
        """Scan all coins for trading opportunities"""
        opportunities = []
        for symbol in self.watchlist:
            if symbol in self.indicators:
                indicators = self.indicators[symbol]
                if self.strategy_type == StrategyType.RSI:
                    rsi = indicators.get("rsi", 50)
                    if rsi < 25 or rsi > 75:
                        opportunities.append(symbol)
                elif self.strategy_type == StrategyType.COMBINED:
                    score = 0
                    if indicators.get("rsi", 50) < 30:
                        score += 1
                    if indicators.get("rsi", 50) > 70:
                        score -= 1
                    if indicators.get("macd", {}).get("histogram", 0) > 0:
                        score += 1
                    if indicators.get("bollinger", {}).get("percent_b", 0.5) < 0.2:
                        score += 1
                    if abs(score) >= 2:
                        opportunities.append(symbol)
        return opportunities[: self.max_coins_to_trade]

    def calculate_position_size_try(self, confidence: str = "medium") -> float:
        """Calculate position size in TRY based on risk"""
        base_size_try = self.balance_try * self.risk_manager.max_position_size
        if confidence == "high":
            return base_size_try
        elif confidence == "medium":
            return base_size_try * 0.7
        else:
            return base_size_try * 0.4

    def execute_trade(
        self, symbol: str, signal: str, price_usd: float, confidence: str = "medium"
    ) -> Dict:
        """Execute a paper trade in TRY"""
        if symbol not in self.positions:
            self.positions[symbol] = CoinPosition(symbol)
        position = self.positions[symbol]
        price_try = price_usd * self.usd_to_try
        trade = {
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "signal": signal,
            "price_usd": price_usd,
            "price_try": price_try,
            "amount": 0,
            "value_try": 0,
            "balance_after_try": self.balance_try,
            "pnl_try": 0,
            "confidence": confidence,
            "indicators": self.indicators.get(symbol, {}),
        }
        if signal == "BUY" and position.amount == 0:
            trade_value_try = self.calculate_position_size_try(confidence)
            trade_value_try = min(trade_value_try, self.balance_try * 0.95)
            if trade_value_try > 1000:
                amount = trade_value_try / price_try
                self.balance_try -= trade_value_try
                position.amount = amount
                position.entry_price_try = price_try
                position.current_price_try = price_try
                position.highest_price_try = price_try
                trade["amount"] = amount
                trade["value_try"] = trade_value_try
                trade["balance_after_try"] = self.balance_try
                self.active_coins.add(symbol)
                logger.info(
                    f"BUY {symbol}: {amount:.6f} @ {price_try:.2f} TRY (Confidence: {confidence})"
                )
        elif signal == "SELL" and position.amount > 0:
            trade_value_try = position.amount * price_try
            self.balance_try += trade_value_try
            trade["pnl_try"] = trade_value_try - position.amount * position.entry_price_try
            position.realized_pnl_try += trade["pnl_try"]
            self.daily_pnl += trade["pnl_try"]
            if not self.best_trade or trade["pnl_try"] > self.best_trade["pnl_try"]:
                self.best_trade = trade
            if not self.worst_trade or trade["pnl_try"] < self.worst_trade["pnl_try"]:
                self.worst_trade = trade
            trade["amount"] = position.amount
            trade["value_try"] = trade_value_try
            trade["balance_after_try"] = self.balance_try
            logger.info(
                f"SELL {symbol}: {position.amount:.6f} @ {price_try:.2f} TRY | P&L: {trade['pnl_try']:+,.2f} TRY"
            )
            position.amount = 0
            position.entry_price_try = 0
            position.unrealized_pnl_try = 0
            self.active_coins.discard(symbol)
        if position.amount > 0:
            self._check_risk_management(symbol, position, price_try, trade)
        if trade["amount"] > 0:
            position.trades.append(trade)
            self.all_trades.append(trade)
        return trade

    def _check_risk_management(
        self, symbol: str, position: CoinPosition, price_try: float, trade: Dict
    ):
        """Check and apply risk management rules"""
        price_usd = price_try / self.usd_to_try
        if self.risk_manager.should_stop_loss(position.entry_price_try, price_try):
            logger.warning(f"STOP LOSS triggered for {symbol} at {price_try:.2f} TRY")
            self.execute_trade(symbol, "SELL", price_usd, "risk_management")
        elif self.risk_manager.should_take_profit(position.entry_price_try, price_try):
            logger.info(f"TAKE PROFIT triggered for {symbol} at {price_try:.2f} TRY")
            self.execute_trade(symbol, "SELL", price_usd, "risk_management")
        else:
            entry_price_usd = position.entry_price_try / self.usd_to_try
            highest_price_usd = position.highest_price_try / self.usd_to_try
            trailing_stop_usd = self.risk_manager.update_trailing_stop(
                symbol, entry_price_usd, price_usd, highest_price_usd
            )
            if self.risk_manager.should_trailing_stop(symbol, price_usd):
                logger.info(f"TRAILING STOP triggered for {symbol} at {price_try:.2f} TRY")
                self.execute_trade(symbol, "SELL", price_usd, "risk_management")

    def get_portfolio_stats(self) -> Dict:
        """Get complete portfolio statistics in TRY"""
        total_position_value_try = sum(
            pos.amount * pos.current_price_try for pos in self.positions.values()
        )
        total_value_try = self.balance_try + total_position_value_try
        total_unrealized_pnl_try = sum(pos.unrealized_pnl_try for pos in self.positions.values())
        total_realized_pnl_try = sum(pos.realized_pnl_try for pos in self.positions.values())
        total_pnl_try = total_value_try - self.initial_balance_try
        pnl_percent = total_pnl_try / self.initial_balance_try * 100
        winning_trades = [t for t in self.all_trades if t.get("pnl_try", 0) > 0]
        losing_trades = [t for t in self.all_trades if t.get("pnl_try", 0) < 0]
        positions_data = {}
        for symbol, pos in self.positions.items():
            if pos.amount > 0:
                positions_data[symbol] = {
                    "amount": round(pos.amount, 6),
                    "entry_price_try": round(pos.entry_price_try, 2),
                    "current_price_try": round(pos.current_price_try, 2),
                    "unrealized_pnl_try": round(pos.unrealized_pnl_try, 2),
                    "realized_pnl_try": round(pos.realized_pnl_try, 2),
                    "value_try": round(pos.amount * pos.current_price_try, 2),
                }
        return {
            "status": self.status.value,
            "strategy": self.strategy_type.value,
            "currency": "TRY",
            "usd_to_try": self.usd_to_try,
            "balance_try": round(self.balance_try, 2),
            "total_value_try": round(total_value_try, 2),
            "initial_balance_try": self.initial_balance_try,
            "total_pnl_try": round(total_pnl_try, 2),
            "pnl_percent": round(pnl_percent, 2),
            "unrealized_pnl_try": round(total_unrealized_pnl_try, 2),
            "realized_pnl_try": round(total_realized_pnl_try, 2),
            "daily_pnl_try": round(self.daily_pnl, 2),
            "total_trades": len(self.all_trades),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": (
                round(len(winning_trades) / len(self.all_trades) * 100, 1) if self.all_trades else 0
            ),
            "active_coins": list(self.active_coins),
            "watchlist_count": len(self.watchlist),
            "positions": positions_data,
            "recent_trades": self.all_trades[-10:],
            "best_trade": self.best_trade,
            "worst_trade": self.worst_trade,
            "risk_settings": {
                "stop_loss": f"{self.risk_manager.stop_loss_pct * 100}%",
                "take_profit": f"{self.risk_manager.take_profit_pct * 100}%",
                "trailing_stop": f"{self.risk_manager.trailing_stop_pct * 100}%",
                "max_position": f"{self.risk_manager.max_position_size * 100}%",
            },
        }

    def start(self):
        """Start the bot"""
        self.status = BotStatus.RUNNING
        logger.info(f"Turkish Trading Bot started with {len(self.watchlist)} coins in watchlist")

    def stop(self):
        """Stop the bot"""
        self.status = BotStatus.STOPPED
        logger.info("Turkish Trading Bot stopped")

    def reset(self):
        """Reset bot to initial state"""
        self.balance_try = self.initial_balance_try
        self.positions = {}
        self.active_coins = set()
        self.all_trades = []
        self.indicators = {}
        self.daily_pnl = 0.0
        self.best_trade = None
        self.worst_trade = None
        self.status = BotStatus.STOPPED
        logger.info("Bot reset to initial state")
