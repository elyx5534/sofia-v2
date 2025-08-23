"""
Automated Test Suite for Sofia V2 Trading Platform
Run with: python test_integration.py
"""

import asyncio
import json
import time
import sys
from typing import Dict, List, Tuple
import aiohttp
import requests
import websocket
from colorama import init, Fore, Style

# Initialize colorama for colored output
init()

class SofiaV2Tester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results = []
        self.total_tests = 0
        self.passed_tests = 0
        
    def print_header(self):
        """Print test header"""
        print("\n" + "="*60)
        print(f"{Fore.CYAN}🧪 Sofia V2 Integration Test Suite{Style.RESET_ALL}")
        print("="*60 + "\n")
        
    def print_result(self, test_name: str, passed: bool, details: str = ""):
        """Print colored test result"""
        self.total_tests += 1
        if passed:
            self.passed_tests += 1
            print(f"{Fore.GREEN}✅ PASS{Style.RESET_ALL} - {test_name}")
            if details:
                print(f"   {Fore.WHITE}→ {details}{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}❌ FAIL{Style.RESET_ALL} - {test_name}")
            if details:
                print(f"   {Fore.YELLOW}→ {details}{Style.RESET_ALL}")
                
    def test_server_running(self) -> bool:
        """Test if server is running"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=2)
            self.print_result("Server Running", True, f"Server is up at {self.base_url}")
            return True
        except:
            self.print_result("Server Running", False, "Server is not responding")
            return False
            
    def test_health_endpoint(self) -> bool:
        """Test /health endpoint"""
        try:
            response = requests.get(f"{self.base_url}/health")
            data = response.json()
            passed = response.status_code == 200 and data.get("status") == "ok"
            self.print_result(
                "Health Endpoint", 
                passed, 
                f"Status: {data.get('status')}, Version: {data.get('version', 'N/A')}"
            )
            return passed
        except Exception as e:
            self.print_result("Health Endpoint", False, str(e))
            return False
            
    def test_status_endpoint(self) -> bool:
        """Test /status endpoint"""
        try:
            response = requests.get(f"{self.base_url}/status")
            data = response.json()
            passed = response.status_code == 200 and data.get("status") == "operational"
            self.print_result(
                "Status Endpoint", 
                passed, 
                f"Services: {', '.join(data.get('services', {}).keys())}"
            )
            return passed
        except Exception as e:
            self.print_result("Status Endpoint", False, str(e))
            return False
            
    def test_data_endpoint(self) -> bool:
        """Test /data endpoint with valid symbol"""
        try:
            response = requests.get(f"{self.base_url}/data?symbol=BTC-USD")
            data = response.json()
            
            if response.status_code == 200 and "last_price" in data:
                provider = data.get("provider", "Unknown")
                price = data.get("last_price", 0)
                self.print_result(
                    "Data Endpoint (BTC-USD)", 
                    True, 
                    f"Price: ${price:,.2f} via {provider}"
                )
                return True
            else:
                self.print_result("Data Endpoint (BTC-USD)", False, "Invalid response format")
                return False
        except Exception as e:
            self.print_result("Data Endpoint (BTC-USD)", False, str(e))
            return False
            
    def test_fallback_system(self) -> bool:
        """Test fallback with invalid symbol"""
        try:
            response = requests.get(f"{self.base_url}/data?symbol=INVALID-XYZ")
            data = response.json()
            
            # Should either return error or try multiple providers
            if "providers_tried" in data:
                providers = data.get("providers_tried", [])
                self.print_result(
                    "Fallback System", 
                    True, 
                    f"Tried {len(providers)} providers: {', '.join(providers)}"
                )
                return True
            else:
                self.print_result("Fallback System", False, "No fallback information")
                return False
        except Exception as e:
            self.print_result("Fallback System", False, str(e))
            return False
            
    def test_portfolio_endpoint(self) -> bool:
        """Test /portfolio endpoint"""
        try:
            response = requests.get(f"{self.base_url}/portfolio")
            data = response.json()
            
            if response.status_code == 200 and "portfolio" in data:
                symbols = list(data["portfolio"].keys())
                total = data.get("summary", {}).get("total_value", 0)
                self.print_result(
                    "Portfolio Endpoint", 
                    True, 
                    f"Tracking {len(symbols)} assets, Total: ${total:,.2f}"
                )
                return True
            else:
                self.print_result("Portfolio Endpoint", False, "Invalid response")
                return False
        except Exception as e:
            self.print_result("Portfolio Endpoint", False, str(e))
            return False
            
    def test_strategy_endpoint(self) -> bool:
        """Test /strategy endpoint"""
        try:
            response = requests.get(f"{self.base_url}/strategy?symbol=ETH-USD")
            data = response.json()
            
            if response.status_code == 200 and "signal" in data:
                signal = data.get("signal", "unknown")
                indicators = data.get("indicators", {})
                rsi = indicators.get("rsi", 0)
                self.print_result(
                    "Strategy Endpoint", 
                    True, 
                    f"Signal: {signal.upper()}, RSI: {rsi:.1f}"
                )
                return True
            else:
                self.print_result("Strategy Endpoint", False, "Invalid response")
                return False
        except Exception as e:
            self.print_result("Strategy Endpoint", False, str(e))
            return False
            
    def test_websocket(self) -> bool:
        """Test WebSocket connection"""
        try:
            ws_url = self.base_url.replace("http", "ws") + "/ws"
            ws = websocket.create_connection(ws_url, timeout=5)
            
            # Receive connection message
            result = ws.recv()
            data = json.loads(result)
            
            if data.get("type") == "connected":
                self.print_result("WebSocket Connection", True, "Connected successfully")
                ws.close()
                return True
            else:
                self.print_result("WebSocket Connection", False, "Unexpected response")
                ws.close()
                return False
        except Exception as e:
            self.print_result("WebSocket Connection", False, str(e))
            return False
            
    def test_dashboard(self) -> bool:
        """Test dashboard loads"""
        try:
            response = requests.get(self.base_url)
            passed = response.status_code == 200 and "Sofia V2" in response.text
            self.print_result(
                "Dashboard Page", 
                passed, 
                "Dashboard HTML loaded" if passed else "Dashboard not loading"
            )
            return passed
        except Exception as e:
            self.print_result("Dashboard Page", False, str(e))
            return False
            
    def run_all_tests(self):
        """Run all tests"""
        self.print_header()
        
        # Check if server is running first
        if not self.test_server_running():
            print(f"\n{Fore.RED}⚠️  Server is not running!{Style.RESET_ALL}")
            print(f"Please start the server with: {Fore.CYAN}uvicorn main:app --reload{Style.RESET_ALL}\n")
            return
            
        # Run all tests
        print(f"\n{Fore.CYAN}Running API Tests...{Style.RESET_ALL}\n")
        self.test_health_endpoint()
        self.test_status_endpoint()
        self.test_data_endpoint()
        self.test_fallback_system()
        self.test_portfolio_endpoint()
        self.test_strategy_endpoint()
        
        print(f"\n{Fore.CYAN}Running WebSocket Tests...{Style.RESET_ALL}\n")
        self.test_websocket()
        
        print(f"\n{Fore.CYAN}Running UI Tests...{Style.RESET_ALL}\n")
        self.test_dashboard()
        
        # Print summary
        self.print_summary()
        
    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*60)
        print(f"{Fore.CYAN}📊 Test Summary{Style.RESET_ALL}")
        print("="*60)
        
        success_rate = (self.passed_tests / self.total_tests * 100) if self.total_tests > 0 else 0
        
        if success_rate == 100:
            status_color = Fore.GREEN
            status_emoji = "🎉"
        elif success_rate >= 80:
            status_color = Fore.YELLOW
            status_emoji = "⚠️"
        else:
            status_color = Fore.RED
            status_emoji = "❌"
            
        print(f"\nTotal Tests: {self.total_tests}")
        print(f"Passed: {Fore.GREEN}{self.passed_tests}{Style.RESET_ALL}")
        print(f"Failed: {Fore.RED}{self.total_tests - self.passed_tests}{Style.RESET_ALL}")
        print(f"\n{status_emoji} Success Rate: {status_color}{success_rate:.1f}%{Style.RESET_ALL}")
        
        if success_rate == 100:
            print(f"\n{Fore.GREEN}✨ All tests passed! Sofia V2 is fully operational!{Style.RESET_ALL}")
        elif success_rate >= 80:
            print(f"\n{Fore.YELLOW}⚠️  Most tests passed, but some issues need attention.{Style.RESET_ALL}")
        else:
            print(f"\n{Fore.RED}❌ Multiple tests failed. Please check the logs above.{Style.RESET_ALL}")
        
        print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    tester = SofiaV2Tester()
    tester.run_all_tests()