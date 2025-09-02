"""Tests for the health endpoint."""

import pytest
from fastapi.testclient import TestClient
from src.data_hub.api import app
from src.data_hub.settings import settings


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


def test_health_endpoint_returns_200(client):
    """Test that health endpoint returns 200 status."""
    response = client.get("/health")
    assert response.status_code == 200


def test_health_endpoint_payload(client):
    """Test health endpoint response payload."""
    response = client.get("/health")
    data = response.json()

    assert "status" in data
    assert data["status"] == "healthy"

    assert "timestamp" in data
    assert "version" in data
    assert data["version"] == settings.api_version


def test_health_endpoint_content_type(client):
    """Test that health endpoint returns JSON."""
    response = client.get("/health")
    assert "application/json" in response.headers["content-type"]


def test_root_endpoint(client):
    """Test root endpoint returns API information."""
    response = client.get("/")
    assert response.status_code == 200

    data = response.json()
    assert "title" in data
    assert "version" in data
    assert "endpoints" in data
    assert "/health" in data["endpoints"]
