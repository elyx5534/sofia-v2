#!/usr/bin/env python3
"""
Strategy Optimization Script
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.optimization.runner import StrategyOptimizer

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    parser = argparse.ArgumentParser(description="Run strategy optimization")
    parser.add_argument(
        "--method",
        choices=["bayesian", "genetic", "both"],
        default="bayesian",
        help="Optimization method",
    )
    parser.add_argument(
        "--trials", type=int, default=100, help="Number of trials for Bayesian optimization"
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=["BTC/USDT", "ETH/USDT", "AAPL", "MSFT"],
        help="Symbols to optimize",
    )
    parser.add_argument("--strategies", nargs="+", help="Strategies to optimize (default: all)")

    args = parser.parse_args()

    optimizer = StrategyOptimizer()

    # Override symbols if provided
    if args.symbols:
        optimizer.symbols = args.symbols

    # Override strategies if provided
    if args.strategies:
        filtered_configs = {
            k: v for k, v in optimizer.strategy_configs.items() if k in args.strategies
        }
        optimizer.strategy_configs = filtered_configs

    logger.info("=" * 60)
    logger.info("STRATEGY OPTIMIZATION STARTING")
    logger.info("=" * 60)
    logger.info(f"Method: {args.method}")
    logger.info(f"Symbols: {optimizer.symbols}")
    logger.info(f"Strategies: {list(optimizer.strategy_configs.keys())}")
    logger.info(f"Trials (Bayesian): {args.trials}")

    start_time = datetime.now()

    try:
        if args.method == "bayesian":
            results = await optimizer.run_optimization("bayesian", n_trials=args.trials)
        elif args.method == "genetic":
            results = await optimizer.run_optimization("genetic")
        elif args.method == "both":
            logger.info("Running Bayesian optimization first...")
            bayesian_results = await optimizer.run_optimization("bayesian", n_trials=args.trials)

            logger.info("Running Genetic Algorithm optimization...")
            ga_results = await optimizer.run_optimization("genetic")

            # Combine results (take best from each method)
            results = {}
            for symbol in optimizer.symbols:
                results[symbol] = []

                # Get results from both methods
                b_results = {r.strategy_name: r for r in bayesian_results.get(symbol, [])}
                g_results = {r.strategy_name: r for r in ga_results.get(symbol, [])}

                # Take best result for each strategy
                all_strategies = set(b_results.keys()) | set(g_results.keys())
                for strategy in all_strategies:
                    b_result = b_results.get(strategy)
                    g_result = g_results.get(strategy)

                    if b_result and g_result:
                        # Compare by OOS Sharpe ratio
                        if b_result.oos_metrics.get("sharpe", 0) > g_result.oos_metrics.get(
                            "sharpe", 0
                        ):
                            results[symbol].append(b_result)
                        else:
                            results[symbol].append(g_result)
                    elif b_result:
                        results[symbol].append(b_result)
                    elif g_result:
                        results[symbol].append(g_result)

        elapsed = (datetime.now() - start_time).total_seconds()

        logger.info("=" * 60)
        logger.info("OPTIMIZATION COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Total time: {elapsed:.1f} seconds")

        # Print summary
        print("\n" + "=" * 80)
        print("OPTIMIZATION SUMMARY")
        print("=" * 80)

        for symbol, symbol_results in results.items():
            if not symbol_results:
                continue

            print(f"\n{symbol}:")
            print("-" * 40)

            # Sort by OOS Sharpe
            sorted_results = sorted(
                symbol_results, key=lambda x: x.oos_metrics.get("sharpe", 0), reverse=True
            )

            for i, result in enumerate(sorted_results[:3]):  # Top 3
                profitable = "✅" if result.profitable else "❌"
                print(
                    f"{i+1:2d}. {result.strategy_name:20s} | "
                    f"Sharpe: {result.oos_metrics.get('sharpe', 0):6.2f} | "
                    f"MAR: {result.oos_metrics.get('mar', 0):6.2f} | "
                    f"MaxDD: {result.oos_metrics.get('max_drawdown', 0):6.1f}% | "
                    f"Trades: {result.total_trades:3d} | {profitable}"
                )

        # Find best overall performers
        all_results = []
        for symbol_results in results.values():
            all_results.extend(symbol_results)

        if all_results:
            print("\n" + "=" * 80)
            print("TOP PERFORMERS OVERALL")
            print("=" * 80)

            top_overall = sorted(
                all_results, key=lambda x: x.oos_metrics.get("sharpe", 0), reverse=True
            )[:5]

            for i, result in enumerate(top_overall):
                profitable = "✅" if result.profitable else "❌"
                print(
                    f"{i+1}. {result.strategy_name} ({result.symbol}) | "
                    f"Sharpe: {result.oos_metrics.get('sharpe', 0):.2f} | "
                    f"MAR: {result.oos_metrics.get('mar', 0):.2f} | {profitable}"
                )

        print("\nReports saved to: reports/optimizer/")
        print("View optimization_report.html for detailed analysis")

    except KeyboardInterrupt:
        logger.info("Optimization interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Optimization failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
