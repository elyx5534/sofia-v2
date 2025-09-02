#!/usr/bin/env python3
"""
Template Lock Validation Script
"""

import asyncio
import json
import os
from datetime import datetime

import requests
from playwright.async_api import async_playwright


class TemplateLockValidator:
    """Validate template lock system"""

    def __init__(self, base_url="http://127.0.0.1:8005"):
        self.base_url = base_url
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "base_url": base_url,
            "template_resolution": {},
            "route_tests": [],
            "anti_blank_tests": [],
            "tb_guarantee_tests": [],
            "summary": {},
        }

        # Ensure reports directory exists
        os.makedirs("reports/ui", exist_ok=True)
        os.makedirs("reports/visual", exist_ok=True)
        os.makedirs("reports/a11y", exist_ok=True)

    async def validate_all(self):
        """Run all validation tests"""

        print("Sofia V2 - Template Lock Validation")
        print("=" * 50)

        # Test template resolution
        await self.test_template_resolution()

        # Test all routes
        await self.test_route_functionality()

        # Test anti-blank markets
        await self.test_anti_blank_markets()

        # Test TB guarantee
        await self.test_tb_guarantee()

        # Generate final report
        self.generate_validation_report()

        return self.results

    async def test_template_resolution(self):
        """Test template resolution system"""

        print("\n🔍 Testing Template Resolution...")

        try:
            # Get template resolution report from API
            response = requests.get(f"{self.base_url}/api/template-resolution", timeout=5)

            if response.status_code == 200:
                resolution_data = response.json()
                self.results["template_resolution"] = resolution_data

                success_rate = resolution_data.get("success_rate", 0)
                total_resolutions = resolution_data.get("total_resolutions", 0)

                print(f"  ✅ Template Resolution API: {response.status_code}")
                print(f"  📊 Success Rate: {success_rate*100:.1f}%")
                print(f"  📈 Total Resolutions: {total_resolutions}")

                # Check canonical mappings
                canonical_usage = resolution_data.get("canonical_usage", {})
                for template, usage in canonical_usage.items():
                    status = "✅" if usage["exists"] else "❌"
                    print(f"  {status} {template}: {usage['usage_count']} uses")

            else:
                print(f"  ❌ Template Resolution API: {response.status_code}")
                self.results["template_resolution"] = {
                    "error": f"API returned {response.status_code}"
                }

        except Exception as e:
            print(f"  ❌ Template Resolution API: ERROR - {e!s}")
            self.results["template_resolution"] = {"error": str(e)}

    async def test_route_functionality(self):
        """Test all route functionality"""

        print("\n🧪 Testing Route Functionality...")

        routes = [
            {"path": "/", "name": "homepage"},
            {"path": "/dashboard", "name": "dashboard"},
            {"path": "/markets", "name": "markets"},
            {"path": "/live", "name": "live"},
            {"path": "/showcase/BTC", "name": "showcase_btc"},
            {"path": "/settings", "name": "settings"},
        ]

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            for route in routes:
                try:
                    # Track console errors
                    console_errors = []
                    page.on(
                        "console",
                        lambda msg: (
                            console_errors.append(msg.text) if msg.type == "error" else None
                        ),
                    )

                    # Navigate to route
                    response = await page.goto(
                        f"{self.base_url}{route['path']}", wait_until="networkidle", timeout=10000
                    )

                    await page.wait_for_timeout(3000)

                    # Check response
                    status_code = response.status if response else "unknown"
                    page_title = await page.title()

                    # Filter console errors
                    critical_errors = [
                        err
                        for err in console_errors
                        if not any(
                            ignore in err.lower()
                            for ignore in ["websocket", "fetch", "net::", "cors"]
                        )
                    ]

                    test_result = {
                        "name": route["name"],
                        "path": route["path"],
                        "status_code": status_code,
                        "title": page_title,
                        "console_errors": len(critical_errors),
                        "critical_errors": critical_errors,
                        "success": status_code == 200 and len(critical_errors) == 0,
                    }

                    self.results["route_tests"].append(test_result)

                    status = "✅" if test_result["success"] else "❌"
                    print(
                        f"  {status} {route['name']}: {status_code} | Errors: {len(critical_errors)}"
                    )

                except Exception as e:
                    print(f"  ❌ {route['name']}: ERROR - {e!s}")
                    self.results["route_tests"].append(
                        {
                            "name": route["name"],
                            "path": route["path"],
                            "error": str(e),
                            "success": False,
                        }
                    )

            await browser.close()

    async def test_anti_blank_markets(self):
        """Test anti-blank markets strategy"""

        print("\n📊 Testing Anti-Blank Markets...")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                await page.goto(f"{self.base_url}/markets")
                await page.wait_for_timeout(5000)

                # Check initial state
                initial_rows = await page.locator("tbody tr").count()
                print(f"  📈 Initial table rows: {initial_rows}")

                # Monitor for 30 seconds (abbreviated test)
                monitor_duration = 30000
                start_time = 0

                while start_time < monitor_duration:
                    current_rows = await page.locator("tbody tr").count()

                    # Should never be zero
                    if current_rows == 0:
                        # Check if showing loading or empty state appropriately
                        loading_visible = await page.locator(
                            "#crypto-loading, #bist-loading"
                        ).is_visible()
                        empty_visible = await page.locator(
                            "#crypto-empty-state, #bist-empty-state"
                        ).is_visible()

                        if not loading_visible and not empty_visible:
                            print(f"  ❌ Table empty with no loading/empty state at {start_time}ms")
                            break

                    await page.wait_for_timeout(5000)
                    start_time += 5000

                final_rows = await page.locator("tbody tr").count()

                test_result = {
                    "initial_rows": initial_rows,
                    "final_rows": final_rows,
                    "duration_ms": monitor_duration,
                    "success": final_rows > 0,
                    "maintained_data": initial_rows > 0 and final_rows > 0,
                }

                self.results["anti_blank_tests"].append(test_result)

                status = "✅" if test_result["success"] else "❌"
                print(f"  {status} Anti-blank test: {initial_rows} → {final_rows} rows")

            except Exception as e:
                print(f"  ❌ Anti-blank test failed: {e!s}")
                self.results["anti_blank_tests"].append({"error": str(e), "success": False})

            await browser.close()

    async def test_tb_guarantee(self):
        """Test Total Balance guarantee"""

        print("\n💰 Testing Total Balance Guarantee...")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                start_time = datetime.now()

                await page.goto(f"{self.base_url}/dashboard")
                await page.wait_for_timeout(2000)

                # Check if TB element exists
                tb_element = page.locator('[data-testid="total-balance"]')

                if await tb_element.count() > 0:
                    # Wait for TB to load (max 5 seconds)
                    try:
                        await page.wait_for_function(
                            """
                            () => {
                                const element = document.querySelector('[data-testid="total-balance"] #total-balance');
                                return element && element.textContent && element.textContent !== '$0.00';
                            }
                        """,
                            timeout=5000,
                        )

                        load_time = (datetime.now() - start_time).total_seconds() * 1000

                        # Get final value
                        balance_text = await page.locator("#total-balance").text_content()

                        # Verify formatting
                        is_formatted = bool(
                            balance_text and "$" in balance_text and "." in balance_text
                        )

                        test_result = {
                            "load_time_ms": load_time,
                            "balance_text": balance_text,
                            "is_formatted": is_formatted,
                            "loaded_within_5s": load_time <= 5000,
                            "success": load_time <= 5000 and is_formatted,
                        }

                        self.results["tb_guarantee_tests"].append(test_result)

                        status = "✅" if test_result["success"] else "❌"
                        print(f"  {status} TB Load Time: {load_time:.0f}ms")
                        print(f"  💵 TB Value: {balance_text}")
                        print(f"  📐 Formatting: {'✅' if is_formatted else '❌'}")

                    except Exception:
                        print("  ⏱️ TB did not load within 5 seconds")

                        # Check if fallback value is shown
                        balance_text = await page.locator("#total-balance").text_content()
                        fallback_ok = balance_text == "$10,000.00"

                        test_result = {
                            "load_time_ms": 5000,
                            "balance_text": balance_text,
                            "fallback_ok": fallback_ok,
                            "loaded_within_5s": False,
                            "success": fallback_ok,
                        }

                        self.results["tb_guarantee_tests"].append(test_result)

                        status = "✅" if fallback_ok else "❌"
                        print(f"  {status} TB Fallback: {balance_text}")

                else:
                    print("  ⚠️ Total Balance element not found")
                    self.results["tb_guarantee_tests"].append(
                        {"error": "TB element not found", "success": False}
                    )

            except Exception as e:
                print(f"  ❌ TB test failed: {e!s}")
                self.results["tb_guarantee_tests"].append({"error": str(e), "success": False})

            await browser.close()

    def generate_validation_report(self):
        """Generate validation report"""

        # Calculate summary
        route_success = sum(1 for test in self.results["route_tests"] if test["success"])
        anti_blank_success = sum(1 for test in self.results["anti_blank_tests"] if test["success"])
        tb_success = sum(1 for test in self.results["tb_guarantee_tests"] if test["success"])

        total_tests = (
            len(self.results["route_tests"])
            + len(self.results["anti_blank_tests"])
            + len(self.results["tb_guarantee_tests"])
        )
        total_success = route_success + anti_blank_success + tb_success

        self.results["summary"] = {
            "total_tests": total_tests,
            "total_success": total_success,
            "success_rate": total_success / total_tests if total_tests > 0 else 0,
            "route_tests": {
                "total": len(self.results["route_tests"]),
                "passed": route_success,
                "rate": (
                    route_success / len(self.results["route_tests"])
                    if self.results["route_tests"]
                    else 0
                ),
            },
            "anti_blank_tests": {
                "total": len(self.results["anti_blank_tests"]),
                "passed": anti_blank_success,
                "rate": (
                    anti_blank_success / len(self.results["anti_blank_tests"])
                    if self.results["anti_blank_tests"]
                    else 0
                ),
            },
            "tb_guarantee_tests": {
                "total": len(self.results["tb_guarantee_tests"]),
                "passed": tb_success,
                "rate": (
                    tb_success / len(self.results["tb_guarantee_tests"])
                    if self.results["tb_guarantee_tests"]
                    else 0
                ),
            },
        }

        # Save results
        with open("reports/ui/template_lock_validation.json", "w") as f:
            json.dump(self.results, f, indent=2, default=str)

        # Generate text report
        self.generate_text_report()

    def generate_text_report(self):
        """Generate human-readable report"""

        summary = self.results["summary"]

        report = f"""Sofia V2 - Template Lock Validation Report
==========================================
Generated: {self.results['timestamp']}
Base URL: {self.results['base_url']}

OVERALL SUMMARY:
===============
Total Tests: {summary['total_tests']}
Passed: {summary['total_success']}
Success Rate: {summary['success_rate']*100:.1f}%

TEMPLATE RESOLUTION:
===================
"""

        if "error" not in self.results["template_resolution"]:
            resolution = self.results["template_resolution"]
            report += f"Success Rate: {resolution.get('success_rate', 0)*100:.1f}%\n"
            report += f"Total Resolutions: {resolution.get('total_resolutions', 0)}\n"
            report += f"Search Paths: {', '.join(resolution.get('search_paths', []))}\n\n"

            canonical_usage = resolution.get("canonical_usage", {})
            for template, usage in canonical_usage.items():
                status = "✅" if usage["exists"] else "❌"
                report += f"{status} {template}: {usage['usage_count']} uses\n"
        else:
            report += f"ERROR: {self.results['template_resolution']['error']}\n"

        report += f"""

ROUTE TESTS ({summary['route_tests']['passed']}/{summary['route_tests']['total']}):
===========
"""

        for test in self.results["route_tests"]:
            status = "✅" if test["success"] else "❌"
            report += f"{status} {test['name']}: {test.get('status_code', 'unknown')} "
            report += f"| Errors: {test.get('console_errors', 0)}\n"

            if "error" in test:
                report += f"    Error: {test['error']}\n"

        report += f"""

ANTI-BLANK MARKETS ({summary['anti_blank_tests']['passed']}/{summary['anti_blank_tests']['total']}):
==================
"""

        for test in self.results["anti_blank_tests"]:
            if "error" not in test:
                status = "✅" if test["success"] else "❌"
                report += f"{status} Data Persistence: {test.get('initial_rows', 0)} → {test.get('final_rows', 0)} rows\n"
                report += (
                    f"    Maintained Data: {'✅' if test.get('maintained_data', False) else '❌'}\n"
                )
            else:
                report += f"❌ Anti-blank test failed: {test['error']}\n"

        report += f"""

TOTAL BALANCE GUARANTEE ({summary['tb_guarantee_tests']['passed']}/{summary['tb_guarantee_tests']['total']}):
=======================
"""

        for test in self.results["tb_guarantee_tests"]:
            if "error" not in test:
                status = "✅" if test["success"] else "❌"
                load_time = test.get("load_time_ms", 0)
                report += f"{status} Load Time: {load_time:.0f}ms ({'✅' if load_time <= 5000 else '❌'} ≤5s)\n"
                report += f"    Balance: {test.get('balance_text', 'N/A')}\n"
                report += f"    Formatting: {'✅' if test.get('is_formatted', False) else '❌'}\n"
                if "fallback_ok" in test:
                    report += f"    Fallback: {'✅' if test['fallback_ok'] else '❌'}\n"
            else:
                report += f"❌ TB test failed: {test['error']}\n"

        overall_status = (
            "✅ PASS"
            if summary["success_rate"] >= 0.8
            else "⚠️ PARTIAL"
            if summary["success_rate"] >= 0.6
            else "❌ FAIL"
        )

        report += f"""

FINAL VALIDATION:
================
Overall Status: {overall_status}
Success Rate: {summary['success_rate']*100:.1f}%

GATE STATUS:
===========
✅ Template Resolution: {'✅' if 'error' not in self.results['template_resolution'] else '❌'}
✅ Route Functionality: {'✅' if summary['route_tests']['rate'] >= 0.8 else '❌'}
✅ Anti-Blank Markets: {'✅' if summary['anti_blank_tests']['rate'] >= 0.8 else '❌'}
✅ TB Guarantee: {'✅' if summary['tb_guarantee_tests']['rate'] >= 0.8 else '❌'}

Validation completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

        # Save text report
        with open("reports/ui/template_lock_validation_report.txt", "w") as f:
            f.write(report)

        print(report)


async def main():
    """Main validation runner"""

    validator = TemplateLockValidator()
    results = await validator.validate_all()

    success_rate = results["summary"]["success_rate"]

    print(
        f"\n{'🎉' if success_rate >= 0.8 else '⚠️' if success_rate >= 0.6 else '❌'} "
        f"Validation completed with {success_rate*100:.1f}% success rate"
    )

    return 0 if success_rate >= 0.8 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
