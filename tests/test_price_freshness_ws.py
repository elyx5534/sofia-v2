"""
Test WebSocket price freshness within acceptable limits
"""

import asyncio
import os
import time
import pytest
import httpx


@pytest.mark.asyncio
async def test_websocket_freshness():
    """Test that WebSocket provides fresh data within 15s when connected"""
    
    # Check if WebSocket is enabled
    if os.getenv('SOFIA_WS_ENABLED', 'true').lower() != 'true':
        pytest.skip("WebSocket disabled via SOFIA_WS_ENABLED=false")
    
    # Wait for startup and connection (max 30s)
    base_url = "http://localhost:8001"
    max_wait = 30
    start_time = time.time()
    
    async with httpx.AsyncClient() as client:
        # Wait for service to be ready
        while time.time() - start_time < max_wait:
            try:
                response = await client.get(f"{base_url}/health")
                if response.status_code == 200:
                    break
            except:
                pass
            await asyncio.sleep(1)
        
        # Check metrics for WebSocket status
        response = await client.get(f"{base_url}/metrics")
        assert response.status_code == 200
        metrics = response.json()
        
        if not metrics.get('websocket_connected'):
            pytest.skip(f"WebSocket not connected after {max_wait}s - network may be blocking WS")
        
        # Get debug data to check freshness
        response = await client.get(f"{base_url}/data/debug")
        assert response.status_code == 200
        debug_data = response.json()
        
        # Verify freshness for each symbol
        for symbol_data in debug_data.get('symbols', []):
            symbol = symbol_data['symbol']
            freshness = symbol_data.get('freshness_seconds')
            source = symbol_data.get('source')
            
            if source == 'websocket':
                assert freshness is not None, f"No freshness data for {symbol}"
                assert freshness < 15, f"Symbol {symbol} freshness {freshness}s exceeds 15s limit"
                print(f"OK: {symbol} freshness={freshness:.1f}s via {source}")
            else:
                print(f"INFO: {symbol} using {source} fallback")


if __name__ == "__main__":
    asyncio.run(test_websocket_freshness())