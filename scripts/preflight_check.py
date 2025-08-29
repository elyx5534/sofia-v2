"""
Preflight Check Script - Run before deployment
"""

import os
import sys
import time
import json
import asyncio
import logging
from typing import Dict, Any, List, Tuple
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.trading.live_adapter import LiveAdapter
from src.risk.engine import RiskEngine
from src.risk.kill_switch import KillSwitch
from src.observability.monitoring import observability

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PreflightChecker:
    """Preflight checks before deployment"""
    
    def __init__(self):
        self.checks_passed = []
        self.checks_failed = []
        self.warnings = []
        
    async def check_environment(self) -> Tuple[bool, str]:
        """Check environment variables"""
        required_vars = [
            'MODE', 'EXCHANGE', 'API_KEY', 'API_SECRET',
            'MAX_DAILY_LOSS', 'MAX_POSITION_USD', 'KILL_SWITCH'
        ]
        
        missing = []
        for var in required_vars:
            if not os.getenv(var):
                missing.append(var)
        
        if missing:
            return False, f"Missing environment variables: {', '.join(missing)}"
        
        mode = os.getenv('MODE')
        if mode == 'live':
            self.warnings.append("MODE=live - Ensure this is intentional!")
        
        return True, "All required environment variables present"
    
    async def check_exchange_connection(self) -> Tuple[bool, str]:
        """Check exchange connectivity"""
        try:
            adapter = LiveAdapter()
            await adapter.initialize()
            
            # Test API connectivity
            markets = adapter.exchange.markets
            if not markets:
                return False, "No markets loaded from exchange"
            
            await adapter.close()
            return True, f"Exchange connected: {len(markets)} markets available"
            
        except Exception as e:
            return False, f"Exchange connection failed: {e}"
    
    async def check_risk_engine(self) -> Tuple[bool, str]:
        """Check risk engine configuration"""
        try:
            engine = RiskEngine()
            
            # Validate configuration
            if engine.max_daily_loss <= 0:
                return False, "Invalid MAX_DAILY_LOSS configuration"
            
            if engine.max_position_usd <= 0:
                return False, "Invalid MAX_POSITION_USD configuration"
            
            # Test pre-trade check
            from decimal import Decimal
            check = await engine.pre_trade_check(
                symbol="BTC/USDT",
                side="buy",
                order_type="limit",
                quantity=Decimal("0.001"),
                price=Decimal("50000")
            )
            
            if check.action.value not in ["ALLOW", "BLOCK", "WARN"]:
                return False, "Risk engine check returned invalid action"
            
            return True, f"Risk engine configured: max_loss=${engine.max_daily_loss}"
            
        except Exception as e:
            return False, f"Risk engine check failed: {e}"
    
    async def check_kill_switch(self) -> Tuple[bool, str]:
        """Check kill switch state"""
        try:
            engine = RiskEngine()
            switch = KillSwitch(engine)
            
            state = switch.get_state()
            
            if state == "ON":
                self.warnings.append("Kill switch is ON - Trading disabled!")
            
            return True, f"Kill switch state: {state}"
            
        except Exception as e:
            return False, f"Kill switch check failed: {e}"
    
    async def check_database(self) -> Tuple[bool, str]:
        """Check database connectivity"""
        try:
            from sqlalchemy import create_engine
            from src.models.backtest import Base
            
            db_url = os.getenv('DATABASE_URL', 'sqlite:///./trading.db')
            engine = create_engine(db_url)
            
            # Test connection
            with engine.connect() as conn:
                result = conn.execute("SELECT 1")
                result.fetchone()
            
            return True, f"Database connected: {db_url}"
            
        except Exception as e:
            return False, f"Database check failed: {e}"
    
    async def check_observability(self) -> Tuple[bool, str]:
        """Check observability configuration"""
        try:
            status = observability.get_status()
            
            if not status['sentry_enabled'] and not status['prometheus_enabled']:
                self.warnings.append("No observability enabled (Sentry/Prometheus)")
            
            return True, f"Observability: Sentry={status['sentry_enabled']}, Prometheus={status['prometheus_enabled']}"
            
        except Exception as e:
            return False, f"Observability check failed: {e}"
    
    async def check_api_health(self) -> Tuple[bool, str]:
        """Check API health"""
        try:
            import aiohttp
            
            api_port = os.getenv('API_PORT', '8023')
            url = f"http://127.0.0.1:{api_port}/health"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        return True, f"API healthy: {data.get('status', 'unknown')}"
                    else:
                        return False, f"API unhealthy: status {response.status}"
                        
        except Exception as e:
            self.warnings.append(f"API not running: {e}")
            return True, "API check skipped (not running)"
    
    async def check_disk_space(self) -> Tuple[bool, str]:
        """Check available disk space"""
        try:
            import shutil
            
            total, used, free = shutil.disk_usage("/")
            free_gb = free / (1024 ** 3)
            
            if free_gb < 1:
                return False, f"Insufficient disk space: {free_gb:.2f}GB"
            elif free_gb < 5:
                self.warnings.append(f"Low disk space: {free_gb:.2f}GB")
            
            return True, f"Disk space available: {free_gb:.2f}GB"
            
        except Exception as e:
            return False, f"Disk space check failed: {e}"
    
    async def run_all_checks(self) -> Dict[str, Any]:
        """Run all preflight checks"""
        logger.info("Starting preflight checks...")
        
        checks = [
            ("Environment", self.check_environment),
            ("Exchange Connection", self.check_exchange_connection),
            ("Risk Engine", self.check_risk_engine),
            ("Kill Switch", self.check_kill_switch),
            ("Database", self.check_database),
            ("Observability", self.check_observability),
            ("API Health", self.check_api_health),
            ("Disk Space", self.check_disk_space),
        ]
        
        for name, check_func in checks:
            logger.info(f"Running check: {name}")
            passed, message = await check_func()
            
            if passed:
                self.checks_passed.append({
                    'name': name,
                    'message': message,
                    'timestamp': datetime.now().isoformat()
                })
                logger.info(f"[PASS] {name}: {message}")
            else:
                self.checks_failed.append({
                    'name': name,
                    'message': message,
                    'timestamp': datetime.now().isoformat()
                })
                logger.error(f"[FAIL] {name}: {message}")
        
        # Generate report
        report = {
            'timestamp': datetime.now().isoformat(),
            'passed': len(self.checks_passed),
            'failed': len(self.checks_failed),
            'warnings': len(self.warnings),
            'checks_passed': self.checks_passed,
            'checks_failed': self.checks_failed,
            'warnings': self.warnings,
            'ready_for_deployment': len(self.checks_failed) == 0
        }
        
        # Save report
        with open('preflight_report.json', 'w') as f:
            json.dump(report, f, indent=2)
        
        return report


async def main():
    """Main preflight check"""
    checker = PreflightChecker()
    report = await checker.run_all_checks()
    
    # Print summary
    print("\n" + "="*60)
    print("PREFLIGHT CHECK SUMMARY")
    print("="*60)
    print(f"Passed: {report['passed']}")
    print(f"Failed: {report['failed']}")
    print(f"Warnings: {report['warnings']}")
    
    if report['warnings']:
        print("\nWarnings:")
        for warning in checker.warnings:
            print(f"  - {warning}")
    
    if report['ready_for_deployment']:
        print("\n[SUCCESS] System ready for deployment!")
        return 0
    else:
        print("\n[FAILURE] System NOT ready for deployment!")
        print("\nFailed checks:")
        for check in report['checks_failed']:
            print(f"  - {check['name']}: {check['message']}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)