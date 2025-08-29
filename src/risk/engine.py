"""
Mock Risk Engine for Testing
"""

from typing import Dict, Any
from decimal import Decimal


class RiskEngine:
    """Mock risk engine for testing"""
    
    def __init__(self):
        pass
    
    async def pre_trade_check(self, symbol: str, side: str, quantity: Decimal, 
                            price: Decimal, **kwargs) -> Dict[str, Any]:
        """Mock pre-trade risk check"""
        return {
            'approved': True,
            'checks': {
                'position_limit': {'passed': True},
                'daily_loss_limit': {'passed': True},
                'symbol_exposure': {'passed': True}
            }
        }