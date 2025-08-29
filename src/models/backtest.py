"""
Database models for backtest jobs and results
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, Float, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class BacktestJob(Base):
    __tablename__ = 'bt_jobs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy = Column(String(100), nullable=False)
    params_json = Column(JSON, nullable=False)
    symbol = Column(String(50), nullable=False)
    timeframe = Column(String(10), default='1h')
    limit = Column(Integer, default=1000)
    status = Column(String(20), default='pending')  # pending|running|done|error
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    
    # Relationship
    result = relationship("BacktestResult", back_populates="job", uselist=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'strategy': self.strategy,
            'params': self.params_json,
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'status': self.status,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'finished_at': self.finished_at.isoformat() if self.finished_at else None,
        }


class BacktestResult(Base):
    __tablename__ = 'bt_results'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey('bt_jobs.id'), unique=True)
    
    # Metrics
    metrics_json = Column(JSON, nullable=False)
    
    # Performance metrics (for quick queries)
    total_return = Column(Float)
    cagr = Column(Float)
    sharpe_ratio = Column(Float)
    max_drawdown = Column(Float)
    win_rate = Column(Float)
    avg_trade = Column(Float)
    total_trades = Column(Integer)
    exposure_time = Column(Float)
    mar_ratio = Column(Float)  # CAGR / MaxDD
    
    # File paths
    equity_csv_path = Column(String(255))
    trades_csv_path = Column(String(255))
    logs_txt_path = Column(String(255))
    report_html_path = Column(String(255))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    job = relationship("BacktestJob", back_populates="result")
    
    def to_dict(self):
        return {
            'id': self.id,
            'job_id': self.job_id,
            'metrics': self.metrics_json,
            'total_return': self.total_return,
            'cagr': self.cagr,
            'sharpe_ratio': self.sharpe_ratio,
            'max_drawdown': self.max_drawdown,
            'win_rate': self.win_rate,
            'avg_trade': self.avg_trade,
            'total_trades': self.total_trades,
            'exposure_time': self.exposure_time,
            'mar_ratio': self.mar_ratio,
            'links': {
                'equity_csv': self.equity_csv_path,
                'trades_csv': self.trades_csv_path,
                'logs': self.logs_txt_path,
                'report_html': self.report_html_path,
            },
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class OptimizationJob(Base):
    __tablename__ = 'opt_jobs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy = Column(String(100), nullable=False)
    mode = Column(String(20), nullable=False)  # grid|ga
    space_json = Column(JSON, nullable=False)  # Parameter space
    symbol = Column(String(50), nullable=False)
    timeframe = Column(String(10), default='1h')
    status = Column(String(20), default='pending')
    progress = Column(Float, default=0.0)  # 0-100%
    best_params = Column(JSON, nullable=True)
    best_score = Column(Float, nullable=True)
    total_runs = Column(Integer, default=0)
    completed_runs = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'strategy': self.strategy,
            'mode': self.mode,
            'space': self.space_json,
            'symbol': self.symbol,
            'status': self.status,
            'progress': self.progress,
            'best_params': self.best_params,
            'best_score': self.best_score,
            'total_runs': self.total_runs,
            'completed_runs': self.completed_runs,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }