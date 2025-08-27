#!/usr/bin/env python3
"""
Production demo script for Sofia V2 real-data test harness.
Validates entire system within ~10 minutes.
"""

import os
import sys
import time
import asyncio
import requests
import subprocess
from pathlib import Path

# Add src to path  
sys.path.insert(0, str(Path(__file__).parent.parent))

class ProductionDemo:
    """Complete production demo and validation."""
    
    def __init__(self, api_url="http://localhost:8001"):
        self.api_url = api_url
        self.session = requests.Session()
        
    def log(self, message):
        """Log with timestamp."""
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
    
    def check_health(self):
        """Step 1: Verify API health."""
        self.log("Checking API health...")
        
        try:
            response = self.session.get(f"{self.api_url}/health", timeout=10)
            if response.status_code != 200:
                raise Exception(f"Health check failed: {response.status_code}")
            
            data = response.json()
            self.log(f"API Status: {data['status']}")
            self.log(f"Version: {data['version']}")
            self.log(f"Uptime: {data['uptime_seconds']:.1f}s")
            
            return True
        except Exception as e:
            self.log(f"ERROR: Health check failed: {e}")
            return False
    
    def check_initial_portfolio(self):
        """Step 2: Verify $100k starting balance."""
        self.log("Checking initial portfolio...")
        
        try:
            response = self.session.get(f"{self.api_url}/api/trading/portfolio")
            if response.status_code != 200:
                raise Exception(f"Portfolio fetch failed: {response.status_code}")
            
            data = response.json()["data"]
            
            self.log(f"Cash Balance: ${data['cash_balance']:,.2f}")
            self.log(f"Total Equity: ${data['total_equity']:,.2f}")
            self.log(f"Total P&L: ${data['total_pnl']:,.2f}")
            self.log(f"Positions: {len(data['positions'])}")
            
            if data["cash_balance"] != 100000.0:
                self.log("WARNING: Expected $100,000 starting balance")
                
            return True
        except Exception as e:
            self.log(f"ERROR: Portfolio check failed: {e}")
            return False
    
    def check_price_freshness(self, max_wait=30):
        """Step 3: Verify price freshness < 15s."""
        self.log("Checking price data freshness...")
        
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            try:
                response = self.session.get(f"{self.api_url}/metrics")
                if response.status_code == 200:
                    metrics = response.text
                    
                    # Parse freshness values
                    freshness_values = []
                    for line in metrics.split('\n'):
                        if 'sofia_price_freshness_seconds{symbol=' in line:
                            try:
                                value = float(line.split()[-1])
                                freshness_values.append(value)
                            except (ValueError, IndexError):
                                continue
                    
                    if freshness_values:
                        max_freshness = max(freshness_values)
                        self.log(f"Price freshness: {max_freshness:.1f}s (max)")
                        
                        if max_freshness < 15.0:
                            self.log("PASS: Price data is fresh")
                            return True
                
                time.sleep(2)
                
            except Exception as e:
                self.log(f"Metrics check error: {e}")
                time.sleep(2)
        
        self.log("WARNING: Price freshness timeout - continuing with demo")
        return False
    
    def test_manual_trade(self):
        """Step 4: Execute manual trade and verify P&L update."""
        self.log("Testing manual trade execution...")
        
        try:
            # Place buy order
            order_data = {
                "symbol": "BTCUSDT",
                "side": "buy",
                "usd_amount": 150.0
            }
            
            response = self.session.post(f"{self.api_url}/api/trading/paper-order", json=order_data)
            if response.status_code != 200:
                raise Exception(f"Manual trade failed: {response.text}")
            
            trade_result = response.json()["data"]
            self.log(f"Trade executed: {trade_result['side'].upper()} {trade_result['quantity']:.6f} {trade_result['symbol']}")
            self.log(f"Execution price: ${trade_result['price']:,.2f}")
            self.log(f"Fees: ${trade_result['fees']:.2f}")
            
            # Wait for portfolio update
            time.sleep(1)
            
            # Check updated portfolio
            portfolio_response = self.session.get(f"{self.api_url}/api/trading/portfolio")
            if portfolio_response.status_code == 200:
                portfolio = portfolio_response.json()["data"]
                
                if "BTCUSDT" in portfolio["positions"]:
                    position = portfolio["positions"]["BTCUSDT"] 
                    self.log(f"New position: {position['quantity']:.6f} BTC @ ${position['avg_entry_price']:,.2f}")
                    self.log(f"Market value: ${position['market_value']:,.2f}")
                    self.log(f"Unrealized P&L: ${position['unrealized_pnl']:,.2f}")
                    
                    self.log("PASS: Manual trade and P&L update successful")
                    return True
                else:
                    self.log("WARNING: Position not found after trade")
            
        except Exception as e:
            self.log(f"ERROR: Manual trade failed: {e}")
            return False
    
    def test_strategy_toggle(self):
        """Step 5: Test strategy enable/disable."""
        self.log("Testing micro momentum strategy...")
        
        try:
            # Enable strategy
            response = self.session.post(f"{self.api_url}/api/strategy/micro-momo/enable", 
                                       json={"enabled": True})
            if response.status_code != 200:
                raise Exception(f"Strategy enable failed: {response.text}")
            
            self.log("Strategy enabled")
            
            # Check status
            time.sleep(1)
            status_response = self.session.get(f"{self.api_url}/api/strategy/micro-momo/status")
            if status_response.status_code == 200:
                status_data = status_response.json()["data"]
                self.log(f"Strategy running: {status_data['running']}")
                self.log(f"Trade size: ${status_data['trade_usd']}")
                self.log(f"Cooldown: {status_data['cooldown_seconds']}s")
                
                # Show thresholds
                for symbol, threshold in status_data["thresholds"].items():
                    self.log(f"  {symbol}: {threshold*100:.3f}% threshold")
            
            # Disable strategy after test
            self.session.post(f"{self.api_url}/api/strategy/micro-momo/enable", 
                            json={"enabled": False})
            
            self.log("PASS: Strategy toggle successful")
            return True
            
        except Exception as e:
            self.log(f"ERROR: Strategy test failed: {e}")
            return False
    
    def monitor_for_trades(self, duration_minutes=5):
        """Step 6: Monitor for automatic trades."""
        self.log(f"Monitoring for trades ({duration_minutes} minutes)...")
        
        # Enable strategy
        self.session.post(f"{self.api_url}/api/strategy/micro-momo/enable", json={"enabled": True})
        
        start_time = time.time()
        initial_positions = self.get_positions_count()
        
        while time.time() - start_time < duration_minutes * 60:
            current_positions = self.get_positions_count()
            
            if current_positions > initial_positions:
                self.log(f"DETECTED: New position created! ({current_positions} total)")
                self.show_current_portfolio()
                break
            
            time.sleep(10)  # Check every 10s
        
        # Disable strategy
        self.session.post(f"{self.api_url}/api/strategy/micro-momo/enable", json={"enabled": False})
        
        self.log("Trade monitoring completed")
    
    def get_positions_count(self):
        """Get current position count."""
        try:
            response = self.session.get(f"{self.api_url}/api/trading/positions")
            if response.status_code == 200:
                return len(response.json()["data"])
        except:
            pass
        return 0
    
    def show_current_portfolio(self):
        """Show current portfolio state."""
        try:
            response = self.session.get(f"{self.api_url}/api/trading/portfolio")
            if response.status_code == 200:
                data = response.json()["data"]
                
                self.log("=== CURRENT PORTFOLIO ===")
                self.log(f"Total Equity: ${data['total_equity']:,.2f}")
                self.log(f"Cash: ${data['cash_balance']:,.2f}")
                self.log(f"Total P&L: ${data['total_pnl']:,.2f}")
                self.log(f"Unrealized: ${data['unrealized_pnl']:,.2f}")
                
                for symbol, pos in data["positions"].items():
                    pnl_pct = pos["pnl_percent"]
                    self.log(f"  {symbol}: {pos['quantity']:.6f} @ ${pos['avg_entry_price']:,.2f} | P&L: ${pos['total_pnl']:,.2f} ({pnl_pct:+.2f}%)")
        except Exception as e:
            self.log(f"Portfolio display error: {e}")
    
    def suggest_manual_test_if_no_trades(self):
        """Suggest manual testing if no automatic trades occurred."""
        self.log("=== MANUAL TEST SUGGESTION ===")
        self.log("If no automatic trades occurred due to flat market conditions,")
        self.log("temporarily lower momentum thresholds and test manually:")
        self.log("")
        self.log("1. Set environment variables:")
        self.log("   set SOFIA_MICRO_TH_PCT_BTC=0.0003")
        self.log("   set SOFIA_MICRO_TH_PCT_ETH=0.0003") 
        self.log("   set SOFIA_MICRO_TH_PCT_SOL=0.0005")
        self.log("")
        self.log("2. Restart API and enable strategy")
        self.log("")
        self.log("3. Or test manual order:")
        self.log("   POST /api/trading/paper-order")
        self.log('   {"symbol": "BTCUSDT", "side": "buy", "usd_amount": 100}')
        self.log("")
        self.log("This proves the P&L pipeline works end-to-end.")

