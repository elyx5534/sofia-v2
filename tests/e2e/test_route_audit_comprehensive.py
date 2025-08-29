#!/usr/bin/env python3
"""
Comprehensive Route Audit E2E Tests
Tests all API endpoints and UI routes for Sofia V2
"""

import pytest
import asyncio
import aiohttp
import time
from typing import List, Dict, Any
import logging
import os

# Configuration
API_BASE_URL = os.getenv('API_BASE_URL', 'http://127.0.0.1:8024')
UI_BASE_URL = os.getenv('UI_BASE_URL', 'http://127.0.0.1:8005')

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RouteAuditor:
    def __init__(self):
        self.api_url = API_BASE_URL
        self.ui_url = UI_BASE_URL
        self.results = []
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def test_api_route(self, method: str, path: str, expected_status: int = 200, data: Dict = None):
        """Test a single API route"""
        url = f"{self.api_url}{path}"
        start_time = time.time()
        
        try:
            if method.upper() == 'GET':
                async with self.session.get(url) as response:
                    status = response.status
                    response_data = await response.json() if response.content_type == 'application/json' else await response.text()
            elif method.upper() == 'POST':
                async with self.session.post(url, json=data or {}) as response:
                    status = response.status
                    response_data = await response.json() if response.content_type == 'application/json' else await response.text()
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            duration = time.time() - start_time
            
            result = {
                'method': method.upper(),
                'path': path,
                'url': url,
                'expected_status': expected_status,
                'actual_status': status,
                'duration_ms': round(duration * 1000, 2),
                'success': status == expected_status,
                'response_size': len(str(response_data)),
                'error': None
            }
            
        except Exception as e:
            duration = time.time() - start_time
            result = {
                'method': method.upper(),
                'path': path,
                'url': url,
                'expected_status': expected_status,
                'actual_status': None,
                'duration_ms': round(duration * 1000, 2),
                'success': False,
                'response_size': 0,
                'error': str(e)
            }
        
        self.results.append(result)
        logger.info(f"{result['method']} {result['path']} - Status: {result['actual_status']} - Duration: {result['duration_ms']}ms - {'✓' if result['success'] else '✗'}")
        return result
    
    async def test_ui_route(self, path: str, expected_status: int = 200):
        """Test a single UI route"""
        url = f"{self.ui_url}{path}"
        start_time = time.time()
        
        try:
            async with self.session.get(url) as response:
                status = response.status
                content = await response.text()
                
            duration = time.time() - start_time
            
            result = {
                'type': 'UI',
                'path': path,
                'url': url,
                'expected_status': expected_status,
                'actual_status': status,
                'duration_ms': round(duration * 1000, 2),
                'success': status == expected_status,
                'response_size': len(content),
                'has_html': '<html' in content.lower(),
                'error': None
            }
            
        except Exception as e:
            duration = time.time() - start_time
            result = {
                'type': 'UI',
                'path': path,
                'url': url,
                'expected_status': expected_status,
                'actual_status': None,
                'duration_ms': round(duration * 1000, 2),
                'success': False,
                'response_size': 0,
                'has_html': False,
                'error': str(e)
            }
        
        self.results.append(result)
        logger.info(f"UI {result['path']} - Status: {result['actual_status']} - Duration: {result['duration_ms']}ms - {'✓' if result['success'] else '✗'}")
        return result

@pytest.mark.asyncio
async def test_api_core_endpoints():
    """Test core API endpoints"""
    async with RouteAuditor() as auditor:
        # Core health and metrics endpoints
        await auditor.test_api_route('GET', '/health', 200)
        await auditor.test_api_route('GET', '/metrics', 200)
        
        # Market data endpoints
        await auditor.test_api_route('GET', '/market/assets/list', 200)
        await auditor.test_api_route('GET', '/market/quotes?symbols=BTCUSDT,ETHUSDT', 200)
        await auditor.test_api_route('GET', '/market/ohlcv?symbol=BTCUSDT&timeframe=1h', 200)
        await auditor.test_api_route('GET', '/symbols', 200)
        await auditor.test_api_route('GET', '/price/BTCUSDT', 200)
        
        # AI endpoints
        await auditor.test_api_route('GET', '/ai/status', 200)
        await auditor.test_api_route('GET', '/ai/models', 200)
        
        # Trading endpoints
        await auditor.test_api_route('GET', '/trade/account', 200)
        await auditor.test_api_route('GET', '/trade/positions', 200)
        await auditor.test_api_route('GET', '/trade/history', 200)
        
        # Check results
        total_tests = len(auditor.results)
        passed_tests = sum(1 for r in auditor.results if r['success'])
        failed_tests = total_tests - passed_tests
        
        logger.info(f"API Core Tests: {passed_tests}/{total_tests} passed, {failed_tests} failed")
        
        # Assert at least 70% pass rate
        assert passed_tests / total_tests >= 0.7, f"API core test pass rate too low: {passed_tests}/{total_tests}"

