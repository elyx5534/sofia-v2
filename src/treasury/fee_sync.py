"""
Fee Synchronization from Exchanges
Fetches real-time fee tiers and applies campaign discounts
"""

import json
import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class FeeSync:
    """Synchronizes fee information from exchanges"""
    
    def __init__(self):
        self.config_file = Path("config/fees.yaml")
        self.load_config()
        
    def load_config(self):
        """Load fee configuration"""
        if self.config_file.exists():
            with open(self.config_file, 'r') as f:
                self.config = yaml.safe_load(f)
        else:
            # Default configuration
            self.config = {
                "binance": {
                    "maker_bps": 10,
                    "taker_bps": 10,
                    "campaign_discount_bps": 0,
                    "vip_level": 0
                },
                "btcturk": {
                    "maker_bps": 25,
                    "taker_bps": 35,
                    "campaign_discount_bps": 0,
                    "volume_tier": 0
                },
                "binance_tr": {
                    "maker_bps": 10,
                    "taker_bps": 10,
                    "campaign_discount_bps": 0
                },
                "tax": {
                    "bsmv_bps": 0,  # BSMV (Banking and Insurance Transaction Tax)
                    "stamp_bps": 0,  # Stamp duty
                    "stopaj_bps": 0  # Withholding tax (if applicable)
                }
            }
            self.save_config()
    
    def save_config(self):
        """Save configuration to file"""
        self.config_file.parent.mkdir(exist_ok=True)
        with open(self.config_file, 'w') as f:
            yaml.dump(self.config, f, default_flow_style=False)
    
    async def sync_from_exchange(self, exchange: str) -> Dict:
        """Sync fee information from exchange API"""
        
        # In production, would fetch from exchange API
        # For now, simulate with mock data
        
        if exchange == "binance":
            # Simulate Binance fee tiers
            mock_fees = {
                "maker": 0.001,  # 0.1%
                "taker": 0.001,
                "tier": {
                    "level": 0,
                    "30d_volume": 0,
                    "bnb_balance": 0
                }
            }
        elif exchange == "btcturk":
            # Simulate BTCTurk fee tiers
            mock_fees = {
                "maker": 0.0025,  # 0.25%
                "taker": 0.0035,
                "tier": {
                    "level": 0,
                    "30d_volume_try": 0
                }
            }
        else:
            mock_fees = {
                "maker": 0.001,
                "taker": 0.001
            }
        
        # Update config with synced values
        if exchange in self.config:
            self.config[exchange]["maker_bps"] = int(mock_fees["maker"] * 10000)
            self.config[exchange]["taker_bps"] = int(mock_fees["taker"] * 10000)
            self.config[exchange]["last_sync"] = datetime.now().isoformat()
        
        logger.info(f"Synced fees for {exchange}: maker={mock_fees['maker']:.4%}, taker={mock_fees['taker']:.4%}")
        
        return mock_fees
    
    def get_effective_fee_bps(self, exchange: str, is_maker: bool = False) -> Decimal:
        """Get effective fee in basis points after discounts"""
        
        if exchange not in self.config:
            logger.warning(f"No fee config for {exchange}, using default")
            return Decimal("10")  # Default 10 bps
        
        exchange_config = self.config[exchange]
        
        # Get base fee
        base_fee_bps = exchange_config["maker_bps"] if is_maker else exchange_config["taker_bps"]
        
        # Apply campaign discount
        campaign_discount = exchange_config.get("campaign_discount_bps", 0)
        
        effective_fee_bps = max(0, base_fee_bps - campaign_discount)
        
        return Decimal(str(effective_fee_bps))
    
    def get_tax_bps(self, tax_type: str) -> Decimal:
        """Get tax rate in basis points"""
        
        tax_config = self.config.get("tax", {})
        
        if tax_type == "bsmv":
            return Decimal(str(tax_config.get("bsmv_bps", 0)))
        elif tax_type == "stamp":
            return Decimal(str(tax_config.get("stamp_bps", 0)))
        elif tax_type == "stopaj":
            return Decimal(str(tax_config.get("stopaj_bps", 0)))
        else:
            return Decimal("0")
    
    def get_total_tax_bps(self) -> Decimal:
        """Get total tax rate in basis points"""
        
        tax_config = self.config.get("tax", {})
        
        total_tax = (
            tax_config.get("bsmv_bps", 0) +
            tax_config.get("stamp_bps", 0) +
            tax_config.get("stopaj_bps", 0)
        )
        
        return Decimal(str(total_tax))
    
    def update_campaign_discount(self, exchange: str, discount_bps: int):
        """Update campaign discount for an exchange"""
        
        if exchange in self.config:
            self.config[exchange]["campaign_discount_bps"] = discount_bps
            self.save_config()
            logger.info(f"Updated {exchange} campaign discount to {discount_bps} bps")
    
    def update_tax_rates(self, bsmv_bps: int = None, stamp_bps: int = None, stopaj_bps: int = None):
        """Update tax rates"""
        
        if "tax" not in self.config:
            self.config["tax"] = {}
        
        if bsmv_bps is not None:
            self.config["tax"]["bsmv_bps"] = bsmv_bps
        
        if stamp_bps is not None:
            self.config["tax"]["stamp_bps"] = stamp_bps
        
        if stopaj_bps is not None:
            self.config["tax"]["stopaj_bps"] = stopaj_bps
        
        self.save_config()
        logger.info(f"Updated tax rates: BSMV={bsmv_bps}, Stamp={stamp_bps}, Stopaj={stopaj_bps}")
    
    def get_fee_summary(self) -> Dict:
        """Get summary of all fees and taxes"""
        
        summary = {
            "exchanges": {},
            "taxes": {},
            "timestamp": datetime.now().isoformat()
        }
        
        # Exchange fees
        for exchange in ["binance", "btcturk", "binance_tr"]:
            if exchange in self.config:
                maker_fee = self.get_effective_fee_bps(exchange, is_maker=True)
                taker_fee = self.get_effective_fee_bps(exchange, is_maker=False)
                
                summary["exchanges"][exchange] = {
                    "maker_bps": float(maker_fee),
                    "taker_bps": float(taker_fee),
                    "campaign_discount_bps": self.config[exchange].get("campaign_discount_bps", 0)
                }
        
        # Tax rates
        summary["taxes"] = {
            "bsmv_bps": float(self.get_tax_bps("bsmv")),
            "stamp_bps": float(self.get_tax_bps("stamp")),
            "stopaj_bps": float(self.get_tax_bps("stopaj")),
            "total_bps": float(self.get_total_tax_bps())
        }
        
        return summary


