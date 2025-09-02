"""
Tests for Scheduler module
Testing scheduled jobs and job runner
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Import scheduler modules
from src.scheduler.jobs import ScheduledJobs
from src.scheduler.run import CryptoScheduler


class TestScheduledJobs:
    """Test ScheduledJobs class"""

    def test_job_fetch_data(self):
        """Test data fetch job"""
        with patch("src.scheduler.jobs.data_pipeline") as mock_pipeline:
            mock_pipeline.update_recent_data.return_value = {"success": True}

            result = ScheduledJobs.job_fetch_data()

            assert result["job"] == "fetch_data"
            assert result["status"] == "success"
            assert "timestamp" in result

    def test_job_scan_signals(self):
        """Test signal scan job"""
        with patch("src.scheduler.jobs.scanner") as mock_scanner:
            mock_scanner.run_scan.return_value = {"signals": []}

            result = ScheduledJobs.job_scan_signals()

            assert result["job"] == "scan_signals"
            assert "timestamp" in result

    def test_job_error_handling(self):
        """Test job error handling"""
        with patch("src.scheduler.jobs.data_pipeline") as mock_pipeline:
            mock_pipeline.update_recent_data.side_effect = Exception("Test error")

            result = ScheduledJobs.job_fetch_data()

            assert result["status"] == "error"
            assert "Test error" in result["error"]


class TestCryptoScheduler:
    """Test CryptoScheduler functionality"""

    @pytest.fixture
    def crypto_scheduler(self):
        """Create scheduler instance"""
        return CryptoScheduler()

    def test_scheduler_initialization(self, crypto_scheduler):
        """Test scheduler initialization"""
        assert crypto_scheduler is not None
        assert hasattr(crypto_scheduler, "scheduler")
        assert crypto_scheduler.is_running is False

    @patch("src.scheduler.run.schedule")
    def test_schedule_jobs(self, mock_schedule, crypto_scheduler):
        """Test scheduling jobs"""
        crypto_scheduler.schedule_jobs()

        # Verify jobs were scheduled
        assert mock_schedule.every.called

    @patch("src.scheduler.run.schedule")
    async def test_start_scheduler(self, mock_schedule, crypto_scheduler):
        """Test starting scheduler"""
        with patch.object(crypto_scheduler, "run", new_callable=AsyncMock) as mock_run:
            await crypto_scheduler.start()
            mock_run.assert_called_once()

    def test_stop_scheduler(self, crypto_scheduler):
        """Test stopping scheduler"""
        crypto_scheduler.is_running = True
        crypto_scheduler.stop()

        assert crypto_scheduler.is_running is False
        assert retrieved_job.name == "test_job"

    @pytest.mark.asyncio
    async def test_run_job(self, scheduler):
        """Test running a job"""
        mock_func = AsyncMock(return_value="result")
        job = ScheduledJob(name="async_job", func=mock_func, interval_seconds=60)

        scheduler.add_job(job)
        await scheduler.run_job("async_job")

        mock_func.assert_called_once()
        assert job.status == JobStatus.COMPLETED

    def test_list_jobs(self, scheduler):
        """Test listing all jobs"""
        jobs = [
            ScheduledJob("job1", lambda: None, 60),
            ScheduledJob("job2", lambda: None, 120),
            ScheduledJob("job3", lambda: None, 180),
        ]

        for job in jobs:
            scheduler.add_job(job)

        job_list = scheduler.list_jobs()
        assert len(job_list) == 3
        assert all(job["name"] in ["job1", "job2", "job3"] for job in job_list)


class TestScheduledJobs:
    """Test individual scheduled job functions"""

    @pytest.mark.asyncio
    @patch("src.scheduler.jobs.database")
    async def test_cleanup_old_data(self, mock_db):
        """Test cleanup old data job"""
        mock_db.execute.return_value = Mock(rows_affected=10)

        result = await cleanup_old_data()

        assert result is not None
        mock_db.execute.assert_called()

    @pytest.mark.asyncio
    @patch("src.scheduler.jobs.market_service")
    async def test_update_market_indicators(self, mock_service):
        """Test update market indicators job"""
        mock_service.update_indicators.return_value = {"BTC/USDT": {"rsi": 65, "macd": "bullish"}}

        result = await update_market_indicators()

        assert result is not None
        mock_service.update_indicators.assert_called()

    @pytest.mark.asyncio
    @patch("src.scheduler.jobs.report_service")
    async def test_generate_daily_report(self, mock_service):
        """Test generate daily report job"""
        mock_service.generate_report.return_value = {
            "date": datetime.now().date(),
            "total_trades": 10,
            "profit": 100.50,
        }

        result = await generate_daily_report()

        assert result is not None
        mock_service.generate_report.assert_called()

    @pytest.mark.asyncio
    @patch("src.scheduler.jobs.exchange_service")
    async def test_sync_exchange_data(self, mock_service):
        """Test sync exchange data job"""
        mock_service.sync_data.return_value = {"synced_symbols": 50, "errors": 0}

        result = await sync_exchange_data()

        assert result is not None
        mock_service.sync_data.assert_called()

    @pytest.mark.asyncio
    @patch("src.scheduler.jobs.portfolio_service")
    async def test_calculate_portfolio_metrics(self, mock_service):
        """Test calculate portfolio metrics job"""
        mock_service.calculate_metrics.return_value = {
            "total_value": 10000,
            "daily_return": 0.02,
            "sharpe_ratio": 1.5,
        }

        result = await calculate_portfolio_metrics()

        assert result is not None
        mock_service.calculate_metrics.assert_called()


class TestSchedulerRunner:
    """Test SchedulerRunner functionality"""

    @pytest.fixture
    def runner(self):
        """Create runner instance"""
        return SchedulerRunner()

    def test_runner_initialization(self, runner):
        """Test runner initialization"""
        assert runner is not None
        assert hasattr(runner, "scheduler")
        assert hasattr(runner, "running")
        assert runner.running is False

    @pytest.mark.asyncio
    async def test_start_runner(self, runner):
        """Test starting the runner"""
        runner.scheduler = Mock()
        runner.scheduler.jobs = []

        # Start and immediately stop
        task = asyncio.create_task(runner.start())
        await asyncio.sleep(0.1)
        runner.stop()

        try:
            await asyncio.wait_for(task, timeout=1)
        except asyncio.TimeoutError:
            pass

        assert runner.running is False

    def test_stop_runner(self, runner):
        """Test stopping the runner"""
        runner.running = True
        runner.stop()

        assert runner.running is False

    def test_add_default_jobs(self, runner):
        """Test adding default jobs"""
        runner.add_default_jobs()

        job_names = [job.name for job in runner.scheduler.jobs]
        assert "cleanup_old_data" in job_names
        assert "update_market_indicators" in job_names
        assert "generate_daily_report" in job_names

    @pytest.mark.asyncio
    async def test_run_single_job(self, runner):
        """Test running a single job"""
        mock_job = Mock()
        mock_job.name = "test_job"
        mock_job.func = AsyncMock(return_value="result")
        mock_job.enabled = True
        mock_job.interval_seconds = 60
        mock_job.last_run = None

        runner.scheduler.jobs = [mock_job]
        await runner._run_job(mock_job)

        mock_job.func.assert_called_once()

    def test_should_run_job(self, runner):
        """Test job run condition checking"""
        job = ScheduledJob(name="test_job", func=lambda: None, interval_seconds=60)

        # Job never run
        assert runner._should_run_job(job) is True

        # Job recently run
        job.last_run = datetime.now()
        assert runner._should_run_job(job) is False

        # Job run long ago
        job.last_run = datetime.now() - timedelta(seconds=120)
        assert runner._should_run_job(job) is True

        # Job disabled
        job.enabled = False
        assert runner._should_run_job(job) is False


class TestSchedulerIntegration:
    """Integration tests for scheduler"""

    @pytest.mark.asyncio
    async def test_full_scheduler_cycle(self):
        """Test full scheduler cycle"""
        runner = SchedulerRunner()

        # Add a test job
        test_results = []

        async def test_job():
            test_results.append(datetime.now())
            return "completed"

        job = ScheduledJob(
            name="fast_job",
            func=test_job,
            interval_seconds=0.1,  # Very fast for testing
        )

        runner.scheduler.add_job(job)

        # Run for a short time
        task = asyncio.create_task(runner.start())
        await asyncio.sleep(0.5)
        runner.stop()

        try:
            await asyncio.wait_for(task, timeout=1)
        except asyncio.TimeoutError:
            pass

        # Check that job ran multiple times
        assert len(test_results) >= 2

    @patch("src.scheduler.run.JobScheduler")
    def test_start_scheduler_function(self, mock_scheduler_class):
        """Test start_scheduler function"""
        mock_scheduler = Mock()
        mock_scheduler_class.return_value = mock_scheduler

        with patch("src.scheduler.run.asyncio.run"):
            start_scheduler()
            mock_scheduler_class.assert_called_once()
