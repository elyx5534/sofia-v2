# Turkish Arbitrage Documentation

## Overview
The Turkish Arbitrage module identifies and executes arbitrage opportunities between Turkish and international cryptocurrency exchanges.

## Arbitrage Types

### Cross-Exchange Arbitrage
Exploiting price differences for the same asset across different exchanges:
- Binance vs BTCTurk
- Paribu vs Binance TR
- BtcTurk vs Paribu

### Triangular Arbitrage
Trading through three currencies to profit from exchange rate discrepancies:
- USD/TRY → BTC/TRY → BTC/USD
- EUR/TRY → ETH/EUR → ETH/TRY

### Funding Rate Arbitrage
Profiting from funding rate differences in perpetual futures:
- Spot vs Perpetual
- Different exchange funding rates

## Implementation

### Scanner
```python
from src.strategies.turkish_arbitrage import TurkishArbitrageScanner

scanner = TurkishArbitrageScanner()
opportunities = scanner.scan_all_pairs()

for opp in opportunities:
    print(f"{opp.pair}: {opp.profit_pct:.2%} profit")
    print(f"  Buy on {opp.buy_exchange} at {opp.buy_price}")
    print(f"  Sell on {opp.sell_exchange} at {opp.sell_price}")
```

### Executor
```python
from src.trading.turkish_arbitrage import ArbitrageExecutor

executor = ArbitrageExecutor(
    min_profit_pct=0.5,  # 0.5% minimum profit
    max_exposure=10000,   # $10k maximum per trade
    exchanges=["binance", "btcturk", "paribu"]
)

executor.start_monitoring()
```

### Risk Management
```python
from src.trading.arb_scorer import ArbitrageScorer

scorer = ArbitrageScorer()
score = scorer.evaluate(
    profit_pct=1.2,
    volume_24h=1000000,
    spread_pct=0.1,
    execution_time_ms=500
)

if score > 0.7:  # High confidence
    # Execute arbitrage
    pass
```

## Exchange Integration

| Exchange | API Support | Avg Latency | Fee | Features |
|----------|-------------|-------------|-----|----------|
| Binance TR | REST + WS | 50ms | 0.1% | High liquidity |
| BTCTurk | REST + WS | 100ms | 0.2% | TRY pairs |
| Paribu | REST | 200ms | 0.2% | Local bank integration |
| Bitexen | REST | 150ms | 0.15% | Growing volume |

## Profit Calculation

```
Gross Profit = (Sell Price - Buy Price) * Amount
Fees = (Buy Fee + Sell Fee + Withdrawal Fee) * Amount
Net Profit = Gross Profit - Fees - Slippage
ROI = Net Profit / Capital Required
```

## Configuration

```python
ARBITRAGE_CONFIG = {
    "min_profit_pct": 0.3,      # Minimum 0.3% profit
    "max_slippage_pct": 0.1,     # Maximum 0.1% slippage
    "execution_timeout_ms": 1000, # 1 second timeout
    "rebalance_threshold": 0.7,   # Rebalance at 70% imbalance
    "exchanges": {
        "binance": {"enabled": True, "api_key": "..."},
        "btcturk": {"enabled": True, "api_key": "..."},
        "paribu": {"enabled": False}  # Disabled
    }
}
```

## Quick Verify

```powershell
# Scan for opportunities
python -c "from src.strategies.turkish_arbitrage import find_arbitrage; opps = find_arbitrage(); print(f'Found {len(opps)} opportunities')"

# Test exchange connections
python -c "from src.exchanges.manager import ExchangeManager; m = ExchangeManager(); print(m.test_all_connections())"

# Calculate profit for sample trade
python -c "buy=50000; sell=50500; amount=0.1; fee=0.002; profit=(sell-buy)*amount*(1-fee*2); print(f'Profit: ${profit:.2f}')"
```
