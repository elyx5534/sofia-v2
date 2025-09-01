# Paper Trading P&L Proof System

## Quick Start

### Option 1: Using Makefile (Recommended)
```bash
# Run 30-minute paper trading session with P&L proof
make proof-today
```

### Option 2: Direct Python
```bash
# Run 30-minute session
python tools/run_paper_session.py

# Run custom duration (e.g., 5 minutes for testing)
python tools/run_paper_session.py 5
```

### Option 3: Complete Demo with API
```bash
# Start API and run 5-minute demo
python start_paper_demo.py
```

## What It Does

The paper trading system:
1. **Simulates real trading** with virtual $1000 USDT
2. **Executes Grid Monster strategy** on BTC/USDT and SOL/USDT
3. **Logs every trade** with timestamp and price source
4. **Displays P&L proof** in real-time and at session end

## P&L Output Format

```
📊 P&L PROOF - TRADING SUMMARY
============================================================

💰 CAPITAL:
  Initial Capital:     $   1000.00 USDT
  Final Capital:       $   1003.45 USDT
              Profit: $      3.45 USDT
           Return %:      +0.35%

📈 TRADING ACTIVITY:
  Total Trades:                15
  Active Grids:                 2
  Successful Grids:             2
  Failed Grids:                 0
  Success Rate:            100.0%

💹 P&L BREAKDOWN:
  Realized P&L:        $      3.45 USDT
  Unrealized P&L:      $      0.00 USDT
  Total P&L:           $      3.45 USDT
```

## Output Files

After each session:
- `logs/paper_audit.log` - Detailed trade-by-trade audit log
- `logs/paper_session_summary.json` - Session P&L summary

## Configuration

Edit `config/strategies/grid_monster.yaml`:
```yaml
symbols:
  - "BTC/USDT"
  - "SOL/USDT"
grid_levels: 30              # Number of grid levels
grid_spacing_pct: 0.25       # Spacing between levels
max_position_pct: 5          # Max 5% per position
daily_max_drawdown_pct: 1.0  # Stop at 1% daily loss
```

## Testing

```bash
# Test paper trading system (1-minute quick test)
python test_paper_trading_proof.py

# Test API endpoints
python test_api_endpoints.py
```

## Architecture

```
Paper Trading Flow:
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│ Grid Monster│────▶│ Paper Engine │────▶│ Audit Logger│
│   Strategy  │     │  (Simulated) │     │   (JSON)    │
└─────────────┘     └──────────────┘     └─────────────┘
       │                    │                     │
       ▼                    ▼                     ▼
  [Config YAML]      [Virtual Balance]      [Audit Log]
                          $1000              + Summary
```

## Verification

Every trade includes:
- **Timestamp** (milliseconds)
- **Symbol** traded
- **Side** (buy/sell)
- **Quantity** and **Price**
- **Price Source** (always "ccxt.binance.fetch_ticker")

Example audit log entry:
```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "level": "INFO",
  "message": "paper_exec",
  "symbol": "BTCUSDT",
  "side": "buy",
  "qty": 0.0001,
  "price_used": 42150.50,
  "price_source": "ccxt.binance.fetch_ticker",
  "ts_ms": 1705315845123
}
```

## Troubleshooting

### API not starting
```bash
# Check if port 8000 is in use
netstat -an | findstr :8000

# Start API manually
uvicorn src.api.main:app --port 8000
```

### No trades executed
- Check market volatility (low volatility = fewer trades)
- Verify grid spacing isn't too wide
- Ensure spread gate isn't blocking trades

### Import errors
```bash
# Ensure all dependencies installed
pip install -r requirements.txt
```