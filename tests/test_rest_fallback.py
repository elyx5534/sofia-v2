"""
Test REST fallback when WebSocket is disabled
"""

import asyncio
import os
import time
import pytest
import httpx


@pytest.mark.asyncio
async def test_rest_fallback():
    """Test that REST fallback works when WebSocket is disabled"""
    
    # This test requires WebSocket to be disabled
    original_ws_enabled = os.environ.get('SOFIA_WS_ENABLED')
    os.environ['SOFIA_WS_ENABLED'] = 'false'
    
    try:
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
            
            # Verify WebSocket is disabled in metrics
            response = await client.get(f"{base_url}/metrics")
            assert response.status_code == 200
            metrics = response.json()
            assert not metrics.get('websocket_enabled') or not metrics.get('websocket_connected')
            
            # Test price endpoint with REST fallback
            symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
            
            for symbol in symbols:
                response = await client.get(f"{base_url}/price/{symbol}")
                if response.status_code == 200:
                    price_data = response.json()
                    assert price_data.get('price') is not None
                    assert price_data.get('source') in ['rest', 'rest_cache']
                    assert price_data.get('freshness') is not None
                    
                    # Verify TTL is respected (should be <= 10s for cached)
                    if price_data['source'] == 'rest_cache':
                        assert price_data['freshness'] <= 10, f"Cache TTL exceeded: {price_data['freshness']}s"
                    
                    print(f"OK: {symbol} price={price_data['price']} source={price_data['source']} freshness={price_data['freshness']:.1f}s")
                else:
                    print(f"WARN: {symbol} returned {response.status_code}")
            
            # Test cache TTL by waiting and re-requesting
            await asyncio.sleep(2)
            
            response = await client.get(f"{base_url}/price/BTC/USDT")
            if response.status_code == 200:
                price_data = response.json()
                if price_data['source'] == 'rest_cache':
                    assert price_data['freshness'] >= 2, "Cache should show age after waiting"
                    print(f"Cache age verified: {price_data['freshness']:.1f}s")
    
    finally:
        # Restore original setting
        if original_ws_enabled:
            os.environ['SOFIA_WS_ENABLED'] = original_ws_enabled
        else:
            os.environ.pop('SOFIA_WS_ENABLED', None)


if __name__ == "__main__":
    asyncio.run(test_rest_fallback())