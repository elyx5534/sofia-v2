#!/usr/bin/env python3
"""
Sofia V2 - Global Crypto Scanner CLI
Command-line interface for managing the crypto scanner system
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

import uvicorn
from loguru import logger

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.data.pipeline import data_pipeline
from src.news.aggregator import news_aggregator
from src.scan.scanner import scanner
from src.scheduler.run import crypto_scheduler


def setup_logging(verbose: bool = False):
    """Setup logging configuration"""
    level = "DEBUG" if verbose else "INFO"
    logger.remove()
    logger.add(
        sys.stdout,
        level=level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )


def cmd_fetch_all(args):
    """Fetch OHLCV data for all USDT pairs"""
    print("🔄 Fetching OHLCV data from exchanges...")

    timeframes = args.timeframes.split(",") if args.timeframes else ["1h", "1d"]

    try:
        results = data_pipeline.fetch_universe_data(
            timeframes=timeframes, days_back=args.days, max_workers=args.max_workers
        )

        print("✅ Data fetch completed:")
        print(f"   📊 Symbols processed: {results['symbols_processed']}")
        print(f"   ❌ Symbols failed: {results['symbols_failed']}")
        print(f"   📈 Total records: {results['total_records']}")

        return True

    except Exception as e:
        print(f"❌ Data fetch failed: {e}")
        return False


def cmd_update_data(args):
    """Update recent OHLCV data"""
    print(f"🔄 Updating recent data (last {args.hours} hours)...")

    try:
        results = data_pipeline.update_recent_data(hours_back=args.hours)

        print("✅ Data update completed:")
        print(f"   📊 Symbols processed: {results['symbols_processed']}")
        print(f"   ❌ Symbols failed: {results['symbols_failed']}")

        return True

    except Exception as e:
        print(f"❌ Data update failed: {e}")
        return False


def cmd_scan(args):
    """Run signal scanner"""
    print("🔍 Scanning for trading signals...")

    try:
        results = scanner.run_scan(timeframe=args.timeframe, save_results=True)

        signal_count = len([r for r in results if r.get("score", 0) > 0])
        top_score = max([r.get("score", 0) for r in results]) if results else 0
        top_symbols = [r["symbol"] for r in results[:5] if r.get("score", 0) > 0]

        print("✅ Signal scan completed:")
        print(f"   📊 Total symbols: {len(results)}")
        print(f"   🚨 Symbols with signals: {signal_count}")
        print(f"   🎯 Top score: {top_score:.2f}")

        if top_symbols:
            print(f"   🏆 Top signals: {', '.join(top_symbols)}")

        return True

    except Exception as e:
        print(f"❌ Signal scan failed: {e}")
        return False


async def cmd_news_async(args):
    """Update news from all sources"""
    print("📰 Updating news from CryptoPanic and GDELT...")

    try:
        # Get top symbols for symbol-specific news
        available_symbols = data_pipeline.get_available_symbols()
        top_symbols = available_symbols[: args.symbol_limit]

        await news_aggregator.update_all_news(symbols=top_symbols, hours_back=args.hours)

        print("✅ News update completed:")
        print("   📰 Global news updated")
        print(f"   🔸 Symbol-specific news: {len(top_symbols)} symbols")

        return True

    except Exception as e:
        print(f"❌ News update failed: {e}")
        return False


def cmd_news(args):
    """Update news (wrapper for async function)"""
    return asyncio.run(cmd_news_async(args))


def cmd_web(args):
    """Start web server"""
    print("🌐 Starting web server...")
    print(f"   📍 URL: http://{args.host}:{args.port}")
    print(f"   🔄 Auto-reload: {args.reload}")

    try:
        uvicorn.run(
            "src.web.app:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_level="info" if not args.verbose else "debug",
        )

    except KeyboardInterrupt:
        print("\n⏹️  Web server stopped")
        return True
    except Exception as e:
        print(f"❌ Web server failed: {e}")
        return False


def cmd_scheduler(args):
    """Start/stop scheduler"""
    if args.action == "start":
        print("⏰ Starting crypto scheduler...")

        try:
            crypto_scheduler.start()
            print("✅ Scheduler started successfully")

            # Keep running
            try:
                while True:
                    import time

                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n⏹️  Stopping scheduler...")
                crypto_scheduler.stop()
                print("✅ Scheduler stopped")

        except Exception as e:
            print(f"❌ Scheduler failed: {e}")
            return False

    elif args.action == "status":
        status = crypto_scheduler.get_job_status()
        print("📊 Scheduler Status:")
        print(f"   🔄 Running: {status['scheduler_running']}")
        print(f"   📋 Total jobs: {status['total_jobs']}")

        for job_name, job_status in status["jobs"].items():
            last_run = job_status["last_run"]
            last_status = job_status["last_status"]

            status_emoji = (
                "✅" if last_status == "success" else "❌" if last_status == "error" else "⏸️"
            )
            print(f"   {status_emoji} {job_name}: {last_status} ({last_run or 'Never'})")

    elif args.action == "run":
        if not args.job:
            print("❌ Job name required for 'run' action")
            return False

        print(f"▶️  Running job: {args.job}")
        result = crypto_scheduler.run_job_now(args.job)

        if result.get("status") == "success":
            print("✅ Job completed successfully")
        else:
            print(f"❌ Job failed: {result.get('error', 'Unknown error')}")

    return True


def cmd_status(args):
    """Show system status"""
    print("📊 Sofia V2 System Status")
    print("=" * 50)

    try:
        # Data status
        available_symbols = data_pipeline.get_available_symbols()
        print("📈 Data:")
        print(f"   Available symbols: {len(available_symbols)}")

        # Signals status
        outputs_dir = Path("./outputs")
        signals_file = outputs_dir / "signals.json"

        if signals_file.exists():
            signals_age = (
                datetime.now() - datetime.fromtimestamp(signals_file.stat().st_mtime)
            ).total_seconds()

            with open(signals_file) as f:
                signals = json.load(f)

            signal_count = len([s for s in signals if s.get("score", 0) > 0])

            print("🚨 Signals:")
            print(f"   Active signals: {signal_count}")
            print(f"   Last updated: {signals_age / 60:.1f} minutes ago")
        else:
            print("🚨 Signals: No signals file found")

        # News status
        news_file = outputs_dir / "news" / "global.json"

        if news_file.exists():
            news_age = (
                datetime.now() - datetime.fromtimestamp(news_file.stat().st_mtime)
            ).total_seconds()

            with open(news_file) as f:
                news_data = json.load(f)

            news_count = news_data.get("total_articles", 0)

            print("📰 News:")
            print(f"   Total articles: {news_count}")
            print(f"   Last updated: {news_age / 60:.1f} minutes ago")
        else:
            print("📰 News: No news data found")

        # Scheduler status
        scheduler_status = crypto_scheduler.get_job_status()
        print("⏰ Scheduler:")
        print(f"   Running: {scheduler_status['scheduler_running']}")
        print(f"   Active jobs: {scheduler_status['total_jobs']}")

        return True

    except Exception as e:
        print(f"❌ Status check failed: {e}")
        return False


def cmd_list_symbols(args):
    """List available symbols"""
    try:
        symbols = data_pipeline.get_available_symbols()

        print(f"📊 Available Symbols ({len(symbols)}):")

        if args.limit:
            symbols = symbols[: args.limit]

        for i, symbol in enumerate(symbols, 1):
            print(f"   {i:3d}. {symbol}")

        if args.limit and len(data_pipeline.get_available_symbols()) > args.limit:
            remaining = len(data_pipeline.get_available_symbols()) - args.limit
            print(f"   ... and {remaining} more")

        return True

    except Exception as e:
        print(f"❌ Failed to list symbols: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Sofia V2 - Global Crypto Scanner CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch all data for last 30 days
  python sofia_cli.py fetch-all --days 30

  # Update recent data and scan for signals
  python sofia_cli.py update && python sofia_cli.py scan

  # Update news
  python sofia_cli.py news

  # Start web server
  python sofia_cli.py web

  # Start scheduler
  python sofia_cli.py scheduler start

  # Show system status
  python sofia_cli.py status
        """,
    )

    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # fetch-all command
    fetch_parser = subparsers.add_parser("fetch-all", help="Fetch OHLCV data for all symbols")
    fetch_parser.add_argument(
        "--days", type=int, default=365, help="Days of data to fetch (default: 365)"
    )
    fetch_parser.add_argument(
        "--timeframes", default="1h,1d", help="Timeframes to fetch (default: 1h,1d)"
    )
    fetch_parser.add_argument(
        "--max-workers", type=int, default=5, help="Max worker threads (default: 5)"
    )

    # update command
    update_parser = subparsers.add_parser("update", help="Update recent OHLCV data")
    update_parser.add_argument(
        "--hours", type=int, default=24, help="Hours back to update (default: 24)"
    )

    # scan command
    scan_parser = subparsers.add_parser("scan", help="Run signal scanner")
    scan_parser.add_argument(
        "--timeframe",
        default="1h",
        choices=["1h", "1d"],
        help="Timeframe for scanning (default: 1h)",
    )

    # news command
    news_parser = subparsers.add_parser("news", help="Update news from all sources")
    news_parser.add_argument(
        "--hours", type=int, default=24, help="Hours back to fetch news (default: 24)"
    )
    news_parser.add_argument(
        "--symbol-limit", type=int, default=10, help="Max symbols for specific news (default: 10)"
    )

    # web command
    web_parser = subparsers.add_parser("web", help="Start web server")
    web_parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    web_parser.add_argument("--port", type=int, default=8000, help="Port to bind (default: 8000)")
    web_parser.add_argument("--reload", action="store_true", help="Enable auto-reload")

    # scheduler command
    scheduler_parser = subparsers.add_parser("scheduler", help="Manage scheduler")
    scheduler_parser.add_argument(
        "action", choices=["start", "status", "run"], help="Scheduler action"
    )
    scheduler_parser.add_argument("--job", help="Job name for 'run' action")

    # status command
    subparsers.add_parser("status", help="Show system status")

    # list-symbols command
    symbols_parser = subparsers.add_parser("list-symbols", help="List available symbols")
    symbols_parser.add_argument("--limit", type=int, help="Limit number of symbols shown")

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)

    if not args.command:
        parser.print_help()
        return 1

    # Command dispatch
    commands = {
        "fetch-all": cmd_fetch_all,
        "update": cmd_update_data,
        "scan": cmd_scan,
        "news": cmd_news,
        "web": cmd_web,
        "scheduler": cmd_scheduler,
        "status": cmd_status,
        "list-symbols": cmd_list_symbols,
    }

    command_func = commands.get(args.command)
    if not command_func:
        print(f"❌ Unknown command: {args.command}")
        return 1

    try:
        success = command_func(args)
        return 0 if success else 1

    except KeyboardInterrupt:
        print("\n⏹️  Operation cancelled by user")
        return 1
    except Exception as e:
        logger.error(f"Command failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
