"""
Comprehensive tests for Scheduler modules
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Mock the imports to avoid import errors
try:
    from src.scheduler.jobs import ScheduledJobs
except ImportError:
    ScheduledJobs = type("ScheduledJobs", (), {})

try:
    from src.scheduler.run import CryptoScheduler
except ImportError:
    CryptoScheduler = type("CryptoScheduler", (), {})


class TestScheduledJobs:
    """Test ScheduledJobs functionality"""

    def test_job_fetch_data_success(self):
        """Test successful data fetch job"""
        with patch("src.scheduler.jobs.data_pipeline") as mock_pipeline:
            mock_pipeline.update_recent_data.return_value = {
                "symbols_updated": 10,
                "records_added": 500,
            }

            result = ScheduledJobs.job_fetch_data()

            assert result["status"] == "success"
            assert result["job"] == "fetch_data"
            assert "timestamp" in result
            assert result["results"]["symbols_updated"] == 10
            mock_pipeline.update_recent_data.assert_called_once_with(hours_back=24)

    def test_job_fetch_data_error(self):
        """Test data fetch job error handling"""
        with patch("src.scheduler.jobs.data_pipeline") as mock_pipeline:
            mock_pipeline.update_recent_data.side_effect = Exception("Connection error")

            result = ScheduledJobs.job_fetch_data()

            assert result["status"] == "error"
            assert result["job"] == "fetch_data"
            assert "Connection error" in result["error"]

    def test_job_scan_signals_success(self):
        """Test successful signal scan job"""
        with patch("src.scheduler.jobs.scanner") as mock_scanner:
            mock_scanner.run_scan.return_value = {
                "signals": [
                    {"symbol": "BTC/USDT", "signal": "buy"},
                    {"symbol": "ETH/USDT", "signal": "sell"},
                ]
            }

            result = ScheduledJobs.job_scan_signals()

            assert result["job"] == "scan_signals"
            assert "timestamp" in result
            mock_scanner.run_scan.assert_called_once_with(timeframe="1h", save_results=True)

    def test_job_update_news_success(self):
        """Test successful news update job"""
        with patch("src.scheduler.jobs.news_aggregator") as mock_news:
            mock_news.fetch_all_news.return_value = {"articles": 25, "sources": 5}

            result = ScheduledJobs.job_update_news()

            assert result["job"] == "update_news"
            assert "timestamp" in result
            mock_news.fetch_all_news.assert_called_once()

    def test_job_calculate_metrics(self):
        """Test metrics calculation job"""
        with patch("src.scheduler.jobs.data_pipeline") as mock_pipeline:
            mock_pipeline.calculate_technical_indicators.return_value = {
                "indicators_calculated": 15
            }

            result = ScheduledJobs.job_calculate_metrics()

            assert result["job"] == "calculate_metrics"
            assert "timestamp" in result

    def test_job_cleanup_old_data(self):
        """Test cleanup old data job"""
        with patch("src.scheduler.jobs.data_pipeline") as mock_pipeline:
            mock_pipeline.cleanup_old_data.return_value = {"records_deleted": 1000}

            result = ScheduledJobs.job_cleanup_old_data()

            assert result["job"] == "cleanup_old_data"
            assert "timestamp" in result

    def test_job_generate_reports(self):
        """Test report generation job"""
        with patch("src.scheduler.jobs.report_generator") as mock_reporter:
            mock_reporter.generate_daily_report.return_value = {
                "report_path": "/reports/daily_2024_01_25.pdf"
            }

            result = ScheduledJobs.job_generate_reports()

            assert result["job"] == "generate_reports"
            assert "timestamp" in result


class TestCryptoScheduler:
    """Test CryptoScheduler functionality"""

    @pytest.fixture
    def scheduler(self):
        """Create scheduler instance"""
        return CryptoScheduler()

    def test_init(self, scheduler):
        """Test scheduler initialization"""
        assert scheduler.scheduler is not None
        assert scheduler.is_running is False
        assert scheduler.jobs == []

    def test_schedule_jobs(self, scheduler):
        """Test job scheduling"""
        with patch("schedule.every") as mock_schedule:
            mock_chain = Mock()
            mock_chain.minutes.do = Mock(return_value=None)
            mock_chain.hours.do = Mock(return_value=None)
            mock_chain.day.at.return_value.do = Mock(return_value=None)
            mock_schedule.return_value = mock_chain

            scheduler.schedule_jobs()

            # Verify jobs were scheduled
            assert mock_schedule.called
            assert len(scheduler.jobs) > 0

    @pytest.mark.asyncio
    async def test_run_async(self, scheduler):
        """Test async run method"""
        scheduler.is_running = True

        with patch("schedule.run_pending") as mock_run:
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                # Run for one iteration then stop
                mock_sleep.side_effect = [None, scheduler.stop()]

                await scheduler.run()

                mock_run.assert_called()
                mock_sleep.assert_called()

    def test_start(self, scheduler):
        """Test starting scheduler"""
        with patch.object(scheduler, "run", new_callable=AsyncMock):
            with patch("asyncio.create_task") as mock_create_task:
                scheduler.start()

                assert scheduler.is_running is True
                mock_create_task.assert_called_once()

    def test_stop(self, scheduler):
        """Test stopping scheduler"""
        scheduler.is_running = True
        scheduler.stop()

        assert scheduler.is_running is False

    def test_add_custom_job(self, scheduler):
        """Test adding custom job"""

        def custom_job():
            return "custom_result"

        scheduler.add_job(custom_job, interval_minutes=30, name="custom_job")

        assert "custom_job" in [job["name"] for job in scheduler.jobs]

    def test_remove_job(self, scheduler):
        """Test removing a job"""
        scheduler.jobs = [
            {"name": "job1", "schedule": Mock()},
            {"name": "job2", "schedule": Mock()},
        ]

        scheduler.remove_job("job1")

        assert len(scheduler.jobs) == 1
        assert scheduler.jobs[0]["name"] == "job2"

    def test_get_job_status(self, scheduler):
        """Test getting job status"""
        scheduler.jobs = [
            {
                "name": "test_job",
                "last_run": datetime.now(),
                "last_result": {"status": "success"},
                "next_run": datetime.now() + timedelta(minutes=15),
            }
        ]

        status = scheduler.get_job_status("test_job")

        assert status is not None
        assert status["name"] == "test_job"
        assert "last_run" in status
        assert "next_run" in status

    def test_list_jobs(self, scheduler):
        """Test listing all jobs"""
        scheduler.jobs = [{"name": "job1", "interval": 15}, {"name": "job2", "interval": 60}]

        jobs = scheduler.list_jobs()

        assert len(jobs) == 2
        assert jobs[0]["name"] == "job1"
        assert jobs[1]["name"] == "job2"

    def test_execute_job_now(self, scheduler):
        """Test immediate job execution"""
        mock_job = Mock(return_value={"result": "success"})
        scheduler.jobs = [{"name": "test_job", "function": mock_job}]

        result = scheduler.execute_job_now("test_job")

        assert result["result"] == "success"
        mock_job.assert_called_once()

    def test_update_job_interval(self, scheduler):
        """Test updating job interval"""
        scheduler.jobs = [{"name": "test_job", "interval": 15}]

        scheduler.update_job_interval("test_job", 30)

        assert scheduler.jobs[0]["interval"] == 30

    def test_pause_resume_job(self, scheduler):
        """Test pausing and resuming jobs"""
        scheduler.jobs = [{"name": "test_job", "enabled": True}]

        scheduler.pause_job("test_job")
        assert scheduler.jobs[0]["enabled"] is False

        scheduler.resume_job("test_job")
        assert scheduler.jobs[0]["enabled"] is True

    def test_error_handling_in_job(self, scheduler):
        """Test error handling in job execution"""

        def failing_job():
            raise Exception("Job failed")

        scheduler.jobs = [{"name": "failing_job", "function": failing_job}]

        with patch("src.scheduler.run.logger") as mock_logger:
            result = scheduler.execute_job_now("failing_job")

            assert result["status"] == "error"
            assert "Job failed" in result["error"]
            mock_logger.error.assert_called()

    def test_job_retry_logic(self, scheduler):
        """Test job retry on failure"""
        mock_job = Mock(side_effect=[Exception("Fail"), {"status": "success"}])

        scheduler.jobs = [
            {"name": "retry_job", "function": mock_job, "max_retries": 3, "retry_count": 0}
        ]

        # First execution fails
        result1 = scheduler.execute_job_with_retry("retry_job")
        assert scheduler.jobs[0]["retry_count"] == 1

        # Second execution succeeds
        result2 = scheduler.execute_job_with_retry("retry_job")
        assert result2["status"] == "success"
        assert scheduler.jobs[0]["retry_count"] == 0

    def test_concurrent_job_execution(self, scheduler):
        """Test concurrent job execution"""

        async def async_job():
            await asyncio.sleep(0.1)
            return {"status": "completed"}

        scheduler.jobs = [
            {"name": "async_job1", "function": async_job},
            {"name": "async_job2", "function": async_job},
        ]

        with patch("asyncio.gather", new_callable=AsyncMock) as mock_gather:
            mock_gather.return_value = [{"status": "completed"}, {"status": "completed"}]

            asyncio.run(scheduler.execute_concurrent_jobs())
            mock_gather.assert_called_once()

    def test_job_dependencies(self, scheduler):
        """Test job dependency management"""
        scheduler.jobs = [
            {"name": "parent_job", "dependencies": []},
            {"name": "child_job", "dependencies": ["parent_job"]},
        ]

        execution_order = scheduler.get_execution_order()

        assert execution_order[0] == "parent_job"
        assert execution_order[1] == "child_job"

    def test_job_metrics_tracking(self, scheduler):
        """Test job metrics tracking"""
        scheduler.job_metrics = {
            "test_job": {"executions": 10, "successes": 8, "failures": 2, "avg_duration": 1.5}
        }

        metrics = scheduler.get_job_metrics("test_job")

        assert metrics["executions"] == 10
        assert metrics["success_rate"] == 0.8
        assert metrics["avg_duration"] == 1.5
