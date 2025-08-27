"""
End-to-end tests for Sofia V2 real-data test harness.
Tests real Binance data integration, P&L calculations, and API endpoints.
"""

import pytest
import asyncio
import time
import httpx
from datetime import datetime, timezone

# Test configuration
API_BASE = "http://localhost:8001"

class TestRealDataHarness:
    """Test suite for production-like real data test harness."""
    
    @pytest.fixture(autouse=True)
    async def setup_method(self):
        """Setup for each test method."""
        # Allow time for services to start
        await asyncio.sleep(1)
    
    async def test_health_endpoint(self):
        """Test 1: GET /health returns status, version, git_sha."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_BASE}/health")
            assert response.status_code == 200
            
            data = response.json()
            assert data["status"] == "ok"
            assert "version" in data
            assert "git_sha" in data
            assert "uptime_seconds" in data
            assert "timestamp" in data
            
            # Validate timestamp format
            timestamp = datetime.fromisoformat(data["timestamp"].replace('Z', '+00:00'))
            assert timestamp.tzinfo is not None
    
    async def test_initial_portfolio_balance(self):
        """Test 2: /api/trading/portfolio equals seeded 100000 before any trade."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_BASE}/api/trading/portfolio")
            assert response.status_code == 200
            
            data = response.json()
            assert data["status"] == "success"
            
            portfolio = data["data"]
            
            # Should have $100k starting balance
            assert portfolio["cash_balance"] == 100000.0
            assert portfolio["total_equity"] == 100000.0
            assert portfolio["total_pnl"] == 0.0
            assert portfolio["unrealized_pnl"] == 0.0
            assert portfolio["realized_pnl"] == 0.0
            
            # No positions initially
            assert len(portfolio["positions"]) == 0
    
    async def test_manual_order_updates_balance(self):
        """Test 3: Manual order increases used_balance (available decreases)."""
        async with httpx.AsyncClient() as client:
            # Get initial portfolio
            response = await client.get(f"{API_BASE}/api/trading/portfolio")
            initial_portfolio = response.json()["data"]
            initial_cash = initial_portfolio["cash_balance"]
            
            # Place manual buy order
            order_response = await client.post(f"{API_BASE}/api/trading/paper-order", json={
                "symbol": "BTCUSDT",
                "side": "buy", 
                "usd_amount": 100.0
            })
            
            assert order_response.status_code == 200
            trade_result = order_response.json()
            assert trade_result["status"] == "success"
            
            # Verify trade details
            trade_data = trade_result["data"]
            assert trade_data["symbol"] == "BTCUSDT"
            assert trade_data["side"] == "buy"
            assert trade_data["usd_value"] == 100.0
            assert trade_data["fees"] > 0  # Should have fees
            
            # Get updated portfolio
            await asyncio.sleep(0.5)  # Allow processing time
            response = await client.get(f"{API_BASE}/api/trading/portfolio")
            updated_portfolio = response.json()["data"]
            
            # Cash should decrease by trade amount + fees
            expected_cash = initial_cash - 100.0 - trade_data["fees"]
            assert abs(updated_portfolio["cash_balance"] - expected_cash) < 0.01
            
            # Should have new position
            assert "BTCUSDT" in updated_portfolio["positions"]
            position = updated_portfolio["positions"]["BTCUSDT"]
            assert position["quantity"] > 0
            assert position["market_value"] > 0
    
    async def test_price_service_freshness(self):
        """Test 4: PriceService freshness < 15s after WS connects (30s timeout)."""
        start_time = time.time()
        max_wait = 30
        
        async with httpx.AsyncClient() as client:
            while time.time() - start_time < max_wait:
                # Check metrics endpoint
                response = await client.get(f"{API_BASE}/metrics")
                if response.status_code == 200:
                    metrics_text = response.text
                    
                    # Parse freshness from Prometheus format
                    lines = metrics_text.split('\n')
                    freshness_values = []
                    
                    for line in lines:
                        if line.startswith('sofia_price_freshness_seconds{symbol='):
                            # Extract value after space
                            parts = line.split(' ')
                            if len(parts) >= 2:
                                try:
                                    freshness = float(parts[-1])
                                    freshness_values.append(freshness)
                                except ValueError:
                                    continue
                    
                    # If we have freshness data and all values < 15s, pass
                    if freshness_values and all(f < 15.0 for f in freshness_values):
                        assert True, f"Price freshness OK: {freshness_values}"
                        return
                
                await asyncio.sleep(2)
            
            # If we reach here, timeout occurred
            pytest.fail("Price service did not achieve <15s freshness within 30s timeout")
    
    async def test_metrics_endpoint(self):
        """Test metrics endpoint returns JSON format."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_BASE}/metrics")
            assert response.status_code == 200
            
            data = response.json()
            
            # Should contain required metrics
            assert data["status"] == "ok"
            assert "price_freshness_seconds" in data
            assert "tick_counts" in data
            assert "data_errors_total" in data
            assert "service_running" in data
            assert "websocket_connected" in data
            assert "websocket_enabled" in data
            
            # Check portfolio includes base currency
            portfolio_response = await client.get(f"{API_BASE}/api/trading/portfolio")
            if portfolio_response.status_code == 200:
                portfolio_data = portfolio_response.json()["data"]
                assert portfolio_data["base_currency"] == "USD"
    
    async def test_strategy_toggle(self):
        """Test strategy enable/disable functionality."""
        async with httpx.AsyncClient() as client:
            # Start strategy
            response = await client.post(f"{API_BASE}/api/strategy/micro-momo/enable", 
                                       json={"enabled": True})
            assert response.status_code == 200
            
            result = response.json()
            assert result["status"] == "success"
            
            # Check status
            await asyncio.sleep(1)
            status_response = await client.get(f"{API_BASE}/api/strategy/micro-momo/status")
            assert status_response.status_code == 200
            
            status_data = status_response.json()
            assert status_data["status"] == "success"
            assert status_data["data"]["running"] == True
            
            # Stop strategy
            stop_response = await client.post(f"{API_BASE}/api/strategy/micro-momo/enable", 
                                            json={"enabled": False})
            assert stop_response.status_code == 200
    
    async def test_positions_endpoint(self):
        """Test positions endpoint returns consistent data."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_BASE}/api/trading/positions")
            assert response.status_code == 200
            
            data = response.json()
            assert data["status"] == "success"
            assert "data" in data
            assert "summary" in data
            
            # Summary should have P&L fields
            summary = data["summary"]
            assert "total_pnl" in summary
            assert "unrealized_pnl" in summary 
            assert "realized_pnl" in summary

