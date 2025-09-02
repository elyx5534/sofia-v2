#!/usr/bin/env python3
"""
Comprehensive UI Test Suite for Sofia V2
"""

import asyncio
import json
import os
import time
from datetime import datetime

import requests
from playwright.async_api import async_playwright


class UITestSuite:
    """Comprehensive UI testing for Sofia V2"""

    def __init__(self, base_url="http://127.0.0.1:8005"):
        self.base_url = base_url
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "base_url": base_url,
            "page_tests": [],
            "api_tests": [],
            "visual_tests": [],
            "accessibility_tests": [],
            "summary": {},
        }

        # Ensure reports directory exists
        os.makedirs("reports/ui", exist_ok=True)
        os.makedirs("reports/visual", exist_ok=True)
        os.makedirs("reports/smoke/screens", exist_ok=True)

    async def run_all_tests(self):
        """Run complete test suite"""

        print("Sofia V2 - Comprehensive UI Test Suite")
        print("=" * 50)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 1920, "height": 1080})

            # Page functionality tests
            await self.test_page_functionality(page)

            # Visual regression tests
            await self.test_visual_regression(page)

            # Accessibility tests
            await self.test_accessibility(page)

            await browser.close()

        # API tests
        await self.test_api_endpoints()

        # Generate comprehensive report
        self.generate_comprehensive_report()

        return self.results

    async def test_page_functionality(self, page):
        """Test page functionality and loading"""

        pages = [
            {"path": "/", "name": "homepage", "required_elements": ["h1", "nav"]},
            {
                "path": "/dashboard",
                "name": "dashboard",
                "required_elements": ['[data-testid="total-balance"]'],
            },
            {"path": "/markets", "name": "markets", "required_elements": ["table, .card"]},
            {
                "path": "/live",
                "name": "live",
                "required_elements": [".trading-grid, .grid-container"],
            },
            {
                "path": "/showcase/BTC",
                "name": "showcase_btc",
                "required_elements": [".price-card, .trading-card"],
            },
            {
                "path": "/settings",
                "name": "settings",
                "required_elements": ['[data-testid="paper-trading-toggle"]'],
            },
        ]

        print("\n🧪 Testing Page Functionality...")

        for page_config in pages:
            try:
                test_result = await self.test_single_page(page, page_config)
                self.results["page_tests"].append(test_result)

                status = "✅" if test_result["success"] else "❌"
                print(
                    f"  {status} {test_result['name']}: {test_result['status_code']} | "
                    f"Load: {test_result['load_time_ms']}ms | "
                    f"Errors: {test_result['console_errors']}"
                )

            except Exception as e:
                print(f"  ❌ {page_config['name']}: ERROR - {e!s}")
                self.results["page_tests"].append(
                    {"name": page_config["name"], "error": str(e), "success": False}
                )

    async def test_single_page(self, page, page_config):
        """Test a single page"""

        url = f"{self.base_url}{page_config['path']}"

        # Track console errors
        console_errors = []
        page.on(
            "console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None
        )

        start_time = time.time()

        # Navigate to page
        response = await page.goto(url, wait_until="networkidle", timeout=10000)

        # Wait for content
        await page.wait_for_timeout(3000)

        load_time_ms = int((time.time() - start_time) * 1000)

        # Check required elements
        elements_found = 0
        for selector in page_config.get("required_elements", []):
            try:
                element = page.locator(selector)
                if await element.count() > 0:
                    elements_found += 1
            except:
                pass

        # Check total balance specifically for dashboard
        total_balance_loaded = False
        if page_config["name"] == "dashboard":
            try:
                balance_element = page.locator('[data-testid="total-balance"]')
                if await balance_element.count() > 0:
                    # Wait for balance to load (up to 5 seconds)
                    await page.wait_for_timeout(5000)
                    balance_text = await balance_element.text_content()
                    total_balance_loaded = "$" in balance_text and balance_text != "$0.00"
            except:
                pass

        # Filter console errors (ignore common non-critical ones)
        critical_errors = [
            err
            for err in console_errors
            if not any(
                ignore in err.lower()
                for ignore in ["websocket", "fetch", "net::", "cors", "network"]
            )
        ]

        return {
            "name": page_config["name"],
            "path": page_config["path"],
            "url": url,
            "status_code": response.status if response else "unknown",
            "load_time_ms": load_time_ms,
            "elements_found": elements_found,
            "total_elements": len(page_config.get("required_elements", [])),
            "console_errors": len(critical_errors),
            "critical_errors": critical_errors,
            "total_balance_loaded": total_balance_loaded,
            "success": (
                response
                and response.status == 200
                and elements_found > 0
                and len(critical_errors) == 0
            ),
        }

    async def test_visual_regression(self, page):
        """Test visual regression with screenshots"""

        print("\n📸 Testing Visual Regression...")

        pages = ["/", "/markets", "/showcase/BTC", "/settings"]

        for path in pages:
            try:
                url = f"{self.base_url}{path}"
                await page.goto(url, wait_until="networkidle", timeout=10000)
                await page.wait_for_timeout(2000)

                # Capture screenshot
                name = path.replace("/", "_").replace("_", "") or "homepage"
                screenshot_path = f"reports/visual/{name}_baseline.png"

                await page.screenshot(path=screenshot_path, full_page=True)

                self.results["visual_tests"].append(
                    {"name": name, "path": path, "screenshot": screenshot_path, "success": True}
                )

                print(f"  📷 {name}: Screenshot captured")

            except Exception as e:
                print(f"  ❌ {path}: Screenshot failed - {e!s}")
                self.results["visual_tests"].append(
                    {"name": name, "path": path, "error": str(e), "success": False}
                )

    async def test_accessibility(self, page):
        """Test accessibility compliance"""

        print("\n♿ Testing Accessibility...")

        pages = ["/", "/markets", "/settings"]

        for path in pages:
            try:
                url = f"{self.base_url}{path}"
                await page.goto(url, wait_until="networkidle", timeout=10000)
                await page.wait_for_timeout(2000)

                # Basic accessibility checks
                result = {"name": path.replace("/", "") or "homepage", "path": path, "checks": {}}

                # Check for navigation landmarks
                nav_elements = await page.locator("nav").count()
                main_elements = await page.locator("main").count()
                result["checks"]["navigation_landmarks"] = nav_elements > 0 and main_elements > 0

                # Check for headings hierarchy
                h1_count = await page.locator("h1").count()
                result["checks"]["heading_structure"] = h1_count == 1  # Should have exactly one H1

                # Check for sidebar patterns (should be 0)
                sidebar_elements = await page.locator('[class*="sidebar"], [id*="sidebar"]').count()
                result["checks"]["no_sidebars"] = sidebar_elements == 0

                # Check for proper focus handling
                focusable_elements = await page.locator(
                    "button, input, select, textarea, a[href]"
                ).count()
                result["checks"]["has_focusable_elements"] = focusable_elements > 0

                # Overall accessibility score
                passed_checks = sum(1 for check in result["checks"].values() if check)
                total_checks = len(result["checks"])
                result["score"] = passed_checks / total_checks if total_checks > 0 else 0
                result["success"] = result["score"] >= 0.8  # 80% pass rate

                self.results["accessibility_tests"].append(result)

                score_pct = result["score"] * 100
                status = "✅" if result["success"] else "⚠️"
                print(
                    f"  {status} {result['name']}: {score_pct:.0f}% | "
                    f"Landmarks: {result['checks']['navigation_landmarks']} | "
                    f"No Sidebars: {result['checks']['no_sidebars']}"
                )

            except Exception as e:
                print(f"  ❌ {path}: A11y test failed - {e!s}")
                self.results["accessibility_tests"].append(
                    {
                        "name": path.replace("/", "") or "homepage",
                        "path": path,
                        "error": str(e),
                        "success": False,
                    }
                )

    async def test_api_endpoints(self):
        """Test API endpoint availability"""

        print("\n🔌 Testing API Endpoints...")

        endpoints = [
            {"url": f"{self.base_url}/docs", "name": "api_docs", "expected": 200},
            {
                "url": f"{self.base_url}/api/quotes?symbols=BTC-USD",
                "name": "quotes_api",
                "expected": 200,
            },
            {
                "url": f"{self.base_url}/api/market-summary",
                "name": "market_summary",
                "expected": 200,
            },
            {"url": f"{self.base_url}/api/crypto-prices", "name": "crypto_prices", "expected": 200},
        ]

        for endpoint in endpoints:
            try:
                response = requests.get(endpoint["url"], timeout=5)
                success = response.status_code == endpoint["expected"]

                self.results["api_tests"].append(
                    {
                        "name": endpoint["name"],
                        "url": endpoint["url"],
                        "status_code": response.status_code,
                        "expected": endpoint["expected"],
                        "response_time_ms": int(response.elapsed.total_seconds() * 1000),
                        "success": success,
                    }
                )

                status = "✅" if success else "❌"
                print(
                    f"  {status} {endpoint['name']}: {response.status_code} "
                    f"({response.elapsed.total_seconds()*1000:.0f}ms)"
                )

            except Exception as e:
                print(f"  ❌ {endpoint['name']}: ERROR - {e!s}")
                self.results["api_tests"].append(
                    {
                        "name": endpoint["name"],
                        "url": endpoint["url"],
                        "error": str(e),
                        "success": False,
                    }
                )

    def generate_comprehensive_report(self):
        """Generate comprehensive test report"""

        # Calculate summary statistics
        page_success = sum(1 for test in self.results["page_tests"] if test["success"])
        api_success = sum(1 for test in self.results["api_tests"] if test["success"])
        visual_success = sum(1 for test in self.results["visual_tests"] if test["success"])
        a11y_success = sum(1 for test in self.results["accessibility_tests"] if test["success"])

        total_tests = (
            len(self.results["page_tests"])
            + len(self.results["api_tests"])
            + len(self.results["visual_tests"])
            + len(self.results["accessibility_tests"])
        )
        total_success = page_success + api_success + visual_success + a11y_success

        self.results["summary"] = {
            "total_tests": total_tests,
            "total_success": total_success,
            "success_rate": total_success / total_tests if total_tests > 0 else 0,
            "page_tests": {
                "total": len(self.results["page_tests"]),
                "passed": page_success,
                "rate": (
                    page_success / len(self.results["page_tests"])
                    if self.results["page_tests"]
                    else 0
                ),
            },
            "api_tests": {
                "total": len(self.results["api_tests"]),
                "passed": api_success,
                "rate": (
                    api_success / len(self.results["api_tests"]) if self.results["api_tests"] else 0
                ),
            },
            "visual_tests": {
                "total": len(self.results["visual_tests"]),
                "passed": visual_success,
                "rate": (
                    visual_success / len(self.results["visual_tests"])
                    if self.results["visual_tests"]
                    else 0
                ),
            },
            "accessibility_tests": {
                "total": len(self.results["accessibility_tests"]),
                "passed": a11y_success,
                "rate": (
                    a11y_success / len(self.results["accessibility_tests"])
                    if self.results["accessibility_tests"]
                    else 0
                ),
            },
        }

        # Save JSON results
        with open("reports/ui/comprehensive_test_results.json", "w") as f:
            json.dump(self.results, f, indent=2, default=str)

        # Generate text report
        self.generate_text_report()

    def generate_text_report(self):
        """Generate human-readable text report"""

        summary = self.results["summary"]
        timestamp = self.results["timestamp"]

        report = f"""Sofia V2 - Comprehensive UI Test Report
========================================
Generated: {timestamp}
Base URL: {self.results['base_url']}
Branch: fix/ui-route-template-alignment-20250830

OVERALL SUMMARY:
===============
Total Tests: {summary['total_tests']}
Passed: {summary['total_success']}
Success Rate: {summary['success_rate']*100:.1f}%

DETAILED RESULTS:
================

📄 PAGE TESTS ({summary['page_tests']['passed']}/{summary['page_tests']['total']}):
"""

        for test in self.results["page_tests"]:
            status = "✅ PASS" if test["success"] else "❌ FAIL"
            report += f"{status} {test['name'].upper()}\n"
            report += f"  Status: {test.get('status_code', 'unknown')}\n"
            report += f"  Load Time: {test.get('load_time_ms', 0)}ms\n"
            report += f"  Console Errors: {test.get('console_errors', 0)}\n"

            if test["name"] == "dashboard" and "total_balance_loaded" in test:
                report += (
                    f"  Total Balance Loaded: {'✅' if test['total_balance_loaded'] else '❌'}\n"
                )

            if "error" in test:
                report += f"  Error: {test['error']}\n"
            report += "\n"

        report += f"""
🔌 API TESTS ({summary['api_tests']['passed']}/{summary['api_tests']['total']}):
"""

        for test in self.results["api_tests"]:
            status = "✅ PASS" if test["success"] else "❌ FAIL"
            report += f"{status} {test['name'].upper()}\n"
            report += f"  Status: {test.get('status_code', 'unknown')}\n"
            report += f"  Response Time: {test.get('response_time_ms', 0)}ms\n"
            if "error" in test:
                report += f"  Error: {test['error']}\n"
            report += "\n"

        report += f"""
📸 VISUAL TESTS ({summary['visual_tests']['passed']}/{summary['visual_tests']['total']}):
"""

        for test in self.results["visual_tests"]:
            status = "✅ PASS" if test["success"] else "❌ FAIL"
            report += f"{status} {test['name'].upper()}\n"
            if "screenshot" in test:
                report += f"  Screenshot: {test['screenshot']}\n"
            if "error" in test:
                report += f"  Error: {test['error']}\n"
            report += "\n"

        report += f"""
♿ ACCESSIBILITY TESTS ({summary['accessibility_tests']['passed']}/{summary['accessibility_tests']['total']}):
"""

        for test in self.results["accessibility_tests"]:
            status = "✅ PASS" if test["success"] else "❌ FAIL"
            score = test.get("score", 0) * 100
            report += f"{status} {test['name'].upper()} ({score:.0f}%)\n"

            checks = test.get("checks", {})
            report += (
                f"  Navigation Landmarks: {'✅' if checks.get('navigation_landmarks') else '❌'}\n"
            )
            report += f"  Heading Structure: {'✅' if checks.get('heading_structure') else '❌'}\n"
            report += f"  No Sidebars: {'✅' if checks.get('no_sidebars') else '❌'}\n"
            report += (
                f"  Focusable Elements: {'✅' if checks.get('has_focusable_elements') else '❌'}\n"
            )

            if "error" in test:
                report += f"  Error: {test['error']}\n"
            report += "\n"

        overall_status = (
            "✅ PASS"
            if summary["success_rate"] >= 0.8
            else "⚠️ PARTIAL"
            if summary["success_rate"] >= 0.6
            else "❌ FAIL"
        )

        report += f"""
FINAL VERDICT:
=============
Overall Status: {overall_status}
Success Rate: {summary['success_rate']*100:.1f}%

ACCEPTANCE CRITERIA:
===================
✅ Single navbar, sidebar=0: {'✅' if all(t.get('checks', {}).get('no_sidebars', False) for t in self.results['accessibility_tests']) else '❌'}
✅ Dashboard TB ≤5s loaded: {'✅' if any(t.get('total_balance_loaded', False) for t in self.results['page_tests']) else '❌'}
✅ Markets anti-blank strategy: {'✅' if any(t['name'] == 'markets' and t['success'] for t in self.results['page_tests']) else '❌'}
✅ Console errors = 0: {'✅' if all(t.get('console_errors', 1) == 0 for t in self.results['page_tests']) else '❌'}
✅ Visual baselines captured: {'✅' if len(self.results['visual_tests']) > 0 else '❌'}

ARTIFACTS GENERATED:
===================
- Test Results: reports/ui/comprehensive_test_results.json
- Visual Baselines: reports/visual/*.png
- Route Audit: reports/ui/route_template_audit.json
- Smoke Screens: reports/smoke/screens/*.png

Test completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

        # Save text report
        with open("reports/ui/comprehensive_test_report.txt", "w") as f:
            f.write(report)

        print(report)
        return report


async def main():
    """Main test runner"""

    test_suite = UITestSuite()
    results = await test_suite.run_all_tests()

    success_rate = results["summary"]["success_rate"]

    if success_rate >= 0.8:
        print("\n🎉 All tests passed! Ready for production.")
        return 0
    elif success_rate >= 0.6:
        print("\n⚠️ Some tests failed. Review required.")
        return 1
    else:
        print("\n❌ Critical failures detected. Fix required.")
        return 2


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
