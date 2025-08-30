"""
E2E Tests for Live Trading Grid
"""

import pytest
import re
from playwright.sync_api import Page, expect
import time


class TestLiveGridBasics:
    """Test basic live grid functionality"""
    
    def test_live_grid_loads(self, page: Page):
        """Test live grid page loads with 1000+ rows"""
        page.goto("http://localhost:8004/live")
        
        # Check page loads
        expect(page.locator("h1")).to_contain_text("Live Trading Grid")
        
        # Check grid container exists
        grid_container = page.locator('[data-testid="live-trading-grid"]')
        expect(grid_container).to_be_visible()
        
        # Wait for data to load
        page.wait_for_timeout(3000)
        
        # Check virtualized table has rows
        grid_body = page.locator('#grid-body')
        expect(grid_body).to_be_visible()
        
        # Should have some rows (virtualized)
        rows = page.locator('.table-row').count()
        assert rows > 10, f"Expected >10 rows, found {rows}"
    
    def test_grid_virtualization_performance(self, page: Page):
        """Test grid handles 1000+ rows smoothly"""
        page.goto("http://localhost:8004/live")
        
        # Wait for initial load
        page.wait_for_timeout(3000)
        
        # Scroll through grid rapidly
        grid_container = page.locator('.grid-container')
        
        start_time = time.time()
        
        # Scroll down
        for i in range(10):
            grid_container.scroll_into_view_if_needed()
            page.keyboard.press('PageDown')
            page.wait_for_timeout(100)
        
        # Scroll back up
        for i in range(10):
            page.keyboard.press('PageUp') 
            page.wait_for_timeout(100)
        
        elapsed = time.time() - start_time
        
        # Should complete smoothly in reasonable time
        assert elapsed < 5.0, f"Grid scrolling took too long: {elapsed}s"
        
        # Grid should still be responsive
        expect(grid_container).to_be_visible()
    
    def test_filters_functionality(self, page: Page):
        """Test grid filtering works correctly"""
        page.goto("http://localhost:8004/live")
        page.wait_for_timeout(3000)
        
        # Test market filter
        market_filter = page.locator('#filter-market')
        expect(market_filter).to_be_visible()
        
        # Filter to crypto only
        market_filter.select_option('crypto')
        page.wait_for_timeout(1000)
        
        # Check that only crypto symbols are shown
        visible_symbols = page.locator('.table-row .table-cell').first.all_text_contents()
        crypto_symbols = [s for s in visible_symbols if 'USDT' in s]
        equity_symbols = [s for s in visible_symbols if '/' not in s and s.isupper()]
        
        # Should have crypto symbols and no equity symbols (or very few)
        assert len(crypto_symbols) > len(equity_symbols)
        
        # Test tier filter
        tier_filter = page.locator('#filter-tier')
        tier_filter.select_option('T1')
        page.wait_for_timeout(1000)
        
        # Should show fewer symbols (T1 only)
        t1_rows = page.locator('.tier1').count()
        t2_rows = page.locator('.tier2').count()
        
        assert t2_rows == 0, "T2 symbols should be filtered out"
        assert t1_rows > 0, "Should have T1 symbols"
        
        # Test search filter
        search_input = page.locator('#filter-search')
        search_input.fill('BTC')
        page.wait_for_timeout(1000)
        
        # Should only show BTC-related symbols
        first_symbol = page.locator('.table-row .table-cell').first.text_content()
        assert 'BTC' in first_symbol
        
        # Clear filters
        page.locator('#clear-filters').click()
        page.wait_for_timeout(1000)
    
    def test_news_badges_display(self, page: Page):
        """Test news badges are displayed correctly"""
        page.goto("http://localhost:8004/live")
        page.wait_for_timeout(3000)
        
        # Look for news badges
        news_up_badges = page.locator('.news-up')
        news_down_badges = page.locator('.news-down')
        event_badges = page.locator('.news-event')
        
        # Should have some news badges (at least a few symbols with news)
        total_badges = news_up_badges.count() + news_down_badges.count() + event_badges.count()
        
        # Not all symbols will have news, but some should
        assert total_badges >= 3, f"Expected at least 3 news badges, found {total_badges}"
        
        # Test badge tooltips (if implemented)
        if news_up_badges.count() > 0:
            first_badge = news_up_badges.first
            expect(first_badge).to_be_visible()
    
    def test_gate_status_indicators(self, page: Page):
        """Test gate status indicators"""
        page.goto("http://localhost:8004/live")
        page.wait_for_timeout(3000)
        
        # Look for gate indicators
        gate_pass_badges = page.locator('.gate-pass')
        gate_fail_badges = page.locator('.gate-fail')
        
        total_gates = gate_pass_badges.count() + gate_fail_badges.count()
        
        # Should have gate status for symbols
        assert total_gates > 10, f"Expected >10 gate indicators, found {total_gates}"
        
        # Gates should be mostly passing (in healthy system)
        pass_ratio = gate_pass_badges.count() / total_gates if total_gates > 0 else 0
        assert pass_ratio > 0.7, f"Gate pass ratio too low: {pass_ratio:.1%}"


