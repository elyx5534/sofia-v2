# Operations & Production Documentation

## Deployment

### Docker Deployment
```bash
# Build image
docker build -t sofia-v2:latest .

# Run with environment
docker run -d \
  --name sofia-v2 \
  -p 8000:8000 \
  -e DATABASE_URL=postgresql://... \
  -e REDIS_URL=redis://... \
  -v ./data:/app/data \
  sofia-v2:latest
```

### Kubernetes Deployment
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sofia-v2
spec:
  replicas: 3
  selector:
    matchLabels:
      app: sofia-v2
  template:
    metadata:
      labels:
        app: sofia-v2
    spec:
      containers:
      - name: sofia-v2
        image: sofia-v2:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: sofia-secrets
              key: database-url
```

## Monitoring

### Health Checks
```python
# /health endpoint
{
  "status": "healthy",
  "version": "2.0.0",
  "uptime": 3600,
  "checks": {
    "database": "ok",
    "redis": "ok",
    "exchanges": "ok"
  }
}
```

### Metrics
- Prometheus metrics at `/metrics`
- Grafana dashboards for visualization
- AlertManager for notifications

### Logging
```python
import logging
from src.core.logging_config import setup_logging

setup_logging(
    level="INFO",
    format="json",  # JSON for log aggregation
    output="file",  # or "console", "both"
    filename="logs/sofia.log"
)
```

## Database

### PostgreSQL Schema
```sql
-- Trades table
CREATE TABLE trades (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20),
    side VARCHAR(4),
    price DECIMAL(20, 8),
    amount DECIMAL(20, 8),
    timestamp TIMESTAMPTZ,
    strategy VARCHAR(50)
);

-- Performance metrics
CREATE TABLE metrics (
    id SERIAL PRIMARY KEY,
    date DATE,
    total_return DECIMAL(10, 4),
    sharpe_ratio DECIMAL(10, 4),
    max_drawdown DECIMAL(10, 4)
);
```

### Redis Cache
```python
# Cache configuration
REDIS_CONFIG = {
    "host": "localhost",
    "port": 6379,
    "db": 0,
    "decode_responses": True,
    "socket_timeout": 5,
    "connection_pool_kwargs": {
        "max_connections": 50,
        "retry_on_timeout": True
    }
}
```

## Security

### API Keys Management
```python
# Use environment variables
import os
from cryptography.fernet import Fernet

# Encrypt sensitive data
key = os.getenv("ENCRYPTION_KEY")
f = Fernet(key)
encrypted_api_key = f.encrypt(api_key.encode())

# Store in database
save_encrypted_key(encrypted_api_key)
```

### Rate Limiting
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/hour", "10/minute"]
)
```

## Backup & Recovery

### Automated Backups
```bash
# Daily database backup
pg_dump $DATABASE_URL | gzip > backup_$(date +%Y%m%d).sql.gz

# Upload to S3
aws s3 cp backup_*.sql.gz s3://sofia-backups/

# Retain 30 days
find backups/ -mtime +30 -delete
```

### Disaster Recovery
1. Database replication (primary + standby)
2. Multi-region deployment
3. Automated failover
4. Point-in-time recovery

## Performance Tuning

### Database Optimization
- Index frequently queried columns
- Partition large tables by date
- Vacuum and analyze regularly
- Connection pooling

### Application Optimization
- Async I/O for external calls
- Redis caching for hot data
- Batch processing for bulk operations
- CDN for static assets

## Quick Verify

```powershell
# Check system health
curl http://localhost:8000/health

# Test database connection
python -c "from src.data_hub.database import test_connection; print('DB OK' if test_connection() else 'DB FAIL')"

# Verify Redis cache
python -c "import redis; r = redis.Redis(); r.ping() and print('Redis OK')"

# Check disk space
python -c "import shutil; usage = shutil.disk_usage('/'); print(f'Disk: {usage.used/usage.total*100:.1f}% used')"
```