@pytest.mark.asyncio
async def test_ui_core_routes():
    """Test core UI routes"""
    async with RouteAuditor() as auditor:
        # Main UI routes
        await auditor.test_ui_route('/', 200)
        await auditor.test_ui_route('/dashboard', 200)
        await auditor.test_ui_route('/markets', 200)
        await auditor.test_ui_route('/portfolio', 200)
        await auditor.test_ui_route('/backtest', 200)
        await auditor.test_ui_route('/trading', 200)
        await auditor.test_ui_route('/manual-trading', 200)
        await auditor.test_ui_route('/strategies', 200)
        await auditor.test_ui_route('/reliability', 200)
        await auditor.test_ui_route('/pricing', 200)
        await auditor.test_ui_route('/login', 200)
        
        # Asset detail routes
        await auditor.test_ui_route('/assets/BTCUSDT', 200)
        await auditor.test_ui_route('/assets/ETHUSDT', 200)
        
        # Check results
        total_tests = len(auditor.results)
        passed_tests = sum(1 for r in auditor.results if r['success'])
        failed_tests = total_tests - passed_tests
        
        logger.info(f"UI Core Tests: {passed_tests}/{total_tests} passed, {failed_tests} failed")
        
        # Verify all successful routes return HTML
        html_routes = [r for r in auditor.results if r['success']]
        html_valid = sum(1 for r in html_routes if r.get('has_html', False))
        
        logger.info(f"HTML Validation: {html_valid}/{len(html_routes)} routes returned valid HTML")
        
        # Assert at least 80% pass rate and HTML validity
        assert passed_tests / total_tests >= 0.8, f"UI core test pass rate too low: {passed_tests}/{total_tests}"
        if html_routes:  # Only check HTML if we have successful routes
            assert html_valid / len(html_routes) >= 0.9, f"HTML validity too low: {html_valid}/{len(html_routes)}"

@pytest.mark.asyncio
async def test_api_error_handling():
    """Test API error handling"""
    async with RouteAuditor() as auditor:
        # Test 404 errors
        await auditor.test_api_route('GET', '/nonexistent/endpoint', 404)
        await auditor.test_api_route('GET', '/market/invalid', 404)
        
        # Test invalid parameters
        await auditor.test_api_route('GET', '/market/quotes?symbols=', 422)
        await auditor.test_api_route('GET', '/market/ohlcv?symbol=INVALID', 422)
        
        # Test malformed requests
        await auditor.test_api_route('POST', '/ai/predict', 422, {'invalid': 'data'})
        
        # Check error handling
        error_tests = [r for r in auditor.results if r['expected_status'] >= 400]
        passed_error_tests = sum(1 for r in error_tests if r['success'])
        
        logger.info(f"API Error Handling: {passed_error_tests}/{len(error_tests)} tests passed")
        
        # Assert good error handling
        if error_tests:
            assert passed_error_tests / len(error_tests) >= 0.8, f"API error handling too poor: {passed_error_tests}/{len(error_tests)}"

@pytest.mark.asyncio 
async def test_performance_benchmarks():
    """Test performance benchmarks"""
    async with RouteAuditor() as auditor:
        # Fast endpoints (should respond in < 100ms)
        fast_endpoints = [
            ('GET', '/health'),
            ('GET', '/ai/status'),
            ('GET', '/symbols')
        ]
        
        # Medium endpoints (should respond in < 500ms)
        medium_endpoints = [
            ('GET', '/market/assets/list'),
            ('GET', '/price/BTCUSDT'),
            ('GET', '/trade/account')
        ]
        
        # Slow endpoints (should respond in < 2000ms)
        slow_endpoints = [
            ('GET', '/market/quotes?symbols=BTCUSDT,ETHUSDT'),
            ('GET', '/market/ohlcv?symbol=BTCUSDT&timeframe=1h'),
            ('GET', '/trade/history')
        ]
        
        # Test fast endpoints
        for method, path in fast_endpoints:
            result = await auditor.test_api_route(method, path)
            assert result['duration_ms'] < 100, f"Fast endpoint {path} too slow: {result['duration_ms']}ms"
        
        # Test medium endpoints
        for method, path in medium_endpoints:
            result = await auditor.test_api_route(method, path)
            assert result['duration_ms'] < 500, f"Medium endpoint {path} too slow: {result['duration_ms']}ms"
        
        # Test slow endpoints (more lenient)
        for method, path in slow_endpoints:
            result = await auditor.test_api_route(method, path)
            if result['success']:  # Only check timing if request succeeded
                assert result['duration_ms'] < 2000, f"Slow endpoint {path} too slow: {result['duration_ms']}ms"
        
        logger.info("Performance benchmarks completed")

@pytest.mark.asyncio
async def test_full_route_audit():
    """Comprehensive route audit test"""
    async with RouteAuditor() as auditor:
        # Run all previous tests
        await test_api_core_endpoints()
        await test_ui_core_routes()
        await test_api_error_handling()
        
        # Generate summary report
        total_tests = len(auditor.results)
        passed_tests = sum(1 for r in auditor.results if r['success'])
        failed_tests = total_tests - passed_tests
        avg_response_time = sum(r['duration_ms'] for r in auditor.results) / total_tests if total_tests > 0 else 0
        
        logger.info("=" * 60)
        logger.info("ROUTE AUDIT SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total Tests: {total_tests}")
        logger.info(f"Passed: {passed_tests}")
        logger.info(f"Failed: {failed_tests}")
        logger.info(f"Pass Rate: {passed_tests/total_tests*100:.1f}%")
        logger.info(f"Average Response Time: {avg_response_time:.1f}ms")
        logger.info("=" * 60)
        
        # Log failed tests
        failed_results = [r for r in auditor.results if not r['success']]
        if failed_results:
            logger.warning("FAILED TESTS:")
            for result in failed_results:
                logger.warning(f"  {result.get('method', 'UI')} {result['path']} - {result.get('error', 'Status: ' + str(result['actual_status']))}")
        
        # Final assertion
        assert passed_tests / total_tests >= 0.75, f"Overall pass rate too low: {passed_tests}/{total_tests} ({passed_tests/total_tests*100:.1f}%)"

if __name__ == "__main__":
    # Run tests directly
    asyncio.run(test_full_route_audit())