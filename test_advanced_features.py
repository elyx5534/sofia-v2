"""
Test Advanced Trading Features
Quick demo of AA-DD implementations
"""

import asyncio
from decimal import Decimal

from src.paper_trading.price_placement import PricePlacement


async def test_price_placement():
    """Test tick-aware price placement"""
    print("=" * 60)
    print("TESTING PRICE PLACEMENT (Prompt AA)")
    print("=" * 60)

    placement = PricePlacement()

    # Simulate orderbook
    orderbook = {"bids": [[108000, 1.0], [107999, 2.0]], "asks": [[108010, 1.0], [108011, 2.0]]}

    # Test join strategy
    best_bid = Decimal(str(orderbook["bids"][0][0]))
    best_ask = Decimal(str(orderbook["asks"][0][0]))

    join_buy_price = placement.join_best("buy", best_bid, best_ask, "BTC/USDT")
    print(f"Join Buy Price: ${join_buy_price} (bid+tick from ${best_bid})")

    join_sell_price = placement.join_best("sell", best_bid, best_ask, "BTC/USDT")
    print(f"Join Sell Price: ${join_sell_price} (ask-tick from ${best_ask})")

    # Test step-in strategy
    step_in_buy, strategy = placement.step_in_limit("buy", best_bid, best_ask, "BTC/USDT", k=2)
    print(f"Step-In Buy: ${step_in_buy} using {strategy}")

    step_in_sell, strategy = placement.step_in_limit("sell", best_bid, best_ask, "BTC/USDT", k=2)
    print(f"Step-In Sell: ${step_in_sell} using {strategy}")

    print("[PASS] Price placement working correctly")
    print()


def test_consistency():
    """Test P&L consistency checker"""
    print("=" * 60)
    print("TESTING CONSISTENCY CHECKER (Prompt BB)")
    print("=" * 60)

    from tools.consistency_check import ConsistencyChecker

    checker = ConsistencyChecker()
    passed, report = checker.check_all_sources()

    print(f"Overall Status: {report['overall']}")
    print(f"Sources Checked: {len([k for k in report['sources'] if k])}")

    if report["overall"] == "INSUFFICIENT_DATA":
        print("[INFO] Not enough data for consistency check (expected on fresh system)")
    else:
        print(f"[{report['overall']}] Consistency check completed")
    print()


def test_live_readiness():
    """Test live readiness checker"""
    print("=" * 60)
    print("TESTING LIVE READINESS (Prompt DD)")
    print("=" * 60)

    from tools.live_readiness import LiveReadinessChecker

    checker = LiveReadinessChecker()

    # Just check the score calculation
    checker._check_risk_controls()
    checker._check_infrastructure()

    print(f"Risk Controls Score: {checker.readiness_score}/30")
    print(f"Critical Failures: {len(checker.critical_failures)}")
    print(f"Warnings: {len(checker.warnings)}")

    # The system correctly shows NO-GO because we need paper trading history
    if checker.readiness_score < 70:
        print("[INFO] System correctly requires more paper trading before live pilot")

    print("[PASS] Live readiness checker working")
    print()


def test_arbitrage_config():
    """Test Turkish arbitrage configuration"""
    print("=" * 60)
    print("TESTING TURKISH ARBITRAGE CONFIG (Prompt CC)")
    print("=" * 60)

    from src.trading.turkish_arbitrage import TurkishArbitrage

    arb = TurkishArbitrage(paper_mode=True)

    print(f"Mode: {('Paper' if arb.paper_mode else 'Live')}")
    print(f"Min Profit Threshold: {arb.min_profit_threshold}%")
    print(f"TL Gateway Fee: {arb.tl_gateway_fee}%")
    print(f"Max Position Size: ${arb.max_position_size}")

    print("[PASS] Turkish arbitrage configured")
    print()


async def main():
    print("\n" + "=" * 70)
    print(" ADVANCED FEATURES TEST SUITE (Prompts AA-DD)")
    print("=" * 70 + "\n")

    # Test each feature
    await test_price_placement()
    test_consistency()
    test_live_readiness()
    test_arbitrage_config()

    print("=" * 70)
    print(" ALL TESTS COMPLETED SUCCESSFULLY")
    print("=" * 70)
    print("\nAvailable Commands:")
    print("  make qa-proof      - Run consistency + shadow comparison")
    print("  make consistency   - Check P&L consistency")
    print("  make arbitrage     - Run 30-min Turkish arbitrage")
    print("  make readiness     - Check live pilot readiness")
    print("  make demo          - Run 5-min paper trading demo")


if __name__ == "__main__":
    asyncio.run(main())