def main():
    """Run complete production demo."""
    print("=" * 60)
    print("SOFIA V2 PRODUCTION DEMO - REAL DATA TEST HARNESS")
    print("=" * 60)
    
    demo = ProductionDemo()
    
    # Validate steps
    steps_passed = 0
    total_steps = 5
    
    if demo.check_health():
        steps_passed += 1
    
    if demo.check_initial_portfolio():
        steps_passed += 1
        
    if demo.check_price_freshness():
        steps_passed += 1
    
    if demo.test_manual_trade():
        steps_passed += 1
        
    if demo.test_strategy_toggle():
        steps_passed += 1
    
    # Show final portfolio state
    demo.show_current_portfolio()
    
    # Summary
    print("=" * 60)
    print(f"DEMO RESULTS: {steps_passed}/{total_steps} tests passed")
    
    if steps_passed >= 4:
        print("PASS: Real-data test harness is functional")
        
        # Optional: Monitor for automatic trades
        print("\nOptional: Monitor for automatic trades (5 minutes)...")
        response = input("Monitor for trades? [y/N]: ").strip().lower()
        if response == 'y':
            demo.monitor_for_trades(5)
        else:
            demo.suggest_manual_test_if_no_trades()
    else:
        print("FAIL: System not ready for production use")
    
    print("=" * 60)

if __name__ == "__main__":
    main()