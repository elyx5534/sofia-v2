# 👥 Sofia V2 - Friend Development Tasks

## 🎯 **Your Mission: Platform Infrastructure & Production Ready**

While your friend focuses on monetization, you'll make Sofia V2 production-ready and scalable.

## ⏰ **Priority Tasks (4-6 hours)**

### **🚀 Task 1: Cloud Deployment Setup (2 hours)**

#### 1.1 Heroku Deployment
```bash
# Install Heroku CLI
# https://devcenter.heroku.com/articles/heroku-cli

# Login and create app
heroku login
heroku create sofia-v2-production

# Add PostgreSQL addon
heroku addons:create heroku-postgresql:mini

# Set environment variables
heroku config:set DATABASE_URL=your_postgres_url
heroku config:set ENVIRONMENT=production
heroku config:set SECRET_KEY=generate_random_secret
```

#### 1.2 Create Procfile
```bash
# Create Procfile in root directory
echo "web: cd sofia_ui && python -m uvicorn server:app --host=0.0.0.0 --port=\$PORT" > Procfile
```

#### 1.3 Update requirements.txt
```bash
# Add production dependencies
echo "psycopg2-binary==2.9.7" >> requirements.txt
echo "gunicorn==21.2.0" >> requirements.txt
```

---

### **🗄️ Task 2: Database Migration (1.5 hours)**

#### 2.1 PostgreSQL Setup
```python
# Update src/data_hub/settings.py
import os
from urllib.parse import urlparse

if os.getenv('DATABASE_URL'):
    url = urlparse(os.getenv('DATABASE_URL'))
    DATABASE_CONFIG = {
        'host': url.hostname,
        'database': url.path[1:],
        'user': url.username,
        'password': url.password,
        'port': url.port,
    }
else:
    DATABASE_CONFIG = {
        'host': 'localhost',
        'database': 'sofia_dev',
        'user': 'postgres',
        'password': 'password',
        'port': 5432,
    }
```

#### 2.2 Migration Scripts
Create migration system for database schema updates.

---

### **📊 Task 3: Performance Monitoring (1 hour)**

#### 3.1 Add Prometheus Metrics
```python
# Add to sofia_ui/server.py
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

# Metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint'])
REQUEST_LATENCY = Histogram('http_request_duration_seconds', 'HTTP request latency')

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    REQUEST_COUNT.labels(method=request.method, endpoint=request.url.path).inc()
    REQUEST_LATENCY.observe(time.time() - start_time)
    return response

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

#### 3.2 Health Checks
```python
@app.get("/health/detailed")
async def detailed_health():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "database": "connected",
        "cache": "operational", 
        "memory_usage": psutil.virtual_memory().percent,
        "disk_usage": psutil.disk_usage('/').percent,
        "uptime": time.time() - start_time
    }
```

---

### **🔒 Task 4: Security Hardening (1 hour)**

#### 4.1 Security Headers
```python
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

# Add security middleware
if os.getenv('ENVIRONMENT') == 'production':
    app.add_middleware(HTTPSRedirectMiddleware)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["sofia-v2.com", "*.sofia-v2.com"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://sofia-v2.com"] if os.getenv('ENVIRONMENT') == 'production' else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

#### 4.2 Rate Limiting
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get("/api/backtest")
@limiter.limit("10/minute")
async def limited_backtest(request: Request):
    # Your backtest logic
    pass
```

---

### **⚡ Task 5: Performance Optimization (0.5 hours)**

#### 5.1 Database Connection Pooling
```python
from sqlalchemy.pool import QueuePool
from sqlalchemy import create_engine

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=0,
    pool_pre_ping=True,
    pool_recycle=300,
)
```

#### 5.2 Response Caching
```python
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend

@app.on_event("startup")
async def startup():
    redis = aioredis.from_url("redis://localhost", encoding="utf8", decode_responses=True)
    FastAPICache.init(RedisBackend(redis), prefix="fastapi-cache")

@app.get("/api/crypto-prices")
@cache(expire=60)  # Cache for 60 seconds
async def cached_crypto_prices():
    # Your logic here
    pass
```

---

## **🧪 Task 6: Testing & Quality (Optional - if time permits)**

### Load Testing
```bash
# Install locust
pip install locust

# Create locustfile.py
# Run load tests
locust -f locustfile.py --host=http://localhost:8000
```

### Integration Tests
```python
# tests/test_integration.py
import pytest
import asyncio
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_full_backtest_flow():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/api/backtest", json={
            "symbol": "BTC-USD",
            "strategy": "sma_cross"
        })
        assert response.status_code == 200
        assert "results" in response.json()
```

---

## **📱 Bonus Task: Mobile API Preparation**

### API Versioning
```python
from fastapi import APIRouter

v1_router = APIRouter(prefix="/api/v1")
v2_router = APIRouter(prefix="/api/v2")

@v1_router.get("/backtest")
async def backtest_v1():
    # Legacy API
    pass

@v2_router.get("/backtest") 
async def backtest_v2():
    # New API with enhanced features
    pass
```

---

## **✅ Checklist - Mark completed tasks:**

- [ ] **Cloud Deployment**: Heroku app created and configured
- [ ] **Database**: PostgreSQL migration completed  
- [ ] **Monitoring**: Metrics and health checks added
- [ ] **Security**: HTTPS, rate limiting, security headers
- [ ] **Performance**: Caching and connection pooling
- [ ] **Testing**: Load tests and integration tests
- [ ] **Documentation**: Deployment guide updated

---

## **🔄 After Completion:**

1. **Test Production Deploy**: Ensure everything works in cloud
2. **Performance Benchmarks**: Document response times and limits
3. **Security Scan**: Run basic security tests
4. **Monitoring Setup**: Configure alerts and dashboards

---

## **🆘 Need Help?**

- **Heroku Issues**: Check Heroku logs with `heroku logs --tail`
- **Database Problems**: Use `heroku pg:psql` for direct database access
- **Performance Issues**: Use `/metrics` endpoint to monitor
- **Security Questions**: Check OWASP guidelines

**Communication**: Update in our shared channel when each task is complete!

---

**Target**: Production-ready Sofia V2 that can handle real users and scale! 🚀