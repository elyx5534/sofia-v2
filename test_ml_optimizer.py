#!/usr/bin/env python3
"""
Test Machine Learning Optimizer
"""

import asyncio

import numpy as np
import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from src.ai.optimizer import (
    MLOptimizer,
)

console = Console()


async def test_ml_optimizer():
    """Test the ML optimizer system"""

    # Configuration
    config = {
        "strategies": ["grid_trading", "arbitrage", "momentum", "mean_reversion"],
        "optimization_interval": 3600,
        "min_data_points": 100,
        "daily_schedule": True,
    }

    # Initialize optimizer
    optimizer = MLOptimizer(config)
    await optimizer.initialize()

    console.print("[green]ML Optimizer initialized[/green]")
    console.print("=" * 60)

    # Test 1: Performance Tracking
    console.print("\n[cyan]Test 1: Performance Tracking[/cyan]")

    # Simulate strategy metrics
    for strategy in config["strategies"]:
        for i in range(10):
            metrics = {
                "total_trades": np.random.randint(10, 50),
                "win_rate": np.random.uniform(0.4, 0.7),
                "profit_factor": np.random.uniform(0.8, 1.5),
                "sharpe_ratio": np.random.uniform(0.5, 2.0),
                "max_drawdown": np.random.uniform(0.05, 0.2),
                "avg_profit": np.random.uniform(50, 200),
                "avg_loss": np.random.uniform(30, 150),
                "total_pnl": np.random.uniform(-500, 1500),
                "volatility": np.random.uniform(0.01, 0.03),
                "volume": np.random.uniform(1e6, 1e8),
                "trend_strength": np.random.uniform(0.2, 0.8),
                "direction": np.random.choice([-1, 1]),
                "parameters": {"stop_loss": 0.01, "take_profit": 0.02, "position_size": 0.05},
            }
            optimizer.tracker.record_metrics(strategy, metrics)

    # Display tracked metrics
    metrics_table = Table(title="Strategy Performance Metrics")
    metrics_table.add_column("Strategy", style="cyan")
    metrics_table.add_column("Trades", style="yellow")
    metrics_table.add_column("Win Rate", style="green")
    metrics_table.add_column("Profit Factor", style="blue")
    metrics_table.add_column("Sharpe", style="magenta")
    metrics_table.add_column("Total PnL", style="white")

    for strategy in config["strategies"]:
        strategy_metrics = [
            m for m in optimizer.tracker.metrics_history if m.strategy_name == strategy
        ]
        if strategy_metrics:
            latest = strategy_metrics[-1]
            pnl_color = "green" if latest.total_pnl > 0 else "red"
            metrics_table.add_row(
                strategy,
                str(latest.total_trades),
                f"{latest.win_rate:.2%}",
                f"{latest.profit_factor:.2f}",
                f"{latest.sharpe_ratio:.2f}",
                f"[{pnl_color}]{latest.total_pnl:.2f}[/{pnl_color}]",
            )

    console.print(metrics_table)

    # Test 2: Market Condition Analysis
    console.print("\n[cyan]Test 2: Market Condition Analysis[/cyan]")

    conditions_table = Table(title="Market Conditions")
    conditions_table.add_column("Time", style="cyan")
    conditions_table.add_column("Condition", style="yellow")
    conditions_table.add_column("Volatility", style="green")
    conditions_table.add_column("Session", style="blue")
    conditions_table.add_column("Risk Level", style="magenta")

    for condition in optimizer.tracker.market_conditions[-5:]:
        risk_color = {"low": "green", "medium": "yellow", "high": "red"}[condition.risk_level]
        conditions_table.add_row(
            condition.timestamp.strftime("%H:%M"),
            condition.condition,
            f"{condition.volatility:.3f}",
            condition.dominant_session,
            f"[{risk_color}]{condition.risk_level.upper()}[/{risk_color}]",
        )

    console.print(conditions_table)

    # Test 3: Best Conditions Analysis
    console.print("\n[cyan]Test 3: Best Performing Conditions[/cyan]")

    for strategy in config["strategies"][:2]:  # Show first 2
        best_conditions = optimizer.tracker.get_best_conditions(strategy)

        if best_conditions:
            best_table = Table(title=f"{strategy} - Best Conditions")
            best_table.add_column("Condition", style="cyan")
            best_table.add_column("Avg PF", style="yellow")
            best_table.add_column("Win Rate", style="green")
            best_table.add_column("Samples", style="blue")

            for condition, stats in best_conditions.items():
                best_table.add_row(
                    condition,
                    f"{stats['avg_profit_factor']:.2f}",
                    f"{stats['win_rate']:.2%}",
                    str(stats["sample_size"]),
                )

            console.print(best_table)

    # Test 4: Generate sample data and train models
    console.print("\n[cyan]Test 4: Training ML Models[/cyan]")

    # Generate sample market data
    dates = pd.date_range(start="2024-01-01", periods=1000, freq="h")
    market_data = pd.DataFrame(
        {
            "timestamp": dates,
            "open": np.random.randn(1000).cumsum() + 100,
            "high": np.random.randn(1000).cumsum() + 101,
            "low": np.random.randn(1000).cumsum() + 99,
            "close": np.random.randn(1000).cumsum() + 100,
            "volume": np.random.uniform(1e6, 1e7, 1000),
        }
    )

    # Generate sample signals
    signals = pd.Series(np.random.choice([0, 1, 2], size=1000))  # 0=hold, 1=buy, 2=sell

    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console
    ) as progress:
        task = progress.add_task("[yellow]Training ML models...", total=None)

        await optimizer.train_models(market_data, signals)

        progress.update(task, completed=True)

    console.print("[green]ML models trained successfully[/green]")

    # Test 5: Get Predictions
    console.print("\n[cyan]Test 5: Market Predictions[/cyan]")

    predictions = await optimizer.get_predictions(market_data.tail(100))

    if predictions:
        pred_table = Table(title="ML Predictions")
        pred_table.add_column("Model", style="cyan")
        pred_table.add_column("Prediction", style="yellow")
        pred_table.add_column("Confidence", style="green")
        pred_table.add_column("Type", style="blue")

        for name, pred in predictions.items():
            if pred:
                pred_table.add_row(
                    pred.model_type,
                    str(pred.prediction),
                    f"{pred.confidence:.2%}" if pred.confidence > 0 else "N/A",
                    name,
                )

        console.print(pred_table)

    # Test 6: Parameter Optimization
    console.print("\n[cyan]Test 6: Parameter Optimization[/cyan]")

    # Define parameter bounds
    param_bounds = {
        "stop_loss": (0.005, 0.02),
        "take_profit": (0.01, 0.05),
        "position_size": (0.01, 0.1),
    }

    # Define fitness function
    def fitness_function(params):
        # Simulate strategy performance with given params
        return np.random.random() * params.get("position_size", 0.05) * 100

    # Run genetic algorithm optimization
    result = optimizer.optimizer.genetic_algorithm_optimize(
        "grid_trading", param_bounds, fitness_function, population_size=20, generations=10
    )

    opt_table = Table(title="Optimization Result")
    opt_table.add_column("Parameter", style="cyan")
    opt_table.add_column("Old Value", style="yellow")
    opt_table.add_column("New Value", style="green")

    for param in param_bounds.keys():
        old_val = result.old_params.get(param, "N/A")
        new_val = result.new_params.get(param, 0)
        opt_table.add_row(param, str(old_val) if old_val != "N/A" else "N/A", f"{new_val:.4f}")

    console.print(opt_table)
    console.print(f"Expected improvement: [green]{result.expected_improvement:.2f}[/green]")

    # Test 7: Capital Allocation
    console.print("\n[cyan]Test 7: RL-based Capital Allocation[/cyan]")

    # Simulate performance history
    performance_history = {
        strategy: [np.random.uniform(0.8, 1.5) for _ in range(20)]
        for strategy in config["strategies"]
    }

    allocation = optimizer.optimizer.reinforcement_learning_allocate(
        config["strategies"],
        performance_history,
        100000,  # $100K total capital
    )

    alloc_table = Table(title="Capital Allocation")
    alloc_table.add_column("Strategy", style="cyan")
    alloc_table.add_column("Allocation", style="yellow")
    alloc_table.add_column("Percentage", style="green")

    total = sum(allocation.values())
    for strategy, amount in allocation.items():
        alloc_table.add_row(strategy, f"${amount:,.2f}", f"{(amount/total)*100:.1f}%")

    console.print(alloc_table)

    # Test 8: Daily Schedule
    console.print("\n[cyan]Test 8: Daily Optimization Schedule[/cyan]")

    schedule_table = Table(title="Daily Routine")
    schedule_table.add_column("Time", style="cyan")
    schedule_table.add_column("Task", style="yellow")
    schedule_table.add_column("Description", style="green")

    schedule_table.add_row("00:00", "Analyze Yesterday", "Review performance, identify patterns")
    schedule_table.add_row("06:00", "Optimize Parameters", "Run GA/Bayesian optimization")
    schedule_table.add_row("12:00", "Rebalance Allocation", "Adjust capital distribution")
    schedule_table.add_row("18:00", "US Session Prep", "Adjust for volatility")

    console.print(schedule_table)

    # Test 9: Auto-Adjustment
    console.print("\n[cyan]Test 9: Auto-Adjustment Based on Performance[/cyan]")

    # Simulate poor performance
    poor_metrics = {
        "total_trades": 20,
        "win_rate": 0.3,
        "profit_factor": 0.8,
        "sharpe_ratio": -0.5,
        "total_pnl": -500,
        "volatility": 0.03,
        "volume": 1e6,
        "trend_strength": 0.8,
    }

    optimizer.tracker.record_metrics("momentum", poor_metrics)

    # Run auto-adjustment
    await optimizer.auto_adjust()

    console.print("[yellow]Auto-adjustment applied for underperforming strategies[/yellow]")

    # Test 10: Optimization Report
    console.print("\n[cyan]Test 10: Optimization Report[/cyan]")

    report = optimizer.get_optimization_report()

    summary = Panel(
        f"""[green]ML Optimizer Summary[/green]

Total Optimizations: {report['total_optimizations']}
Strategies Optimized: {len(report['best_parameters'])}

Performance Trends:
{chr(10).join([f"  {s}: {d['trend']}" for s, d in report['performance_summary'].items()])}

Recent Improvements:
{chr(10).join([f"  {opt['strategy']}: +{opt['improvement']:.2f}" for opt in report['recent_optimizations'][:3]])}

[yellow]Key Features:[/yellow]
• XGBoost price prediction
• LSTM volatility forecasting
• Random Forest signal generation
• Genetic algorithm optimization
• Reinforcement learning allocation
• Bayesian threshold tuning
• Automated daily routines""",
        title="ML Optimizer Report",
        border_style="green",
    )

    console.print(summary)

    # Cleanup
    await optimizer.shutdown()
    console.print("\n[green]ML Optimizer test completed![/green]")


async def main():
    """Main entry point"""
    console.print("[bold cyan]Machine Learning Optimizer Test[/bold cyan]")
    console.print("[yellow]Performance tracking, prediction, and optimization[/yellow]")
    console.print("=" * 60)

    try:
        await test_ml_optimizer()
    except KeyboardInterrupt:
        console.print("\n[yellow]Test interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Test failed: {e}[/red]")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
