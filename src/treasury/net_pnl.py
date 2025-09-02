"""
Net P&L Calculator with Fees and TR Taxes
Calculates net profit after exchange fees and Turkish taxes
"""

from decimal import Decimal
from typing import Dict, List, Optional
from datetime import datetime
import logging

from .fee_sync import FeeSync

logger = logging.getLogger(__name__)


class NetPnLCalculator:
    """Calculates net P&L after fees and taxes"""
    
    def __init__(self):
        self.fee_sync = FeeSync()
        
    def calculate_trade_fees(
        self,
        exchange: str,
        notional_value: Decimal,
        is_maker: bool = False
    ) -> Decimal:
        """Calculate exchange fees for a trade"""
        
        fee_bps = self.fee_sync.get_effective_fee_bps(exchange, is_maker)
        fee_amount = (notional_value * fee_bps) / Decimal("10000")
        
        return fee_amount
    
    def calculate_taxes(self, notional_value: Decimal) -> Dict[str, Decimal]:
        """Calculate Turkish taxes on trading"""
        
        taxes = {}
        
        # BSMV (Banking and Insurance Transaction Tax)
        bsmv_bps = self.fee_sync.get_tax_bps("bsmv")
        taxes["bsmv"] = (notional_value * bsmv_bps) / Decimal("10000")
        
        # Stamp duty
        stamp_bps = self.fee_sync.get_tax_bps("stamp")
        taxes["stamp"] = (notional_value * stamp_bps) / Decimal("10000")
        
        # Stopaj (withholding tax) - usually on profits only
        stopaj_bps = self.fee_sync.get_tax_bps("stopaj")
        taxes["stopaj"] = Decimal("0")  # Applied on profits later
        
        taxes["total"] = taxes["bsmv"] + taxes["stamp"] + taxes["stopaj"]
        
        return taxes
    
    def calculate_net_pnl(
        self,
        gross_pnl: Decimal,
        trades: List[Dict],
        currency: str = "TL"
    ) -> Dict:
        """
        Calculate net P&L after fees and taxes
        
        trades format: [
            {
                "exchange": "binance",
                "side": "buy/sell",
                "price": Decimal,
                "quantity": Decimal,
                "is_maker": bool
            }
        ]
        """
        
        result = {
            "gross_pnl": gross_pnl,
            "fees": {},
            "taxes": {},
            "net_pnl": gross_pnl,
            "currency": currency
        }
        
        total_fees = Decimal("0")
        total_taxes = Decimal("0")
        
        # Calculate fees for each trade
        for trade in trades:
            exchange = trade["exchange"]
            notional = trade["price"] * trade["quantity"]
            is_maker = trade.get("is_maker", False)
            
            # Exchange fees
            trade_fee = self.calculate_trade_fees(exchange, notional, is_maker)
            
            if exchange not in result["fees"]:
                result["fees"][exchange] = Decimal("0")
            
            result["fees"][exchange] += trade_fee
            total_fees += trade_fee
            
            # Taxes (for TR exchanges or TL pairs)
            if currency == "TL" or "tr" in exchange.lower():
                trade_taxes = self.calculate_taxes(notional)
                
                for tax_type, amount in trade_taxes.items():
                    if tax_type != "total":
                        if tax_type not in result["taxes"]:
                            result["taxes"][tax_type] = Decimal("0")
                        result["taxes"][tax_type] += amount
                
                total_taxes += trade_taxes["total"]
        
        # Apply stopaj on profits if applicable
        if gross_pnl > 0 and currency == "TL":
            stopaj_bps = self.fee_sync.get_tax_bps("stopaj")
            stopaj_amount = (gross_pnl * stopaj_bps) / Decimal("10000")
            result["taxes"]["stopaj"] = stopaj_amount
            total_taxes += stopaj_amount
        
        # Calculate net P&L
        result["total_fees"] = total_fees
        result["total_taxes"] = total_taxes
        result["net_pnl"] = gross_pnl - total_fees - total_taxes
        
        # Add percentage breakdown
        if gross_pnl != 0:
            result["fee_percentage"] = (total_fees / abs(gross_pnl)) * 100
            result["tax_percentage"] = (total_taxes / abs(gross_pnl)) * 100
            result["net_percentage"] = (result["net_pnl"] / gross_pnl) * 100
        else:
            result["fee_percentage"] = Decimal("0")
            result["tax_percentage"] = Decimal("0")
            result["net_percentage"] = Decimal("0")
        
        return result
    
    def calculate_arbitrage_net_pnl(
        self,
        spread_bps: Decimal,
        size_tl: Decimal,
        exchange_a: str = "btcturk",
        exchange_b: str = "binance_tr"
    ) -> Dict:
        """Calculate net P&L for an arbitrage trade"""
        
        # Gross profit from spread
        gross_pnl = (size_tl * spread_bps) / Decimal("10000")
        
        # Simulate two trades (buy on A, sell on B)
        trades = [
            {
                "exchange": exchange_a,
                "side": "buy",
                "price": size_tl,  # Simplified
                "quantity": Decimal("1"),
                "is_maker": False  # Taker for arbitrage
            },
            {
                "exchange": exchange_b,
                "side": "sell",
                "price": size_tl,
                "quantity": Decimal("1"),
                "is_maker": False
            }
        ]
        
        result = self.calculate_net_pnl(gross_pnl, trades, currency="TL")
        
        # Add arbitrage-specific metrics
        result["spread_bps"] = spread_bps
        result["size_tl"] = size_tl
        result["net_spread_bps"] = (result["net_pnl"] / size_tl) * Decimal("10000")
        
        return result
    
    def format_pnl_report(self, pnl_data: Dict) -> str:
        """Format P&L data as readable report"""
        
        lines = []
        lines.append("="*50)
        lines.append(" NET P&L REPORT")
        lines.append("="*50)
        
        lines.append(f"Gross P&L: {pnl_data['gross_pnl']:.2f} {pnl_data['currency']}")
        
        if pnl_data["fees"]:
            lines.append("\nFees:")
            for exchange, amount in pnl_data["fees"].items():
                lines.append(f"  {exchange}: {amount:.2f} {pnl_data['currency']}")
            lines.append(f"  Total: {pnl_data['total_fees']:.2f} {pnl_data['currency']}")
        
        if pnl_data["taxes"]:
            lines.append("\nTaxes:")
            for tax_type, amount in pnl_data["taxes"].items():
                if amount > 0:
                    lines.append(f"  {tax_type.upper()}: {amount:.2f} {pnl_data['currency']}")
            lines.append(f"  Total: {pnl_data['total_taxes']:.2f} {pnl_data['currency']}")
        
        lines.append("\n" + "-"*30)
        lines.append(f"Net P&L: {pnl_data['net_pnl']:.2f} {pnl_data['currency']}")
        
        if pnl_data["gross_pnl"] != 0:
            lines.append(f"Net Ratio: {pnl_data['net_percentage']:.1f}%")
        
        lines.append("="*50)
        
        return "\n".join(lines)


