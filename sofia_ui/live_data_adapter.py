"""
Adapter to connect existing Sofia UI with new Data Reliability Pack
"""

import asyncio
import sys
from pathlib import Path
from typing import Dict, Optional, Any

# Add src to path for new modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.price_service_real import price_service
from src.services.symbols import symbol_mapper


class LiveDataAdapter:
    """Adapter between old UI and new data service"""
    
    def __init__(self):
        self.price_service = price_service
    
    async def get_live_price(self, symbol: str) -> Dict[str, Any]:
        """Get live price compatible with existing UI"""
        # Convert symbol format if needed
        ui_symbol = symbol
        if '/' not in symbol:
            # Convert BTCUSDT to BTC/USDT format
            if symbol.endswith('USDT'):
                base = symbol[:-4]
                ui_symbol = f"{base}/USDT"
        
        # Get price from new service
        price_data = await self.price_service.get_price(ui_symbol)
        
        if price_data:
            # Format for existing UI
            return {
                'symbol': symbol,
                'name': ui_symbol.split('/')[0],
                'price': price_data['price'],
                'change': 0,  # Calculate if historical data available
                'change_percent': 0,
                'volume': '0',
                'high_24h': price_data['price'] * 1.02,  # Estimate
                'low_24h': price_data['price'] * 0.98,   # Estimate
                'last_updated': 'Live',
                'source': price_data['source']
            }
        else:
            # Fallback data
            return {
                'symbol': symbol,
                'name': 'Unknown',
                'price': 0,
                'change': 0,
                'change_percent': 0,
                'volume': '0',
                'high_24h': 0,
                'low_24h': 0,
                'last_updated': 'Error',
                'source': 'none'
            }
    
    async def get_multiple_prices(self, symbols: list) -> Dict[str, Any]:
        """Get prices for multiple symbols"""
        results = {}
        for symbol in symbols:
            results[symbol] = await self.get_live_price(symbol)
        return results
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get service metrics"""
        return self.price_service.get_metrics()


# Global instance to replace old live_data_service
live_data_service = LiveDataAdapter()