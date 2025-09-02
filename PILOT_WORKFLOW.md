# Sofia V2 - Pilot Trading Workflow

## Complete Workflow for Pilot Trading

This document shows the complete workflow from development to live pilot trading.

### 1. Start Development Environment

```bash
# Start API and Dashboard (browsers open automatically)
make up

# Or directly:
python scripts/dev_up.py

# This will:
# - Start API on http://localhost:8002/dev
# - Start Dashboard on http://localhost:5000/
# - Open both URLs in browser after health checks pass
# - Logs go to logs/dev/
```

### 2. Run 24-Hour Campaign (Proof Sprint)

```bash
# Run 3 sessions of Grid + Turkish Arbitrage
make quick-campaign

# Or directly:
python tools/run_quick_campaign.py

# This runs:
# - Session 1: AM symbols, EV Gate ON, normal route
# - Session 2: PM symbols, EV Gate ON, fast route (A/B test)
# - Session 3: Mixed symbols, EV Gate ON, normal route
# - Generates: reports/quick_campaign.json and .md
```

### 3. Check Readiness (Strict GO/NO-GO)

```bash
# Check if system is ready for live trading
make readiness-v2

# Or directly:
python tools/live_readiness_v2_enhanced.py

# Checks 12 criteria:
# - All 3 sessions must PASS
# - Shadow p95 < 7 bps
# - Grid fill rate ≥ 60%
# - Arbitrage success rate ≥ 55%
# - Max drawdown ≥ -1%
# - Zero anomalies
# - Clean reconciliation
# Exit code: 0 = GO, 1 = NO-GO
```

### 4. Enable Live Trading (if GO)

```bash
# Start with warmup mode (lower caps)
make live-on

# Or for normal mode:
python tools/live_toggle.py on

# Or for warmup:
python tools/live_toggle.py on --warmup

# This sets:
# - Strategy: turkish_arbitrage only
# - Per trade cap: 100 TL (warmup) or 250 TL (normal)
# - Max notional: 500 TL (warmup) or 1000 TL (normal)
# - Hours: 10:00-18:00 Istanbul time
# - Requires two-man approval in config/approvals.json
```

### 5. Monitor Pilot Status

```bash
# Check current pilot status
make pilot-status

# Or directly:
python tools/pilot_status.py

# Shows:
# - Live trading enabled/disabled
# - Current P&L
# - Active positions
# - Trigger status
# - Health checks
```

### 6. Pilot Telemetry (Running in Background)

```bash
# Start telemetry collection (5-second intervals)
python tools/pilot_telemetry.py start

# View current telemetry
python tools/pilot_telemetry.py

# Collects:
# - Capital usage
# - Live P&L (net after fees+tax)
# - EV rejects
# - Latency metrics
# - Active positions
```

### 7. End of Day Report

```bash
# Generate daily pilot report
python tools/pilot_day_report.py

# Generates:
# - reports/pilot_day_report_{date}.json
# - reports/pilot_day_report_{date}.md
# - Net P&L after Turkish taxes
# - Hit rate
# - EV rejection analysis
# - Best/worst hours
# - Recommendations
```

### 8. Emergency Shutdown (if needed)

```bash
# Manual emergency stop
make pilot-off

# Or directly:
python tools/pilot_off.py stop --manual

# Auto-triggers on:
# - Anomaly detection
# - Reconciliation failure
# - Drawdown breach < -1%

# Incident snapshot:
python tools/incident_snapshot.py --manual
# Collects logs, P&L, orders, network state
# Saves to: reports/incidents/{timestamp}/
```

### 9. Post-Pilot Analysis

```bash
# Analyze EV gate effectiveness
python tools/ev_impact.py

# Generates:
# - Correlation between predicted vs realized
# - Variance reduction metrics
# - Recommendations for EV tuning

# Plan next day symbols
python tools/attribution_decider.py

# Generates:
# - config/symbol_plan_tomorrow.json
# - Best AM/PM symbols based on attribution
# - Position limits by volatility
```

### 10. Stop Development Environment

```bash
# Stop all services cleanly
make down

# Or directly:
python scripts/dev_down.py

# View logs anytime:
make logs
```

## Quick Command Reference

```bash
# Daily workflow
make up                    # Start dev environment
make quick-campaign        # Run 24h proof
make readiness-v2          # Check GO/NO-GO

# If GO:
make live-on              # Enable pilot (requires approvals)
make pilot-status         # Monitor status

# End of day:
python tools/pilot_day_report.py        # Daily report
python tools/ev_impact.py               # EV analysis
python tools/attribution_decider.py     # Next day plan

# Shutdown:
make pilot-off            # Disable pilot
make down                 # Stop dev environment
```

## Safety Features

1. **Strict Readiness Gate**: ALL 12 criteria must pass for GO
2. **Two-Man Approval**: Both operators must approve in `config/approvals.json`
3. **Auto-Pause Triggers**: Anomaly, reconciliation fail, DD breach
4. **Micro Limits**: Max 1000 TL notional, single strategy only
5. **Time Restrictions**: 10:00-18:00 Istanbul time only
6. **Warmup Mode**: Start with 100 TL cap for safety
7. **Emergency Stop**: Instant shutdown with full snapshot

## Files Generated

- `logs/dev/` - API and Dashboard logs
- `reports/quick_campaign.json` - Campaign results
- `reports/live_readiness_v2.json` - Readiness check
- `config/live.yaml` - Live trading configuration
- `logs/pilot_telemetry.json` - Real-time metrics
- `reports/pilot_day_report_{date}.json` - Daily summary
- `reports/incidents/{timestamp}/` - Emergency snapshots
- `reports/ev_impact_analysis.json` - EV effectiveness
- `config/symbol_plan_tomorrow.json` - Next day plan

## Troubleshooting

### Services won't start
```bash
# Check if ports are in use
netstat -an | grep 8002
netstat -an | grep 5000

# Kill orphaned processes
python scripts/dev_down.py
```

### Readiness fails
```bash
# Check detailed failures
cat reports/live_readiness_v2.json | grep why_not

# Re-run campaign with better parameters
python tools/run_quick_campaign.py
```

### Live trading won't enable
```bash
# Check approvals
cat config/approvals.json

# Both operators must set approved=true with timestamp
```

### Emergency situation
```bash
# Immediate stop
python tools/pilot_off.py stop --manual

# Collect evidence
python tools/incident_snapshot.py --manual

# Check snapshot
ls -la reports/incidents/
```