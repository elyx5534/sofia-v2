"""
Scheduled jobs for automated data fetching, scanning, and news updates
"""
import asyncio
from datetime import datetime
from typing import List, Dict, Any
from loguru import logger

from ..data.pipeline import data_pipeline
from ..scan.scanner import scanner
from ..news.aggregator import news_aggregator


class ScheduledJobs:
    """Container for all scheduled job functions"""
    
    @staticmethod
    def job_fetch_data() -> Dict[str, Any]:
        """Fetch OHLCV data from exchanges (15-minute interval)"""
        try:
            logger.info("Starting scheduled data fetch job")
            
            # Update recent data (last 24 hours)
            results = data_pipeline.update_recent_data(hours_back=24)
            
            logger.info(f"Data fetch completed: {results}")
            return {
                "job": "fetch_data",
                "status": "success", 
                "timestamp": datetime.now().isoformat(),
                "results": results
            }
            
        except Exception as e:
            logger.error(f"Data fetch job failed: {e}")
            return {
                "job": "fetch_data",
                "status": "error",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
    
    @staticmethod  
    def job_scan_signals() -> Dict[str, Any]:
        """Scan for trading signals (5-minute interval)"""
        try:
            logger.info("Starting scheduled signal scan job")
            
            # Run scan and save results
            results = scanner.run_scan(timeframe='1h', save_results=True)
            
            signal_count = len([r for r in results if r.get('score', 0) > 0])
            top_score = max([r.get('score', 0) for r in results]) if results else 0
            
            logger.info(f"Signal scan completed: {len(results)} symbols, {signal_count} with signals, top score: {top_score:.2f}")
            
            return {
                "job": "scan_signals",
                "status": "success",
                "timestamp": datetime.now().isoformat(),
                "results": {
                    "total_symbols": len(results),
                    "symbols_with_signals": signal_count,
                    "top_score": top_score
                }
            }
            
        except Exception as e:
            logger.error(f"Signal scan job failed: {e}")
            return {
                "job": "scan_signals", 
                "status": "error",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
    
    @staticmethod
    def job_update_news() -> Dict[str, Any]:
        """Update news from CryptoPanic and GDELT (15-minute interval)"""
        try:
            logger.info("Starting scheduled news update job")
            
            # Run async news update
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Get top symbols for symbol-specific news
                available_symbols = data_pipeline.get_available_symbols()
                top_symbols = available_symbols[:5]  # Limit to top 5 to avoid rate limiting
                
                loop.run_until_complete(
                    news_aggregator.update_all_news(symbols=top_symbols, hours_back=24)
                )
                
                logger.info("News update completed successfully")
                
                return {
                    "job": "update_news",
                    "status": "success", 
                    "timestamp": datetime.now().isoformat(),
                    "results": {
                        "symbols_updated": len(top_symbols),
                        "global_news_updated": True
                    }
                }
                
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"News update job failed: {e}")
            return {
                "job": "update_news",
                "status": "error",
                "timestamp": datetime.now().isoformat(), 
                "error": str(e)
            }
    
    @staticmethod
    def job_full_data_sync() -> Dict[str, Any]:
        """Full data synchronization (daily at 02:00)"""
        try:
            logger.info("Starting scheduled full data sync job")
            
            # Fetch data for all symbols for last 30 days
            results = data_pipeline.fetch_universe_data(
                timeframes=['1h', '1d'], 
                days_back=30,
                max_workers=3
            )
            
            logger.info(f"Full data sync completed: {results}")
            
            return {
                "job": "full_data_sync",
                "status": "success",
                "timestamp": datetime.now().isoformat(),
                "results": results
            }
            
        except Exception as e:
            logger.error(f"Full data sync job failed: {e}")
            return {
                "job": "full_data_sync", 
                "status": "error",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
    
    @staticmethod
    def job_cleanup_old_data() -> Dict[str, Any]:
        """Clean up old data files (weekly)"""
        try:
            logger.info("Starting scheduled cleanup job")
            
            # This is a placeholder for cleanup logic
            # Could include removing old parquet files, compacting data, etc.
            
            return {
                "job": "cleanup_old_data",
                "status": "success",
                "timestamp": datetime.now().isoformat(),
                "results": {"files_cleaned": 0}
            }
            
        except Exception as e:
            logger.error(f"Cleanup job failed: {e}")
            return {
                "job": "cleanup_old_data",
                "status": "error", 
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
    
    @staticmethod
    def job_health_check() -> Dict[str, Any]:
        """System health check (every 10 minutes)"""
        try:
            # Check available symbols
            available_symbols = data_pipeline.get_available_symbols()
            
            # Check recent signals
            signals_file = data_pipeline.outputs_dir / "signals.json"
            signals_age = None
            
            if signals_file.exists():
                signals_age = (datetime.now() - 
                             datetime.fromtimestamp(signals_file.stat().st_mtime)).total_seconds()
            
            # Check news
            news_file = news_aggregator.news_dir / "global.json"
            news_age = None
            
            if news_file.exists():
                news_age = (datetime.now() - 
                          datetime.fromtimestamp(news_file.stat().st_mtime)).total_seconds()
            
            health_status = "healthy"
            issues = []
            
            if len(available_symbols) < 10:
                issues.append("Low symbol count")
                health_status = "warning"
                
            if signals_age and signals_age > 600:  # 10 minutes
                issues.append("Stale signal data")
                health_status = "warning"
                
            if news_age and news_age > 1800:  # 30 minutes
                issues.append("Stale news data")
                health_status = "warning"
            
            return {
                "job": "health_check",
                "status": "success",
                "timestamp": datetime.now().isoformat(),
                "health_status": health_status,
                "results": {
                    "available_symbols": len(available_symbols),
                    "signals_age_seconds": signals_age,
                    "news_age_seconds": news_age,
                    "issues": issues
                }
            }
            
        except Exception as e:
            logger.error(f"Health check job failed: {e}")
            return {
                "job": "health_check",
                "status": "error",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }


# Export job functions for scheduler
SCHEDULED_JOBS = {
    "fetch_data": ScheduledJobs.job_fetch_data,
    "scan_signals": ScheduledJobs.job_scan_signals, 
    "update_news": ScheduledJobs.job_update_news,
    "full_data_sync": ScheduledJobs.job_full_data_sync,
    "cleanup_old_data": ScheduledJobs.job_cleanup_old_data,
    "health_check": ScheduledJobs.job_health_check
}