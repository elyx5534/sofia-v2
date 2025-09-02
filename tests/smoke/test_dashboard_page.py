"""
Smoke test for dashboard page
"""

import os
import sys

from fastapi.testclient import TestClient

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


def test_dashboard_page_loads():
    """Test that dashboard page returns 200 and contains expected text"""
    from src.api.main import app

    client = TestClient(app)
    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "Trading Dashboard" in response.text or "Dashboard" in response.text


def test_dashboard_has_live_proof():
    """Test that dashboard contains Live Proof section"""
    from src.api.main import app

    client = TestClient(app)
    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "Live Proof" in response.text or "live-proof" in response.text.lower()


def test_static_files_accessible():
    """Test that static files are served"""
    from src.api.main import app

    client = TestClient(app)

    # Test CSS
    response = client.get("/static/styles.css")
    assert response.status_code == 200
    assert "Sofia V2" in response.text or "css" in response.headers.get("content-type", "").lower()

    # Test JS
    response = client.get("/static/app.js")
    assert response.status_code == 200
    assert (
        "apiFetch" in response.text
        or "javascript" in response.headers.get("content-type", "").lower()
    )


def test_api_health_endpoint():
    """Test that health endpoint is accessible"""
    from src.api.main import app

    client = TestClient(app)
    response = client.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert "status" in data


if __name__ == "__main__":
    test_dashboard_page_loads()
    test_dashboard_has_live_proof()
    test_static_files_accessible()
    test_api_health_endpoint()
    print("Dashboard page tests passed!")
