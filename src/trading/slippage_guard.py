"""
Slippage Guard Module
Protects against excessive slippage in trading operations
"""


class SlippageController:
    """Controls and monitors slippage in trading operations"""

    def __init__(self, max_slippage: float = 0.02):
        """
        Initialize slippage controller

        Args:
            max_slippage: Maximum allowed slippage (default 2%)
        """
        self.max_slippage = max_slippage
        self.slippage_events = []

    def check_slippage(self, expected_price: float, actual_price: float, side: str = "buy") -> bool:
        """
        Check if slippage is within acceptable limits

        Args:
            expected_price: Expected execution price
            actual_price: Actual execution price
            side: "buy" or "sell"

        Returns:
            True if slippage is acceptable, False otherwise
        """
        if expected_price == 0:
            return False
        slippage = abs(actual_price - expected_price) / expected_price
        if side == "buy" and actual_price > expected_price:
            slippage = -slippage
        elif side == "sell" and actual_price < expected_price:
            slippage = -slippage
        self.slippage_events.append(
            {"expected": expected_price, "actual": actual_price, "slippage": slippage, "side": side}
        )
        return abs(slippage) <= self.max_slippage

    def get_stats(self) -> dict:
        """Get slippage statistics"""
        if not self.slippage_events:
            return {"total_events": 0, "avg_slippage": 0, "max_slippage": 0, "violations": 0}
        slippages = [e["slippage"] for e in self.slippage_events]
        violations = sum(1 for s in slippages if abs(s) > self.max_slippage)
        return {
            "total_events": len(self.slippage_events),
            "avg_slippage": sum(slippages) / len(slippages),
            "max_slippage": max(abs(s) for s in slippages),
            "violations": violations,
        }
