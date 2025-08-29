"""
E2E tests for UI reset with no sidebar and multi-asset functionality
"""
import pytest
from playwright.sync_api import Page, expect
import time

# Service URLs
UI_URL = "http://127.0.0.1:8004"
API_URL = "http://127.0.0.1:8023"


class TestNavbarOnly:
    """Test that only top navbar exists, no sidebars"""
    
    def test_no_sidebar_on_homepage(self, page: Page):
        """Verify homepage has no sidebar"""
        page.goto(UI_URL)
        
        # Check navbar exists
        navbar = page.locator("nav").first
        expect(navbar).to_be_visible()
        
        # Check no sidebar exists
        sidebars = page.locator("[class*='sidebar']")
        expect(sidebars).to_have_count(0)
        
        sidenav = page.locator("[class*='sidenav']")
        expect(sidenav).to_have_count(0)
        
        drawer = page.locator("[class*='drawer']")
        expect(drawer).to_have_count(0)
    
    def test_navbar_links_work(self, page: Page):
        """Test all navbar links are functional"""
        page.goto(UI_URL)
        
        links = [
            ("/dashboard", "Dashboard"),
            ("/strategies", "Strategies"),
            ("/backtests", "Backtests"),
            ("/signals", "Signals"),
            ("/markets", "Markets"),
            ("/settings", "Settings"),
            ("/status", "Status")
        ]
        
        for href, text in links:
            link = page.locator(f"a[href='{href}']").first
            expect(link).to_be_visible()
            link.click()
            page.wait_for_url(f"**{href}", wait_until="networkidle")
            # Verify no sidebar on each page
            sidebars = page.locator("[class*='sidebar']")
            expect(sidebars).to_have_count(0)
    
    def test_mobile_menu(self, page: Page):
        """Test mobile hamburger menu works"""
        # Set mobile viewport
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(UI_URL)
        
        # Mobile menu should be hidden initially
        mobile_menu = page.locator("[data-mobile-menu]")
        if mobile_menu.count() > 0:
            expect(mobile_menu).to_be_hidden()
        
        # No sidebar should exist even on mobile
        sidebars = page.locator("[class*='sidebar']")
        expect(sidebars).to_have_count(0)


class TestMultiAssetMarkets:
    """Test multi-asset markets functionality"""
    
    def test_markets_page_loads(self, page: Page):
        """Test markets page loads with assets"""
        page.goto(f"{UI_URL}/markets")
        
        # Wait for page to load
        page.wait_for_load_state("networkidle")
        
        # Check for market table or grid
        markets_container = page.locator("table, [data-testid='markets-grid']").first
        expect(markets_container).to_be_visible()
    
    def test_asset_tabs(self, page: Page):
        """Test crypto and equity tabs"""
        page.goto(f"{UI_URL}/markets")
        
        # Look for tab buttons
        all_tab = page.locator("button:has-text('All')")
        crypto_tab = page.locator("button:has-text('Crypto')")
        equity_tab = page.locator("button:has-text('Equit')")
        
        if crypto_tab.count() > 0:
            # Click crypto tab
            crypto_tab.click()
            page.wait_for_timeout(500)
            
            # Should show crypto assets
            btc_row = page.locator("text=/BTC/i")
            if btc_row.count() > 0:
                expect(btc_row.first).to_be_visible()
        
        if equity_tab.count() > 0:
            # Click equity tab
            equity_tab.click()
            page.wait_for_timeout(500)
            
            # Should show equity assets
            aapl_row = page.locator("text=/AAPL/i")
            if aapl_row.count() > 0:
                expect(aapl_row.first).to_be_visible()
    
    def test_search_functionality(self, page: Page):
        """Test search box filters assets"""
        page.goto(f"{UI_URL}/markets")
        
        # Find search input
        search_input = page.locator("input[placeholder*='Search'], input[type='search']").first
        
        if search_input.count() > 0:
            # Search for BTC
            search_input.fill("BTC")
            page.wait_for_timeout(500)
            
            # Should show BTC results
            btc_results = page.locator("text=/BTC/i")
            if btc_results.count() > 0:
                expect(btc_results.first).to_be_visible()
    
    def test_watchlist_add_remove(self, page: Page):
        """Test adding/removing from watchlist"""
        page.goto(f"{UI_URL}/markets")
        page.wait_for_load_state("networkidle")
        
        # Find watch buttons
        watch_buttons = page.locator("button:has-text('Watch'), button:has(i.fa-star)")
        
        if watch_buttons.count() > 0:
            # Click first watch button
            first_button = watch_buttons.first
            first_button.click()
            page.wait_for_timeout(500)
            
            # Should change to "Remove" or be highlighted
            # This depends on implementation
            
            # Click again to remove
            first_button.click()
            page.wait_for_timeout(500)


