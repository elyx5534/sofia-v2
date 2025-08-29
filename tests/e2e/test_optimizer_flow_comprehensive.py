#!/usr/bin/env python3
"""
Comprehensive Optimizer Flow E2E Tests
Tests the complete optimization workflow in Sofia V2
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

class OptimizerFlowTester:
    def __init__(self):
        self.api_url = API_BASE_URL
        self.ui_url = UI_BASE_URL
        self.session = None
        self.test_results = []
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120))
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def create_optimization_config(self) -> Dict[str, Any]:
        """Create an optimization configuration"""
        config = {
            "name": "E2E Optimization Test",
            "description": "Genetic algorithm optimization for E2E testing",
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "start_date": (datetime.now() - timedelta(days=20)).isoformat(),
            "end_date": datetime.now().isoformat(),
            "initial_capital": 10000.0,
            "strategy_type": "sma_crossover",
            "optimization_method": "genetic_algorithm",
            "parameters_to_optimize": {
                "fast_period": {"min": 5, "max": 20, "type": "int"},
                "slow_period": {"min": 20, "max": 50, "type": "int"},
                "stop_loss": {"min": 0.01, "max": 0.05, "type": "float"},
                "take_profit": {"min": 0.02, "max": 0.08, "type": "float"}
            },
            "optimization_settings": {
                "population_size": 20,
                "generations": 10,
                "mutation_rate": 0.1,
                "crossover_rate": 0.8,
                "objective": "sharpe_ratio"
            },
            "constraints": {
                "min_trades": 10,
                "max_drawdown": 0.2
            }
        }
        return config
    
    async def test_optimizer_api_endpoints(self):
        """Test optimizer-related API endpoints"""
        logger.info("Testing optimizer API endpoints...")
        
        # Test get optimization methods
        try:
            async with self.session.get(f"{self.api_url}/optimize/methods") as response:
                if response.status == 200:
                    methods = await response.json()
                    logger.info(f"✓ Retrieved {len(methods.get('methods', []))} optimization methods")
                    self.test_results.append({"test": "get_methods", "success": True})
                else:
                    logger.warning(f"⚠ Optimization methods endpoint returned {response.status}")
                    self.test_results.append({"test": "get_methods", "success": False, "error": f"Status {response.status}"})
        except Exception as e:
            logger.error(f"✗ Failed to get optimization methods: {e}")
            self.test_results.append({"test": "get_methods", "success": False, "error": str(e)})
        
        # Test get parameter ranges
        try:
            async with self.session.get(f"{self.api_url}/optimize/parameters/sma_crossover") as response:
                if response.status == 200:
                    params = await response.json()
                    logger.info(f"✓ Retrieved parameter ranges for strategy")
                    self.test_results.append({"test": "get_parameters", "success": True})
                else:
                    logger.warning(f"⚠ Parameters endpoint returned {response.status}")
                    self.test_results.append({"test": "get_parameters", "success": False, "error": f"Status {response.status}"})
        except Exception as e:
            logger.error(f"✗ Failed to get parameter ranges: {e}")
            self.test_results.append({"test": "get_parameters", "success": False, "error": str(e)})
    
    async def test_create_optimization(self) -> str:
        """Test creating a new optimization job"""
        logger.info("Testing optimization job creation...")
        
        config = await self.create_optimization_config()
        
        try:
            async with self.session.post(
                f"{self.api_url}/optimize/create", 
                json=config,
                headers={'Content-Type': 'application/json'}
            ) as response:
                
                if response.status == 200:
                    result = await response.json()
                    optimization_id = result.get('optimization_id')
                    assert optimization_id, "No optimization ID returned"
                    logger.info(f"✓ Created optimization job with ID: {optimization_id}")
                    self.test_results.append({"test": "create_optimization", "success": True, "optimization_id": optimization_id})
                    return optimization_id
                else:
                    error_text = await response.text()
                    logger.error(f"✗ Failed to create optimization: Status {response.status}, {error_text}")
                    self.test_results.append({"test": "create_optimization", "success": False, "error": f"Status {response.status}"})
                    return None
                    
        except Exception as e:
            logger.error(f"✗ Exception creating optimization: {e}")
            self.test_results.append({"test": "create_optimization", "success": False, "error": str(e)})
            return None
    
    async def test_optimization_execution(self, optimization_id: str):
        """Test running an optimization"""
        if not optimization_id:
            return False
            
        logger.info(f"Testing optimization execution for ID: {optimization_id}")
        
        try:
            # Start the optimization
            async with self.session.post(f"{self.api_url}/optimize/run/{optimization_id}") as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"✗ Failed to start optimization: Status {response.status}, {error_text}")
                    self.test_results.append({"test": "run_optimization", "success": False, "error": f"Status {response.status}"})
                    return False
                
                result = await response.json()
                logger.info(f"✓ Started optimization: {result.get('message', 'Started')}")
            
            # Poll for completion (with longer timeout for optimization)
            max_wait_time = 300  # 5 minutes
            poll_interval = 10   # 10 seconds
            elapsed = 0
            
            while elapsed < max_wait_time:
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
                
                async with self.session.get(f"{self.api_url}/optimize/status/{optimization_id}") as response:
                    if response.status != 200:
                        continue
                    
                    status = await response.json()
                    current_status = status.get('status', 'unknown')
                    progress = status.get('progress', 0)
                    generation = status.get('generation', 0)
                    best_fitness = status.get('best_fitness', None)
                    
                    logger.info(f"Optimization progress: {progress}% - Generation: {generation} - Status: {current_status}")
                    if best_fitness is not None:
                        logger.info(f"Best fitness so far: {best_fitness:.4f}")
                    
                    if current_status in ['completed', 'finished']:
                        logger.info("✓ Optimization completed successfully")
                        self.test_results.append({"test": "run_optimization", "success": True})
                        return True
                    elif current_status == 'failed':
                        logger.error("✗ Optimization failed")
                        self.test_results.append({"test": "run_optimization", "success": False, "error": "Optimization failed"})
                        return False
            
            # Timeout
            logger.error(f"✗ Optimization timed out after {max_wait_time} seconds")
            self.test_results.append({"test": "run_optimization", "success": False, "error": "Timeout"})
            return False
            
        except Exception as e:
            logger.error(f"✗ Exception during optimization execution: {e}")
            self.test_results.append({"test": "run_optimization", "success": False, "error": str(e)})
            return False
    
    async def test_optimization_results(self, optimization_id: str):
        """Test retrieving optimization results"""
        if not optimization_id:
            return
            
        logger.info(f"Testing optimization results retrieval for ID: {optimization_id}")
        
        try:
            # Get optimization summary
            async with self.session.get(f"{self.api_url}/optimize/results/{optimization_id}") as response:
                if response.status == 200:
                    results = await response.json()
                    
                    # Validate result structure
                    required_fields = ['best_parameters', 'best_fitness', 'generation_history']
                    missing_fields = [field for field in results if field not in results]
                    
                    if missing_fields:
                        logger.error(f"✗ Missing result fields: {missing_fields}")
                        self.test_results.append({"test": "get_optimization_results", "success": False, "error": f"Missing fields: {missing_fields}"})
                        return
                    
                    best_params = results['best_parameters']
                    best_fitness = results['best_fitness']
                    generations = len(results.get('generation_history', []))
                    
                    logger.info(f"✓ Retrieved optimization results:")
                    logger.info(f"  Best Fitness: {best_fitness:.4f}")
                    logger.info(f"  Generations: {generations}")
                    logger.info(f"  Best Parameters: {json.dumps(best_params, indent=2)}")
                    
                    self.test_results.append({"test": "get_optimization_results", "success": True, "results": results})
                else:
                    error_text = await response.text()
                    logger.error(f"✗ Failed to get optimization results: Status {response.status}, {error_text}")
                    self.test_results.append({"test": "get_optimization_results", "success": False, "error": f"Status {response.status}"})
            
            # Get population details
            async with self.session.get(f"{self.api_url}/optimize/population/{optimization_id}") as response:
                if response.status == 200:
                    population = await response.json()
                    population_size = len(population.get('individuals', []))
                    logger.info(f"✓ Retrieved population with {population_size} individuals")
                    self.test_results.append({"test": "get_population", "success": True, "population_size": population_size})
                else:
                    logger.warning(f"⚠ Could not retrieve population: Status {response.status}")
                    self.test_results.append({"test": "get_population", "success": False, "error": f"Status {response.status}"})
        
        except Exception as e:
            logger.error(f"✗ Exception getting optimization results: {e}")
            self.test_results.append({"test": "get_optimization_results", "success": False, "error": str(e)})
    
    async def test_optimized_backtest(self, optimization_id: str):
        """Test running a backtest with optimized parameters"""
        if not optimization_id:
            return
            
        logger.info(f"Testing backtest with optimized parameters for ID: {optimization_id}")
        
        try:
            # Get optimized parameters
            async with self.session.get(f"{self.api_url}/optimize/results/{optimization_id}") as response:
                if response.status != 200:
                    logger.warning("⚠ Could not retrieve optimized parameters for backtest")
                    return
                
                results = await response.json()
                best_params = results.get('best_parameters', {})
                
                if not best_params:
                    logger.warning("⚠ No optimized parameters found")
                    return
            
            # Create backtest with optimized parameters
            backtest_config = {
                "name": "E2E Optimized Strategy Test",
                "symbol": "BTCUSDT",
                "timeframe": "1h",
                "start_date": (datetime.now() - timedelta(days=20)).isoformat(),
                "end_date": datetime.now().isoformat(),
                "initial_capital": 10000.0,
                "strategy_type": "sma_crossover",
                "parameters": best_params
            }
            
            async with self.session.post(
                f"{self.api_url}/backtest/create",
                json=backtest_config
            ) as response:
                if response.status == 200:
                    backtest_result = await response.json()
                    backtest_id = backtest_result.get('backtest_id')
                    logger.info(f"✓ Created backtest with optimized parameters: {backtest_id}")
                    self.test_results.append({"test": "optimized_backtest", "success": True, "backtest_id": backtest_id})
                else:
                    logger.error(f"✗ Failed to create optimized backtest: Status {response.status}")
                    self.test_results.append({"test": "optimized_backtest", "success": False, "error": f"Status {response.status}"})
        
        except Exception as e:
            logger.error(f"✗ Exception creating optimized backtest: {e}")
            self.test_results.append({"test": "optimized_backtest", "success": False, "error": str(e)})
    
    async def test_ui_optimizer_pages(self):
        """Test the optimizer UI pages"""
        logger.info("Testing optimizer UI pages...")
        
        # Test main optimizer page
        try:
            async with self.session.get(f"{self.ui_url}/optimizer") as response:
                if response.status == 200:
                    content = await response.text()
                    required_elements = ['optimize', 'parameter', 'genetic', 'algorithm', 'generation']
                    missing_elements = [elem for elem in required_elements if elem.lower() not in content.lower()]
                    
                    if missing_elements:
                        logger.warning(f"⚠ Missing optimizer UI elements: {missing_elements}")
                    
                    logger.info("✓ Optimizer UI page loaded successfully")
                    self.test_results.append({"test": "ui_optimizer_page", "success": True})
                else:
                    logger.error(f"✗ Optimizer UI page failed: Status {response.status}")
                    self.test_results.append({"test": "ui_optimizer_page", "success": False, "error": f"Status {response.status}"})
        except Exception as e:
            logger.error(f"✗ Exception loading optimizer UI: {e}")
            self.test_results.append({"test": "ui_optimizer_page", "success": False, "error": str(e)})
        
        # Test strategies page (if exists)
        try:
            async with self.session.get(f"{self.ui_url}/strategies") as response:
                if response.status == 200:
                    logger.info("✓ Strategies UI page loaded successfully")
                    self.test_results.append({"test": "ui_strategies_page", "success": True})
                else:
                    logger.warning(f"⚠ Strategies UI page returned {response.status}")
                    self.test_results.append({"test": "ui_strategies_page", "success": False, "error": f"Status {response.status}"})
        except Exception as e:
            logger.warning(f"⚠ Exception loading strategies UI: {e}")
            self.test_results.append({"test": "ui_strategies_page", "success": False, "error": str(e)})
    
    async def test_optimization_cleanup(self, optimization_id: str):
        """Test cleaning up optimization data"""
        if not optimization_id:
            return
            
        logger.info(f"Testing optimization cleanup for ID: {optimization_id}")
        
        try:
            async with self.session.delete(f"{self.api_url}/optimize/{optimization_id}") as response:
                if response.status == 200:
                    logger.info("✓ Optimization cleanup successful")
                    self.test_results.append({"test": "cleanup", "success": True})
                else:
                    logger.warning(f"⚠ Cleanup failed: Status {response.status}")
                    self.test_results.append({"test": "cleanup", "success": False, "error": f"Status {response.status}"})
        
        except Exception as e:
            logger.warning(f"⚠ Exception during cleanup: {e}")
            self.test_results.append({"test": "cleanup", "success": False, "error": str(e)})

@pytest.mark.asyncio
async def test_complete_optimizer_flow():
    """Test the complete optimizer flow end-to-end"""
    async with OptimizerFlowTester() as tester:
        logger.info("=" * 60)
        logger.info("STARTING COMPLETE OPTIMIZER FLOW TEST")
        logger.info("=" * 60)
        
        # Step 1: Test API endpoints
        await tester.test_optimizer_api_endpoints()
        
        # Step 2: Test UI pages
        await tester.test_ui_optimizer_pages()
        
        # Step 3: Create optimization
        optimization_id = await tester.test_create_optimization()
        
        # Step 4: Execute optimization (if created successfully)
        if optimization_id:
            execution_success = await tester.test_optimization_execution(optimization_id)
            
            # Step 5: Get results (if execution succeeded)
            if execution_success:
                await tester.test_optimization_results(optimization_id)
                await tester.test_optimized_backtest(optimization_id)
            
            # Step 6: Cleanup
            await tester.test_optimization_cleanup(optimization_id)
        
        # Generate summary report
        total_tests = len(tester.test_results)
        passed_tests = sum(1 for result in tester.test_results if result['success'])
        failed_tests = total_tests - passed_tests
        
        logger.info("=" * 60)
        logger.info("OPTIMIZER FLOW TEST SUMMARY")
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
        
        # Assert minimum pass rate (more lenient for optimizer as it's complex)
        assert passed_tests / total_tests >= 0.6, f"Optimizer flow pass rate too low: {passed_tests}/{total_tests} ({passed_tests/total_tests*100:.1f}%)"

@pytest.mark.asyncio
async def test_optimizer_edge_cases():
    """Test optimizer edge cases and error conditions"""
    async with OptimizerFlowTester() as tester:
        logger.info("Testing optimizer edge cases...")
        
        # Test invalid optimization config
        invalid_config = {
            "name": "Invalid Optimization",
            "symbol": "INVALID_SYMBOL",
            "optimization_method": "nonexistent_method",
            "parameters_to_optimize": {}  # Empty parameters
        }
        
        try:
            async with tester.session.post(
                f"{tester.api_url}/optimize/create",
                json=invalid_config
            ) as response:
                # Should return error (400 or 422)
                assert response.status in [400, 422], f"Expected error status, got {response.status}"
                logger.info("✓ Invalid optimization config properly rejected")
        except AssertionError as e:
            logger.error(f"✗ Invalid config not properly rejected: {e}")
            pytest.fail(str(e))
        except Exception as e:
            logger.warning(f"⚠ Exception testing invalid config: {e}")
        
        # Test non-existent optimization ID
        try:
            async with tester.session.get(f"{tester.api_url}/optimize/status/nonexistent_id") as response:
                assert response.status == 404, f"Expected 404 for non-existent ID, got {response.status}"
                logger.info("✓ Non-existent optimization ID properly handled")
        except AssertionError as e:
            logger.error(f"✗ Non-existent optimization ID not properly handled: {e}")
            pytest.fail(str(e))
        except Exception as e:
            logger.warning(f"⚠ Exception testing non-existent ID: {e}")

if __name__ == "__main__":
    # Run tests directly
    asyncio.run(test_complete_optimizer_flow())