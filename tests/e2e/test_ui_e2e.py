"""
End-to-end tests for Sofia V2 UI using Playwright
"""
import pytest
from playwright.sync_api import Page, expect
import time

# UI and API URLs
UI_URL = "http://127.0.0.1:8004"
API_URL = "http://127.0.0.1:8020"


class TestHomepage:
    """Test homepage functionality"""
    
    def test_homepage_loads(self, page: Page):
        """Test that homepage loads successfully"""
        page.goto(UI_URL)
        
        # Check for Sofia V2 branding
        expect(page.locator("text=SOFIA V2")).to_be_visible()
        
        # Check for AI Trading Platform text
        expect(page.locator("text=AI Trading Platform")).to_be_visible()
    
    def test_navigation_links_visible(self, page: Page):
        """Test that all navigation links are visible"""
        page.goto(UI_URL)
        
        # Check main navigation links
        expect(page.locator("a[href='/dashboard']")).to_be_visible()
        expect(page.locator("a[href='/portfolio']")).to_be_visible()
        expect(page.locator("a[href='/markets']")).to_be_visible()
        expect(page.locator("a[href='/trading']")).to_be_visible()
        expect(page.locator("a[href='/manual-trading']")).to_be_visible()
        expect(page.locator("a[href='/reliability']")).to_be_visible()
    
    def test_no_sidebar_present(self, page: Page):
        """Test that sidebar has been removed"""
        page.goto(UI_URL)
        
        # Check that sidebar element is not present
        sidebar = page.locator("aside")
        expect(sidebar).to_have_count(0)
    
    def test_responsive_design(self, page: Page):
        """Test responsive design at different viewport sizes"""
        # Desktop view
        page.set_viewport_size({"width": 1920, "height": 1080})
        page.goto(UI_URL)
        expect(page.locator("nav")).to_be_visible()
        
        # Tablet view
        page.set_viewport_size({"width": 768, "height": 1024})
        expect(page.locator("nav")).to_be_visible()
        
        # Mobile view
        page.set_viewport_size({"width": 375, "height": 667})
        expect(page.locator("nav")).to_be_visible()


class TestNavigation:
    """Test navigation between pages"""
    
    def test_navigate_to_dashboard(self, page: Page):
        """Test navigation to dashboard"""
        page.goto(UI_URL)
        page.click("a[href='/dashboard']")
        
        # Should navigate to dashboard
        expect(page).to_have_url(f"{UI_URL}/dashboard")
    
    def test_navigate_to_portfolio(self, page: Page):
        """Test navigation to portfolio"""
        page.goto(UI_URL)
        page.click("a[href='/portfolio']")
        
        # Should navigate to portfolio
        expect(page).to_have_url(f"{UI_URL}/portfolio")
    
    def test_navigate_to_markets(self, page: Page):
        """Test navigation to markets"""
        page.goto(UI_URL)
        page.click("a[href='/markets']")
        
        # Should navigate to markets
        expect(page).to_have_url(f"{UI_URL}/markets")
    
    def test_navigate_to_ai_trading(self, page: Page):
        """Test navigation to AI trading"""
        page.goto(UI_URL)
        page.click("a[href='/trading']")
        
        # Should navigate to AI trading
        expect(page).to_have_url(f"{UI_URL}/trading")
    
    def test_back_to_home(self, page: Page):
        """Test navigation back to home"""
        page.goto(f"{UI_URL}/portfolio")
        page.click("text=SOFIA V2")
        
        # Should navigate back to home
        expect(page).to_have_url(UI_URL + "/")


class TestErrorHandling:
    """Test error handling and 404 pages"""
    
    def test_404_page(self, page: Page):
        """Test 404 error page"""
        page.goto(f"{UI_URL}/nonexistent-page")
        
        # Should show 404 page
        expect(page.locator("text=404")).to_be_visible()
        expect(page.locator("text=Page Not Found")).to_be_visible()
    
    def test_404_back_to_home(self, page: Page):
        """Test navigation from 404 page back to home"""
        page.goto(f"{UI_URL}/nonexistent-page")
        
        # Click back to home button
        page.click("text=Back to Home")
        
        # Should navigate to homepage
        expect(page).to_have_url(UI_URL + "/")


class TestPerformance:
    """Test page performance"""
    
    def test_page_load_time(self, page: Page):
        """Test that pages load within acceptable time"""
        start_time = time.time()
        page.goto(UI_URL)
        page.wait_for_load_state("networkidle")
        load_time = time.time() - start_time
        
        # Page should load within 3 seconds
        assert load_time < 3.0, f"Page took {load_time:.2f}s to load"
    
    def test_navigation_speed(self, page: Page):
        """Test navigation speed between pages"""
        page.goto(UI_URL)
        
        routes = ["/dashboard", "/portfolio", "/markets"]
        
        for route in routes:
            start_time = time.time()
            page.click(f"a[href='{route}']")
            page.wait_for_load_state("networkidle")
            nav_time = time.time() - start_time
            
            # Navigation should complete within 2 seconds
            assert nav_time < 2.0, f"Navigation to {route} took {nav_time:.2f}s"
            
            # Go back to home for next test
            page.goto(UI_URL)


class TestAccessibility:
    """Test accessibility features"""
    
    def test_keyboard_navigation(self, page: Page):
        """Test keyboard navigation"""
        page.goto(UI_URL)
        
        # Tab through navigation links
        page.keyboard.press("Tab")
        page.keyboard.press("Tab")
        page.keyboard.press("Tab")
        
        # Press Enter to navigate
        page.keyboard.press("Enter")
        
        # Should navigate to a page
        assert page.url != UI_URL
    
    def test_focus_indicators(self, page: Page):
        """Test that focus indicators are visible"""
        page.goto(UI_URL)
        
        # Focus on first link
        first_link = page.locator("a").first
        first_link.focus()
        
        # Check that element has focus styling (this depends on CSS)
        # Just verify it can be focused
        expect(first_link).to_be_focused()


class TestThemeIntegrity:
    """Test that purple gradient theme is preserved"""
    
    def test_purple_gradient_present(self, page: Page):
        """Test that purple gradient is in the CSS"""
        page.goto(UI_URL)
        
        # Check for gradient classes in the page
        gradient_elements = page.locator("[class*='gradient']")
        assert gradient_elements.count() > 0, "No gradient elements found"
        
        # Check for purple color references
        purple_elements = page.locator("[class*='purple']")
        assert purple_elements.count() > 0, "No purple elements found"
    
    def test_dark_mode_active(self, page: Page):
        """Test that dark mode is active"""
        page.goto(UI_URL)
        
        # Check for dark class on html element
        html = page.locator("html")
        expect(html).to_have_class("dark")


class TestAPIIntegration:
    """Test UI-API integration"""
    
    def test_api_health_displayed(self, page: Page):
        """Test that API health status is displayed"""
        page.goto(UI_URL)
        
        # Look for API status indicators
        # This might be "Live Data" or similar indicator
        expect(page.locator("text=Live Data")).to_be_visible()


if __name__ == "__main__":
    # Run with: playwright install chromium
    # Then: python -m pytest tests/e2e/test_ui_e2e.py --headed
    pytest.main([__file__, "-v", "--tb=short"])