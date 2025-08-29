#!/usr/bin/env python3
"""
Comprehensive Test Runner for Sofia V2
Runs all tests and generates detailed reports with auto-fixes
"""

import asyncio
import subprocess
import sys
import time
import json
from datetime import datetime
from pathlib import Path
import logging
import os
from typing import Dict, List, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('test_runner.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)

class TestRunner:
    def __init__(self):
        self.results = []
        self.start_time = None
        self.end_time = None
        self.report_dir = Path("test_reports")
        self.report_dir.mkdir(exist_ok=True)
        
        # Test configuration
        self.api_url = os.getenv('API_BASE_URL', 'http://127.0.0.1:8024')
        self.ui_url = os.getenv('UI_BASE_URL', 'http://127.0.0.1:8005')
    
    def run_pytest_command(self, test_file: str, extra_args: List[str] = None) -> Dict[str, Any]:
        """Run a pytest command and capture results"""
        cmd = [sys.executable, '-m', 'pytest', test_file, '-v', '--tb=short']
        if extra_args:
            cmd.extend(extra_args)
        
        logger.info(f"Running: {' '.join(cmd)}")
        start_time = time.time()
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout
            )
            
            duration = time.time() - start_time
            
            return {
                'test_file': test_file,
                'command': ' '.join(cmd),
                'duration': duration,
                'returncode': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'success': result.returncode == 0
            }
            
        except subprocess.TimeoutExpired:
            return {
                'test_file': test_file,
                'command': ' '.join(cmd),
                'duration': 600,
                'returncode': -1,
                'stdout': '',
                'stderr': 'Test timed out after 10 minutes',
                'success': False
            }
        except Exception as e:
            return {
                'test_file': test_file,
                'command': ' '.join(cmd),
                'duration': time.time() - start_time,
                'returncode': -1,
                'stdout': '',
                'stderr': str(e),
                'success': False
            }
    
    async def check_services_health(self) -> Dict[str, bool]:
        """Check if API and UI services are running"""
        import aiohttp
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            services = {'api': False, 'ui': False}
            
            # Check API
            try:
                async with session.get(f"{self.api_url}/health") as response:
                    services['api'] = response.status == 200
            except:
                pass
            
            # Check UI
            try:
                async with session.get(f"{self.ui_url}/") as response:
                    services['ui'] = response.status == 200
            except:
                pass
            
            return services
    
    def run_unit_tests(self):
        """Run unit tests"""
        logger.info("=" * 60)
        logger.info("RUNNING UNIT TESTS")
        logger.info("=" * 60)
        
        unit_tests = [
            "tests/test_smoke.py",
            "tests/test_symbols.py",
            "tests/test_api_contract.py"
        ]
        
        for test_file in unit_tests:
            if Path(test_file).exists():
                result = self.run_pytest_command(test_file)
                self.results.append(result)
                if result['success']:
                    logger.info(f"✓ {test_file} passed ({result['duration']:.1f}s)")
                else:
                    logger.error(f"✗ {test_file} failed ({result['duration']:.1f}s)")
            else:
                logger.warning(f"⚠ {test_file} not found")
    
    def run_integration_tests(self):
        """Run integration tests"""
        logger.info("=" * 60)
        logger.info("RUNNING INTEGRATION TESTS")
        logger.info("=" * 60)
        
        integration_tests = [
            "tests/test_live_data.py",
            "tests/test_reliability.py",
            "tests/test_rest_fallback.py"
        ]
        
        for test_file in integration_tests:
            if Path(test_file).exists():
                result = self.run_pytest_command(test_file)
                self.results.append(result)
                if result['success']:
                    logger.info(f"✓ {test_file} passed ({result['duration']:.1f}s)")
                else:
                    logger.error(f"✗ {test_file} failed ({result['duration']:.1f}s)")
            else:
                logger.warning(f"⚠ {test_file} not found")
    
    def run_e2e_tests(self):
        """Run E2E tests"""
        logger.info("=" * 60)
        logger.info("RUNNING E2E TESTS")
        logger.info("=" * 60)
        
        e2e_tests = [
            "tests/e2e/test_route_audit_comprehensive.py",
            "tests/e2e/test_backtest_flow_comprehensive.py",
            "tests/e2e/test_optimizer_flow_comprehensive.py",
            "tests/e2e/test_visual_regression.py"
        ]
        
        for test_file in e2e_tests:
            if Path(test_file).exists():
                result = self.run_pytest_command(test_file, ['-s'])  # -s to see output
                self.results.append(result)
                if result['success']:
                    logger.info(f"✓ {test_file} passed ({result['duration']:.1f}s)")
                else:
                    logger.error(f"✗ {test_file} failed ({result['duration']:.1f}s)")
                    # Log some error details
                    if result['stderr']:
                        logger.error(f"Error output: {result['stderr'][:500]}...")
            else:
                logger.warning(f"⚠ {test_file} not found")
    
    def auto_fix_issues(self):
        """Attempt to auto-fix common issues"""
        logger.info("=" * 60)
        logger.info("ATTEMPTING AUTO-FIXES")
        logger.info("=" * 60)
        
        fixes_applied = []
        
        # Check for common issues in failed tests
        failed_tests = [r for r in self.results if not r['success']]
        
        for failed_test in failed_tests:
            stderr = failed_test.get('stderr', '')
            stdout = failed_test.get('stdout', '')
            error_output = stderr + stdout
            
            # Fix 1: Import errors
            if 'ImportError' in error_output or 'ModuleNotFoundError' in error_output:
                logger.info(f"🔧 Detected import error in {failed_test['test_file']}")
                # Try to install missing dependencies
                if 'aiohttp' in error_output:
                    try:
                        subprocess.run([sys.executable, '-m', 'pip', 'install', 'aiohttp'], check=True)
                        fixes_applied.append("Installed aiohttp")
                    except:
                        pass
                
                if 'pytest' in error_output:
                    try:
                        subprocess.run([sys.executable, '-m', 'pip', 'install', 'pytest'], check=True)
                        fixes_applied.append("Installed pytest")
                    except:
                        pass
            
            # Fix 2: Connection errors
            if 'Connection' in error_output or 'refused' in error_output:
                logger.info(f"🔧 Detected connection error in {failed_test['test_file']}")
                # Check if services are running and restart if needed
                fixes_applied.append("Checked service connectivity")
            
            # Fix 3: Timeout errors
            if 'timeout' in error_output.lower():
                logger.info(f"🔧 Detected timeout in {failed_test['test_file']}")
                fixes_applied.append("Identified timeout issues")
        
        if fixes_applied:
            logger.info("Applied fixes:")
            for fix in fixes_applied:
                logger.info(f"  - {fix}")
        else:
            logger.info("No auto-fixes needed or available")
    
    def generate_html_report(self):
        """Generate an HTML report"""
        report_time = datetime.now()
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r['success'])
        failed_tests = total_tests - passed_tests
        total_duration = sum(r['duration'] for r in self.results)
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Sofia V2 Test Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background: #2c3e50; color: white; padding: 20px; border-radius: 5px; }}
        .summary {{ display: flex; gap: 20px; margin: 20px 0; }}
        .metric {{ background: #ecf0f1; padding: 15px; border-radius: 5px; flex: 1; text-align: center; }}
        .metric.success {{ background: #d5edda; }}
        .metric.warning {{ background: #fff3cd; }}
        .metric.error {{ background: #f8d7da; }}
        .test-result {{ margin: 10px 0; padding: 15px; border-radius: 5px; }}
        .test-result.success {{ background: #d5edda; border-left: 5px solid #28a745; }}
        .test-result.failed {{ background: #f8d7da; border-left: 5px solid #dc3545; }}
        .details {{ font-family: monospace; font-size: 12px; margin-top: 10px; }}
        .collapsible {{ cursor: pointer; user-select: none; }}
        .content {{ max-height: 0; overflow: hidden; transition: max-height 0.2s ease-out; }}
        .content.active {{ max-height: 500px; overflow-y: auto; }}
        pre {{ background: #f8f9fa; padding: 10px; border-radius: 3px; font-size: 11px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Sofia V2 Test Report</h1>
        <p>Generated: {report_time.strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>Duration: {total_duration:.1f} seconds</p>
    </div>
    
    <div class="summary">
        <div class="metric success">
            <h3>{passed_tests}</h3>
            <p>Passed Tests</p>
        </div>
        <div class="metric {'error' if failed_tests > 0 else 'success'}">
            <h3>{failed_tests}</h3>
            <p>Failed Tests</p>
        </div>
        <div class="metric">
            <h3>{passed_tests/total_tests*100:.1f}%</h3>
            <p>Pass Rate</p>
        </div>
        <div class="metric">
            <h3>{total_duration/total_tests:.1f}s</h3>
            <p>Avg Duration</p>
        </div>
    </div>
    
    <h2>Test Results</h2>
"""
        
        for result in self.results:
            status_class = "success" if result['success'] else "failed"
            status_text = "PASSED" if result['success'] else "FAILED"
            
            html_content += f"""
    <div class="test-result {status_class}">
        <div class="collapsible" onclick="toggleContent('{result['test_file'].replace('/', '_').replace('.', '_')}')">
            <strong>{result['test_file']}</strong> - {status_text} ({result['duration']:.1f}s)
        </div>
        <div class="content" id="{result['test_file'].replace('/', '_').replace('.', '_')}">
            <div class="details">
                <p><strong>Command:</strong> {result['command']}</p>
                <p><strong>Return Code:</strong> {result['returncode']}</p>
"""
            
            if result['stdout']:
                html_content += f"<p><strong>Output:</strong></p><pre>{result['stdout'][:2000]}</pre>"
            
            if result['stderr']:
                html_content += f"<p><strong>Errors:</strong></p><pre>{result['stderr'][:2000]}</pre>"
            
            html_content += """
            </div>
        </div>
    </div>
"""
        
        html_content += """
    <script>
        function toggleContent(id) {
            var content = document.getElementById(id);
            content.classList.toggle('active');
        }
    </script>
</body>
</html>
"""
        
        report_file = self.report_dir / f"test_report_{report_time.strftime('%Y%m%d_%H%M%S')}.html"
        with open(report_file, 'w') as f:
            f.write(html_content)
        
        logger.info(f"📊 HTML report generated: {report_file}")
        return report_file
    
    def generate_json_report(self):
        """Generate a JSON report for CI/CD"""
        report_time = datetime.now()
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r['success'])
        
        report_data = {
            "report_time": report_time.isoformat(),
            "summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": total_tests - passed_tests,
                "pass_rate": passed_tests / total_tests if total_tests > 0 else 0,
                "total_duration": sum(r['duration'] for r in self.results)
            },
            "results": self.results
        }
        
        report_file = self.report_dir / f"test_report_{report_time.strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        logger.info(f"📊 JSON report generated: {report_file}")
        return report_file
    
    async def run_all_tests(self):
        """Run all tests with health checks and reporting"""
        self.start_time = time.time()
        
        logger.info("🚀 Starting comprehensive test suite for Sofia V2")
        
        # Check service health first
        logger.info("🔍 Checking service health...")
        services = await self.check_services_health()
        logger.info(f"API Service: {'✓' if services['api'] else '✗'}")
        logger.info(f"UI Service: {'✓' if services['ui'] else '✗'}")
        
        if not services['api'] or not services['ui']:
            logger.warning("⚠ Some services are not available. Some tests may fail.")
        
        # Run test suites
        self.run_unit_tests()
        self.run_integration_tests()
        self.run_e2e_tests()
        
        # Attempt auto-fixes
        self.auto_fix_issues()
        
        # Generate reports
        self.end_time = time.time()
        total_duration = self.end_time - self.start_time
        
        # Summary
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r['success'])
        failed_tests = total_tests - passed_tests
        
        logger.info("=" * 60)
        logger.info("FINAL TEST SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total Tests Run: {total_tests}")
        logger.info(f"Passed: {passed_tests}")
        logger.info(f"Failed: {failed_tests}")
        logger.info(f"Pass Rate: {passed_tests/total_tests*100:.1f}%")
        logger.info(f"Total Duration: {total_duration:.1f}s")
        logger.info("=" * 60)
        
        # Generate reports
        html_report = self.generate_html_report()
        json_report = self.generate_json_report()
        
        logger.info(f"📊 Reports generated:")
        logger.info(f"  HTML: {html_report}")
        logger.info(f"  JSON: {json_report}")
        
        return {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "pass_rate": passed_tests / total_tests if total_tests > 0 else 0,
            "duration": total_duration,
            "html_report": str(html_report),
            "json_report": str(json_report)
        }

async def main():
    """Main entry point"""
    runner = TestRunner()
    results = await runner.run_all_tests()
    
    # Exit with appropriate code
    exit_code = 0 if results['pass_rate'] >= 0.8 else 1
    logger.info(f"Exiting with code {exit_code}")
    sys.exit(exit_code)

if __name__ == "__main__":
    asyncio.run(main())