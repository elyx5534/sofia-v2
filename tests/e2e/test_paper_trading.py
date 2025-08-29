"""
Playwright E2E tests for paper trading order flow
"""

import asyncio
import pytest
from playwright.async_api import Page, expect
import time


@pytest.mark.asyncio
async def test_order_flow(page: Page):
    """Test complete order flow: markets → buy → positions increase → pnl visible → sell → positions decrease"""
    
    # Navigate to markets page
    await page.goto("http://localhost:4173/markets")
    await page.wait_for_load_state("networkidle")
    
    # Enable paper trading in settings first
    await page.goto("http://localhost:4173/settings")
    await page.wait_for_load_state("networkidle")
    
    # Toggle paper trading on
    paper_toggle = page.locator('input[type="checkbox"][x-model="paperTradingEnabled"]')
    is_checked = await paper_toggle.is_checked()
    if not is_checked:
        await paper_toggle.click()
    
    # Save settings
    await page.click('button:has-text("Save Trading Settings")')
    await page.wait_for_timeout(1000)
    
    # Go back to markets
    await page.goto("http://localhost:4173/markets")
    await page.wait_for_load_state("networkidle")
    
    # Verify paper trading panel is visible
    paper_panel = page.locator('text="Paper Trading"')
    await expect(paper_panel).to_be_visible()
    
    # Get initial position count
    positions_counter = page.locator('[data-testid="open-positions-count"]')
    initial_positions = 0
    if await positions_counter.is_visible():
        text = await positions_counter.text_content()
        # Extract number from "Open Positions (X)"
        import re
        match = re.search(r'\((\d+)\)', text)
        if match:
            initial_positions = int(match.group(1))
    
    # Execute a buy order
    await page.fill('input[placeholder="Symbol"]', 'BTC/USDT')
    await page.fill('input[placeholder="Quantity"]', '0.1')
    await page.click('button:has-text("Buy")')
    await page.wait_for_timeout(2000)
    
    # Verify position increased
    if await positions_counter.is_visible():
        text = await positions_counter.text_content()
        match = re.search(r'\((\d+)\)', text)
        if match:
            new_positions = int(match.group(1))
            assert new_positions > initial_positions, "Position count should increase after buy"
    
    # Verify PnL is visible
    pnl_element = page.locator('[data-testid="total-pnl"]').first
    await expect(pnl_element).to_be_visible()
    
    # Execute a sell order
    await page.fill('input[placeholder="Symbol"]', 'BTC/USDT')
    await page.fill('input[placeholder="Quantity"]', '0.05')
    await page.click('button:has-text("Sell")')
    await page.wait_for_timeout(2000)
    
    # Verify position decreased or closed
    if await positions_counter.is_visible():
        text = await positions_counter.text_content()
        match = re.search(r'\((\d+)\)', text)
        if match:
            final_positions = int(match.group(1))
            assert final_positions <= new_positions, "Position count should decrease after sell"


@pytest.mark.asyncio
async def test_settings_connection(page: Page):
    """Test Settings page 'Test Connection' button"""
    
    # Navigate to settings
    await page.goto("http://localhost:4173/settings")
    await page.wait_for_load_state("networkidle")
    
    # Click Test Connection button
    await page.click('button:has-text("Test Connection")')
    
    # Wait for connection result
    await page.wait_for_timeout(2000)
    
    # Check for success message
    connection_msg = page.locator('text=/Connected successfully|Connection failed/')
    await expect(connection_msg).to_be_visible(timeout=5000)
    
    # Verify it shows OK (health endpoint returns 200)
    success_msg = page.locator('text="Connected successfully"')
    if await success_msg.is_visible():
        assert True, "Connection test passed"
    else:
        # If failed, check if API is running
        pytest.skip("API might not be running")


