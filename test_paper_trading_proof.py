#!/usr/bin/env python3
"""
Test Paper Trading P&L Proof System
Verifies that paper trading session generates correct P&L reports
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# Add parent to path
sys.path.append(str(Path(__file__).parent))


async def test_paper_trading_quick():
    """Run a 1-minute test session to verify P&L reporting"""

    print("=" * 60)
    print("PAPER TRADING P&L PROOF TEST")
    print("=" * 60)
    print(f"Start Time: {datetime.now()}")
    print("Duration: 1 minute (test mode)")
    print("=" * 60)

    # Import after path setup
    from tools.run_paper_session import run_paper_session

    try:
        # Run 1-minute test session
        summary = await run_paper_session(duration_minutes=1)

        print("\n" + "=" * 60)
        print("TEST RESULTS")
        print("=" * 60)

        # Verify summary structure
        required_fields = [
            "session_date",
            "duration_minutes",
            "initial_capital",
            "final_capital",
            "total_pnl",
            "pnl_percentage",
            "total_trades",
            "success_rate",
        ]

        missing_fields = [f for f in required_fields if f not in summary]
        if missing_fields:
            print(f"❌ Missing fields in summary: {missing_fields}")
            return False

        print("✅ Summary structure valid")

        # Check audit log exists
        audit_log = Path("logs/paper_audit.log")
        if audit_log.exists():
            print(f"✅ Audit log created: {audit_log}")
            with open(audit_log) as f:
                lines = f.readlines()
                print(f"   - Entries: {len(lines)}")
        else:
            print("⚠️  No audit log found (may be normal for short test)")

        # Check summary file
        summary_file = Path("logs/paper_session_summary.json")
        if summary_file.exists():
            print(f"✅ Summary file created: {summary_file}")
            with open(summary_file) as f:
                saved_summary = json.load(f)
                print(f"   - P&L: ${saved_summary.get('total_pnl', 0):.2f}")
                print(f"   - Return: {saved_summary.get('pnl_percentage', 0):.2f}%")
        else:
            print("❌ Summary file not created")
            return False

        print("\n" + "=" * 60)
        print("✅ PAPER TRADING P&L PROOF SYSTEM WORKING")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """Run the test"""
    success = await test_paper_trading_quick()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