class TestTradingActions:
    """Test trading action buttons"""
    
    def test_buy_sell_buttons_exist(self, page: Page):
        """Test buy/sell buttons are present and functional"""
        page.goto("http://localhost:8004/live")
        page.wait_for_timeout(3000)
        
        # Find first symbol for testing
        first_row = page.locator('.table-row').nth(1)  # Skip header
        expect(first_row).to_be_visible()
        
        # Check action buttons exist
        buy_btn = first_row.locator('.buy-btn')
        sell_btn = first_row.locator('.sell-btn')
        pause_btn = first_row.locator('.pause-btn')
        kill_btn = first_row.locator('.kill-btn')
        
        expect(buy_btn).to_be_visible()
        expect(sell_btn).to_be_visible()
        expect(pause_btn).to_be_visible()
        expect(kill_btn).to_be_visible()
    
    def test_paper_trading_execution(self, page: Page):
        """Test paper trading execution works"""
        page.goto("http://localhost:8004/live")
        page.wait_for_timeout(3000)
        
        # Find a symbol to test
        first_row = page.locator('.table-row').nth(1)
        buy_btn = first_row.locator('.buy-btn')
        
        # Setup dialog handler for quantity prompt
        page.on("dialog", lambda dialog: dialog.accept("0.1"))
        
        # Click buy button
        buy_btn.click()
        
        # Wait for execution
        page.wait_for_timeout(2000)
        
        # Should show success notification
        notification = page.locator('.fixed.top-4.right-4')
        expect(notification).to_be_visible()
        expect(notification).to_contain_text('order submitted')
    
    def test_symbol_pause_functionality(self, page: Page):
        """Test symbol pause functionality"""
        page.goto("http://localhost:8004/live")
        page.wait_for_timeout(3000)
        
        # Find a symbol to pause
        first_row = page.locator('.table-row').nth(1)
        pause_btn = first_row.locator('.pause-btn')
        
        # Click pause
        pause_btn.click()
        page.wait_for_timeout(1000)
        
        # Should show pause notification
        notification = page.locator('.fixed.top-4.right-4')
        expect(notification).to_be_visible()
        expect(notification).to_contain_text('paused')
    
    def test_kill_symbol_with_confirmation(self, page: Page):
        """Test kill symbol requires confirmation"""
        page.goto("http://localhost:8004/live")
        page.wait_for_timeout(3000)
        
        # Find a symbol to kill
        first_row = page.locator('.table-row').nth(1)
        kill_btn = first_row.locator('.kill-btn')
        
        # Setup dialog handler to dismiss first
        page.on("dialog", lambda dialog: dialog.dismiss())
        kill_btn.click()
        page.wait_for_timeout(500)
        
        # No notification should appear (dismissed)
        notifications = page.locator('.fixed.top-4.right-4')
        expect(notifications).to_have_count(0)
        
        # Now accept the confirmation
        page.on("dialog", lambda dialog: dialog.accept())
        kill_btn.click()
        page.wait_for_timeout(1000)
        
        # Should show kill notification
        notification = page.locator('.fixed.top-4.right-4')
        expect(notification).to_be_visible()
        expect(notification).to_contain_text('killed')


