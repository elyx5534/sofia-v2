# Sofia V2 - Operations Runbook

## 🚨 Emergency Procedures

### System Down - Complete Outage
```bash
# 1. Check core services
systemctl status redis
systemctl status postgresql
ps aux | grep uvicorn

# 2. Restart infrastructure
./scripts/emergency_restart.sh

# 3. Verify health
curl http://localhost:8013/health
curl http://localhost:8000/metrics

# 4. Check logs
tail -f logs/api.log
tail -f logs/ingestion.log
```

### UI Theme Broken
```bash
# IMMEDIATE ACTION - Restore UI
git status sofia_ui/
git restore --source=origin/main -- sofia_ui/

# Verify theme
python tests/e2e/test_ui_theme.py

# If still broken
git checkout origin/main -- sofia_ui/
git commit -m "EMERGENCY: Restore UI theme"
```

### Data Feed Issues
```bash
# Check exchange connections
curl http://localhost:8000/metrics | grep reconnect

# Restart specific ingester
pkill -f crypto_ws.py
python ingestors/crypto_ws.py &

# Force fallback
export EQUITY_PRIMARY=yahoo
systemctl restart sofia-equity-service
```

## 📊 Monitoring Checklist

### Every 5 Minutes
- [ ] Check `/health` endpoint
- [ ] Verify data freshness (stale_ratio < 0.1)
- [ ] Monitor Redis memory usage
- [ ] Check API latency (P95 < 150ms)

### Every Hour
- [ ] Review Grafana dashboard
- [ ] Check disk space
- [ ] Verify backup completion
- [ ] Test fallback data sources

### Daily
- [ ] Run theme regression test
- [ ] Review error logs
- [ ] Check paper trading PnL
- [ ] Verify news feed updates

## 🔄 Routine Operations

### Starting Services (Order Matters!)

```bash
#!/bin/bash
# Start in this exact order

# 1. Database & Cache
redis-server --daemonize yes
systemctl start postgresql  # If using TimescaleDB
questdb start  # If using QuestDB

# 2. Wait for databases
sleep 5

# 3. Start monitoring
python monitoring/metrics_server.py &
echo $! > pids/metrics.pid

# 4. Start data ingestion
python ingestors/crypto_ws.py &
echo $! > pids/crypto_ws.pid

python ingestors/equities_pull.py &
echo $! > pids/equities.pid

# 5. Start writers
python writers/ts_writer.py &
echo $! > pids/writer.pid

# 6. Start news & alerts
python news/rss_agg.py &
echo $! > pids/news.pid

python alerts/whale_trade.py &
echo $! > pids/whale.pid

# 7. Start API (last)
uvicorn src.api.main:app --port 8013 &
echo $! > pids/api.pid

# 8. Verify all running
sleep 10
curl http://localhost:8013/health
```

### Stopping Services

```bash
#!/bin/bash
# Stop in reverse order

# 1. Stop API
kill $(cat pids/api.pid)

# 2. Stop processors
kill $(cat pids/whale.pid)
kill $(cat pids/news.pid)

# 3. Stop writers
kill $(cat pids/writer.pid)

# 4. Stop ingestors
kill $(cat pids/equities.pid)
kill $(cat pids/crypto_ws.pid)

# 5. Stop monitoring
kill $(cat pids/metrics.pid)

# 6. Stop databases (optional)
redis-cli shutdown
questdb stop
```

### Backup Procedures

```bash
# Daily backup script
#!/bin/bash
DATE=$(date +%Y%m%d)
BACKUP_DIR=/backups/$DATE

# 1. Create backup directory
mkdir -p $BACKUP_DIR

# 2. Backup Redis
redis-cli BGSAVE
cp /var/lib/redis/dump.rdb $BACKUP_DIR/

# 3. Backup QuestDB
questdb backup -d $BACKUP_DIR/questdb

# 4. Backup configs
cp .env $BACKUP_DIR/
cp -r sofia_ui/extensions $BACKUP_DIR/

# 5. Backup AI models
cp -r models/ $BACKUP_DIR/

# 6. Upload to S3
aws s3 sync $BACKUP_DIR s3://sofia-backups/$DATE/

# 7. Clean old backups (keep 30 days)
find /backups -mtime +30 -delete
```

### Restore Procedures

```bash
# Restore from backup
#!/bin/bash
BACKUP_DATE=$1  # e.g., 20250828

# 1. Stop services
./scripts/stop_all.sh

# 2. Download backup
aws s3 sync s3://sofia-backups/$BACKUP_DATE/ /tmp/restore/

# 3. Restore Redis
cp /tmp/restore/dump.rdb /var/lib/redis/
redis-server --loadmodule restore

# 4. Restore QuestDB
questdb restore -s /tmp/restore/questdb

# 5. Restore configs
cp /tmp/restore/.env .
cp -r /tmp/restore/extensions sofia_ui/

# 6. Restore models
cp -r /tmp/restore/models/ .

# 7. Start services
./scripts/start_all.sh

# 8. Verify
curl http://localhost:8013/health
```

## 🔍 Debugging Procedures

### High Latency Investigation
```bash
# 1. Check system resources
top -b -n 1
free -h
df -h

# 2. Profile API
python -m cProfile -o profile.stats src/api/main.py
python -m pstats profile.stats

# 3. Check Redis
redis-cli --latency
redis-cli INFO stats

# 4. Database queries
# QuestDB
echo "SELECT count(*) FROM ticks WHERE timestamp > now() - INTERVAL '1 minute'" | questdb query

# 5. Network issues
netstat -an | grep ESTABLISHED | wc -l
ss -s
```

