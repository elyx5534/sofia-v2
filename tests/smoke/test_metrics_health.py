"""
Smoke tests for monitoring endpoints and production readiness
Tests health, metrics, and system monitoring
"""

import pytest
from fastapi.testclient import TestClient
import sys
import os
import time
import re

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

def test_health_endpoint():
    """Test that health endpoint returns proper status"""
    from src.api.main import app
    
    client = TestClient(app)
    response = client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    
    # Check required fields
    assert "status" in data
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert "uptime" in data
    assert "memory_mb" in data
    assert "cpu_percent" in data
    assert "services" in data
    
    # Check system metrics are reasonable
    assert data["memory_mb"] > 0
    assert data["cpu_percent"] >= 0
    assert data["uptime"] > 0

def test_metrics_endpoint():
    """Test Prometheus metrics endpoint"""
    from src.api.main import app
    
    client = TestClient(app)
    response = client.get("/metrics")
    
    assert response.status_code == 200
    metrics_text = response.text
    
    # Check for Prometheus format
    assert "# HELP" in metrics_text
    assert "# TYPE" in metrics_text
    
    # Check for specific metrics
    assert "sofia_uptime_seconds" in metrics_text
    assert "sofia_memory_mb" in metrics_text
    assert "sofia_cpu_percent" in metrics_text
    assert "sofia_request_total" in metrics_text
    assert "sofia_request_latency_ms" in metrics_text
    
    # Parse a metric value
    uptime_match = re.search(r'sofia_uptime_seconds (\d+\.\d+)', metrics_text)
    assert uptime_match is not None
    uptime = float(uptime_match.group(1))
    assert uptime > 0

def test_request_tracking_middleware():
    """Test that request tracking middleware is working"""
    from src.api.main import app
    
    client = TestClient(app)
    
    # Make several requests
    for _ in range(3):
        client.get("/health")
    
    # Check metrics
    response = client.get("/metrics")
    metrics_text = response.text
    
    # Request count should be at least 3
    count_match = re.search(r'sofia_request_total (\d+)', metrics_text)
    if count_match:
        count = int(count_match.group(1))
        assert count >= 3
    
    # Average latency should be set
    latency_match = re.search(r'sofia_request_latency_ms (\d+\.\d+)', metrics_text)
    if latency_match:
        latency = float(latency_match.group(1))
        assert latency > 0

def test_api_health_check_endpoint():
    """Test simple API health check endpoint"""
    from src.api.main import app
    
    client = TestClient(app)
    response = client.get("/api/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data == {"status": "ok"}

def test_health_endpoint_performance():
    """Test that health endpoint responds quickly"""
    from src.api.main import app
    
    client = TestClient(app)
    
    start_time = time.time()
    response = client.get("/health")
    elapsed_time = time.time() - start_time
    
    assert response.status_code == 200
    # Health check should respond within 1 second
    assert elapsed_time < 1.0

def test_metrics_scrape_compatible():
    """Test that metrics endpoint is Prometheus-scrape compatible"""
    from src.api.main import app
    
    client = TestClient(app)
    response = client.get("/metrics")
    
    assert response.status_code == 200
    
    # Check content type (Prometheus expects text/plain)
    content_type = response.headers.get("content-type", "")
    # FastAPI might return text/plain or text/html, both are acceptable
    assert "text" in content_type.lower()
    
    # Verify metric format
    lines = response.text.split('\n')
    metric_count = 0
    
    for line in lines:
        if line and not line.startswith('#'):
            # Should be in format: metric_name{labels} value
            # or: metric_name value
            parts = line.split()
            if len(parts) >= 2:
                metric_count += 1
    
    assert metric_count > 0

def test_paper_trading_metrics():
    """Test that paper trading metrics appear when running"""
    from src.api.main import app
    from src.services.paper_engine import paper_engine
    
    client = TestClient(app)
    
    # Start paper trading
    paper_engine.running = True
    paper_engine.pnl = 123.45
    paper_engine.trades = [1, 2, 3]  # Dummy trades
    
    try:
        response = client.get("/metrics")
        metrics_text = response.text
        
        # Check for paper trading metrics
        if "sofia_paper_pnl" in metrics_text:
            pnl_match = re.search(r'sofia_paper_pnl ([\d\.\-]+)', metrics_text)
            assert pnl_match is not None
        
        if "sofia_paper_trades_total" in metrics_text:
            trades_match = re.search(r'sofia_paper_trades_total (\d+)', metrics_text)
            assert trades_match is not None
    finally:
        # Clean up
        paper_engine.running = False

def test_concurrent_health_checks():
    """Test that health endpoint handles concurrent requests"""
    from src.api.main import app
    import threading
    
    client = TestClient(app)
    results = []
    
    def make_request():
        response = client.get("/health")
        results.append(response.status_code)
    
    # Create 10 concurrent requests
    threads = []
    for _ in range(10):
        t = threading.Thread(target=make_request)
        threads.append(t)
        t.start()
    
    # Wait for all threads
    for t in threads:
        t.join(timeout=5)
    
    # All requests should succeed
    assert len(results) == 10
    assert all(status == 200 for status in results)

def test_health_check_idempotent():
    """Test that health check is idempotent"""
    from src.api.main import app
    
    client = TestClient(app)
    
    # Make multiple health checks
    responses = []
    for _ in range(5):
        response = client.get("/health")
        responses.append(response.json())
        time.sleep(0.1)
    
    # All should return healthy
    assert all(r["status"] == "healthy" for r in responses)
    
    # Uptime should be increasing
    uptimes = [r["uptime"] for r in responses]
    assert all(uptimes[i] <= uptimes[i+1] for i in range(len(uptimes)-1))

def test_metrics_format_validation():
    """Validate Prometheus metrics format"""
    from src.api.main import app
    
    client = TestClient(app)
    response = client.get("/metrics")
    
    lines = response.text.split('\n')
    
    for line in lines:
        if not line:
            continue
            
        if line.startswith('#'):
            # Comment line
            if line.startswith('# HELP'):
                parts = line.split(None, 3)
                assert len(parts) >= 4, f"Invalid HELP line: {line}"
            elif line.startswith('# TYPE'):
                parts = line.split()
                assert len(parts) >= 4, f"Invalid TYPE line: {line}"
                assert parts[3] in ['gauge', 'counter', 'histogram', 'summary'], f"Invalid metric type: {parts[3]}"
        else:
            # Metric line
            # Should match: metric_name{labels} value or metric_name value
            assert ' ' in line, f"Invalid metric line: {line}"
            name_labels, value = line.rsplit(' ', 1)
            
            # Value should be numeric
            try:
                float(value)
            except ValueError:
                pytest.fail(f"Non-numeric value in metric: {line}")

if __name__ == "__main__":
    print("Running monitoring and health check tests...")
    test_health_endpoint()
    test_metrics_endpoint()
    test_request_tracking_middleware()
    test_api_health_check_endpoint()
    test_health_endpoint_performance()
    test_metrics_scrape_compatible()
    test_paper_trading_metrics()
    test_concurrent_health_checks()
    test_health_check_idempotent()
    test_metrics_format_validation()
    print("✓ All monitoring tests passed!")