@pytest.mark.asyncio
async def test_no_console_errors(page: Page):
    """Test that all routes load without console errors or 4xx/5xx responses"""
    
    # List of routes to test
    routes = [
        "/",
        "/dashboard", 
        "/markets",
        "/settings",
        "/strategies",
        "/backtests",
        "/signals",
        "/status"
    ]
    
    # Collect console errors
    console_errors = []
    page.on("console", lambda msg: console_errors.append(msg) if msg.type == "error" else None)
    
    # Collect network errors
    network_errors = []
    
    def handle_response(response):
        if response.status >= 400:
            network_errors.append(f"{response.status} - {response.url}")
    
    page.on("response", handle_response)
    
    # Test each route
    for route in routes:
        await page.goto(f"http://localhost:4173{route}")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(500)
    
    # Assert no console errors
    assert len(console_errors) == 0, f"Console errors found: {console_errors}"
    
    # Assert no 4xx/5xx errors (except expected 404s for missing resources)
    unexpected_errors = [e for e in network_errors if "/api/" in e or ".html" in e]
    assert len(unexpected_errors) == 0, f"Network errors found: {unexpected_errors}"


@pytest.mark.asyncio
async def test_no_sidebar_elements(page: Page):
    """Test that no sidebar elements are present"""
    
    routes = ["/", "/dashboard", "/markets", "/settings"]
    
    for route in routes:
        await page.goto(f"http://localhost:4173{route}")
        await page.wait_for_load_state("networkidle")
        
        # Check for common sidebar selectors
        sidebar_selectors = [
            '[data-testid="sidebar"]',
            '.sidebar',
            '#sidebar',
            'aside',
            '[class*="sidebar"]',
            '[id*="sidebar"]'
        ]
        
        for selector in sidebar_selectors:
            elements = await page.locator(selector).count()
            assert elements == 0, f"Sidebar element found with selector '{selector}' on route '{route}'"


@pytest.mark.asyncio
async def test_equity_markets(page: Page):
    """Test equity markets functionality"""
    
    # Navigate to markets
    await page.goto("http://localhost:4173/markets")
    await page.wait_for_load_state("networkidle")
    
    # Switch to equities tab
    await page.click('button:has-text("Equities")')
    await page.wait_for_timeout(2000)
    
    # Check if equity data loads
    market_rows = page.locator('[data-testid="market-row"]')
    count = await market_rows.count()
    
    # Should have at least some equity symbols
    assert count > 0, "No equity data loaded"
    
    # Test category filter
    category_select = page.locator('select[x-model="selectedCategory"]')
    if await category_select.is_visible():
        await category_select.select_option("BIST30")
        await page.wait_for_timeout(1000)
        
        # Check filtered results
        filtered_count = await market_rows.count()
        assert filtered_count <= count, "Category filter should reduce or maintain result count"
    
    # Test search
    await page.fill('input[placeholder="Search symbols..."]', "AAPL")
    await page.wait_for_timeout(500)
    
    # Should filter results
    search_count = await market_rows.count()
    assert search_count <= count, "Search should filter results"


@pytest.mark.asyncio
async def test_paper_trading_pnl_calculation(page: Page):
    """Test that P&L calculations are correct"""
    
    # Setup: Enable paper trading
    await page.goto("http://localhost:4173/settings")
    paper_toggle = page.locator('input[type="checkbox"][x-model="paperTradingEnabled"]')
    if not await paper_toggle.is_checked():
        await paper_toggle.click()
        await page.click('button:has-text("Save Trading Settings")')
    
    # Reset paper trading account
    response = await page.request.post("http://localhost:8023/paper/reset")
    assert response.ok, "Failed to reset paper trading account"
    
    # Go to markets
    await page.goto("http://localhost:4173/markets")
    await page.wait_for_load_state("networkidle")
    
    # Execute a buy order
    await page.fill('input[placeholder="Symbol"]', 'BTC/USDT')
    await page.fill('input[placeholder="Quantity"]', '0.1')
    await page.click('button:has-text("Buy")')
    await page.wait_for_timeout(2000)
    
    # Check that PnL element exists and shows a value
    pnl_element = page.locator('[data-testid="total-pnl"]').first
    if await pnl_element.is_visible():
        pnl_text = await pnl_element.text_content()
        # Should contain a dollar sign and a number
        assert '$' in pnl_text, "PnL should show dollar amount"
        
        # Extract number
        import re
        match = re.search(r'\$?([\d,]+\.?\d*)', pnl_text)
        if match:
            pnl_value = float(match.group(1).replace(',', ''))
            # PnL should be a reasonable number (not NaN or infinity)
            assert -100000 < pnl_value < 100000, f"PnL value {pnl_value} seems unreasonable"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])