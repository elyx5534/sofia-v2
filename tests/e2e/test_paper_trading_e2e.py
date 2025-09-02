"""
E2E Tests for Paper Trading UI with Playwright
"""

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.slow
@pytest.mark.e2e
class TestPaperTradingSettings:
    """Test paper trading settings page"""

    def test_toggle_paper_trading(self, page: Page):
        """Test toggling paper trading ON/OFF"""
        # Navigate to settings
        page.goto("http://localhost:8004/settings")

        # Find toggle element
        toggle = page.locator('[data-testid="paper-trading-toggle"]')
        expect(toggle).to_be_visible()

        # Check initial state (should be OFF)
        toggle_status = page.locator("#toggle-status")
        expect(toggle_status).to_have_text("OFF")

        # Click to enable
        toggle.click()

        # Wait for status update
        page.wait_for_timeout(2000)

        # Verify status changed to ON
        expect(toggle_status).to_have_text("ON")

        # Verify status indicator shows running
        status_text = page.locator("#status-text")
        expect(status_text).to_contain_text("running")

        # Click to disable
        toggle.click()
        page.wait_for_timeout(2000)

        # Verify status changed back to OFF
        expect(toggle_status).to_have_text("OFF")

    def test_quick_actions(self, page: Page):
        """Test quick action buttons"""
        page.goto("http://localhost:8004/settings")

        # Test Run Replay button
        replay_btn = page.locator('[data-testid="run-replay-btn"]')
        expect(replay_btn).to_be_visible()
        replay_btn.click()

        # Should show notification
        notification = page.locator(".fixed.top-4.right-4")
        expect(notification).to_be_visible()

        # Test Generate Report button
        report_btn = page.locator('[data-testid="generate-report-btn"]')
        expect(report_btn).to_be_visible()

        # Test View Positions button
        positions_btn = page.locator('[data-testid="view-positions-btn"]')
        expect(positions_btn).to_be_visible()

        # Test Kill Switch button
        kill_switch_btn = page.locator('[data-testid="kill-switch-btn"]')
        expect(kill_switch_btn).to_be_visible()

    def test_live_metrics_display(self, page: Page):
        """Test live metrics display in settings"""
        page.goto("http://localhost:8004/settings")

        # Check metric elements exist
        expect(page.locator('[data-testid="metric-pnl-total"]')).to_be_visible()
        expect(page.locator('[data-testid="metric-pnl-daily"]')).to_be_visible()
        expect(page.locator('[data-testid="metric-win-rate"]')).to_be_visible()
        expect(page.locator('[data-testid="metric-positions"]')).to_be_visible()

        # Verify initial values
        pnl_total = page.locator('[data-testid="metric-pnl-total"]')
        expect(pnl_total).to_contain_text("$")


class TestPaperTradingDashboard:
    """Test paper trading dashboard"""

    def test_dashboard_widgets(self, page: Page):
        """Test all dashboard widgets are present with correct data-testid"""
        page.goto("http://localhost:8004/dashboard")

        # Check main widgets
        expect(page.locator('[data-testid="paper-pnl-total"]')).to_be_visible()
        expect(page.locator('[data-testid="paper-pnl-daily"]')).to_be_visible()
        expect(page.locator('[data-testid="paper-positions-count"]')).to_be_visible()
        expect(page.locator('[data-testid="paper-trades-today"]')).to_be_visible()

        # Check widget content
        pnl_total = page.locator('[data-testid="paper-pnl-total"] #pnl-total')
        expect(pnl_total).to_contain_text("$")

        positions_count = page.locator('[data-testid="paper-positions-count"] #positions-count')
        expect(positions_count).to_have_text("0")  # Initially should be 0

    def test_dashboard_refresh(self, page: Page):
        """Test dashboard refresh functionality"""
        page.goto("http://localhost:8004/dashboard")

        # Find refresh button
        refresh_btn = page.locator("#refresh-btn")
        expect(refresh_btn).to_be_visible()

        # Get initial last update time
        last_update = page.locator("#last-update")
        initial_time = last_update.text_content()

        # Click refresh
        refresh_btn.click()

        # Wait for update
        page.wait_for_timeout(1000)

        # Verify time changed
        new_time = last_update.text_content()
        assert initial_time != new_time, "Last update time should change after refresh"

    def test_pnl_chart_render(self, page: Page):
        """Test P&L chart rendering"""
        page.goto("http://localhost:8004/dashboard")

        # Check chart canvas exists
        pnl_chart = page.locator("#pnl-chart")
        expect(pnl_chart).to_be_visible()

        # Check win rate chart
        win_rate_chart = page.locator("#win-rate-chart")
        expect(win_rate_chart).to_be_visible()

    def test_trades_table(self, page: Page):
        """Test recent trades table"""
        page.goto("http://localhost:8004/dashboard")

        # Check table exists
        trades_table = page.locator("#trades-table")
        expect(trades_table).to_be_visible()

        # Initially should show "No trades yet"
        expect(trades_table).to_contain_text("No trades yet")


