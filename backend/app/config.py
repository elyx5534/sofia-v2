"""
Sofia V2 Realtime DataHub - Configuration Management
Production-grade configuration with validation and environment support
"""

import os
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import structlog

logger = structlog.get_logger(__name__)

class ExchangeConfig(BaseSettings):
    """Exchange-specific configuration"""
    enabled: bool = True
    spot: bool = True
    futures: bool = False
    endpoints: Dict[str, str] = {}
    streams: List[str] = []
    rate_limits: Dict[str, int] = {}

class NewsConfig(BaseSettings):
    """News provider configuration"""
    provider: str = "cryptopanic_rss"
    poll_seconds_day: int = 30
    poll_seconds_night: int = 90
    night_hours: List[int] = [22, 23, 0, 1, 2, 3, 4, 5, 6, 7]
    endpoints: Dict[str, str] = {}
    params: Dict[str, Any] = {}
    deduplication: Dict[str, Any] = {}

class ThresholdsConfig(BaseSettings):
    """Detection thresholds configuration"""
    big_trade_usd_min: float = 250000.0
    liq_spike_sigma: float = 3.0
    connection_timeout: int = 10
    reconnect_max_delay: int = 15
    ping_interval: int = 30

class StorageConfig(BaseSettings):
    """Storage backend configuration"""
    parquet: Dict[str, Any] = {}
    timescale: Dict[str, Any] = {}

class MonitoringConfig(BaseSettings):
    """Monitoring and metrics configuration"""
    metrics: Dict[str, Any] = {}
    health_check: Dict[str, Any] = {}
    logging: Dict[str, Any] = {}

class PerformanceConfig(BaseSettings):
    """Performance tuning configuration"""
    backpressure_limit: int = 10000
    max_concurrent_operations: int = 100
    memory_limit_mb: int = 1000
    cpu_usage_alert: int = 80

