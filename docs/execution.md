# Execution & Trading Documentation

## Overview
The execution layer handles live trading, paper trading, and risk management for Sofia V2.

## Components

### Execution Engine
- Order routing and management
- Smart order execution (TWAP, VWAP)
- Slippage estimation
- Fee calculation

### Paper Trading Engine
- Realistic market simulation
- Order fill modeling
- Latency simulation
- Portfolio tracking

### Risk Management
- Position sizing (Kelly, fixed, volatility-based)
- Stop-loss and take-profit orders
- Maximum drawdown limits
- Correlation-based exposure limits

## Usage

### Live Trading
```python
from src.core.engine import TradingEngine
from src.strategies.sma import SMAStrategy

engine = TradingEngine(mode="live")
engine.add_strategy(SMAStrategy(fast=20, slow=50))
engine.add_symbol("BTC/USDT")
engine.start()
```

### Paper Trading
```python
from src.core.paper_trading_engine import PaperTradingEngine

paper = PaperTradingEngine(initial_balance=10000)
paper.add_strategy("momentum", {"threshold": 0.02})
paper.run_session(duration_hours=24)
print(f"Final balance: ${paper.get_balance():.2f}")
```

### Risk Management
```python
from src.core.risk_manager import RiskManager

risk = RiskManager(
    max_position_size=0.1,  # 10% per position
    max_drawdown=0.2,       # 20% max drawdown
    stop_loss=0.02,         # 2% stop loss
    take_profit=0.05        # 5% take profit
)

# Check if trade is allowed
if risk.can_trade(symbol="BTC/USDT", size=1000, price=50000):
    # Execute trade
    pass
```

## Order Types

| Type | Description | Parameters |
|------|-------------|------------|
| Market | Immediate execution at best price | size |
| Limit | Execute at specific price or better | size, price |
| Stop | Trigger market order at price | size, stop_price |
| Stop-Limit | Trigger limit order at price | size, stop_price, limit_price |
| Trailing Stop | Dynamic stop following price | size, trail_percent |

## Position Management

### Entry Signals
- Technical indicators (RSI, MACD, Bollinger)
- Volume analysis
- Price action patterns
- Machine learning predictions

### Exit Signals
- Target profit reached
- Stop loss triggered
- Time-based exits
- Reversal signals

## Quick Verify

```powershell
# Test paper trading
python -c "from src.core.paper_trading_engine import PaperTradingEngine; p = PaperTradingEngine(); p.buy('BTC/USDT', 0.01); print(f'Position: {p.get_position('BTC/USDT')}')"

# Check risk limits
python -c "from src.core.risk_manager import RiskManager; r = RiskManager(); print('Risk OK' if r.check_health() else 'Risk FAIL')"

# Verify execution engine
python -c "from src.core.engine import TradingEngine; e = TradingEngine(mode='paper'); print('Engine OK' if e.status == 'ready' else 'Engine FAIL')"
```
