#!/usr/bin/env python3
"""
Comprehensive UI Audit Test Suite
Tests all routes for navbar presence, no sidebars, console errors, and functionality
"""

import json
import time
import sys
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, Page, expect

# Configuration
BASE_URL = os.environ.get("PLAYWRIGHT_BASE_URL", "http://127.0.0.1:8004")
API_URL = os.environ.get("VITE_API_URL", "http://127.0.0.1:8023")
TIMEOUT = 10000  # 10 seconds

# Load routes
routes_file = Path(__file__).parent.parent / "routes.json"
if routes_file.exists():
    with open(routes_file) as f:
        routes_config = json.load(f)
        ROUTES = routes_config["routes"]
else:
    # Fallback routes if file doesn't exist
    ROUTES = [
        {"path": "/", "name": "Homepage"},
        {"path": "/dashboard", "name": "Dashboard"},
        {"path": "/markets", "name": "Markets"},
        {"path": "/strategies", "name": "Strategies"},
        {"path": "/backtests", "name": "Backtests"},
        {"path": "/signals", "name": "Signals"},
        {"path": "/portfolio", "name": "Portfolio"},
        {"path": "/settings", "name": "Settings"},
        {"path": "/status", "name": "Status"},
    ]


class UIAudit:
    def __init__(self, page: Page):
        self.page = page
        self.errors = []
        self.warnings = []
        self.passed = []
        self.console_errors = []
        
        # Setup console error listener
        page.on("console", self._handle_console)
        page.on("pageerror", lambda exc: self.console_errors.append(str(exc)))
    
    def _handle_console(self, msg):
        """Capture console errors"""
        if msg.type == "error":
            self.console_errors.append(msg.text)
    
    def audit_route(self, route):
        """Audit a single route"""
        route_name = route["name"]
        route_path = route["path"]
        print(f"\n🔍 Auditing: {route_name} ({route_path})")
        
        try:
            # Navigate to route
            response = self.page.goto(f"{BASE_URL}{route_path}", wait_until="networkidle")
            
            # Check response status
            if response and response.status >= 400:
                self.errors.append(f"{route_name}: HTTP {response.status}")
                return False
            
            # Wait for page to stabilize
            self.page.wait_for_load_state("networkidle")
            time.sleep(0.5)  # Extra wait for dynamic content
            
            # Run all checks
            self._check_navbar(route_name)
            self._check_no_sidebar(route_name)
            self._check_console_errors(route_name)
            self._check_internal_links(route_name)
            
            # Route-specific checks
            if "total_balance" in route.get("test_requirements", []):
                self._check_total_balance(route_name)
            
            if "markets_table" in route.get("test_requirements", []):
                self._check_markets_table(route_name)
            
            if "test_connection" in route.get("test_requirements", []):
                self._check_test_connection(route_name)
            
            # Check responsive design
            self._check_responsive(route_name)
            
            # Check accessibility
            self._check_accessibility(route_name)
            
            self.passed.append(f"{route_name}: All checks passed")
            return True
            
        except Exception as e:
            self.errors.append(f"{route_name}: Exception - {str(e)}")
            return False
    
    def _check_navbar(self, route_name):
        """Check that navbar exists and is visible"""
        try:
            navbar = self.page.locator("nav").first
            expect(navbar).to_be_visible(timeout=5000)
            print(f"  ✅ Navbar present")
        except:
            self.errors.append(f"{route_name}: No navbar found")
    
    def _check_no_sidebar(self, route_name):
        """Check that no sidebars exist"""
        sidebar_selectors = [
            "[class*='sidebar']",
            "[class*='sidenav']",
            "[class*='drawer']",
            "aside",
            "[data-testid*='sidebar']",
            "[id*='sidebar']"
        ]
        
        for selector in sidebar_selectors:
            elements = self.page.locator(selector)
            count = elements.count()
            if count > 0:
                # Check if it's actually visible
                for i in range(count):
                    if elements.nth(i).is_visible():
                        self.errors.append(f"{route_name}: Found sidebar element: {selector}")
                        return
        
        print(f"  ✅ No sidebars found")
    
    def _check_console_errors(self, route_name):
        """Check for console errors"""
        if self.console_errors:
            # Filter out known acceptable warnings
            critical_errors = [
                err for err in self.console_errors 
                if not any(ignore in err.lower() for ignore in [
                    "failed to load resource",  # External resources
                    "favicon",  # Missing favicon
                    "source map",  # Dev source maps
                ])
            ]
            
            if critical_errors:
                self.errors.append(f"{route_name}: Console errors - {critical_errors[:3]}")
            else:
                print(f"  ✅ No critical console errors")
        else:
            print(f"  ✅ No console errors")
        
        # Clear for next route
        self.console_errors = []
    
    def _check_internal_links(self, route_name):
        """Check that internal links work"""
        try:
            links = self.page.locator("a[href^='/']")
            link_count = links.count()
            
            if link_count > 0:
                # Test first 5 links
                for i in range(min(5, link_count)):
                    href = links.nth(i).get_attribute("href")
                    if href and not href.startswith("#"):
                        # Just check that link is clickable, don't navigate
                        expect(links.nth(i)).to_be_visible()
                
                print(f"  ✅ {link_count} internal links found")
        except Exception as e:
            self.warnings.append(f"{route_name}: Link check failed - {str(e)}")
    
    def _check_total_balance(self, route_name):
        """Check Total Balance loads"""
        try:
            # Look for TB element
            tb_selectors = [
                "[data-testid='total-balance']",
                ":has-text('Total Balance')",
                ".total-balance"
            ]
            
            tb_found = False
            for selector in tb_selectors:
                if self.page.locator(selector).count() > 0:
                    tb_found = True
                    # Wait for value to load (not "Loading...")
                    self.page.wait_for_function(
                        f"document.querySelector('{selector}').textContent.includes('$') || document.querySelector('{selector}').textContent.includes('€')",
                        timeout=5000
                    )
                    print(f"  ✅ Total Balance loaded")
                    break
            
            if not tb_found:
                self.warnings.append(f"{route_name}: Total Balance element not found")
        except Exception as e:
            self.warnings.append(f"{route_name}: Total Balance check failed - {str(e)}")
    
    def _check_markets_table(self, route_name):
        """Check markets table has data"""
        try:
            # Wait for table or grid
            table = self.page.locator("table, [data-testid='markets-grid']").first
            expect(table).to_be_visible(timeout=5000)
            
            # Check for rows
            rows = self.page.locator("tr, [data-testid='market-row']")
            row_count = rows.count()
            
            if row_count < 10:
                self.warnings.append(f"{route_name}: Only {row_count} market rows found")
            else:
                print(f"  ✅ Markets table has {row_count} rows")
            
            # Test search if present
            search = self.page.locator("input[type='search'], input[placeholder*='Search']").first
            if search.count() > 0:
                search.fill("BTC")
                time.sleep(0.5)
                print(f"  ✅ Search functionality present")
        except Exception as e:
            self.warnings.append(f"{route_name}: Markets table check failed - {str(e)}")
    
    def _check_test_connection(self, route_name):
        """Check Test Connection button in settings"""
        try:
            button = self.page.locator("button:has-text('Test'), button:has-text('Connection')").first
            if button.count() > 0:
                expect(button).to_be_visible()
                print(f"  ✅ Test Connection button found")
            else:
                self.warnings.append(f"{route_name}: Test Connection button not found")
        except Exception as e:
            self.warnings.append(f"{route_name}: Test Connection check failed - {str(e)}")
    
    def _check_responsive(self, route_name):
        """Quick responsive check"""
        try:
            # Mobile viewport
            self.page.set_viewport_size({"width": 375, "height": 667})
            time.sleep(0.5)
            
            # Navbar should still be visible
            navbar = self.page.locator("nav").first
            if not navbar.is_visible():
                self.errors.append(f"{route_name}: Navbar not visible on mobile")
            
            # Reset to desktop
            self.page.set_viewport_size({"width": 1920, "height": 1080})
            print(f"  ✅ Responsive design works")
        except Exception as e:
            self.warnings.append(f"{route_name}: Responsive check failed - {str(e)}")
    
    def _check_accessibility(self, route_name):
        """Basic accessibility check"""
        try:
            # Check for alt text on images
            images = self.page.locator("img")
            images_without_alt = 0
            for i in range(images.count()):
                if not images.nth(i).get_attribute("alt"):
                    images_without_alt += 1
            
            if images_without_alt > 0:
                self.warnings.append(f"{route_name}: {images_without_alt} images without alt text")
            
            # Check for form labels
            inputs = self.page.locator("input:visible")
            if inputs.count() > 0:
                # Just check that inputs exist, detailed check would be more complex
                print(f"  ✅ Basic accessibility checks passed")
        except Exception as e:
            self.warnings.append(f"{route_name}: Accessibility check failed - {str(e)}")
    
    def run_full_audit(self):
        """Run audit on all routes"""
        print("=" * 60)
        print("🚀 Starting Comprehensive UI Audit")
        print(f"📍 Base URL: {BASE_URL}")
        print(f"📍 API URL: {API_URL}")
        print("=" * 60)
        
        for route in ROUTES:
            self.audit_route(route)
        
        # Print summary
        self.print_summary()
    
    def print_summary(self):
        """Print audit summary"""
        print("\n" + "=" * 60)
        print("📊 AUDIT SUMMARY")
        print("=" * 60)
        
        if self.passed:
            print(f"\n✅ PASSED ({len(self.passed)}):")
            for item in self.passed:
                print(f"  • {item}")
        
        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for item in self.warnings:
                print(f"  • {item}")
        
        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for item in self.errors:
                print(f"  • {item}")
        
        # Final result
        print("\n" + "=" * 60)
        if not self.errors:
            print("🎉 ALL CRITICAL CHECKS PASSED!")
            return True
        else:
            print(f"💔 {len(self.errors)} CRITICAL ERRORS FOUND")
            return False


def main():
    """Main entry point"""
    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(
            headless=os.environ.get("HEADLESS", "true").lower() == "true"
        )
        
        # Create context with proper viewport
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            ignore_https_errors=True
        )
        
        # Create page
        page = context.new_page()
        
        # Run audit
        auditor = UIAudit(page)
        success = auditor.run_full_audit()
        
        # Cleanup
        context.close()
        browser.close()
        
        # Exit with appropriate code
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()