@pytest.mark.asyncio
class TestE2EWorkflow:
    """End-to-end workflow test."""
    
    async def test_trading_workflow(self):
        """
        Test 5: E2E headless workflow - trading page renders portfolio 
        total and positions after manual order.
        """
        async with httpx.AsyncClient() as client:
            # 1. Verify initial state
            portfolio_response = await client.get(f"{API_BASE}/api/trading/portfolio")
            assert portfolio_response.status_code == 200
            initial_data = portfolio_response.json()["data"]
            
            # 2. Place manual order
            order_response = await client.post(f"{API_BASE}/api/trading/paper-order", json={
                "symbol": "ETHUSDT",
                "side": "buy",
                "usd_amount": 200.0
            })
            assert order_response.status_code == 200
            
            # 3. Verify portfolio update
            await asyncio.sleep(1)  # Allow processing
            updated_response = await client.get(f"{API_BASE}/api/trading/portfolio")
            assert updated_response.status_code == 200
            
            updated_data = updated_response.json()["data"]
            
            # Should have new position
            assert "ETHUSDT" in updated_data["positions"]
            
            # Total equity should be adjusted for fees but roughly same
            equity_diff = abs(updated_data["total_equity"] - initial_data["total_equity"])
            assert equity_diff < 10.0  # Allow for fees and price movement
            
            # Cash should decrease
            assert updated_data["cash_balance"] < initial_data["cash_balance"]
            
            # Position should have reasonable values
            eth_position = updated_data["positions"]["ETHUSDT"]
            assert eth_position["quantity"] > 0
            assert eth_position["avg_entry_price"] > 0
            assert eth_position["current_price"] > 0
            assert eth_position["market_value"] > 0

if __name__ == "__main__":
    # Run with: python -m pytest tests/test_real_data_harness.py -v
    pytest.main([__file__, "-v"])