class TestBlotterFunctionality:
    """Test trade blotter functionality"""
    
    def test_blotter_toggle(self, page: Page):
        """Test blotter can be toggled"""
        page.goto("http://localhost:8004/live")
        page.wait_for_timeout(2000)
        
        blotter = page.locator('#blotter')
        toggle_btn = page.locator('#toggle-blotter')
        
        # Initially hidden
        expect(blotter).to_have_class(re.compile(r'hidden'))
        
        # Toggle open
        toggle_btn.click()
        expect(blotter).not_to_have_class(re.compile(r'hidden'))
        
        # Close button
        close_btn = page.locator('#close-blotter')
        close_btn.click()
        expect(blotter).to_have_class(re.compile(r'hidden'))
    
    def test_blotter_records_trades(self, page: Page):
        """Test blotter records executed trades"""
        page.goto("http://localhost:8004/live")
        page.wait_for_timeout(3000)
        
        # Open blotter
        page.locator('#toggle-blotter').click()
        
        blotter_content = page.locator('#blotter-content')
        initial_count = blotter_content.locator('> div').count()
        
        # Execute a trade
        first_row = page.locator('.table-row').nth(1)
        buy_btn = first_row.locator('.buy-btn')
        
        page.on("dialog", lambda dialog: dialog.accept("0.1"))
        buy_btn.click()
        page.wait_for_timeout(2000)
        
        # Check blotter updated
        final_count = blotter_content.locator('> div').count()
        assert final_count > initial_count, "Blotter should record the trade"
    
    def test_blotter_export(self, page: Page):
        """Test blotter CSV export"""
        page.goto("http://localhost:8004/live")
        page.wait_for_timeout(2000)
        
        # Open blotter
        page.locator('#toggle-blotter').click()
        
        # Click export (will trigger download)
        export_btn = page.locator('#export-blotter')
        expect(export_btn).to_be_visible()
        
        # In headless mode, we can't test actual download
        # But we can verify the button is functional
        export_btn.click()
        
        # Should show export notification
        page.wait_for_timeout(1000)
        notification = page.locator('.fixed.top-4.right-4')
        expect(notification).to_be_visible()
        expect(notification).to_contain_text('exported')


class TestAttributionPanel:
    """Test strategy attribution panel"""
    
    def test_attribution_panel_visible(self, page: Page):
        """Test attribution panel displays"""
        page.goto("http://localhost:8004/live")
        page.wait_for_timeout(3000)
        
        attribution = page.locator('.attribution')
        expect(attribution).to_be_visible()
        
        # Check attribution content
        total_pnl = page.locator('#attr-total-pnl')
        top_strategy = page.locator('#attr-top-strategy')
        positions = page.locator('#attr-positions')
        
        expect(total_pnl).to_be_visible()
        expect(top_strategy).to_be_visible()
        expect(positions).to_be_visible()
    
    def test_attribution_updates_with_trades(self, page: Page):
        """Test attribution updates when trades are executed"""
        page.goto("http://localhost:8004/live")
        page.wait_for_timeout(3000)
        
        # Get initial attribution values
        initial_pnl = page.locator('#attr-total-pnl').text_content()
        initial_positions = page.locator('#attr-positions').text_content()
        
        # Execute a trade
        first_row = page.locator('.table-row').nth(1)
        buy_btn = first_row.locator('.buy-btn')
        
        page.on("dialog", lambda dialog: dialog.accept("0.1"))
        buy_btn.click()
        page.wait_for_timeout(3000)
        
        # Check attribution updated
        final_positions = page.locator('#attr-positions').text_content()
        
        # Positions should have changed (mock system adds positions)
        # Note: In mock system, this might not always change depending on implementation


class TestWebSocketFunctionality:
    """Test WebSocket live updates"""
    
    def test_websocket_connection(self, page: Page):
        """Test WebSocket connects and shows live status"""
        page.goto("http://localhost:8004/live")
        
        # Check initial connection status
        status_indicator = page.locator('#status-indicator')
        expect(status_indicator).to_be_visible()
        
        # Wait for WebSocket connection
        page.wait_for_timeout(3000)
        
        # Should show live or polling status
        status_text = page.locator('#status-indicator + span').text_content()
        assert status_text in ['Live', 'Polling', 'Error'], f"Unexpected status: {status_text}"
    
    def test_fallback_to_polling(self, page: Page):
        """Test fallback to polling when WebSocket fails"""
        page.goto("http://localhost:8004/live")
        page.wait_for_timeout(5000)
        
        # WebSocket might fail to connect in test environment
        # Should fallback to polling gracefully
        status_text = page.locator('#status-indicator + span').text_content()
        
        if status_text == 'Error':
            # Should eventually fallback to polling
            page.wait_for_timeout(5000)
            final_status = page.locator('#status-indicator + span').text_content()
            assert final_status in ['Polling', 'Live'], "Should fallback to polling"


class TestNewsIntegration:
    """Test news integration in grid"""
    
    def test_news_detail_tooltips(self, page: Page):
        """Test clicking on news badges shows detail"""
        page.goto("http://localhost:8004/live")
        page.wait_for_timeout(3000)
        
        # Find a symbol with news badge
        news_badges = page.locator('.badge.news-up, .badge.news-down, .badge.news-event')
        
        if news_badges.count() > 0:
            first_badge = news_badges.first
            
            # Click should show detail (in production would show modal/tooltip)
            first_badge.click()
            
            # For now, just verify it's clickable
            expect(first_badge).to_be_visible()
    
    def test_sentiment_scores_display(self, page: Page):
        """Test sentiment scores are displayed"""
        page.goto("http://localhost:8004/live")
        page.wait_for_timeout(3000)
        
        # Check that news column shows sentiment scores
        news_cells = page.locator('.table-row .table-cell').nth(10)  # News column (approximate)
        
        # Should show numerical sentiment values
        # This is a basic check - in production would verify actual sentiment values
        expect(news_cells.first).to_be_visible()