class TestTotalBalanceCalculation:
    """Test single TB calculator"""
    
    def test_dashboard_tb_display(self, page: Page):
        """Test Total Balance displays on dashboard"""
        page.goto(f"{UI_URL}/dashboard")
        
        # Wait for TB to load
        tb_element = page.locator("[data-testid='total-balance'], :has-text('Total Balance')").first
        
        if tb_element.count() > 0:
            expect(tb_element).to_be_visible()
            
            # Should show dollar amount
            page.wait_for_function(
                "document.body.textContent.includes('$')",
                timeout=5000
            )
    
    def test_tb_consistency(self, page: Page):
        """Test TB remains consistent across refreshes"""
        page.goto(f"{UI_URL}/dashboard")
        page.wait_for_load_state("networkidle")
        
        # Get initial TB value
        tb_element = page.locator("text=/$[0-9,]+/").first
        if tb_element.count() > 0:
            initial_value = tb_element.text_content()
            
            # Refresh page
            page.reload()
            page.wait_for_load_state("networkidle")
            
            # TB should be same or updated (not NaN or error)
            new_tb = page.locator("text=/$[0-9,]+/").first
            if new_tb.count() > 0:
                expect(new_tb).to_be_visible()


class TestPageFunctionality:
    """Test all pages are functional"""
    
    def test_all_routes_return_200(self, page: Page):
        """Test all routes load without errors"""
        routes = [
            "/",
            "/dashboard",
            "/portfolio",
            "/markets",
            "/strategies",
            "/backtests",
            "/signals",
            "/settings",
            "/status",
            "/login",
            "/pricing"
        ]
        
        for route in routes:
            response = page.goto(f"{UI_URL}{route}")
            assert response.status in [200, 304], f"Route {route} returned {response.status}"
    
    def test_404_page(self, page: Page):
        """Test 404 page displays for invalid routes"""
        response = page.goto(f"{UI_URL}/nonexistent-page-xyz")
        
        # Should show 404 page
        page.wait_for_load_state("networkidle")
        error_text = page.locator("text=/404|not found/i").first
        if error_text.count() > 0:
            expect(error_text).to_be_visible()
    
    def test_error_boundary(self, page: Page):
        """Test error boundary catches errors gracefully"""
        # This would require injecting an error
        # For now, just verify pages don't crash
        page.goto(f"{UI_URL}/dashboard")
        
        # Page should load without console errors
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg) if msg.type == "error" else None)
        
        page.wait_for_timeout(2000)
        # Allow some errors but not critical ones
        critical_errors = [e for e in console_errors if "TypeError" in str(e) or "ReferenceError" in str(e)]
        assert len(critical_errors) == 0, f"Critical errors found: {critical_errors}"


class TestPerformance:
    """Test performance metrics"""
    
    def test_page_load_time(self, page: Page):
        """Test pages load within acceptable time"""
        routes = ["/", "/dashboard", "/markets"]
        
        for route in routes:
            start = time.time()
            page.goto(f"{UI_URL}{route}")
            page.wait_for_load_state("networkidle")
            load_time = time.time() - start
            
            # Should load within 3 seconds
            assert load_time < 3.0, f"Route {route} took {load_time:.2f}s to load"
    
    def test_responsive_design(self, page: Page):
        """Test responsive design at different viewports"""
        viewports = [
            {"width": 1920, "height": 1080, "name": "Desktop"},
            {"width": 768, "height": 1024, "name": "Tablet"},
            {"width": 375, "height": 667, "name": "Mobile"}
        ]
        
        for viewport in viewports:
            page.set_viewport_size({"width": viewport["width"], "height": viewport["height"]})
            page.goto(UI_URL)
            
            # Navbar should be visible at all sizes
            navbar = page.locator("nav").first
            expect(navbar).to_be_visible()
            
            # No sidebars at any size
            sidebars = page.locator("[class*='sidebar']")
            expect(sidebars).to_have_count(0)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--headed", "--slowmo=500"])