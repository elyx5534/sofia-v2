"""
APScheduler-based job scheduler for automated tasks
"""

import json
from datetime import datetime
from pathlib import Path

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from .jobs import SCHEDULED_JOBS


class CryptoScheduler:
    """Scheduler for cryptocurrency scanning jobs"""

    def __init__(self, outputs_dir: str = "./outputs"):
        self.outputs_dir = Path(outputs_dir)
        self.outputs_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir = self.outputs_dir / "scheduler_logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        executors = {"default": ThreadPoolExecutor(max_workers=3)}
        self.scheduler = BackgroundScheduler(executors=executors, timezone="UTC")
        self.is_running = False

    def add_jobs(self):
        """Add all scheduled jobs with their cron triggers"""
        self.scheduler.add_job(
            func=self._run_job_with_logging,
            args=["fetch_data"],
            trigger=CronTrigger(minute="*/15"),
            id="fetch_data",
            name="Fetch OHLCV Data",
            replace_existing=True,
            max_instances=1,
        )
        self.scheduler.add_job(
            func=self._run_job_with_logging,
            args=["scan_signals"],
            trigger=CronTrigger(minute="*/5"),
            id="scan_signals",
            name="Scan Trading Signals",
            replace_existing=True,
            max_instances=1,
        )
        self.scheduler.add_job(
            func=self._run_job_with_logging,
            args=["update_news"],
            trigger=CronTrigger(minute="*/15"),
            id="update_news",
            name="Update News",
            replace_existing=True,
            max_instances=1,
        )
        self.scheduler.add_job(
            func=self._run_job_with_logging,
            args=["health_check"],
            trigger=CronTrigger(minute="*/10"),
            id="health_check",
            name="System Health Check",
            replace_existing=True,
            max_instances=1,
        )
        self.scheduler.add_job(
            func=self._run_job_with_logging,
            args=["full_data_sync"],
            trigger=CronTrigger(hour=2, minute=0),
            id="full_data_sync",
            name="Full Data Sync",
            replace_existing=True,
            max_instances=1,
        )
        self.scheduler.add_job(
            func=self._run_job_with_logging,
            args=["cleanup_old_data"],
            trigger=CronTrigger(day_of_week="sun", hour=3, minute=0),
            id="cleanup_old_data",
            name="Cleanup Old Data",
            replace_existing=True,
            max_instances=1,
        )
        logger.info(f"Added {len(self.scheduler.get_jobs())} scheduled jobs")

    def _run_job_with_logging(self, job_name: str):
        """Run a job with comprehensive logging"""
        start_time = datetime.now()
        try:
            logger.info(f"Starting job: {job_name}")
            job_func = SCHEDULED_JOBS.get(job_name)
            if not job_func:
                raise ValueError(f"Unknown job: {job_name}")
            result = job_func()
            execution_time = (datetime.now() - start_time).total_seconds()
            result["execution_time_seconds"] = execution_time
            self._save_job_log(job_name, result)
            if result.get("status") == "success":
                logger.info(f"Job {job_name} completed successfully in {execution_time:.1f}s")
            else:
                logger.error(f"Job {job_name} failed: {result.get('error', 'Unknown error')}")
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            error_result = {
                "job": job_name,
                "status": "error",
                "timestamp": datetime.now().isoformat(),
                "execution_time_seconds": execution_time,
                "error": str(e),
            }
            self._save_job_log(job_name, error_result)
            logger.error(f"Job {job_name} crashed after {execution_time:.1f}s: {e}")

    def _save_job_log(self, job_name: str, result: dict):
        """Save job execution log"""
        try:
            log_file = self.logs_dir / f"{job_name}.json"
            logs = []
            if log_file.exists():
                try:
                    with open(log_file) as f:
                        logs = json.load(f)
                except:
                    logs = []
            logs.append(result)
            logs = logs[-100:]
            with open(log_file, "w") as f:
                json.dump(logs, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save job log for {job_name}: {e}")

    def start(self):
        """Start the scheduler"""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return
        try:
            self.add_jobs()
            self.scheduler.start()
            self.is_running = True
            logger.info("Crypto scheduler started successfully")
            self.print_schedule()
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
            raise

    def stop(self):
        """Stop the scheduler"""
        if not self.is_running:
            return
        try:
            self.scheduler.shutdown(wait=True)
            self.is_running = False
            logger.info("Crypto scheduler stopped")
        except Exception as e:
            logger.error(f"Failed to stop scheduler: {e}")

    def print_schedule(self):
        """Print current job schedule"""
        jobs = self.scheduler.get_jobs()
        logger.info("Scheduled Jobs:")
        for job in jobs:
            logger.info(f"  {job.name} ({job.id}): {job.trigger}")

    def get_job_logs(self, job_name: str, limit: int = 10) -> list:
        """Get recent logs for a specific job"""
        log_file = self.logs_dir / f"{job_name}.json"
        if not log_file.exists():
            return []
        try:
            with open(log_file) as f:
                logs = json.load(f)
            return logs[-limit:] if limit else logs
        except Exception as e:
            logger.error(f"Failed to load logs for {job_name}: {e}")
            return []

    def get_job_status(self) -> dict:
        """Get status of all jobs"""
        status = {
            "scheduler_running": self.is_running,
            "total_jobs": len(self.scheduler.get_jobs()) if self.is_running else 0,
            "jobs": {},
        }
        for job_name in SCHEDULED_JOBS.keys():
            recent_logs = self.get_job_logs(job_name, limit=1)
            if recent_logs:
                last_run = recent_logs[0]
                status["jobs"][job_name] = {
                    "last_run": last_run.get("timestamp"),
                    "last_status": last_run.get("status"),
                    "last_execution_time": last_run.get("execution_time_seconds"),
                }
            else:
                status["jobs"][job_name] = {
                    "last_run": None,
                    "last_status": "never_run",
                    "last_execution_time": None,
                }
        return status

    def run_job_now(self, job_name: str) -> dict:
        """Manually run a specific job"""
        if job_name not in SCHEDULED_JOBS:
            return {"error": f"Unknown job: {job_name}"}
        logger.info(f"Manually running job: {job_name}")
        self._run_job_with_logging(job_name)
        logs = self.get_job_logs(job_name, limit=1)
        return logs[0] if logs else {"error": "Job executed but no log found"}


crypto_scheduler = CryptoScheduler()
