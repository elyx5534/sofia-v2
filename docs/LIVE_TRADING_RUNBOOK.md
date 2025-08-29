# Sofia V2 - Live Trading Runbook

## Table of Contents
1. [System Overview](#system-overview)
2. [Pre-Deployment Checklist](#pre-deployment-checklist)
3. [Deployment Procedures](#deployment-procedures)
4. [Operational Procedures](#operational-procedures)
5. [Emergency Procedures](#emergency-procedures)
6. [Monitoring & Alerts](#monitoring--alerts)
7. [Troubleshooting Guide](#troubleshooting-guide)
8. [Recovery Procedures](#recovery-procedures)

---

## System Overview

### Architecture Components
- **Live Trading Adapter** (`src/trading/live_adapter.py`): CCXT-based order execution
- **Risk Engine** (`src/risk/engine.py`): Pre-trade and runtime risk checks
- **Kill Switch** (`src/risk/kill_switch.py`): Emergency trading halt mechanism
- **Shadow Mode** (`src/trading/shadow_mode.py`): Safe testing environment
- **Observability** (`src/observability/monitoring.py`): Sentry + Prometheus
- **Reconciliation** (`src/reconciliation/eod_reports.py`): Daily P&L and position reconciliation

### Trading Modes
1. **Shadow Mode**: Logs orders without execution
2. **Canary Mode**: Executes configurable percentage (10-100%)
3. **Live Mode**: Full execution

---

## Pre-Deployment Checklist

### Environment Setup
```bash
# 1. Copy and configure environment
cp .env.testnet .env
# Edit .env with production values

# 2. Verify configuration
cat .env | grep -E "MODE|EXCHANGE|KILL_SWITCH"
```

### Required Environment Variables
```env
MODE=testnet                    # testnet|live
EXCHANGE=binance                # binance|kraken|coinbase
API_KEY=your_api_key
API_SECRET=your_api_secret
MAX_DAILY_LOSS=200              # Maximum daily loss in USD
MAX_POSITION_USD=1000           # Maximum position size
KILL_SWITCH=AUTO                # OFF|ON|AUTO
```

### Preflight Check
```bash
# Run comprehensive preflight check
python scripts/preflight_check.py

# Expected output:
# [PASS] Environment: All required environment variables present
# [PASS] Exchange Connection: Exchange connected: 500 markets available
# [PASS] Risk Engine: Risk engine configured: max_loss=$200
# [PASS] Kill Switch: Kill switch state: AUTO
# [PASS] Database: Database connected
# [PASS] Observability: Sentry=True, Prometheus=True
# [PASS] Disk Space: Disk space available: 50.2GB
```

---

## Deployment Procedures

### 1. Shadow Mode Deployment (Day 1)
```bash
# Set shadow mode
export TRADING_MODE=shadow
export KILL_SWITCH=OFF

# Start services
python start_api.py &
python workers/backtest_worker.py &

# Monitor shadow orders
tail -f shadow_orders.jsonl
```

### 2. Canary Deployment (Day 2-3)
```bash
# Run canary deployment script
python scripts/canary_deployment.py

# Monitor canary progress
watch -n 5 'curl http://localhost:8023/shadow/status'
```

#### Canary Phases
- **Phase 1** (10%): 1 hour, monitor closely
- **Phase 2** (25%): 2 hours, check metrics
- **Phase 3** (50%): 4 hours, validate P&L
- **Phase 4** (75%): 8 hours, full validation
- **Phase 5** (100%): Production ready

### 3. Production Deployment (Day 4+)
```bash
# Set production mode
export TRADING_MODE=live
export KILL_SWITCH=AUTO
export ENVIRONMENT=production

# Start with systemd (recommended)
sudo systemctl start sofia-trading
sudo systemctl start sofia-workers
sudo systemctl enable sofia-trading
```

---

## Operational Procedures

### Daily Operations

#### Morning Checklist (Market Open)
1. Check kill switch state
2. Review overnight positions
3. Verify risk limits
4. Check system health

```bash
# Morning check script
curl http://localhost:8023/risk/status
curl http://localhost:8023/health
python -c "from src.risk.kill_switch import KillSwitch; print(KillSwitch().get_state())"
```

#### EOD Procedures (Market Close)
1. Generate EOD report
2. Reconcile positions
3. Review P&L
4. Archive logs

```bash
# EOD script
curl -X POST http://localhost:8023/reconciliation/run
curl -X POST http://localhost:8023/reports/eod
```

### Position Reconciliation
```bash
# Manual reconciliation
curl -X POST http://localhost:8023/reconciliation/positions

# Check discrepancies
cat reports/reconciliation/reconciliation_*.json | jq '.discrepancies'
```

### Order Management

#### Create Order (Manual)
```python
from src.trading.live_adapter import LiveAdapter
from decimal import Decimal
import asyncio

async def create_order():
    adapter = LiveAdapter()
    await adapter.initialize()
    
    order = await adapter.create_order(
        symbol="BTC/USDT",
        side="buy",
        order_type="limit",
        quantity=Decimal("0.01"),
        price=Decimal("50000")
    )
    print(f"Order created: {order.order_id}")
    
asyncio.run(create_order())
```

#### Cancel All Orders
```bash
# Emergency cancel all
curl -X POST http://localhost:8023/orders/cancel-all
```

---

## Emergency Procedures

### 1. IMMEDIATE HALT (Kill Switch)

#### Manual Activation
```bash
# Via API
curl -X POST http://localhost:8023/kill-switch/activate \
  -H "Content-Type: application/json" \
  -d '{"reason": "Manual emergency halt"}'

# Via Python
python -c "
from src.risk.kill_switch import KillSwitch, TriggerType
import asyncio
async def halt():
    ks = KillSwitch()
    await ks.activate(TriggerType.MANUAL, 'Emergency halt')
asyncio.run(halt())
"
```

#### Deactivation (After Resolution)
```bash
curl -X POST http://localhost:8023/kill-switch/deactivate \
  -H "Content-Type: application/json" \
  -d '{"reason": "Issue resolved"}'
```

### 2. Rollback to Shadow Mode
```bash
# Immediate rollback
export TRADING_MODE=shadow
curl -X POST http://localhost:8023/shadow/rollback

# Verify rollback
curl http://localhost:8023/shadow/status
```

### 3. P&L Breach Response
```
IF daily_loss > MAX_DAILY_LOSS:
1. Kill switch auto-activates (if AUTO mode)
2. Cancel all open orders
3. Send alert to team
4. Generate incident report
5. Review positions before restart
```

### 4. System Crash Recovery
```bash
# 1. Check system state
systemctl status sofia-trading

# 2. Review logs
journalctl -u sofia-trading -n 100

# 3. Run reconciliation
python -c "
from src.reconciliation.eod_reports import ReconciliationEngine
import asyncio
async def reconcile():
    engine = ReconciliationEngine()
    report = await engine.reconcile_positions()
    print(report)
asyncio.run(reconcile())
"

# 4. Restart in shadow mode first
export TRADING_MODE=shadow
systemctl restart sofia-trading

# 5. Verify health
curl http://localhost:8023/health

# 6. Resume normal operations
export TRADING_MODE=live
systemctl restart sofia-trading
```

---

## Monitoring & Alerts

### Key Metrics to Monitor

#### Real-time Metrics
- **Order Success Rate**: > 95%
- **API Latency**: < 100ms (p95)
- **WebSocket Status**: Connected
- **Daily P&L**: Within limits
- **Position Exposure**: < MAX_POSITION_USD

#### Prometheus Queries
```promql
# Order success rate (last 5m)
rate(trading_orders_total{status="success"}[5m]) / rate(trading_orders_total[5m])

# Average latency
histogram_quantile(0.95, order_latency_seconds)

# Error rate
rate(trading_errors_total[5m])

# Current P&L
trading_pnl_usd

# Position exposure
sum(trading_position_usd)
```

### Alert Configuration

#### Critical Alerts (Page immediately)
- Kill switch activated
- Daily loss > 80% of limit
- WebSocket down > 30 seconds
- Order error rate > 10%

#### Warning Alerts (Notify team)
- Latency > 1 second
- Daily loss > 50% of limit
- Disk space < 5GB
- Reconciliation discrepancies

### Grafana Dashboard
```json
{
  "dashboard": {
    "title": "Sofia Trading System",
    "panels": [
      {
        "title": "Order Success Rate",
        "targets": [{"expr": "rate(trading_orders_total{status='success'}[5m])"}]
      },
      {
        "title": "Daily P&L",
        "targets": [{"expr": "trading_pnl_usd"}]
      },
      {
        "title": "Position Exposure",
        "targets": [{"expr": "sum(trading_position_usd) by (symbol)"}]
      },
      {
        "title": "API Latency (p95)",
        "targets": [{"expr": "histogram_quantile(0.95, api_latency_seconds)"}]
      }
    ]
  }
}
```

---

## Troubleshooting Guide

### Common Issues

#### 1. "Time drift too large" Error
```bash
# Sync system time
sudo ntpdate -s time.nist.gov
# Or
sudo chrony sources -v
```

#### 2. "Insufficient balance" Error
```bash
# Check exchange balance
curl http://localhost:8023/exchange/balance

# Verify position limits
curl http://localhost:8023/risk/status
```

#### 3. WebSocket Disconnections
```bash
# Check network
ping api.binance.com

# Restart WebSocket
curl -X POST http://localhost:8023/ws/restart

# Check firewall
sudo iptables -L | grep 9443
```

#### 4. High Latency
```bash
# Check system load
top -n 1

# Check network latency
mtr api.binance.com

# Review slow queries
tail -f logs/api.log | grep "duration"
```

#### 5. Reconciliation Discrepancies
```python
# Manual position sync
from src.trading.live_adapter import LiveAdapter
import asyncio

async def sync():
    adapter = LiveAdapter()
    await adapter.initialize()
    result = await adapter.resync()
    print(result)
    
asyncio.run(sync())
```

---

## Recovery Procedures

### After Kill Switch Activation

1. **Identify Root Cause**
```bash
# Review kill switch events
cat kill_switch_state.json | jq '.events[-5:]'

# Check audit log
curl http://localhost:8023/risk/audit?limit=50
```

2. **Resolve Issue**
- Fix configuration if needed
- Clear error conditions
- Verify exchange connectivity

3. **Test in Shadow Mode**
```bash
export TRADING_MODE=shadow
python scripts/preflight_check.py
```

4. **Gradual Resumption**
```bash
# Start with 10% canary
export TRADING_MODE=canary
export CANARY_PERCENTAGE=10

# Monitor for 1 hour
sleep 3600

# If stable, increase to 50%
export CANARY_PERCENTAGE=50
```

5. **Full Production**
```bash
export TRADING_MODE=live
export KILL_SWITCH=AUTO
```

### After System Crash

1. **Data Recovery**
```bash
# Backup current state
tar -czf backup_$(date +%Y%m%d).tar.gz reports/ *.db *.json

# Check database integrity
sqlite3 trading.db "PRAGMA integrity_check;"
```

2. **State Reconciliation**
```python
# Full system reconciliation
python scripts/full_reconciliation.py
```

3. **Gradual Restart**
- Start API in read-only mode
- Verify all positions
- Enable shadow mode
- Run canary deployment
- Resume full trading

---

## Appendix

### Important Files
- Configuration: `.env`, `.env.testnet`
- Logs: `logs/api.log`, `logs/worker.log`
- Reports: `reports/eod/`, `reports/reconciliation/`
- State: `kill_switch_state.json`, `shadow_orders.jsonl`

### Support Contacts
- Trading Desk: trading@company.com
- DevOps: devops@company.com
- On-call: Use PagerDuty

### References
- [CCXT Documentation](https://docs.ccxt.com)
- [Risk Management Best Practices](./RISK_MANAGEMENT.md)
- [API Documentation](./API_DOCS.md)
- [Release Notes](./RELEASE_NOTES_v0.2.0.md)

---

**Last Updated**: August 29, 2025
**Version**: v0.2.0