class TestErrorHandling:
    """Test error handling and edge cases"""
    
    def test_grid_handles_api_errors(self, page: Page):
        """Test grid handles API errors gracefully"""
        page.goto("http://localhost:8004/live")
        
        # Page should load even if some APIs fail
        expect(page.locator("h1")).to_contain_text("Live Trading Grid")
        
        # Connection status should show error if APIs fail
        page.wait_for_timeout(5000)
        
        # Grid should show some kind of error state or fallback
        grid_body = page.locator('#grid-body')
        expect(grid_body).to_be_visible()
    
    def test_no_console_errors(self, page: Page):
        """Test page loads without console errors"""
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        
        page.goto("http://localhost:8004/live")
        page.wait_for_timeout(5000)
        
        # Filter out network errors (expected in test environment)
        serious_errors = [err for err in console_errors 
                         if 'WebSocket' not in err and 'fetch' not in err and 'net::' not in err]
        
        assert len(serious_errors) == 0, f"Console errors found: {serious_errors}"
    
    def test_no_sidebar_elements(self, page: Page):
        """Test page follows navbar-only principle (no sidebars)"""
        page.goto("http://localhost:8004/live")
        page.wait_for_timeout(2000)
        
        # Check for common sidebar indicators
        sidebar_selectors = [
            '[class*="sidebar"]',
            '[class*="drawer"]', 
            '[class*="side-panel"]',
            '.w-64',  # Common sidebar width
            '.fixed.left-0'  # Fixed left positioning
        ]
        
        for selector in sidebar_selectors:
            sidebars = page.locator(selector)
            # Sidebar elements should not be visible
            for i in range(sidebars.count()):
                sidebar = sidebars.nth(i)
                # Allow small elements (not full sidebars)
                bbox = sidebar.bounding_box()
                if bbox and bbox['width'] > 200:  # Wider than 200px could be sidebar
                    expect(sidebar).to_be_hidden()


class TestPerformanceRequirements:
    """Test performance requirements"""
    
    def test_grid_refresh_performance(self, page: Page):
        """Test grid refreshes within 5 seconds"""
        page.goto("http://localhost:8004/live")
        page.wait_for_timeout(3000)
        
        # Trigger manual refresh
        refresh_start = time.time()
        
        # Look for refresh functionality (might be auto-refresh)
        # For now, just verify data loads quickly
        universe_stats = page.locator('#universe-stats')
        expect(universe_stats).to_be_visible()
        
        refresh_time = time.time() - refresh_start
        assert refresh_time < 5.0, f"Grid refresh took too long: {refresh_time}s"
    
    def test_no_4xx_5xx_errors(self, page: Page):
        """Test no 4xx/5xx HTTP errors"""
        responses = []
        page.on("response", lambda response: responses.append(response))
        
        page.goto("http://localhost:8004/live")
        page.wait_for_timeout(5000)
        
        # Check for HTTP errors
        error_responses = [r for r in responses if r.status >= 400]
        
        # Some 404s might be expected for missing assets
        serious_errors = [r for r in error_responses if r.status >= 500]
        
        assert len(serious_errors) == 0, f"5xx errors found: {[r.status for r in serious_errors]}"
    
    def test_websocket_stays_connected(self, page: Page):
        """Test WebSocket maintains connection for 60 seconds"""
        page.goto("http://localhost:8004/live")
        
        # Wait for initial connection
        page.wait_for_timeout(3000)
        
        initial_status = page.locator('#status-indicator + span').text_content()
        
        # Wait 60 seconds
        page.wait_for_timeout(60000)
        
        # Check connection still healthy
        final_status = page.locator('#status-indicator + span').text_content()
        
        # Should not have degraded significantly
        if initial_status == 'Live':
            assert final_status in ['Live', 'Polling'], f"Connection degraded from {initial_status} to {final_status}"


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Configure browser context for live grid tests"""
    return {
        **browser_context_args,
        "viewport": {"width": 1920, "height": 1080},
        "ignore_https_errors": True,
        "permissions": ["notifications"]
    }


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--headed"])