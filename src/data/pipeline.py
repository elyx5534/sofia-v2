"""
Data pipeline for fetching and storing OHLCV data from multiple exchanges
"""
import asyncio
import aiofiles
import aiofiles.os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from loguru import logger
import httpx
from concurrent.futures import ThreadPoolExecutor, as_completed

from .exchanges import exchange_manager


class DataPipeline:
    """Data pipeline for OHLCV collection and storage"""
    
    def __init__(self, data_dir: str = "./data"):
        self.data_dir = Path(data_dir)
        self.ohlcv_dir = self.data_dir / "ohlcv"
        self.ohlcv_dir.mkdir(parents=True, exist_ok=True)
        
    def get_parquet_path(self, symbol: str, timeframe: str) -> Path:
        """Get parquet file path for symbol and timeframe"""
        safe_symbol = symbol.replace('/', '-')
        return self.ohlcv_dir / f"{safe_symbol}_{timeframe}.parquet"
        
    def load_existing_data(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """Load existing parquet data if available"""
        parquet_path = self.get_parquet_path(symbol, timeframe)
        
        if parquet_path.exists():
            try:
                df = pd.read_parquet(parquet_path)
                logger.debug(f"Loaded {len(df)} existing records for {symbol} {timeframe}")
                return df
            except Exception as e:
                logger.warning(f"Failed to load existing data for {symbol}: {e}")
                
        return pd.DataFrame()
        
    def save_ohlcv_data(self, symbol: str, timeframe: str, df: pd.DataFrame):
        """Save OHLCV data to parquet format"""
        if df.empty:
            return
            
        parquet_path = self.get_parquet_path(symbol, timeframe)
        
        try:
            # Load existing data
            existing_df = self.load_existing_data(symbol, timeframe)
            
            if not existing_df.empty:
                # Combine with new data and remove duplicates
                combined_df = pd.concat([existing_df, df])
                combined_df = combined_df[~combined_df.index.duplicated(keep='last')]
                combined_df.sort_index(inplace=True)
            else:
                combined_df = df.sort_index()
                
            # Save to parquet
            combined_df.to_parquet(parquet_path, compression='snappy')
            logger.info(f"Saved {len(combined_df)} records to {parquet_path}")
            
        except Exception as e:
            logger.error(f"Failed to save data for {symbol}: {e}")
            
    def fetch_symbol_data(self, symbol: str, timeframe: str, 
                         since: datetime, limit: int = 1000) -> pd.DataFrame:
        """Fetch data for a single symbol"""
        try:
            # Get best data from available exchanges
            df = exchange_manager.get_best_data(symbol, timeframe, since, limit)
            
            if not df.empty:
                # Add metadata
                df['symbol'] = symbol
                df['exchange'] = 'multi'  # Could track which exchange was selected
                
            return df
            
        except Exception as e:
            logger.error(f"Failed to fetch {symbol}: {e}")
            return pd.DataFrame()
            
    def fetch_universe_data(self, timeframes: List[str] = None, 
                          days_back: int = 365, max_workers: int = 5) -> Dict[str, Any]:
        """Fetch data for entire USDT universe"""
        if timeframes is None:
            timeframes = ['1h', '1d']
            
        # Get unified symbol list
        symbols = exchange_manager.get_unified_symbol_list()
        since = datetime.now() - timedelta(days=days_back)
        
        logger.info(f"Starting data fetch for {len(symbols)} symbols, {len(timeframes)} timeframes")
        
        results = {
            'symbols_processed': 0,
            'symbols_failed': 0,
            'total_records': 0,
            'timeframes': timeframes
        }
        
        # Process each timeframe
        for timeframe in timeframes:
            logger.info(f"Processing timeframe: {timeframe}")
            
            # Determine limit based on timeframe
            if timeframe == '1h':
                limit = min(24 * days_back, 1000)
            elif timeframe == '1d':
                limit = min(days_back, 1000)
            else:
                limit = 1000
                
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all symbol fetch tasks
                future_to_symbol = {
                    executor.submit(self.fetch_symbol_data, symbol, timeframe, since, limit): symbol
                    for symbol in symbols
                }
                
                # Process completed tasks
                for future in as_completed(future_to_symbol):
                    symbol = future_to_symbol[future]
                    
                    try:
                        df = future.result(timeout=60)
                        
                        if not df.empty:
                            self.save_ohlcv_data(symbol, timeframe, df)
                            results['symbols_processed'] += 1
                            results['total_records'] += len(df)
                        else:
                            results['symbols_failed'] += 1
                            
                    except Exception as e:
                        logger.error(f"Error processing {symbol} {timeframe}: {e}")
                        results['symbols_failed'] += 1
                        
        logger.info(f"Data fetch completed: {results}")
        return results
        
    def update_recent_data(self, hours_back: int = 24) -> Dict[str, Any]:
        """Update recent data for all symbols"""
        since = datetime.now() - timedelta(hours=hours_back)
        
        # Get symbols that have existing data
        existing_symbols = []
        for parquet_file in self.ohlcv_dir.glob("*_1h.parquet"):
            symbol = parquet_file.stem.replace('_1h', '').replace('-', '/')
            existing_symbols.append(symbol)
            
        if not existing_symbols:
            logger.warning("No existing symbols found for update")
            return {'symbols_processed': 0, 'symbols_failed': 0}
            
        results = {'symbols_processed': 0, 'symbols_failed': 0}
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_symbol = {
                executor.submit(self.fetch_symbol_data, symbol, '1h', since, 100): symbol
                for symbol in existing_symbols
            }
            
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                
                try:
                    df = future.result(timeout=30)
                    
                    if not df.empty:
                        self.save_ohlcv_data(symbol, '1h', df)
                        results['symbols_processed'] += 1
                    else:
                        results['symbols_failed'] += 1
                        
                except Exception as e:
                    logger.error(f"Error updating {symbol}: {e}")
                    results['symbols_failed'] += 1
                    
        logger.info(f"Data update completed: {results}")
        return results
        
    def get_available_symbols(self) -> List[str]:
        """Get list of symbols with available data"""
        symbols = []
        
        for parquet_file in self.ohlcv_dir.glob("*_1h.parquet"):
            symbol = parquet_file.stem.replace('_1h', '').replace('-', '/')
            symbols.append(symbol)
            
        return sorted(symbols)
        
    def get_symbol_data(self, symbol: str, timeframe: str = '1h') -> pd.DataFrame:
        """Get stored data for a symbol"""
        return self.load_existing_data(symbol, timeframe)


# Global instance
data_pipeline = DataPipeline()