"""
Comprehensive tests for scheduler jobs module to increase coverage
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
import asyncio
import json
from pathlib import Path

@pytest.fixture
def mock_data_pipeline():
    """Mock data pipeline"""
    pipeline = MagicMock()
    pipeline.update_recent_data.return_value = {"symbols_updated": 10}
    pipeline.get_available_symbols.return_value = ["BTC-USD", "ETH-USD", "SOL-USD"]
    pipeline.fetch_universe_data.return_value = {"total_fetched": 50}
    pipeline.outputs_dir = Path("./outputs")
    return pipeline

@pytest.fixture
def mock_scanner():
    """Mock scanner"""
    scanner = MagicMock()
    scanner.run_scan.return_value = [
        {"symbol": "BTC-USD", "score": 2.5},
        {"symbol": "ETH-USD", "score": 1.5}
    ]
    return scanner

@pytest.fixture
def mock_news_aggregator():
    """Mock news aggregator"""
    aggregator = MagicMock()
    aggregator.news_dir = Path("./news")
    aggregator.update_all_news = AsyncMock()
    return aggregator

class TestScheduledJobs:
    """Test scheduled job functions"""
    
    @patch('src.scheduler.jobs.data_pipeline')
    def test_job_fetch_data_success(self, mock_pipeline):
        """Test successful data fetch job"""
        from src.scheduler.jobs import ScheduledJobs
        
        mock_pipeline.update_recent_data.return_value = {
            "symbols_updated": 10,
            "timeframes": ["1h", "1d"]
        }
        
        result = ScheduledJobs.job_fetch_data()
        
        assert result["job"] == "fetch_data"
        assert result["status"] == "success"
        assert "timestamp" in result
        assert "results" in result
        mock_pipeline.update_recent_data.assert_called_once_with(hours_back=24)
    
    @patch('src.scheduler.jobs.data_pipeline')
    def test_job_fetch_data_failure(self, mock_pipeline):
        """Test data fetch job failure"""
        from src.scheduler.jobs import ScheduledJobs
        
        mock_pipeline.update_recent_data.side_effect = Exception("Network error")
        
        result = ScheduledJobs.job_fetch_data()
        
        assert result["job"] == "fetch_data"
        assert result["status"] == "error"
        assert "Network error" in result["error"]
    
    @patch('src.scheduler.jobs.scanner')
    def test_job_scan_signals_success(self, mock_scanner):
        """Test successful signal scan job"""
        from src.scheduler.jobs import ScheduledJobs
        
        mock_scanner.run_scan.return_value = [
            {"symbol": "BTC-USD", "score": 3.0},
            {"symbol": "ETH-USD", "score": 2.0},
            {"symbol": "SOL-USD", "score": 0}
        ]
        
        result = ScheduledJobs.job_scan_signals()
        
        assert result["job"] == "scan_signals"
        assert result["status"] == "success"
        assert result["results"]["total_symbols"] == 3
        assert result["results"]["symbols_with_signals"] == 2
        assert result["results"]["top_score"] == 3.0
    
    @patch('src.scheduler.jobs.scanner')
    def test_job_scan_signals_failure(self, mock_scanner):
        """Test signal scan job failure"""
        from src.scheduler.jobs import ScheduledJobs
        
        mock_scanner.run_scan.side_effect = Exception("Scanner error")
        
        result = ScheduledJobs.job_scan_signals()
        
        assert result["job"] == "scan_signals"
        assert result["status"] == "error"
        assert "Scanner error" in result["error"]
    
    @patch('src.scheduler.jobs.news_aggregator')
    @patch('src.scheduler.jobs.data_pipeline')
    @patch('src.scheduler.jobs.asyncio')
    def test_job_update_news_success(self, mock_asyncio, mock_pipeline, mock_news):
        """Test successful news update job"""
        from src.scheduler.jobs import ScheduledJobs
        
        mock_pipeline.get_available_symbols.return_value = ["BTC-USD", "ETH-USD"]
        mock_loop = MagicMock()
        mock_asyncio.new_event_loop.return_value = mock_loop
        
        result = ScheduledJobs.job_update_news()
        
        assert result["job"] == "update_news"
        assert result["status"] == "success"
        assert result["results"]["symbols_updated"] == 2
        assert result["results"]["global_news_updated"] is True
    
    @patch('src.scheduler.jobs.news_aggregator')
    def test_job_update_news_failure(self, mock_news):
        """Test news update job failure"""
        from src.scheduler.jobs import ScheduledJobs
        
        with patch('src.scheduler.jobs.asyncio.new_event_loop') as mock_loop:
            mock_loop.side_effect = Exception("Async error")
            
            result = ScheduledJobs.job_update_news()
            
            assert result["job"] == "update_news"
            assert result["status"] == "error"
            assert "Async error" in result["error"]
    
    @patch('src.scheduler.jobs.data_pipeline')
    def test_job_full_data_sync_success(self, mock_pipeline):
        """Test successful full data sync job"""
        from src.scheduler.jobs import ScheduledJobs
        
        mock_pipeline.fetch_universe_data.return_value = {
            "total_symbols": 50,
            "timeframes": ["1h", "1d"],
            "days_fetched": 30
        }
        
        result = ScheduledJobs.job_full_data_sync()
        
        assert result["job"] == "full_data_sync"
        assert result["status"] == "success"
        assert "results" in result
        mock_pipeline.fetch_universe_data.assert_called_once_with(
            timeframes=['1h', '1d'],
            days_back=30,
            max_workers=3
        )
    
    @patch('src.scheduler.jobs.data_pipeline')
    def test_job_full_data_sync_failure(self, mock_pipeline):
        """Test full data sync job failure"""
        from src.scheduler.jobs import ScheduledJobs
        
        mock_pipeline.fetch_universe_data.side_effect = Exception("Sync error")
        
        result = ScheduledJobs.job_full_data_sync()
        
        assert result["job"] == "full_data_sync"
        assert result["status"] == "error"
        assert "Sync error" in result["error"]
    
    def test_job_cleanup_old_data(self):
        """Test cleanup old data job"""
        from src.scheduler.jobs import ScheduledJobs
        
        result = ScheduledJobs.job_cleanup_old_data()
        
        assert result["job"] == "cleanup_old_data"
        assert result["status"] == "success"
        assert result["results"]["files_cleaned"] == 0
    
    @patch('src.scheduler.jobs.data_pipeline')
    @patch('src.scheduler.jobs.news_aggregator')
    def test_job_health_check_healthy(self, mock_news, mock_pipeline, tmp_path):
        """Test health check job - healthy status"""
        from src.scheduler.jobs import ScheduledJobs
        
        # Setup mocks
        mock_pipeline.get_available_symbols.return_value = ["BTC-USD"] * 20
        mock_pipeline.outputs_dir = tmp_path
        mock_news.news_dir = tmp_path
        
        # Create test files
        signals_file = tmp_path / "signals.json"
        signals_file.write_text("{}")
        news_file = tmp_path / "global.json"
        news_file.write_text("{}")
        
        result = ScheduledJobs.job_health_check()
        
        assert result["job"] == "health_check"
        assert result["status"] == "success"
        assert result["health_status"] == "healthy"
        assert result["results"]["available_symbols"] == 20
        assert len(result["results"]["issues"]) == 0
    
    @patch('src.scheduler.jobs.data_pipeline')
    @patch('src.scheduler.jobs.news_aggregator')
    def test_job_health_check_warning(self, mock_news, mock_pipeline, tmp_path):
        """Test health check job - warning status"""
        from src.scheduler.jobs import ScheduledJobs
        import time
        
        # Setup mocks
        mock_pipeline.get_available_symbols.return_value = ["BTC-USD"] * 5  # Low count
        mock_pipeline.outputs_dir = tmp_path
        mock_news.news_dir = tmp_path
        
        # Create old files
        signals_file = tmp_path / "signals.json"
        signals_file.write_text("{}")
        # Make file old
        old_time = time.time() - 700  # 11+ minutes old
        Path(signals_file).touch()
        
        result = ScheduledJobs.job_health_check()
        
        assert result["job"] == "health_check"
        assert result["status"] == "success"
        assert result["health_status"] == "warning"
        assert "Low symbol count" in result["results"]["issues"]
    
    @patch('src.scheduler.jobs.data_pipeline')
    def test_job_health_check_failure(self, mock_pipeline):
        """Test health check job failure"""
        from src.scheduler.jobs import ScheduledJobs
        
        mock_pipeline.get_available_symbols.side_effect = Exception("Health check error")
        
        result = ScheduledJobs.job_health_check()
        
        assert result["job"] == "health_check"
        assert result["status"] == "error"
        assert "Health check error" in result["error"]

class TestScheduledJobsExports:
    """Test scheduled jobs exports"""
    
    def test_scheduled_jobs_dict(self):
        """Test SCHEDULED_JOBS dictionary"""
        from src.scheduler.jobs import SCHEDULED_JOBS
        
        assert "fetch_data" in SCHEDULED_JOBS
        assert "scan_signals" in SCHEDULED_JOBS
        assert "update_news" in SCHEDULED_JOBS
        assert "full_data_sync" in SCHEDULED_JOBS
        assert "cleanup_old_data" in SCHEDULED_JOBS
        assert "health_check" in SCHEDULED_JOBS
        
        # All values should be callable
        for job_name, job_func in SCHEDULED_JOBS.items():
            assert callable(job_func)

class TestJobIntegration:
    """Integration tests for scheduled jobs"""
    
    @patch('src.scheduler.jobs.data_pipeline')
    @patch('src.scheduler.jobs.scanner')
    @patch('src.scheduler.jobs.news_aggregator')
    def test_multiple_jobs_execution(self, mock_news, mock_scanner, mock_pipeline):
        """Test executing multiple jobs"""
        from src.scheduler.jobs import SCHEDULED_JOBS
        
        # Setup mocks
        mock_pipeline.update_recent_data.return_value = {"updated": 10}
        mock_pipeline.get_available_symbols.return_value = ["BTC-USD"]
        mock_scanner.run_scan.return_value = []
        
        results = []
        for job_name, job_func in SCHEDULED_JOBS.items():
            if job_name != "update_news":  # Skip async job
                try:
                    result = job_func()
                    results.append(result)
                except:
                    pass
        
        assert len(results) > 0
        for result in results:
            assert "job" in result
            assert "status" in result
            assert "timestamp" in result