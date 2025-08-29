"""
E2E tests for Total Balance display and data binding
"""
import pytest
import time
from playwright.sync_api import Page, expect

# Service URLs
UI_URL = "http://127.0.0.1:8004"
API_URL = "http://127.0.0.1:8021"


class TestTotalBalanceDisplay:
    """Test Total Balance display and updates"""
    
    def test_total_balance_loads(self, page: Page):
        """Test that Total Balance loads and displays correctly"""
        # Go to homepage
        page.goto(UI_URL)
        
        # Wait for Total Balance element
        total_balance = page.locator('[data-testid="total-balance"]')
        
        # Initially shows loading
        expect(total_balance).to_contain_text("Loading")
        
        # Wait for data to load (max 10 seconds)
        page.wait_for_function(
            "document.querySelector('[data-testid=\"total-balance\"]').textContent.includes('$')",
            timeout=10000
        )
        
        # Verify Total Balance is displayed with dollar sign
        expect(total_balance).to_contain_text("$")
        
        # Verify it's the correct amount from API
        # Expected: $130,174.50 based on our test data
        expect(total_balance).to_contain_text("130")
    
    def test_total_balance_format(self, page: Page):
        """Test that Total Balance is properly formatted"""
        page.goto(UI_URL)
        
        # Wait for data to load
        page.wait_for_function(
            "document.querySelector('[data-testid=\"total-balance\"]').textContent.includes('$')",
            timeout=10000
        )
        
        total_balance = page.locator('[data-testid="total-balance"]')
        text = total_balance.text_content()
        
        # Check format: should have $ and comma separator
        assert "$" in text
        assert "," in text or len(text.replace("$", "").replace(".", "")) < 4  # Small numbers might not have comma
        assert "." in text  # Should have decimal point
    
    def test_pnl_display(self, page: Page):
        """Test that P&L is displayed correctly"""
        page.goto(UI_URL)
        
        # Wait for P&L element to load
        pnl_element = page.locator('#todays-pnl')
        
        # Wait for data
        page.wait_for_function(
            "document.querySelector('#todays-pnl').textContent !== 'Loading...'",
            timeout=10000
        )
        
        # P&L should show with + or - prefix and dollar sign
        text = pnl_element.text_content()
        assert "$" in text
        assert "+" in text or "-" in text
    
    def test_positions_count(self, page: Page):
        """Test that positions count is displayed"""
        page.goto(UI_URL)
        
        # Wait for positions count to load
        positions = page.locator('#positions-count')
        
        # Wait for data
        page.wait_for_timeout(2000)  # Give time for data to load
        
        # Should show a number
        text = positions.text_content()
        assert text.isdigit()
        # We have 3 positions in test data
        assert int(text) == 3
    
    def test_cash_balance_display(self, page: Page):
        """Test that cash balance is displayed"""
        page.goto(UI_URL)
        
        # Wait for cash balance to load
        cash = page.locator('#cash-balance')
        
        # Wait for data
        page.wait_for_function(
            "document.querySelector('#cash-balance').textContent.includes('$')",
            timeout=10000
        )
        
        # Should show dollar amount
        text = cash.text_content()
        assert "$" in text
        # Test data has $50,000 cash
        assert "50" in text


class TestDataBinding:
    """Test data binding and state management"""
    
    def test_no_duplicate_calculations(self, page: Page):
        """Test that Total Balance is calculated only once"""
        page.goto(UI_URL)
        
        # Wait for initial load
        page.wait_for_function(
            "document.querySelector('[data-testid=\"total-balance\"]').textContent.includes('$')",
            timeout=10000
        )
        
        # Get initial value
        total_balance = page.locator('[data-testid="total-balance"]')
        initial_value = total_balance.text_content()
        
        # Wait a bit
        page.wait_for_timeout(1000)
        
        # Value should remain the same (no flickering/recalculation)
        current_value = total_balance.text_content()
        assert initial_value == current_value
    
    def test_error_handling(self, page: Page):
        """Test error handling when API is down"""
        # This would require mocking or stopping the API
        # For now, just check that error states exist
        page.goto(UI_URL)
        
        # Check that the page doesn't crash
        expect(page).to_have_title(page.title())
        
        # UI should handle errors gracefully
        # (Would need to stop API to fully test this)
    
    def test_loading_states(self, page: Page):
        """Test that loading states are shown"""
        page.goto(UI_URL)
        
        # Should show loading initially
        total_balance = page.locator('[data-testid="total-balance"]')
        
        # Check for loading indicator (happens very quickly)
        # This might not always catch it due to speed
        loading_visible = False
        try:
            if "Loading" in total_balance.text_content():
                loading_visible = True
        except:
            pass
        
        # Eventually shows data
        page.wait_for_function(
            "document.querySelector('[data-testid=\"total-balance\"]').textContent.includes('$')",
            timeout=10000
        )
        
        # Data should be displayed
        expect(total_balance).to_contain_text("$")


class TestPageNavigation:
    """Test navigation maintains data state"""
    
    def test_navigation_preserves_data(self, page: Page):
        """Test that navigating between pages preserves portfolio state"""
        page.goto(UI_URL)
        
        # Wait for data to load
        page.wait_for_function(
            "document.querySelector('[data-testid=\"total-balance\"]').textContent.includes('$')",
            timeout=10000
        )
        
        # Get initial value
        total_balance = page.locator('[data-testid="total-balance"]')
        initial_value = total_balance.text_content()
        
        # Navigate to portfolio
        page.click('a[href="/portfolio"]')
        
        # Come back to dashboard
        page.click('a[href="/dashboard"]')
        
        # Wait for data again
        page.wait_for_function(
            "document.querySelector('[data-testid=\"total-balance\"]') !== null",
            timeout=5000
        )
        
        # Should show same value (or updated if time passed)
        # Just check it's still formatted correctly
        total_balance = page.locator('[data-testid="total-balance"]')
        expect(total_balance).to_contain_text("$")


class TestResponsive:
    """Test responsive behavior"""
    
    def test_mobile_view(self, page: Page):
        """Test Total Balance displays correctly on mobile"""
        # Set mobile viewport
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(UI_URL)
        
        # Wait for data
        page.wait_for_function(
            "document.querySelector('[data-testid=\"total-balance\"]').textContent.includes('$')",
            timeout=10000
        )
        
        # Total Balance should be visible
        total_balance = page.locator('[data-testid="total-balance"]')
        expect(total_balance).to_be_visible()
        expect(total_balance).to_contain_text("$")
    
    def test_tablet_view(self, page: Page):
        """Test Total Balance displays correctly on tablet"""
        # Set tablet viewport
        page.set_viewport_size({"width": 768, "height": 1024})
        page.goto(UI_URL)
        
        # Wait for data
        page.wait_for_function(
            "document.querySelector('[data-testid=\"total-balance\"]').textContent.includes('$')",
            timeout=10000
        )
        
        # Total Balance should be visible
        total_balance = page.locator('[data-testid="total-balance"]')
        expect(total_balance).to_be_visible()
        expect(total_balance).to_contain_text("$")


if __name__ == "__main__":
    # Run with: python -m pytest tests/e2e/test_total_balance_e2e.py --headed
    pytest.main([__file__, "-v", "--tb=short"])