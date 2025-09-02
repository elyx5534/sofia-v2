"""
Test Fault Injector
Verify kill-switch scenarios work correctly
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tools.fault_injector import FaultInjector


class TestFaultInjector:
    @pytest.fixture
    def injector(self):
        """Create fault injector instance"""
        return FaultInjector()

    def test_clock_skew_scenario(self, injector):
        """Test clock skew detection"""
        result = injector.inject_clock_skew()

        assert "scenario" in result
        assert result["scenario"] == "CLOCK_SKEW"
        assert "triggered_pause" in result
        assert "injected_skew_seconds" in result

        # Should trigger pause for 5s skew (> 4s threshold)
        assert result["injected_skew_seconds"] == 5
        assert result["triggered_pause"] == True

    def test_error_burst_scenario(self, injector):
        """Test error burst detection"""
        result = injector.inject_error_burst()

        assert result["scenario"] == "ERROR_BURST"
        assert "errors_injected" in result
        assert "triggered_pause" in result

        # Should trigger pause for 12 errors (> 10 threshold)
        assert result["errors_injected"] == 12
        assert result["triggered_pause"] == True

    def test_rate_limit_scenario(self, injector):
        """Test rate limit detection"""
        result = injector.inject_rate_limit()

        assert result["scenario"] == "RATE_LIMIT"
        assert "triggered_pause" in result
        assert "api_calls_before_limit" in result

        # Should handle rate limit exception
        assert result["api_calls_before_limit"] == 3

    def test_daily_drawdown_scenario(self, injector):
        """Test daily drawdown detection"""
        result = injector.inject_daily_drawdown()

        assert result["scenario"] == "DAILY_DD"
        assert "drawdown_pct" in result
        assert "limit_pct" in result
        assert "triggered_pause" in result

        # Should trigger pause for -1.2% drawdown (> -1% limit)
        assert result["drawdown_pct"] == -1.2
        assert result["limit_pct"] == -1.0
        assert result["triggered_pause"] == True

    def test_run_all_scenarios(self, injector):
        """Test running all scenarios"""
        results = injector.run_all_scenarios()

        assert len(results) == 4  # Should have 4 scenarios

        for result in results:
            assert "scenario" in result
            assert "triggered_pause" in result
            assert "timestamp" in result

    def test_generate_report(self, injector):
        """Test report generation"""
        # Run scenarios first
        injector.run_all_scenarios()

        # Generate report
        report = injector.generate_report()

        assert "test_id" in report
        assert "timestamp" in report
        assert "scenarios_tested" in report
        assert "scenarios_passed" in report
        assert "results" in report
        assert "summary" in report

        # Check summary
        summary = report["summary"]
        assert "total_scenarios" in summary
        assert "passed" in summary
        assert "failed" in summary
        assert "success_rate" in summary
        assert "all_passed" in summary

    def test_watchdog_reset_between_scenarios(self, injector):
        """Test that watchdog state is reset between scenarios"""
        # Run first scenario
        injector.inject_error_burst()

        # Check that error counts were added
        assert len(injector.watchdog.error_counts) > 0

        # Reset should clear state
        injector.watchdog.reset_state()
        assert len(injector.watchdog.error_counts) == 0
        assert injector.watchdog.consecutive_api_errors == 0

    @patch("tools.fault_injector.Path")
    def test_save_report(self, mock_path, injector):
        """Test saving report to file"""
        # Mock file operations
        mock_file = Mock()
        mock_path.return_value.parent.mkdir = Mock()
        mock_path.return_value.open = Mock(return_value=mock_file)
        mock_file.__enter__ = Mock(return_value=mock_file)
        mock_file.__exit__ = Mock(return_value=None)

        # Run scenarios and generate report
        injector.run_all_scenarios()
        report = injector.generate_report()

        # Save report
        injector.save_report(report)

        # Verify file operations were called
        mock_path.return_value.parent.mkdir.assert_called()

    def test_scenario_independence(self, injector):
        """Test that scenarios don't affect each other"""
        # Run all scenarios
        results = injector.run_all_scenarios()

        # Each scenario should have its own result
        scenario_names = [r["scenario"] for r in results]
        assert len(scenario_names) == len(set(scenario_names))  # All unique

        # Check expected scenarios
        expected = ["CLOCK_SKEW", "ERROR_BURST", "RATE_LIMIT", "DAILY_DD"]
        for expected_scenario in expected:
            assert expected_scenario in scenario_names