def test_fee_sync():
    """Test fee synchronization"""
    
    fee_sync = FeeSync()
    
    print("="*60)
    print(" FEE SYNC TEST")
    print("="*60)
    
    # Get current fees
    for exchange in ["binance", "btcturk"]:
        maker_fee = fee_sync.get_effective_fee_bps(exchange, is_maker=True)
        taker_fee = fee_sync.get_effective_fee_bps(exchange, is_maker=False)
        
        print(f"\n{exchange}:")
        print(f"  Maker: {maker_fee} bps ({float(maker_fee)/100:.2f}%)")
        print(f"  Taker: {taker_fee} bps ({float(taker_fee)/100:.2f}%)")
    
    # Test campaign discount
    fee_sync.update_campaign_discount("binance", 2)  # 2 bps discount
    
    print("\nAfter campaign discount:")
    maker_fee = fee_sync.get_effective_fee_bps("binance", is_maker=True)
    print(f"  Binance Maker: {maker_fee} bps")
    
    # Test tax rates
    fee_sync.update_tax_rates(bsmv_bps=5, stamp_bps=2)  # 0.05% BSMV, 0.02% stamp
    
    print("\nTax Rates:")
    print(f"  BSMV: {fee_sync.get_tax_bps('bsmv')} bps")
    print(f"  Stamp: {fee_sync.get_tax_bps('stamp')} bps")
    print(f"  Total: {fee_sync.get_total_tax_bps()} bps")
    
    # Get summary
    summary = fee_sync.get_fee_summary()
    print("\nFee Summary:")
    print(json.dumps(summary, indent=2))
    
    print("="*60)


if __name__ == "__main__":
    test_fee_sync()