### Memory Leak Detection
```bash
# 1. Monitor memory over time
while true; do
    ps aux | grep python | awk '{print $2, $4, $11}' >> memory_log.txt
    sleep 60
done

# 2. Use memory profiler
pip install memory_profiler
python -m memory_profiler ingestors/crypto_ws.py

# 3. Check Redis memory
redis-cli INFO memory
```

### WebSocket Disconnection Issues
```bash
# 1. Check metrics
curl http://localhost:8000/metrics | grep -E "reconnect|websocket"

# 2. Review logs
grep -E "ERROR|disconnect|reconnect" logs/crypto_ws.log | tail -100

# 3. Test connectivity
python -c "
import websocket
ws = websocket.WebSocket()
ws.connect('wss://stream.binance.com:9443/ws/btcusdt@ticker')
print(ws.recv())
"

# 4. Force reconnect
kill -USR1 $(cat pids/crypto_ws.pid)  # Soft restart
```

## 📈 Performance Tuning

### Database Optimization
```sql
-- QuestDB: Optimize partitions
ALTER TABLE ticks DROP PARTITION WHERE timestamp < dateadd('d', -30, now());
VACUUM TABLE ticks;

-- TimescaleDB: Compression
ALTER TABLE ticks SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol'
);
SELECT add_compression_policy('ticks', INTERVAL '7 days');
```

### Redis Optimization
```bash
# Check memory fragmentation
redis-cli INFO memory | grep fragmentation

# If fragmentation > 1.5
redis-cli CONFIG SET activedefrag yes

# Optimize for latency
redis-cli CONFIG SET tcp-nodelay yes
redis-cli CONFIG SET tcp-keepalive 60
```

### API Performance
```python
# Add to .env for production
WORKERS=4  # Number of Uvicorn workers
REDIS_POOL_SIZE=20
DB_POOL_SIZE=10
API_CACHE_TTL=5
```

## 🏥 Health Checks

### Automated Health Monitoring
```python
# health_monitor.py
import requests
import time

def check_health():
    checks = {
        'API': 'http://localhost:8009/health',
        'Metrics': 'http://localhost:8000/health',
        'Redis': lambda: redis_cli.ping(),
        'WebSocket': check_websocket_status,
    }
    
    for name, check in checks.items():
        try:
            if callable(check):
                result = check()
            else:
                result = requests.get(check, timeout=5).status_code == 200
            
            print(f"✅ {name}: OK" if result else f"❌ {name}: FAILED")
        except Exception as e:
            print(f"❌ {name}: ERROR - {e}")

# Run every minute
while True:
    check_health()
    time.sleep(60)
```

### Manual Health Verification
```bash
# Complete health check
#!/bin/bash

echo "=== Sofia V2 Health Check ==="

# 1. API Health
echo -n "API: "
curl -s http://localhost:8009/health | jq .status

# 2. Data freshness
echo -n "Data Age: "
curl -s http://localhost:8000/metrics | grep stale_seconds

# 3. Memory usage
echo -n "Memory: "
free -h | grep Mem | awk '{print $3 "/" $2}'

# 4. Disk usage
echo -n "Disk: "
df -h / | tail -1 | awk '{print $3 "/" $2 " (" $5 ")"}'

# 5. Active connections
echo -n "Connections: "
netstat -an | grep ESTABLISHED | wc -l

# 6. Error rate (last hour)
echo -n "Errors/hour: "
grep ERROR logs/api.log | grep "$(date -d '1 hour ago' '+%Y-%m-%d %H')" | wc -l

# 7. UI Theme check
echo -n "UI Theme: "
python tests/e2e/test_ui_theme.py --check-only
```

## 🚀 Deployment Checklist

### Before Deployment
- [ ] Run all tests: `pytest && playwright test`
- [ ] Check UI theme: `python tests/e2e/test_ui_theme.py`
- [ ] Backup current state
- [ ] Review configuration changes
- [ ] Test in staging environment

### During Deployment
- [ ] Set maintenance mode
- [ ] Stop services gracefully
- [ ] Deploy new code
- [ ] Run database migrations
- [ ] Update configurations
- [ ] Start services in order
- [ ] Verify health checks

### After Deployment
- [ ] Remove maintenance mode
- [ ] Monitor metrics for 30 minutes
- [ ] Check error logs
- [ ] Verify data flow
- [ ] Test critical paths
- [ ] Update documentation

## 📞 Escalation

### Level 1 - Automated Recovery
- Auto-restart on crash
- Fallback data sources
- Circuit breakers

### Level 2 - On-Call Engineer
- Manual intervention required
- Service degradation
- Performance issues

### Level 3 - Senior Engineer
- Data corruption
- Security breach
- Multiple system failure

### Contacts
- On-Call: Check PagerDuty
- Escalation: engineering@company.com
- Security: security@company.com

## 📋 Maintenance Windows

### Weekly (Sunday 02:00-04:00 UTC)
- Database vacuum/optimize
- Log rotation
- Backup verification
- Security updates

### Monthly (First Sunday)
- Full system restart
- Performance profiling
- Capacity planning review
- Disaster recovery test

---

**Document Version**: 1.0.0
**Last Updated**: 2025-08-28
**Next Review**: 2025-09-28