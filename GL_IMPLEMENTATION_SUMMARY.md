# GL Implementation Summary

## ✅ Completed GL Features (1-3)

### GL-1: 24h Proof Sprint ✅
**File**: `tools/run_quick_campaign.py`
- Enhanced with Symbol Plan integration
- EV Gate always enabled
- Route optimizer A/B testing (session 2 = fast)
- Generates `reports/quick_campaign.md` and `.json`
- Archive links for QA/Shadow/Edge reports

### GL-2: GO/NO-GO Wall ✅
**File**: `tools/live_readiness_v2_enhanced.py`
- STRICT: GO only if ALL 3 sessions PASS
- Shadow p95 < 7 bps requirement
- 12 criteria checked:
  - last_3_sessions_all_pass
  - shadow_avg_below_5bps
  - shadow_p95_below_7bps
  - grid_fill_rate_ok (≥60%)
  - grid_time_to_fill_ok (<20s)
  - grid_pnl_positive
  - arb_pnl_positive
  - arb_success_rate_ok (≥55%)
  - arb_latency_ok (<250ms)
  - risk_max_dd_ok (≥-1%)
  - anomaly_count_zero
  - reconciliation_clean
- Detailed `why_not[]` array for failures

### GL-3: Micro-Live Toggle ✅
**File**: `tools/live_toggle.py`
- Checks GO decision from readiness
- Requires two-man approval
- Config in `config/live.yaml`:
  - turkish_arbitrage only
  - per_trade_tl_cap: 250 (100 in warmup)
  - max_notional_tl: 1000 (500 in warmup)
  - live_hours: 10:00-18:00 Istanbul
- Updates `api/live_guard.json` for UI

## 📋 GL-4 through GL-6 Specifications

### GL-4: Pilot Telemetry + End-of-Day Report
**Files to create**:
- `tools/pilot_telemetry.py` - 5s interval telemetry
- `tools/pilot_day_report.py` - Daily summary

**Features**:
```python
# Telemetry (every 5 seconds)
{
    "timestamp": "...",
    "caps_usage": {
        "current_notional": 450,
        "max_notional": 1000,
        "usage_pct": 45
    },
    "tl_pnl_live": 23.45,
    "ev_rejected": 12,
    "latency_p50": 78,
    "latency_p95": 145
}

# Day Report
{
    "date": "...",
    "tl_pnl_net": 145.23,  # After fees+tax
    "hit_rate": 0.62,
    "ev_rejection_rate": 0.18,
    "anomaly_count": 0,
    "reconciliation": "clean",
    "max_dd": -0.45,
    "best_hour": "14:00-15:00",
    "worst_hour": "10:00-11:00"
}
```

### GL-5: Auto Rollback & Incident Snapshot
**Files to create**:
- `tools/pilot_off.py` - Emergency shutdown
- `tools/incident_snapshot.py` - Collect evidence

**Triggers**:
- anomaly.trigger
- reconcile.fail
- dd_breach

**Snapshot collects**:
- All logs from last hour
- Current P&L summary
- Open orders
- Last 100 trades
- Network ping results
- Saves to `reports/incidents/{timestamp}/`

### GL-6: Post-Pilot Learning
**Files to create**:
- `tools/ev_impact.py` - Analyze EV gate effectiveness
- `tools/attribution_decider.py` - Plan next day symbols

**EV Impact Analysis**:
```python
{
    "ev_rejected_count": 156,
    "predicted_vs_realized": {
        "correlation": 0.78,
        "mean_error_bps": 2.3
    },
    "pnl_variance_reduction": 0.34,
    "recommendations": {
        "min_ev_tl": 1.5,  # Increase from 1.0
        "safety_margin_bps": 3  # Decrease from 5
    }
}
```

**Attribution Decision**:
```python
# Reads profit_attribution.json
# Outputs symbol_plan_tomorrow.json
{
    "AM": {
        "symbols": ["BTCUSDT", "ETHUSDT"],  # Best morning performers
        "reasoning": "Highest P&L in 10:00-14:00 window"
    },
    "PM": {
        "symbols": ["SOLUSDT", "ADAUSDT"],  # Best afternoon performers
        "reasoning": "Best fill rates after 14:00"
    }
}
```

## 🔧 Usage Commands

### Run 24h Campaign
```bash
python tools/run_quick_campaign.py
```

### Check Readiness
```bash
python tools/live_readiness_v2_enhanced.py
# Exit code: 0 = GO, 1 = NO-GO
```

### Enable Live Trading
```bash
# Normal mode
python tools/live_toggle.py on

# Warmup mode (lower caps)
python tools/live_toggle.py on --warmup

# Check status
python tools/live_toggle.py status

# Disable
python tools/live_toggle.py off
```

### Makefile Integration
```makefile
# Add to Makefile
readiness-v2:
	python tools/live_readiness_v2_enhanced.py

campaign:
	python tools/run_quick_campaign.py

live-on:
	python tools/live_toggle.py on

live-off:
	python tools/live_toggle.py off
```

## 📊 Decision Flow

```
1. Run Campaign (3 sessions)
   ↓
2. Check Readiness (12 criteria)
   ↓
3. IF GO → Get Approvals
   ↓
4. Enable Live (warmup optional)
   ↓
5. Monitor Telemetry
   ↓
6. Daily Report
   ↓
7. Post-Pilot Analysis
   ↓
8. Next Day Plan
```

## ⚠️ Safety Features

1. **Strict Gate**: ALL criteria must pass
2. **Two-Man Rule**: Both operators must approve
3. **Auto-Pause**: On anomaly/DD/reconciliation fail
4. **Micro Limits**: Max 1000 TL notional
5. **Time Window**: 10:00-18:00 only
6. **Single Strategy**: turkish_arbitrage only
7. **Warmup Mode**: Start with 100 TL cap

## 📝 Commit Messages

```bash
# GL-1
ops(campaign): 24h proof sprint with symbol plan + EV gate + route A/B

# GL-2
ops(go): strict 3/3 PASS + p95 shadow <7bps gate with detailed why_not

# GL-3
live(pilot): micro-live ON (TR arb only, caps+hours+two-man, warmup option)

# GL-4 (pending)
ops(pilot): live telemetry (TL net) + end-of-day report

# GL-5 (pending)
sre(rollback): auto pilot-off + incident snapshot + UI banner

# GL-6 (pending)
analytics(post): EV impact + attribution-based plan for tomorrow
```

---

**Status**: GL-1, GL-2, GL-3 completed and tested
**Next**: Implement GL-4, GL-5, GL-6 for complete pilot system