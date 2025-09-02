"""Fake yfinance module for offline testing."""

import pandas as pd
from datetime import datetime, timedelta

class Ticker:
    def __init__(self, symbol):
        self.symbol = symbol
    
    def history(self, start=None, end=None, interval="1d", **kwargs):
        """Return fake historical data."""
        # Generate synthetic data
        if not start:
            start = datetime.now() - timedelta(days=30)
        if not end:
            end = datetime.now()
        
        # Create date range based on interval
        if interval in ["1m", "5m", "15m", "30m"]:
            freq = "1h"  # Simplify for testing
        elif interval == "1h":
            freq = "1h"
        else:
            freq = "1d"
        
        dates = pd.date_range(start, end, freq=freq)[:100]  # Limit to 100 points
        
        # Generate synthetic prices
        base_price = 50000 if "BTC" in self.symbol else 100
        
        df = pd.DataFrame({
            'Open': [base_price + i * 10 for i in range(len(dates))],
            'High': [base_price + i * 10 + 50 for i in range(len(dates))],
            'Low': [base_price + i * 10 - 50 for i in range(len(dates))],
            'Close': [base_price + i * 10 + 20 for i in range(len(dates))],
            'Volume': [1000 + i * 10 for i in range(len(dates))]
        }, index=dates)
        
        return df
    
    def info(self):
        """Return fake ticker info."""
        return {
            'symbol': self.symbol,
            'longName': f'Mock {self.symbol}',
            'regularMarketPrice': 50000 if "BTC" in self.symbol else 100,
            'volume': 1000000
        }

def download(tickers, **kwargs):
    """Mock download function."""
    if isinstance(tickers, str):
        tickers = [tickers]
    
    # Return fake data for first ticker
    ticker = Ticker(tickers[0])
    return ticker.history(**kwargs)