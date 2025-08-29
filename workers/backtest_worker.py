"""
Backtest worker - processes backtest jobs from queue
"""

import os
import sys
import time
import json
import logging
import traceback
from datetime import datetime
from pathlib import Path
import pandas as pd
import yfinance as yf

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.backtest import BacktestJob, BacktestResult, Base
from src.strategies.sma_cross import SmaCross, EmaBreakout, RSIMeanReversion
from src.backtest.runner import BacktestRunner
from src.reports.generator import ReportGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database setup
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./backtest.db')
engine = create_engine(DATABASE_URL)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

# Strategy registry
STRATEGIES = {
    'sma_cross': SmaCross(),
    'ema_breakout': EmaBreakout(),
    'rsi_reversion': RSIMeanReversion(),
}

# Directories for outputs
OUTPUTS_DIR = Path('outputs')
OUTPUTS_DIR.mkdir(exist_ok=True)
EQUITY_DIR = OUTPUTS_DIR / 'equity'
TRADES_DIR = OUTPUTS_DIR / 'trades'
LOGS_DIR = OUTPUTS_DIR / 'logs'
REPORTS_DIR = OUTPUTS_DIR / 'reports'

for dir in [EQUITY_DIR, TRADES_DIR, LOGS_DIR, REPORTS_DIR]:
    dir.mkdir(exist_ok=True)


class BacktestWorker:
    """Worker to process backtest jobs"""
    
    def __init__(self):
        self.session = Session()
        self.runner = BacktestRunner()
        self.report_generator = ReportGenerator()
        self.running = True
        
    def fetch_pending_job(self):
        """Fetch next pending job from queue"""
        job = self.session.query(BacktestJob).filter_by(
            status='pending'
        ).order_by(BacktestJob.created_at).first()
        
        if job:
            job.status = 'running'
            job.started_at = datetime.utcnow()
            self.session.commit()
            logger.info(f"Fetched job {job.id}: {job.strategy}")
        
        return job
    
    def fetch_ohlcv_data(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        """Fetch OHLCV data for backtesting"""
        
        # Map timeframe to yfinance period
        period_map = {
            '1m': '7d',
            '5m': '1mo',
            '15m': '1mo',
            '1h': '3mo',
            '4h': '1y',
            '1d': '2y',
        }
        
        interval_map = {
            '1m': '1m',
            '5m': '5m',
            '15m': '15m',
            '1h': '60m',
            '4h': '1d',  # yfinance doesn't support 4h
            '1d': '1d',
        }
        
        period = period_map.get(timeframe, '3mo')
        interval = interval_map.get(timeframe, '60m')
        
        try:
            # Remove /USDT suffix for yfinance
            ticker_symbol = symbol.replace('/USDT', '-USD').replace('/', '-')
            
            ticker = yf.Ticker(ticker_symbol)
            df = ticker.history(period=period, interval=interval)
            
            if df.empty:
                # Try mock data for testing
                logger.warning(f"No data for {symbol}, using mock data")
                df = self.generate_mock_data(limit)
            
            # Rename columns to lowercase
            df.columns = df.columns.str.lower()
            
            # Limit rows
            if len(df) > limit:
                df = df.tail(limit)
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            # Return mock data for testing
            return self.generate_mock_data(limit)
    
    def generate_mock_data(self, limit: int) -> pd.DataFrame:
        """Generate mock OHLCV data for testing"""
        import numpy as np
        
        dates = pd.date_range(end=datetime.now(), periods=limit, freq='1h')
        
        # Generate random walk price
        returns = np.random.randn(limit) * 0.01
        price = 100 * np.exp(np.cumsum(returns))
        
        df = pd.DataFrame({
            'open': price * (1 + np.random.randn(limit) * 0.001),
            'high': price * (1 + np.abs(np.random.randn(limit)) * 0.002),
            'low': price * (1 - np.abs(np.random.randn(limit)) * 0.002),
            'close': price,
            'volume': np.random.randint(1000000, 10000000, limit)
        }, index=dates)
        
        return df
    
    def process_job(self, job: BacktestJob):
        """Process a single backtest job"""
        try:
            logger.info(f"Processing job {job.id}")
            
            # Get strategy
            strategy = STRATEGIES.get(job.strategy)
            if not strategy:
                raise ValueError(f"Unknown strategy: {job.strategy}")
            
            # Fetch OHLCV data
            ohlcv = self.fetch_ohlcv_data(job.symbol, job.timeframe, job.limit)
            
            # Generate signals
            signals = strategy(ohlcv, job.params_json)
            
            # Run backtest
            metrics, equity_df, trades_df, logs_str = self.runner.run_backtest(
                ohlcv, signals
            )
            
            # Save outputs
            job_id = job.id
            equity_path = EQUITY_DIR / f'{job_id}_equity.csv'
            trades_path = TRADES_DIR / f'{job_id}_trades.csv'
            logs_path = LOGS_DIR / f'{job_id}_logs.txt'
            
            equity_df.to_csv(equity_path)
            if not trades_df.empty:
                trades_df.to_csv(trades_path)
            else:
                trades_path = None
            
            with open(logs_path, 'w') as f:
                f.write(logs_str)
            
            # Generate HTML report
            report_path = self.report_generator.generate(
                job_id=job_id,
                strategy_name=job.strategy,
                params=job.params_json,
                metrics=metrics,
                equity_df=equity_df,
                trades_df=trades_df,
                symbol=job.symbol
            )
            
            # Create result record
            result = BacktestResult(
                job_id=job_id,
                metrics_json=metrics,
                total_return=metrics['total_return'],
                cagr=metrics['cagr'],
                sharpe_ratio=metrics['sharpe_ratio'],
                max_drawdown=metrics['max_drawdown'],
                win_rate=metrics['win_rate'],
                avg_trade=metrics['avg_trade'],
                total_trades=metrics['total_trades'],
                exposure_time=metrics['exposure_time'],
                mar_ratio=metrics['mar_ratio'],
                equity_csv_path=str(equity_path),
                trades_csv_path=str(trades_path) if trades_path else None,
                logs_txt_path=str(logs_path),
                report_html_path=str(report_path)
            )
            
            self.session.add(result)
            
            # Update job status
            job.status = 'done'
            job.finished_at = datetime.utcnow()
            self.session.commit()
            
            logger.info(f"Job {job_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Error processing job {job.id}: {e}")
            logger.error(traceback.format_exc())
            
            # Update job with error
            job.status = 'error'
            job.error_message = str(e)
            job.finished_at = datetime.utcnow()
            self.session.commit()
    
    def run(self):
        """Main worker loop"""
        logger.info("Backtest worker started")
        
        while self.running:
            try:
                # Fetch pending job
                job = self.fetch_pending_job()
                
                if job:
                    self.process_job(job)
                else:
                    # No jobs, wait
                    time.sleep(5)
                    
            except KeyboardInterrupt:
                logger.info("Worker interrupted by user")
                self.running = False
                
            except Exception as e:
                logger.error(f"Worker error: {e}")
                logger.error(traceback.format_exc())
                time.sleep(5)
        
        logger.info("Backtest worker stopped")
        self.session.close()


if __name__ == "__main__":
    worker = BacktestWorker()
    worker.run()