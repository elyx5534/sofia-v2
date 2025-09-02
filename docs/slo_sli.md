# Service Level Objectives (SLO) and Indicators (SLI)

## Executive Summary

Sofia V2 Trading Platform commits to the following service levels:
- **Data Freshness**: 99% of market data < 5 seconds old
- **API Availability**: 99.5% uptime during market hours
- **Order Success Rate**: 95% of orders execute without system errors
- **Reconciliation Accuracy**: 100% trade matching within 24 hours

---

## Service Level Indicators (SLIs)

### 1. Data Freshness
**Definition**: Time between exchange timestamp and system processing

**Measurement**:
```python
data_freshness = (system_time - exchange_timestamp).total_seconds()
```

**Collection**:
- Sampled every tick
- Aggregated per minute
- P99 calculated hourly

### 2. Fill Report Latency
**Definition**: Time from order placement to fill confirmation

**Measurement**:
```python
fill_latency = (fill_reported_time - order_placed_time).total_seconds()
```

**Collection**:
- Measured for every order
- Bucketed by exchange
- P50, P95, P99 calculated

### 3. Job Success Rate
**Definition**: Percentage of scheduled jobs completing successfully

**Measurement**:
```python
success_rate = successful_jobs / total_jobs * 100
```

**Collection**:
- Tracked per job type
- Daily aggregation
- Weekly trends

### 4. API Response Time
**Definition**: Time to respond to API requests

**Measurement**:
```python
response_time = request_end - request_start
```

**Collection**:
- Measured at nginx/API gateway
- Excludes websocket connections
- Bucketed by endpoint

### 5. System Error Rate
**Definition**: Percentage of operations resulting in errors

**Measurement**:
```python
error_rate = error_count / total_operations * 100
```

**Collection**:
- Log parsing for ERROR level
- Grouped by component
- 5-minute windows

---

## Service Level Objectives (SLOs)

### Critical SLOs (Market Hours: 10:00-18:00 Istanbul)

| SLI | Target | Window | Error Budget |
|-----|--------|--------|--------------|
| Data Freshness < 5s | 99% | 1 hour | 6 minutes/month |
| API Availability | 99.5% | 1 day | 3.6 hours/month |
| Order Success Rate | 95% | 1 hour | 36 hours/month |
| Reconciliation Match | 100% | 24 hours | 0 mismatches |

### Non-Critical SLOs (24/7)

| SLI | Target | Window | Error Budget |
|-----|--------|--------|--------------|
| Job Success Rate | 90% | 1 day | 3 days/month |
| API Response P95 < 1s | 95% | 1 hour | 36 hours/month |
| Error Rate < 1% | 99% | 1 hour | 7.2 hours/month |
| Memory Usage < 80% | 95% | 1 hour | 36 hours/month |

---

## Error Budget Policy

### Budget Calculation
```
Monthly Error Budget = (1 - SLO) × Time Period
Example: 99% SLO = 1% error budget = 7.2 hours/month
```

### Budget Consumption Triggers

**25% Consumed**:
- Review recent changes
- Increase monitoring

**50% Consumed**:
- Freeze non-critical deployments
- Conduct mini-postmortem

**75% Consumed**:
- Freeze all deployments
- Implement fixes only

**100% Consumed**:
- Halt all changes
- Focus on reliability
- Executive review required

---

## Monitoring Implementation

### SLO Dashboard Configuration

```python
# src/monitoring/slo_tracker.py

class SLOTracker:
    def __init__(self):
        self.slos = {
            "data_freshness": {
                "target": 0.99,
                "window_hours": 1,
                "threshold_seconds": 5
            },
            "api_availability": {
                "target": 0.995,
                "window_hours": 24,
                "measurement": "uptime"
            },
            "order_success": {
                "target": 0.95,
                "window_hours": 1,
                "measurement": "success_rate"
            }
        }
        
    def calculate_error_budget(self, slo_name: str) -> dict:
        slo = self.slos[slo_name]
        budget_seconds = (1 - slo["target"]) * slo["window_hours"] * 3600
        
        # Get actual performance
        actual = self.get_actual_performance(slo_name)
        consumed = (1 - actual) * slo["window_hours"] * 3600
        
        return {
            "total_budget": budget_seconds,
            "consumed": consumed,
            "remaining": budget_seconds - consumed,
            "percentage_used": (consumed / budget_seconds) * 100
        }
```

### Alert Rules

```yaml
# config/slo_alerts.yaml

alerts:
  - name: data_freshness_violation
    sli: data_freshness
    condition: p99 > 5s
    duration: 5m
    severity: warning
    
  - name: api_down
    sli: api_availability
    condition: up == 0
    duration: 1m
    severity: critical
    
  - name: error_budget_50
    sli: "*"
    condition: error_budget_used > 50%
    duration: immediate
    severity: warning
    
  - name: error_budget_exhausted
    sli: "*"
    condition: error_budget_used >= 100%
    duration: immediate
    severity: critical
```

---

## Reporting

### Weekly SLO Report

Generated every Monday at 09:00 Istanbul time:

1. **SLO Performance**
   - Achievement percentage for each SLO
   - Violation incidents with timestamps
   - Error budget consumption

2. **Trend Analysis**
   - Week-over-week comparison
   - Identifying degrading services
   - Capacity planning needs

3. **Action Items**
   - Required fixes for violations
   - Preventive measures
   - SLO adjustments if needed

### Monthly Review

1. **SLO Calibration**
   - Are targets too aggressive/lenient?
   - Should windows be adjusted?
   - New SLIs needed?

2. **Incident Impact**
   - Correlation with SLO violations
   - Customer impact assessment
   - Process improvements

3. **Error Budget Planning**
   - Allocation for next month
   - Feature velocity vs reliability
   - Investment priorities

---

## SLO Status Banner

The `/dev` dashboard displays real-time SLO status:

```html
<!-- SLO Status Banner -->
<div class="slo-banner">
    <div class="slo-item">
        <span class="label">Data Fresh</span>
        <span class="value ok">99.2%</span>
        <span class="budget">Budget: 42%</span>
    </div>
    <div class="slo-item">
        <span class="label">API Up</span>
        <span class="value ok">99.8%</span>
        <span class="budget">Budget: 15%</span>
    </div>
    <div class="slo-item">
        <span class="label">Orders OK</span>
        <span class="value warning">94.5%</span>
        <span class="budget">Budget: 78%</span>
    </div>
</div>
```

### Status Colors
- 🟢 Green: Meeting SLO, budget > 50%
- 🟡 Yellow: Meeting SLO, budget < 50%
- 🔴 Red: Violating SLO or budget exhausted

---

## Implementation Checklist

- [x] Define SLIs and measurement methods
- [x] Set initial SLO targets
- [x] Calculate error budgets
- [x] Create monitoring queries
- [x] Build SLO dashboard
- [x] Configure alerts
- [x] Document policies
- [ ] Deploy to production
- [ ] Train operators
- [ ] First monthly review

---

## References

- [Google SRE Book - SLOs](https://sre.google/sre-book/service-level-objectives/)
- [Error Budget Policy](https://sre.google/workbook/error-budget-policy/)
- [Monitoring Distributed Systems](https://sre.google/sre-book/monitoring-distributed-systems/)

Last Updated: 2024-01-15
Version: 1.0.0