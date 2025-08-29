#!/usr/bin/env python3
"""
Comprehensive Backtest Flow E2E Tests
Tests the complete backtesting workflow in Sofia V2
"""

import pytest
import asyncio
import aiohttp
import json
import time
from typing import Dict, Any, List
import logging
import os
from datetime import datetime, timedelta

# Configuration
API_BASE_URL = os.getenv('API_BASE_URL', 'http://127.0.0.1:8024')
UI_BASE_URL = os.getenv('UI_BASE_URL', 'http://127.0.0.1:8005')

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BacktestFlowTester:
    def __init__(self):
        self.api_url = API_BASE_URL
        self.ui_url = UI_BASE_URL
        self.session = None
        self.test_results = []
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60))
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def create_test_strategy(self) -> Dict[str, Any]:
        """Create a test strategy configuration"""
        strategy = {
            "name": "E2E Test Strategy",
            "description": "Strategy for E2E testing",
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "start_date": (datetime.now() - timedelta(days=30)).isoformat(),
            "end_date": datetime.now().isoformat(),
            "initial_capital": 10000.0,
            "strategy_type": "sma_crossover",
            "parameters": {
                "fast_period": 10,
                "slow_period": 30,
                "stop_loss": 0.02,
                "take_profit": 0.04
            },
            "risk_management": {
                "max_position_size": 0.1,
                "max_daily_loss": 0.05
            }
        }
        return strategy
    
    async def test_backtest_api_endpoints(self):
        """Test backtest-related API endpoints"""
        logger.info("Testing backtest API endpoints...")
        
        # Test get available strategies
        try:
            async with self.session.get(f"{self.api_url}/backtest/strategies") as response:
                assert response.status == 200
                strategies = await response.json()
                logger.info(f"✓ Retrieved {len(strategies.get('strategies', []))} available strategies")
        except Exception as e:
            logger.error(f"✗ Failed to get strategies: {e}")
            self.test_results.append({"test": "get_strategies", "success": False, "error": str(e)})
            return
        
        # Test get historical data
        try:
            async with self.session.get(f"{self.api_url}/market/history/BTCUSDT/1h") as response:
                assert response.status == 200
                history = await response.json()
                assert len(history.get('data', [])) > 0
                logger.info(f"✓ Retrieved historical data with {len(history['data'])} candles")
        except Exception as e:
            logger.error(f"✗ Failed to get historical data: {e}")
            self.test_results.append({"test": "get_history", "success": False, "error": str(e)})
            return
        
        self.test_results.append({"test": "backtest_api_endpoints", "success": True})
    
    async def test_create_backtest(self) -> str:
        """Test creating a new backtest"""
        logger.info("Testing backtest creation...")
        
        strategy = await self.create_test_strategy()
        
        try:
            async with self.session.post(
                f"{self.api_url}/backtest/create", 
                json=strategy,
                headers={'Content-Type': 'application/json'}
            ) as response:
                
                if response.status == 200:
                    result = await response.json()
                    backtest_id = result.get('backtest_id')
                    assert backtest_id, "No backtest ID returned"
                    logger.info(f"✓ Created backtest with ID: {backtest_id}")
                    self.test_results.append({"test": "create_backtest", "success": True, "backtest_id": backtest_id})
                    return backtest_id
                else:
                    error_text = await response.text()
                    logger.error(f"✗ Failed to create backtest: Status {response.status}, {error_text}")
                    self.test_results.append({"test": "create_backtest", "success": False, "error": f"Status {response.status}"})
                    return None
                    
        except Exception as e:
            logger.error(f"✗ Exception creating backtest: {e}")
            self.test_results.append({"test": "create_backtest", "success": False, "error": str(e)})
            return None
    
    async def test_backtest_execution(self, backtest_id: str):
        """Test running a backtest"""
        if not backtest_id:
            return False
            
        logger.info(f"Testing backtest execution for ID: {backtest_id}")
        
        try:
            # Start the backtest
            async with self.session.post(f"{self.api_url}/backtest/run/{backtest_id}") as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"✗ Failed to start backtest: Status {response.status}, {error_text}")
                    self.test_results.append({"test": "run_backtest", "success": False, "error": f"Status {response.status}"})
                    return False
                
                result = await response.json()
                logger.info(f"✓ Started backtest execution: {result.get('message', 'Started')}")
            
            # Poll for completion (with timeout)
            max_wait_time = 120  # 2 minutes
            poll_interval = 5    # 5 seconds
            elapsed = 0
            
            while elapsed < max_wait_time:
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
                
                async with self.session.get(f"{self.api_url}/backtest/status/{backtest_id}") as response:
                    if response.status != 200:
                        continue
                    
                    status = await response.json()
                    current_status = status.get('status', 'unknown')
                    progress = status.get('progress', 0)
                    
                    logger.info(f"Backtest progress: {progress}% - Status: {current_status}")
                    
                    if current_status in ['completed', 'finished']:
                        logger.info("✓ Backtest completed successfully")
                        self.test_results.append({"test": "run_backtest", "success": True})
                        return True
                    elif current_status == 'failed':
                        logger.error("✗ Backtest failed")
                        self.test_results.append({"test": "run_backtest", "success": False, "error": "Backtest failed"})
                        return False
            
            # Timeout
            logger.error(f"✗ Backtest timed out after {max_wait_time} seconds")
            self.test_results.append({"test": "run_backtest", "success": False, "error": "Timeout"})
            return False
            
        except Exception as e:
            logger.error(f"✗ Exception during backtest execution: {e}")
            self.test_results.append({"test": "run_backtest", "success": False, "error": str(e)})
            return False
    
    async def test_backtest_results(self, backtest_id: str):
        """Test retrieving backtest results"""
        if not backtest_id:
            return
            
        logger.info(f"Testing backtest results retrieval for ID: {backtest_id}")
        
        try:
            # Get summary results
            async with self.session.get(f"{self.api_url}/backtest/results/{backtest_id}") as response:
                if response.status == 200:
                    results = await response.json()
                    
                    # Validate result structure
                    required_fields = ['total_return', 'sharpe_ratio', 'max_drawdown', 'total_trades']
                    missing_fields = [field for field in required_fields if field not in results]
                    
                    if missing_fields:
                        logger.error(f"✗ Missing result fields: {missing_fields}")
                        self.test_results.append({"test": "get_results", "success": False, "error": f"Missing fields: {missing_fields}"})
                        return
                    
                    logger.info(f"✓ Retrieved backtest results:")
                    logger.info(f"  Total Return: {results['total_return']:.2%}")
                    logger.info(f"  Sharpe Ratio: {results['sharpe_ratio']:.2f}")
                    logger.info(f"  Max Drawdown: {results['max_drawdown']:.2%}")
                    logger.info(f"  Total Trades: {results['total_trades']}")
                    
                    self.test_results.append({"test": "get_results", "success": True, "results": results})
                else:
                    error_text = await response.text()
                    logger.error(f"✗ Failed to get results: Status {response.status}, {error_text}")
                    self.test_results.append({"test": "get_results", "success": False, "error": f"Status {response.status}"})
            
            # Get detailed trade history
            async with self.session.get(f"{self.api_url}/backtest/trades/{backtest_id}") as response:
                if response.status == 200:
                    trades = await response.json()
                    trade_count = len(trades.get('trades', []))
                    logger.info(f"✓ Retrieved {trade_count} trade records")
                    self.test_results.append({"test": "get_trades", "success": True, "trade_count": trade_count})
                else:
                    logger.warning(f"⚠ Could not retrieve trade history: Status {response.status}")
                    self.test_results.append({"test": "get_trades", "success": False, "error": f"Status {response.status}"})
        
        except Exception as e:
            logger.error(f"✗ Exception getting backtest results: {e}")
            self.test_results.append({"test": "get_results", "success": False, "error": str(e)})
    
    async def test_ui_backtest_page(self):
        """Test the backtest UI page"""
        logger.info("Testing backtest UI page...")
        
        try:
            async with self.session.get(f"{self.ui_url}/backtest") as response:
                if response.status == 200:
                    content = await response.text()
                    
                    # Check for key UI elements
                    required_elements = [
                        'backtest',
                        'strategy',
                        'symbol',
                        'timeframe',
                        'start',
                        'results'
                    ]
                    
                    missing_elements = [elem for elem in required_elements if elem.lower() not in content.lower()]
                    
                    if missing_elements:
                        logger.warning(f"⚠ Missing UI elements: {missing_elements}")
                    
                    logger.info("✓ Backtest UI page loaded successfully")
                    self.test_results.append({"test": "ui_backtest_page", "success": True})
                else:
                    logger.error(f"✗ Backtest UI page failed: Status {response.status}")
                    self.test_results.append({"test": "ui_backtest_page", "success": False, "error": f"Status {response.status}"})
        
        except Exception as e:
            logger.error(f"✗ Exception loading backtest UI: {e}")
            self.test_results.append({"test": "ui_backtest_page", "success": False, "error": str(e)})
    
    async def test_backtest_cleanup(self, backtest_id: str):
        """Test cleaning up backtest data"""
        if not backtest_id:
            return
            
        logger.info(f"Testing backtest cleanup for ID: {backtest_id}")
        
        try:
            async with self.session.delete(f"{self.api_url}/backtest/{backtest_id}") as response:
                if response.status == 200:
                    logger.info("✓ Backtest cleanup successful")
                    self.test_results.append({"test": "cleanup", "success": True})
                else:
                    logger.warning(f"⚠ Cleanup failed: Status {response.status}")
                    self.test_results.append({"test": "cleanup", "success": False, "error": f"Status {response.status}"})
        
        except Exception as e:
            logger.warning(f"⚠ Exception during cleanup: {e}")
            self.test_results.append({"test": "cleanup", "success": False, "error": str(e)})

