#!/usr/bin/env python3
"""
Manual Smoke Test with Screenshots
"""

import asyncio
import json
from datetime import datetime

import requests
from playwright.async_api import async_playwright


async def run_smoke_tests():
    """Run smoke tests and capture screenshots"""

    base_url = "http://127.0.0.1:8005"
    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})

        # Pages to test
        pages = [
            {"path": "/", "name": "homepage"},
            {"path": "/dashboard", "name": "dashboard"},
            {"path": "/markets", "name": "markets"},
            {"path": "/live", "name": "live"},
            {"path": "/showcase/BTC", "name": "showcase_btc"},
            {"path": "/settings", "name": "settings"},
        ]

        print("Running Sofia V2 Smoke Tests...")
        print("=" * 50)

        for page_config in pages:
            path = page_config["path"]
            name = page_config["name"]
            url = f"{base_url}{path}"

            print(f"Testing {name}: {url}")

            try:
                # Navigate to page
                response = await page.goto(url, wait_until="networkidle", timeout=10000)

                # Wait for content to load
                await page.wait_for_timeout(3000)

                # Capture screenshot
                await page.screenshot(path=f"reports/smoke/screens/{name}.png", full_page=True)

                # Check for console errors
                console_errors = []
                page.on(
                    "console",
                    lambda msg: console_errors.append(msg.text) if msg.type == "error" else None,
                )

                # Basic checks
                page_title = await page.title()
                has_content = len(await page.content()) > 1000

                result = {
                    "name": name,
                    "path": path,
                    "url": url,
                    "status_code": response.status if response else "unknown",
                    "title": page_title,
                    "has_content": has_content,
                    "console_errors": len(console_errors),
                    "screenshot": f"reports/smoke/screens/{name}.png",
                    "success": response and response.status == 200 and has_content,
                }

                results.append(result)

                status = "✅" if result["success"] else "❌"
                print(
                    f"  {status} {name}: {response.status if response else 'ERROR'} | Title: {page_title[:50]}..."
                )

            except Exception as e:
                print(f"  ❌ {name}: ERROR - {e!s}")
                result = {
                    "name": name,
                    "path": path,
                    "url": url,
                    "status_code": "error",
                    "error": str(e),
                    "success": False,
                }
                results.append(result)

        await browser.close()

    # Test API endpoints
    print("\nTesting API endpoints...")

    api_tests = [
        {"url": f"{base_url}/docs", "name": "api_docs"},
        {"url": f"{base_url}/api/quotes?symbols=BTC-USD", "name": "quotes_api"},
        {"url": f"{base_url}/api/market-summary", "name": "market_summary"},
    ]

    for api_test in api_tests:
        try:
            response = requests.get(api_test["url"], timeout=5)
            success = response.status_code == 200
            print(f"  {'✅' if success else '❌'} {api_test['name']}: {response.status_code}")

            results.append(
                {
                    "name": api_test["name"],
                    "url": api_test["url"],
                    "status_code": response.status_code,
                    "success": success,
                }
            )

        except Exception as e:
            print(f"  ❌ {api_test['name']}: ERROR - {e!s}")
            results.append(
                {
                    "name": api_test["name"],
                    "url": api_test["url"],
                    "error": str(e),
                    "success": False,
                }
            )

    return results


def generate_report(results):
    """Generate smoke test report"""

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Count successes
    page_tests = [r for r in results if "screenshot" in r]
    api_tests = [r for r in results if "screenshot" not in r]

    page_success = sum(1 for r in page_tests if r["success"])
    api_success = sum(1 for r in api_tests if r["success"])

    report = f"""Sofia V2 - Automated Smoke Test Report
==========================================
Generated: {timestamp}
Branch: fix/ui-restore-polish-20250830
UI Server: http://127.0.0.1:8005 ⭐ (ACTIVE)

PAGE TESTS SUMMARY:
==================
Total Pages: {len(page_tests)}
Successful: {page_success}/{len(page_tests)}
Success Rate: {(page_success/len(page_tests)*100):.1f}%

PAGE RESULTS:
============
"""

    for result in page_tests:
        status = "✅ PASS" if result["success"] else "❌ FAIL"
        report += f"{status} {result['name'].upper()}\n"
        report += f"  URL: {result['url']}\n"
        report += f"  Status: {result.get('status_code', 'unknown')}\n"
        report += f"  Title: {result.get('title', 'N/A')[:60]}...\n"
        report += f"  Console Errors: {result.get('console_errors', 'N/A')}\n"
        report += f"  Screenshot: {result.get('screenshot', 'N/A')}\n"
        if "error" in result:
            report += f"  Error: {result['error']}\n"
        report += "\n"

    report += f"""API TESTS SUMMARY:
=================
Total APIs: {len(api_tests)}
Successful: {api_success}/{len(api_tests)}
Success Rate: {(api_success/len(api_tests)*100):.1f}%

API RESULTS:
===========
"""

    for result in api_tests:
        status = "✅ PASS" if result["success"] else "❌ FAIL"
        report += f"{status} {result['name'].upper()}\n"
        report += f"  URL: {result['url']}\n"
        report += f"  Status: {result.get('status_code', 'unknown')}\n"
        if "error" in result:
            report += f"  Error: {result['error']}\n"
        report += "\n"

    overall_success = (page_success + api_success) / (len(page_tests) + len(api_tests)) * 100

    report += f"""OVERALL RESULT:
==============
Overall Success Rate: {overall_success:.1f}%
Status: {'✅ PASS' if overall_success >= 80 else '⚠️ PARTIAL' if overall_success >= 60 else '❌ FAIL'}

Test completed at: {timestamp}
Screenshots saved to: reports/smoke/screens/
"""

    return report


async def main():
    """Main test runner"""

    print("Sofia V2 Automated Smoke Test")
    print("============================")

    # Run tests
    results = await run_smoke_tests()

    # Generate report
    report = generate_report(results)

    # Save report
    with open("reports/smoke/summary.txt", "w") as f:
        f.write(report)

    # Save JSON results
    with open("reports/smoke/results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)

    print("\n" + "=" * 50)
    print("SMOKE TEST COMPLETED")
    print("=" * 50)
    print("Report saved: reports/smoke/summary.txt")
    print("Screenshots: reports/smoke/screens/")

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
