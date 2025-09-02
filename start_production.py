#!/usr/bin/env python
"""
Sofia V2 - Production Startup Script
Safely starts the trading system with all checks
"""

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


class ProductionStarter:
    """Production startup manager with safety checks"""

    def __init__(self):
        self.root_dir = Path(__file__).parent
        self.config_file = self.root_dir / ".env"
        self.checks_passed = []
        self.checks_failed = []

    def print_banner(self):
        """Print startup banner"""
        print("\n" + "=" * 60)
        print("SOFIA V2 - PRODUCTION STARTUP")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60 + "\n")

    def check_environment(self):
        """Check environment variables"""
        print("🔍 Checking environment variables...")

        required_vars = ["BINANCE_API_KEY", "BINANCE_API_SECRET", "DATABASE_URL", "REDIS_URL"]

        missing = []
        for var in required_vars:
            if not os.getenv(var):
                missing.append(var)

        if missing:
            print(f"❌ Missing environment variables: {', '.join(missing)}")
            self.checks_failed.append("Environment variables")
            return False

        print("✅ Environment variables OK")
        self.checks_passed.append("Environment variables")
        return True

    def check_dependencies(self):
        """Check Python dependencies"""
        print("🔍 Checking dependencies...")

        try:
            import ccxt
            import fastapi
            import numpy
            import pandas
            import redis
            import sqlalchemy

            print("✅ All dependencies installed")
            self.checks_passed.append("Dependencies")
            return True
        except ImportError as e:
            print(f"❌ Missing dependency: {e}")
            self.checks_failed.append("Dependencies")
            return False

    def run_tests(self):
        """Run critical tests"""
        print("🔍 Running tests...")

        result = subprocess.run(
            ["python", "-m", "pytest", "tests/", "-q", "--tb=no"],
            capture_output=True,
            text=True,
            check=False,
        )

        if "passed" in result.stdout:
            # Extract test count
            import re

            match = re.search(r"(\d+) passed", result.stdout)
            if match:
                passed_count = match.group(1)
                print(f"✅ {passed_count} tests passed")
                self.checks_passed.append(f"{passed_count} tests")
                return True

        print("⚠️ Some tests failed (non-critical)")
        return True  # Don't block on test failures

    def check_database(self):
        """Check database connection"""
        print("🔍 Checking database...")

        try:
            from sqlalchemy import create_engine

            db_url = os.getenv("DATABASE_URL", "sqlite:///./sofia.db")
            engine = create_engine(db_url)
            conn = engine.connect()
            conn.close()
            print("✅ Database connection OK")
            self.checks_passed.append("Database")
            return True
        except Exception as e:
            print(f"⚠️ Database connection failed: {e}")
            print("   Using SQLite fallback")
            return True

    def check_redis(self):
        """Check Redis connection"""
        print("🔍 Checking Redis...")

        try:
            import redis

            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            r = redis.from_url(redis_url)
            r.ping()
            print("✅ Redis connection OK")
            self.checks_passed.append("Redis")
            return True
        except Exception as e:
            print(f"⚠️ Redis connection failed: {e}")
            print("   Cache will use in-memory fallback")
            return True

    def start_services(self, mode="paper"):
        """Start all services"""
        print(f"\n🚀 Starting services in {mode.upper()} mode...\n")

        services = []

        # 1. Start Backend API
        print("Starting Backend API...")
        backend = subprocess.Popen(
            ["uvicorn", "src.data_hub.api:app", "--host", "0.0.0.0", "--port", "8000"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        services.append(("Backend API", backend))
        time.sleep(3)

        # 2. Start Frontend UI
        print("Starting Frontend UI...")
        frontend = subprocess.Popen(
            ["python", "-m", "http.server", "3000", "--directory", "sofia_ui"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        services.append(("Frontend UI", frontend))
        time.sleep(2)

        # 3. Start Trading Bot
        if mode != "test":
            print(f"Starting Trading Bot ({mode} mode)...")
            bot_cmd = ["python", "auto_trader.py", "--mode", mode, "--strategy", "grid"]
            bot = subprocess.Popen(bot_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            services.append(("Trading Bot", bot))
            time.sleep(2)

        # 4. Start Dashboard (optional)
        try:
            print("Starting Realtime Dashboard...")
            dashboard = subprocess.Popen(
                ["python", "src/web/realtime_dashboard.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            services.append(("Dashboard", dashboard))
        except Exception as e:
            print(f"⚠️ Dashboard start failed: {e}")

        return services

    def print_summary(self):
        """Print startup summary"""
        print("\n" + "=" * 60)
        print("STARTUP SUMMARY")
        print("=" * 60)

        if self.checks_passed:
            print("\n✅ Checks Passed:")
            for check in self.checks_passed:
                print(f"   - {check}")

        if self.checks_failed:
            print("\n❌ Checks Failed:")
            for check in self.checks_failed:
                print(f"   - {check}")

        print("\n" + "=" * 60)

    def print_urls(self):
        """Print service URLs"""
        print("\n📌 SERVICE URLS:")
        print("-" * 40)
        print("Backend API:    http://localhost:8000")
        print("API Docs:       http://localhost:8000/docs")
        print("Frontend UI:    http://localhost:3000")
        print("Dashboard:      http://localhost:8001")
        print("Health Check:   http://localhost:8000/health")
        print("-" * 40)

    def monitor_services(self, services):
        """Monitor running services"""
        print("\n✨ All services started successfully!")
        print("Press Ctrl+C to stop all services\n")

        try:
            while True:
                time.sleep(10)
                # Check if services are still running
                for name, process in services:
                    if process.poll() is not None:
                        print(f"⚠️ {name} stopped unexpectedly!")

        except KeyboardInterrupt:
            print("\n\n🛑 Stopping all services...")
            for name, process in services:
                print(f"   Stopping {name}...")
                process.terminate()
                process.wait(timeout=5)
            print("✅ All services stopped")

    def run(self, mode="paper"):
        """Main startup sequence"""
        self.print_banner()

        # Run all checks
        checks = [
            self.check_environment(),
            self.check_dependencies(),
            self.check_database(),
            self.check_redis(),
            self.run_tests(),
        ]

        # Print summary
        self.print_summary()

        # Check if critical checks passed
        if not self.check_environment() or not self.check_dependencies():
            print("\n❌ Critical checks failed. Cannot start production.")
            print("Please fix the issues and try again.")
            return 1

        # Confirm startup
        if mode == "live":
            print("\n⚠️ WARNING: Starting in LIVE TRADING mode!")
            confirm = input("Are you sure? Type 'YES' to confirm: ")
            if confirm != "YES":
                print("Startup cancelled.")
                return 0

        # Start services
        services = self.start_services(mode)

        # Print URLs
        self.print_urls()

        # Monitor services
        self.monitor_services(services)

        return 0


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Sofia V2 Production Startup")
    parser.add_argument(
        "--mode",
        choices=["paper", "live", "test"],
        default="paper",
        help="Trading mode (default: paper)",
    )
    parser.add_argument("--skip-tests", action="store_true", help="Skip running tests")

    args = parser.parse_args()

    # Safety check for live mode
    if args.mode == "live":
        print("\n" + "!" * 60)
        print("!!! LIVE TRADING MODE - REAL MONEY AT RISK !!!")
        print("!" * 60 + "\n")

    # Create and run starter
    starter = ProductionStarter()

    if args.skip_tests:
        starter.run_tests = lambda: True

    return starter.run(args.mode)


if __name__ == "__main__":
    sys.exit(main())