def test_net_pnl():
    """Test net P&L calculator"""
    
    calc = NetPnLCalculator()
    
    print("="*60)
    print(" NET P&L CALCULATOR TEST")
    print("="*60)
    
    # Test 1: Simple trade with fees
    print("\nTest 1: Single Trade")
    trades = [
        {
            "exchange": "binance",
            "side": "buy",
            "price": Decimal("100000"),
            "quantity": Decimal("0.01"),
            "is_maker": True
        }
    ]
    
    result = calc.calculate_net_pnl(Decimal("50"), trades, currency="USDT")
    print(calc.format_pnl_report(result))
    
    # Test 2: Turkish arbitrage with taxes
    print("\nTest 2: Turkish Arbitrage")
    
    # Update tax rates for testing
    calc.fee_sync.update_tax_rates(bsmv_bps=5, stamp_bps=2)
    
    arb_result = calc.calculate_arbitrage_net_pnl(
        spread_bps=Decimal("25"),  # 25 bps spread
        size_tl=Decimal("10000"),  # 10,000 TL
        exchange_a="btcturk",
        exchange_b="binance_tr"
    )
    
    print(calc.format_pnl_report(arb_result))
    print(f"\nNet Spread: {arb_result['net_spread_bps']:.2f} bps (was {arb_result['spread_bps']} bps gross)")
    
    print("="*60)


if __name__ == "__main__":
    test_net_pnl()