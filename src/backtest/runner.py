"""
Backtest runner with fees, slippage, and risk management
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, Tuple, Optional, List
import pandas as pd
import numpy as np
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class BacktestRunner:
    """Run backtests with realistic trading conditions"""
    
    def __init__(
        self,
        initial_capital: Decimal = Decimal("10000"),
        fee_rate: Decimal = Decimal("0.001"),
        slippage_rate: Decimal = Decimal("0.0005"),
        use_stops: bool = True
    ):
        self.initial_capital = initial_capital
        self.fee_rate = fee_rate
        self.slippage_rate = slippage_rate
        self.use_stops = use_stops
        
    def run_backtest(
        self,
        ohlcv: pd.DataFrame,
        signals: pd.Series,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        position_size: float = 1.0
    ) -> Tuple[Dict[str, Any], pd.DataFrame, pd.DataFrame, str]:
        """
        Run backtest on OHLCV data with signals
        
        Returns:
            metrics: Performance metrics dictionary
            equity_df: Equity curve DataFrame
            trades_df: Trades DataFrame
            logs_str: Log string
        """
        
        logs = []
        logs.append(f"Backtest started at {datetime.now()}")
        logs.append(f"Initial capital: {self.initial_capital}")
        logs.append(f"Fee rate: {self.fee_rate}, Slippage rate: {self.slippage_rate}")
        
        # Initialize tracking variables
        capital = Decimal(str(self.initial_capital))
        position = Decimal("0")
        entry_price = Decimal("0")
        trades = []
        equity_curve = []
        
        # Ensure signals align with OHLCV
        signals = signals.reindex(ohlcv.index, fill_value=0)
        
        for i, (timestamp, row) in enumerate(ohlcv.iterrows()):
            signal = signals.iloc[i] if i < len(signals) else 0
            price = Decimal(str(row['close']))
            
            # Apply slippage
            if signal > 0:  # Buy
                execution_price = price * (Decimal("1") + self.slippage_rate)
            elif signal < 0:  # Sell
                execution_price = price * (Decimal("1") - self.slippage_rate)
            else:
                execution_price = price
            
            # Check stop loss and take profit
            if position != 0 and self.use_stops:
                high = Decimal(str(row['high']))
                low = Decimal(str(row['low']))
                
                # Check stop loss
                if stop_loss and position > 0:
                    stop_price = entry_price * (Decimal("1") - Decimal(str(stop_loss)))
                    if low <= stop_price:
                        signal = -1  # Force sell
                        execution_price = stop_price
                        logs.append(f"Stop loss triggered at {timestamp}")
                
                # Check take profit
                if take_profit and position > 0:
                    target_price = entry_price * (Decimal("1") + Decimal(str(take_profit)))
                    if high >= target_price:
                        signal = -1  # Force sell
                        execution_price = target_price
                        logs.append(f"Take profit triggered at {timestamp}")
            
            # Execute trades
            if signal > 0 and position == 0:  # Buy signal
                # Calculate position size
                position_value = capital * Decimal(str(position_size))
                fee = position_value * self.fee_rate
                position = (position_value - fee) / execution_price
                capital = capital - position_value
                entry_price = execution_price
                
                trades.append({
                    'timestamp': timestamp,
                    'type': 'BUY',
                    'price': float(execution_price),
                    'quantity': float(position),
                    'fee': float(fee),
                    'capital': float(capital)
                })
                
            elif signal < 0 and position > 0:  # Sell signal
                # Sell position
                sell_value = position * execution_price
                fee = sell_value * self.fee_rate
                capital = capital + sell_value - fee
                
                # Calculate trade PnL
                pnl = (execution_price - entry_price) * position - fee
                pnl_pct = float(pnl / (entry_price * position) * 100)
                
                trades.append({
                    'timestamp': timestamp,
                    'type': 'SELL',
                    'price': float(execution_price),
                    'quantity': float(position),
                    'fee': float(fee),
                    'pnl': float(pnl),
                    'pnl_pct': pnl_pct,
                    'capital': float(capital)
                })
                
                position = Decimal("0")
                entry_price = Decimal("0")
            
            # Calculate current equity
            if position > 0:
                current_equity = capital + (position * price)
            else:
                current_equity = capital
            
            equity_curve.append({
                'timestamp': timestamp,
                'equity': float(current_equity),
                'capital': float(capital),
                'position_value': float(position * price) if position > 0 else 0
            })
        
        # Create DataFrames
        equity_df = pd.DataFrame(equity_curve)
        equity_df.set_index('timestamp', inplace=True)
        
        trades_df = pd.DataFrame(trades) if trades else pd.DataFrame()
        
        # Calculate metrics
        metrics = self.calculate_metrics(equity_df, trades_df, ohlcv)
        
        # Generate log string
        logs.append(f"Backtest completed at {datetime.now()}")
        logs.append(f"Total trades: {len(trades)}")
        logs.append(f"Final equity: {equity_df['equity'].iloc[-1] if not equity_df.empty else self.initial_capital}")
        logs_str = "\n".join(logs)
        
        return metrics, equity_df, trades_df, logs_str
    
    def calculate_metrics(
        self,
        equity_df: pd.DataFrame,
        trades_df: pd.DataFrame,
        ohlcv: pd.DataFrame
    ) -> Dict[str, Any]:
        """Calculate performance metrics"""
        
        if equity_df.empty:
            return self._empty_metrics()
        
        initial = float(self.initial_capital)
        final = equity_df['equity'].iloc[-1]
        
        # Total return
        total_return = (final - initial) / initial * 100
        
        # CAGR
        days = (equity_df.index[-1] - equity_df.index[0]).days
        years = max(days / 365.25, 0.001)  # Avoid division by zero
        cagr = (pow(final / initial, 1 / years) - 1) * 100 if years > 0 else 0
        
        # Sharpe ratio
        returns = equity_df['equity'].pct_change().dropna()
        if len(returns) > 1:
            sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
        else:
            sharpe = 0
        
        # Max drawdown
        rolling_max = equity_df['equity'].cummax()
        drawdown = (equity_df['equity'] - rolling_max) / rolling_max * 100
        max_drawdown = abs(drawdown.min())
        
        # Trade statistics
        if not trades_df.empty:
            sell_trades = trades_df[trades_df['type'] == 'SELL']
            if not sell_trades.empty:
                winning_trades = sell_trades[sell_trades['pnl'] > 0]
                win_rate = len(winning_trades) / len(sell_trades) * 100
                avg_trade = sell_trades['pnl_pct'].mean()
                avg_win = winning_trades['pnl_pct'].mean() if not winning_trades.empty else 0
                losing_trades = sell_trades[sell_trades['pnl'] <= 0]
                avg_loss = losing_trades['pnl_pct'].mean() if not losing_trades.empty else 0
                profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else 0
            else:
                win_rate = avg_trade = avg_win = avg_loss = profit_factor = 0
            
            total_trades = len(trades_df) // 2  # Buy + Sell pairs
        else:
            win_rate = avg_trade = avg_win = avg_loss = profit_factor = 0
            total_trades = 0
        
        # Exposure time
        if not trades_df.empty:
            buy_times = trades_df[trades_df['type'] == 'BUY']['timestamp']
            sell_times = trades_df[trades_df['type'] == 'SELL']['timestamp']
            
            exposure_time = 0
            for buy, sell in zip(buy_times, sell_times):
                exposure_time += (sell - buy).total_seconds()
            
            total_time = (equity_df.index[-1] - equity_df.index[0]).total_seconds()
            exposure_pct = exposure_time / total_time * 100 if total_time > 0 else 0
        else:
            exposure_pct = 0
        
        # MAR ratio (CAGR / MaxDD)
        mar_ratio = cagr / max_drawdown if max_drawdown > 0 else 0
        
        return {
            'total_return': round(total_return, 2),
            'cagr': round(cagr, 2),
            'sharpe_ratio': round(sharpe, 2),
            'max_drawdown': round(max_drawdown, 2),
            'win_rate': round(win_rate, 2),
            'avg_trade': round(avg_trade, 2),
            'avg_win': round(avg_win, 2),
            'avg_loss': round(avg_loss, 2),
            'profit_factor': round(profit_factor, 2),
            'total_trades': total_trades,
            'exposure_time': round(exposure_pct, 2),
            'mar_ratio': round(mar_ratio, 2),
            'initial_capital': initial,
            'final_capital': round(final, 2),
        }
    
    def _empty_metrics(self) -> Dict[str, Any]:
        """Return empty metrics structure"""
        return {
            'total_return': 0,
            'cagr': 0,
            'sharpe_ratio': 0,
            'max_drawdown': 0,
            'win_rate': 0,
            'avg_trade': 0,
            'avg_win': 0,
            'avg_loss': 0,
            'profit_factor': 0,
            'total_trades': 0,
            'exposure_time': 0,
            'mar_ratio': 0,
            'initial_capital': float(self.initial_capital),
            'final_capital': float(self.initial_capital),
        }