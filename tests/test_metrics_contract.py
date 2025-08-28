"""
Test metrics endpoint contract
"""

import asyncio
import pytest
import httpx


@pytest.mark.asyncio
async def test_metrics_contract():
    """Test that /metrics endpoint has required fields"""
    
    base_url = "http://localhost:8001"
    
    async with httpx.AsyncClient() as client:
        # Wait for service to be ready
        max_retries = 10
        for _ in range(max_retries):
            try:
                response = await client.get(f"{base_url}/health")
                if response.status_code == 200:
                    break
            except:
                pass
            await asyncio.sleep(1)
        
        # Get metrics
        response = await client.get(f"{base_url}/metrics")
        assert response.status_code == 200, f"Metrics endpoint returned {response.status_code}"
        
        metrics = response.json()
        
        # Check required fields
        required_fields = [
            'websocket_enabled',
            'websocket_connected',
            'ws_last_connect_ts',
            'stale_symbols',
            'cache_ttl',
            'rest_timeout'
        ]
        
        for field in required_fields:
            assert field in metrics, f"Metrics missing required field: {field}"
            print(f"OK: {field} = {metrics[field]}")
        
        # Check field types
        assert isinstance(metrics['websocket_enabled'], bool)
        assert isinstance(metrics['websocket_connected'], bool)
        assert isinstance(metrics['ws_last_connect_ts'], (int, float))
        assert isinstance(metrics['stale_symbols'], list)
        assert isinstance(metrics['cache_ttl'], (int, float))
        assert isinstance(metrics['rest_timeout'], (int, float))
        
        # If WebSocket is enabled, check additional fields
        if metrics['websocket_enabled']:
            assert 'websocket_metrics' in metrics
            ws_metrics = metrics['websocket_metrics']
            assert 'connected' in ws_metrics
            assert 'error_count' in ws_metrics
            print(f"WebSocket metrics present: connected={ws_metrics['connected']}")
        
        print("\nMetrics contract test passed!")


if __name__ == "__main__":
    asyncio.run(test_metrics_contract())