class Settings(BaseSettings):
    """Main application settings"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )
    
    # Core Configuration
    symbols: str = Field(default="BTCUSDT,ETHUSDT,SOLUSDT", env="SYMBOLS")
    debug: bool = Field(default=False, env="DEBUG")
    
    # Database
    use_timescale: bool = Field(default=False, env="USE_TIMESCALE")
    database_url: Optional[str] = Field(default=None, env="DATABASE_URL")
    
    # Storage
    data_dir: str = Field(default="./data", env="DATA_DIR")
    parquet_rotation_hours: int = Field(default=24, env="PARQUET_ROTATION_HOURS")
    max_retention_days: int = Field(default=30, env="MAX_RETENTION_DAYS")
    
    # Exchange Toggles
    binance_spot: bool = Field(default=True, env="BINANCE_SPOT")
    binance_futures: bool = Field(default=True, env="BINANCE_FUTURES")
    okx_enabled: bool = Field(default=True, env="OKX_ENABLED")
    bybit_enabled: bool = Field(default=True, env="BYBIT_ENABLED")
    coinbase_enabled: bool = Field(default=True, env="COINBASE_ENABLED")
    
    # News
    cryptopanic_enabled: bool = Field(default=True, env="CRYPTOPANIC_ENABLED")
    news_poll_seconds_day: int = Field(default=30, env="NEWS_POLL_SECONDS_DAY")
    news_poll_seconds_night: int = Field(default=90, env="NEWS_POLL_SECONDS_NIGHT")
    
    # Thresholds
    big_trade_usd_min: float = Field(default=250000.0, env="BIG_TRADE_USD_MIN")
    liq_spike_sigma: float = Field(default=3.0, env="LIQ_SPIKE_SIGMA")
    
    # Fallback
    coingecko_fallback: bool = Field(default=True, env="COINGECKO_FALLBACK")
    cmc_fallback: bool = Field(default=False, env="CMC_FALLBACK")
    
    # Server
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    
    # Logging & Monitoring
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(default="json", env="LOG_FORMAT")
    enable_metrics: bool = Field(default=True, env="ENABLE_METRICS")
    metrics_port: int = Field(default=9090, env="METRICS_PORT")
    
    # Performance
    max_reconnect_delay: int = Field(default=15, env="MAX_RECONNECT_DELAY")
    ping_interval: int = Field(default=30, env="PING_INTERVAL")
    connection_timeout: int = Field(default=10, env="CONNECTION_TIMEOUT")
    ws_buffer_size: int = Field(default=1048576, env="WS_BUFFER_SIZE")
    max_concurrent_connections: int = Field(default=1000, env="MAX_CONCURRENT_CONNECTIONS")
    backpressure_limit: int = Field(default=10000, env="BACKPRESSURE_LIMIT")
    
    # Parsed data
    _symbols_list: Optional[List[str]] = None
    _yaml_config: Optional[Dict[str, Any]] = None
    
    @validator('symbols')
    def validate_symbols(cls, v):
        if not v or not v.strip():
            raise ValueError("SYMBOLS cannot be empty")
        return v.upper()
    
    @validator('log_level')
    def validate_log_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of {valid_levels}")
        return v.upper()
    
    @property
    def symbols_list(self) -> List[str]:
        """Get parsed list of symbols"""
        if self._symbols_list is None:
            self._symbols_list = [s.strip() for s in self.symbols.split(',') if s.strip()]
        return self._symbols_list
    
    @property
    def yaml_config(self) -> Dict[str, Any]:
        """Load and cache YAML configuration"""
        if self._yaml_config is None:
            config_path = Path("config.yml")
            if config_path.exists():
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        self._yaml_config = yaml.safe_load(f) or {}
                    logger.info("Loaded YAML configuration", path=str(config_path))
                except Exception as e:
                    logger.error("Failed to load YAML config", error=str(e))
                    self._yaml_config = {}
            else:
                logger.warning("config.yml not found, using defaults")
                self._yaml_config = {}
        return self._yaml_config
    
    def get_exchange_config(self, exchange: str) -> Dict[str, Any]:
        """Get exchange-specific configuration"""
        exchanges = self.yaml_config.get('exchanges', {})
        return exchanges.get(exchange, {})
    
    def get_news_config(self) -> Dict[str, Any]:
        """Get news configuration"""
        return self.yaml_config.get('news', {})
    
    def get_thresholds_config(self) -> Dict[str, Any]:
        """Get thresholds configuration"""
        return self.yaml_config.get('thresholds', {})
    
    def get_storage_config(self) -> Dict[str, Any]:
        """Get storage configuration"""
        return self.yaml_config.get('storage', {})
    
    def get_monitoring_config(self) -> Dict[str, Any]:
        """Get monitoring configuration"""
        return self.yaml_config.get('monitoring', {})
    
    def is_exchange_enabled(self, exchange: str) -> bool:
        """Check if exchange is enabled"""
        exchange_config = self.get_exchange_config(exchange)
        if not exchange_config:
            return False
        
        # Check both YAML and env var
        yaml_enabled = exchange_config.get('enabled', True)
        
        if exchange == 'binance':
            return yaml_enabled and (self.binance_spot or self.binance_futures)
        elif exchange == 'okx':
            return yaml_enabled and self.okx_enabled
        elif exchange == 'bybit':
            return yaml_enabled and self.bybit_enabled
        elif exchange == 'coinbase':
            return yaml_enabled and self.coinbase_enabled
        
        return yaml_enabled
    
    def get_enabled_exchanges(self) -> List[str]:
        """Get list of enabled exchanges"""
        exchanges = []
        for exchange in ['binance', 'okx', 'bybit', 'coinbase']:
            if self.is_exchange_enabled(exchange):
                exchanges.append(exchange)
        return exchanges
    
    def validate_config(self) -> bool:
        """Validate complete configuration"""
        try:
            # Check if at least one exchange is enabled
            if not self.get_enabled_exchanges():
                raise ValueError("At least one exchange must be enabled")
            
            # Check symbols
            if not self.symbols_list:
                raise ValueError("At least one symbol must be configured")
            
            # Check data directory
            data_path = Path(self.data_dir)
            data_path.mkdir(parents=True, exist_ok=True)
            
            # Check database URL if TimescaleDB enabled
            if self.use_timescale and not self.database_url:
                raise ValueError("DATABASE_URL required when USE_TIMESCALE=true")
            
            logger.info(
                "Configuration validated successfully",
                exchanges=self.get_enabled_exchanges(),
                symbols_count=len(self.symbols_list),
                timescale_enabled=self.use_timescale,
                metrics_enabled=self.enable_metrics
            )
            return True
            
        except Exception as e:
            logger.error("Configuration validation failed", error=str(e))
            return False

# Global settings instance
settings = Settings()

def get_settings() -> Settings:
    """Get global settings instance"""
    return settings

def reload_settings() -> Settings:
    """Reload settings (useful for testing)"""
    global settings
    settings = Settings()
    return settings