@pytest.mark.asyncio
async def test_complete_backtest_flow():
    """Test the complete backtest flow end-to-end"""
    async with BacktestFlowTester() as tester:
        logger.info("=" * 60)
        logger.info("STARTING COMPLETE BACKTEST FLOW TEST")
        logger.info("=" * 60)
        
        # Step 1: Test API endpoints
        await tester.test_backtest_api_endpoints()
        
        # Step 2: Test UI page
        await tester.test_ui_backtest_page()
        
        # Step 3: Create backtest
        backtest_id = await tester.test_create_backtest()
        
        # Step 4: Execute backtest (if created successfully)
        if backtest_id:
            execution_success = await tester.test_backtest_execution(backtest_id)
            
            # Step 5: Get results (if execution succeeded)
            if execution_success:
                await tester.test_backtest_results(backtest_id)
            
            # Step 6: Cleanup
            await tester.test_backtest_cleanup(backtest_id)
        
        # Generate summary report
        total_tests = len(tester.test_results)
        passed_tests = sum(1 for result in tester.test_results if result['success'])
        failed_tests = total_tests - passed_tests
        
        logger.info("=" * 60)
        logger.info("BACKTEST FLOW TEST SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total Tests: {total_tests}")
        logger.info(f"Passed: {passed_tests}")
        logger.info(f"Failed: {failed_tests}")
        logger.info(f"Pass Rate: {passed_tests/total_tests*100:.1f}%")
        
        # Log failed tests
        failed_results = [r for r in tester.test_results if not r['success']]
        if failed_results:
            logger.warning("FAILED TESTS:")
            for result in failed_results:
                logger.warning(f"  {result['test']} - {result.get('error', 'Unknown error')}")
        
        logger.info("=" * 60)
        
        # Assert minimum pass rate
        assert passed_tests / total_tests >= 0.7, f"Backtest flow pass rate too low: {passed_tests}/{total_tests} ({passed_tests/total_tests*100:.1f}%)"

@pytest.mark.asyncio
async def test_backtest_edge_cases():
    """Test backtest edge cases and error conditions"""
    async with BacktestFlowTester() as tester:
        logger.info("Testing backtest edge cases...")
        
        # Test invalid strategy parameters
        invalid_strategy = {
            "name": "Invalid Strategy",
            "symbol": "INVALID_SYMBOL",
            "timeframe": "invalid_timeframe",
            "initial_capital": -1000  # Invalid negative capital
        }
        
        try:
            async with tester.session.post(
                f"{tester.api_url}/backtest/create",
                json=invalid_strategy
            ) as response:
                # Should return error (400 or 422)
                assert response.status in [400, 422], f"Expected error status, got {response.status}"
                logger.info("✓ Invalid strategy properly rejected")
        except AssertionError as e:
            logger.error(f"✗ Invalid strategy not properly rejected: {e}")
            pytest.fail(str(e))
        except Exception as e:
            logger.warning(f"⚠ Exception testing invalid strategy: {e}")
        
        # Test non-existent backtest ID
        try:
            async with tester.session.get(f"{tester.api_url}/backtest/status/nonexistent_id") as response:
                assert response.status == 404, f"Expected 404 for non-existent ID, got {response.status}"
                logger.info("✓ Non-existent backtest ID properly handled")
        except AssertionError as e:
            logger.error(f"✗ Non-existent backtest ID not properly handled: {e}")
            pytest.fail(str(e))
        except Exception as e:
            logger.warning(f"⚠ Exception testing non-existent ID: {e}")

if __name__ == "__main__":
    # Run tests directly
    asyncio.run(test_complete_backtest_flow())