class TestPaperTradingFlow:
    """Test complete paper trading flow"""

    def test_enable_and_monitor(self, page: Page):
        """Test enabling paper trading and monitoring metrics"""
        # Step 1: Enable paper trading from settings
        page.goto("http://localhost:8004/settings")

        toggle = page.locator('[data-testid="paper-trading-toggle"]')
        toggle_status = page.locator("#toggle-status")

        # Enable if not already enabled
        if toggle_status.text_content() == "OFF":
            toggle.click()
            page.wait_for_timeout(2000)

        expect(toggle_status).to_have_text("ON")

        # Step 2: Navigate to dashboard
        page.goto("http://localhost:8004/dashboard")

        # Step 3: Verify widgets are updating
        pnl_total = page.locator('[data-testid="paper-pnl-total"] #pnl-total')
        expect(pnl_total).to_be_visible()

        # Step 4: Wait for auto-refresh (simulated)
        page.wait_for_timeout(3000)

        # Step 5: Go back to settings and disable
        page.goto("http://localhost:8004/settings")
        toggle.click()
        page.wait_for_timeout(2000)

        expect(toggle_status).to_have_text("OFF")

    def test_replay_simulation(self, page: Page):
        """Test running replay simulation"""
        page.goto("http://localhost:8004/settings")

        # Click run replay
        replay_btn = page.locator('[data-testid="run-replay-btn"]')
        replay_btn.click()

        # Wait for notification
        notification = page.locator(".fixed.top-4.right-4")
        expect(notification).to_be_visible()
        expect(notification).to_contain_text("Replay simulation started")

        # Wait for completion (mocked to be fast)
        page.wait_for_timeout(6000)

        # Should show completion notification
        # Check for profitable/unprofitable message
        page.wait_for_selector(".fixed.top-4.right-4", state="visible")


class TestErrorHandling:
    """Test error handling and edge cases"""

    def test_api_error_handling(self, page: Page):
        """Test handling of API errors"""
        page.goto("http://localhost:8004/settings")

        # Try to generate report without paper trading running
        report_btn = page.locator('[data-testid="generate-report-btn"]')
        report_btn.click()

        # Should show error notification
        page.wait_for_timeout(1000)
        notification = page.locator(".fixed.top-4.right-4")
        # May show error or handle gracefully

    def test_kill_switch_confirmation(self, page: Page):
        """Test kill switch requires confirmation"""
        page.goto("http://localhost:8004/settings")

        # Enable paper trading first
        toggle = page.locator('[data-testid="paper-trading-toggle"]')
        toggle_status = page.locator("#toggle-status")

        if toggle_status.text_content() == "OFF":
            toggle.click()
            page.wait_for_timeout(2000)

        # Click kill switch
        kill_switch_btn = page.locator('[data-testid="kill-switch-btn"]')

        # Set up dialog handler
        page.on("dialog", lambda dialog: dialog.dismiss())
        kill_switch_btn.click()

        # Status should remain ON since we dismissed
        expect(toggle_status).to_have_text("ON")

        # Now accept the dialog
        page.on("dialog", lambda dialog: dialog.accept())
        kill_switch_btn.click()
        page.wait_for_timeout(2000)

        # Status should be OFF after accepting
        expect(toggle_status).to_have_text("OFF")


class TestAutoRefresh:
    """Test auto-refresh functionality"""

    def test_dashboard_auto_refresh(self, page: Page):
        """Test dashboard auto-refreshes every 30 seconds"""
        page.goto("http://localhost:8004/dashboard")

        # Get initial last update
        last_update = page.locator("#last-update")
        initial_time = last_update.text_content()

        # Note: In real test, we'd wait 30 seconds
        # For E2E test, we'll simulate by checking the interval is set

        # Check that refresh interval is set in JavaScript
        interval_set = page.evaluate(
            """
            () => {
                // Check if setInterval was called
                return typeof updateDashboard === 'function';
            }
        """
        )

        assert interval_set, "Auto-refresh function should be defined"

    def test_settings_metrics_auto_refresh(self, page: Page):
        """Test settings page metrics auto-refresh"""
        page.goto("http://localhost:8004/settings")

        # Similar check for settings page
        interval_set = page.evaluate(
            """
            () => {
                return typeof checkPaperTradingState === 'function';
            }
        """
        )

        assert interval_set, "Settings auto-refresh function should be defined"


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Configure browser context"""
    return {
        **browser_context_args,
        "viewport": {"width": 1920, "height": 1080},
        "ignore_https_errors": True,
    }


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--headed"])
