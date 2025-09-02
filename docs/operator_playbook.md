# Operator Playbook - Sofia V2

## Table of Contents
1. [Daily Operations](#daily-operations)
2. [Start/Stop Procedures](#startstop-procedures)
3. [Incident Response](#incident-response)
4. [Reconciliation](#reconciliation)
5. [Monitoring](#monitoring)
6. [Emergency Procedures](#emergency-procedures)

---

## Daily Operations

### Morning Checklist (09:00 Istanbul Time)
```bash
# 1. Check system health
curl http://localhost:8000/api/health
curl http://localhost:8000/api/dev/status

# 2. Review overnight logs
tail -n 100 logs/sofia.log | grep ERROR
tail -n 100 logs/tr_arb_audit.log

# 3. Check reconciliation status
cat reports/reconciliation.json | jq .status

# 4. Verify data feeds
python tools/check_feeds.py

# 5. Review P&L
cat reports/daily_score.json | jq .total_pnl

# 6. Check SLO status
curl http://localhost:8000/api/slo/status
```

### Pre-Market Checks (09:30)
```bash
# 1. Verify exchange connectivity
python src/exec/latency_probe.py

# 2. Check inventory levels
python tools/inventory_planner.py

# 3. Update fee configuration if needed
python src/treasury/fee_sync.py

# 4. Run quick backtest
python tools/quick_backtest.py --symbol BTCUSDT --days 1
```

### Market Hours Operations (10:00-18:00)
- Monitor `/dev` dashboard every 30 minutes
- Check anomaly detector status hourly
- Review profit attribution at 14:00
- Rebalance inventory if drift > 20%

### End of Day (18:00)
```bash
# 1. Generate daily reports
python tools/profit_attribution.py
python tools/generate_daily_report.py

# 2. Backup audit logs
cp logs/audit_chain.jsonl backups/audit_$(date +%Y%m%d).jsonl

# 3. Run reconciliation
python src/audit/reconcile.py

# 4. Clear old logs (keep 7 days)
find logs -name "*.log" -mtime +7 -delete
```

---

## Start/Stop Procedures

### Starting the System

#### Development Mode
```bash
# 1. Start dependencies
docker compose up -d postgres redis

# 2. Start API
uvicorn src.api.main:app --reload --port 8000

# 3. Start worker
python src/scheduler/run.py

# 4. Start UI
python sofia_ui/server.py
```

#### Production Mode (Blue-Green)
```powershell
# Windows PowerShell
.\scripts\deploy.ps1 deploy

# Linux/Mac
./scripts/deploy.sh deploy
```

### Stopping the System

#### Graceful Shutdown
```bash
# 1. Disable new trades
python tools/live_toggle.py off

# 2. Wait for open positions to close
python tools/wait_for_flat.py

# 3. Stop services
docker compose down

# 4. Backup state
python tools/backup_state.py
```

#### Emergency Stop
```bash
# EMERGENCY ONLY - May lose state
python tools/pilot_off.py
docker compose down --volumes
```

---

## Incident Response

### Severity Levels

| Level | Description | Response Time | Escalation |
|-------|-------------|--------------|------------|
| P1 | System down, trading halted | < 5 min | Immediate |
| P2 | Degraded performance, partial outage | < 30 min | After 1 hour |
| P3 | Non-critical issue, monitoring only | < 2 hours | Next day |
| P4 | Minor issue, cosmetic | Next day | Weekly review |

### P1 Incident Flow

1. **Detection**
   ```bash
   # Check health
   curl http://localhost:8000/api/health
   
   # Check processes
   docker ps
   ps aux | grep python
   ```

2. **Immediate Actions**
   ```bash
   # Halt trading
   python tools/pilot_off.py
   
   # Snapshot state
   python tools/emergency_snapshot.py
   
   # Check audit logs
   tail -n 100 logs/audit_chain.jsonl
   ```

3. **Diagnosis**
   - Check error logs: `grep ERROR logs/*.log`
   - Check anomaly detector: `cat logs/anomalies.json`
   - Verify chain integrity: `python src/audit/verify_chain.py`

4. **Recovery**
   - Fix root cause
   - Restore from snapshot if needed
   - Run reconciliation
   - Gradual restart with pilot mode

5. **Post-Incident**
   - Create incident report
   - Update runbook
   - Schedule postmortem

### P2 Incident Flow

1. **Identify Degradation**
   ```bash
   # Check latency
   python src/exec/latency_probe.py
   
   # Check fill rates
   cat reports/daily_score.json | jq .fill_rate
   ```

2. **Mitigate**
   - Switch to backup route
   - Reduce position sizes
   - Increase timeouts

3. **Monitor**
   - Watch for recovery
   - Escalate if not resolved in 1 hour

---

## Reconciliation

### Daily Reconciliation Process

1. **Export Exchange Trades**
   ```python
   from src.data.exchanges import get_trades
   trades = get_trades(start_date=today, end_date=today)
   ```

2. **Run Reconciliation**
   ```bash
   python src/audit/reconcile_v2.py \
     --exchange-file data/exchange_trades.json \
     --internal-file logs/audit_chain.jsonl
   ```

3. **Review Discrepancies**
   ```bash
   cat reports/reconciliation.json | jq .discrepancies
   ```

4. **Resolution Steps**
   - For price mismatches < 0.1%: Log and continue
   - For quantity mismatches: Investigate fills
   - For missing trades: Check audit chain integrity
   - For extra trades: Verify duplicate detection

### Failed Reconciliation

If reconciliation fails:
1. System auto-pauses trading
2. Operator must investigate
3. Fix discrepancies
4. Clear reconciliation flag
5. Resume trading

---

## Monitoring

### Key Metrics to Watch

| Metric | Normal Range | Alert Threshold | Action |
|--------|-------------|-----------------|---------|
| API Latency | < 100ms | > 500ms | Check load |
| Fill Rate | > 60% | < 40% | Review strategy |
| Position Drift | < 5% | > 10% | Rebalance |
| Error Rate | < 0.1% | > 1% | Check logs |
| Memory Usage | < 4GB | > 6GB | Restart worker |

### Dashboard URLs
- Main Dashboard: http://localhost:8001/
- Dev Console: http://localhost:8001/dev
- Profit Attribution: http://localhost:8001/reports/profit
- SLO Status: http://localhost:8000/api/slo/dashboard

### Alert Configuration
```yaml
# config/alerts.yaml
alerts:
  - name: high_latency
    metric: api_latency_ms
    threshold: 500
    duration: 5m
    action: email
    
  - name: low_fill_rate
    metric: fill_rate
    threshold: 0.4
    duration: 15m
    action: slack
    
  - name: position_drift
    metric: position_delta
    threshold: 0.1
    duration: immediate
    action: pagerduty
```

---

## Emergency Procedures

### Complete System Failure

1. **Immediate Actions**
   ```bash
   # Kill all processes
   pkill -9 python
   docker compose down --volumes
   
   # Notify team
   ./scripts/notify_emergency.sh "SYSTEM DOWN"
   ```

2. **Recovery**
   ```bash
   # Restore from backup
   ./scripts/restore_backup.sh latest
   
   # Start in safe mode
   SAFE_MODE=true ./scripts/start.sh
   
   # Verify integrity
   python src/audit/verify_all.py
   ```

### Exchange Outage

1. **Detection**
   - Latency probe shows timeout
   - Multiple failed orders
   - Anomaly detector triggers

2. **Response**
   ```bash
   # Switch to backup exchange
   python tools/switch_exchange.py --to backup
   
   # Pause affected strategies
   python tools/pause_strategy.py --exchange binance
   ```

### Data Corruption

1. **Detection**
   - Hash chain verification fails
   - Reconciliation shows impossible values
   - Negative balances

2. **Response**
   ```bash
   # Stop immediately
   python tools/pilot_off.py
   
   # Verify all chains
   python src/audit/deep_verify.py
   
   # Restore from last known good
   python tools/restore_chain.py --timestamp "2024-01-15T10:00:00"
   ```

---

## Runbook Updates

This playbook should be updated:
- After each incident
- When new features are deployed
- During quarterly reviews
- When SLOs change

Last Updated: 2024-01-15
Version: 2.0.0