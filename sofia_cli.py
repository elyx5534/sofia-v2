#!/usr/bin/env python
"""Sofia Trading Platform CLI - Modular command-line interface."""

import click
import asyncio
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.syntax import Syntax
from rich import print as rprint
import json
import pandas as pd
from datetime import datetime
from pathlib import Path
import yfinance as yf

# Import Sofia modules
from src.backtester.strategies.registry import StrategyRegistry
from src.backtester.engine import BacktestEngine
from src.optimizer.optimizer_queue import optimizer_queue, JobPriority
from src.ml.price_predictor import PricePredictor
from src.data_hub.providers.multi_source import MultiSourceDataProvider, DataSource

console = Console()


@click.group()
@click.version_option(version='2.0.0', prog_name='Sofia Trading Platform')
def cli():
    """Sofia Trading Platform - Professional Trading CLI"""
    pass


# ==================== Strategy Commands ====================

@cli.group()
def strategy():
    """Manage trading strategies"""
    pass


@strategy.command('list')
@click.option('--category', '-c', help='Filter by category')
def list_strategies(category):
    """List all available strategies"""
    registry = StrategyRegistry()
    strategies = registry.list_strategies(category)
    
    table = Table(title="Available Trading Strategies", show_header=True)
    table.add_column("Name", style="cyan")
    table.add_column("Display Name", style="green")
    table.add_column("Category", style="yellow")
    table.add_column("Risk Level", style="magenta")
    table.add_column("Parameters", style="blue")
    
    for s in strategies:
        params = f"{len(s.parameters)} params"
        table.add_row(
            s.name,
            s.display_name,
            s.category,
            s.risk_level,
            params
        )
    
    console.print(table)


@strategy.command('info')
@click.argument('name')
def strategy_info(name):
    """Show detailed information about a strategy"""
    registry = StrategyRegistry()
    metadata = registry.get_metadata(name)
    
    if not metadata:
        console.print(f"[red]Strategy '{name}' not found[/red]")
        return
    
    # Basic info panel
    info_text = f"""
[bold cyan]Name:[/bold cyan] {metadata.name}
[bold cyan]Display Name:[/bold cyan] {metadata.display_name}
[bold cyan]Description:[/bold cyan] {metadata.description}
[bold cyan]Category:[/bold cyan] {metadata.category}
[bold cyan]Author:[/bold cyan] {metadata.author}
[bold cyan]Version:[/bold cyan] {metadata.version}
[bold cyan]Risk Level:[/bold cyan] {metadata.risk_level}
[bold cyan]Timeframes:[/bold cyan] {', '.join(metadata.timeframes)}
[bold cyan]Tags:[/bold cyan] {', '.join(metadata.tags)}
    """
    console.print(Panel(info_text, title=f"Strategy: {metadata.display_name}"))
    
    # Parameters table
    if metadata.parameters:
        table = Table(title="Strategy Parameters", show_header=True)
        table.add_column("Parameter", style="cyan")
        table.add_column("Type", style="green")
        table.add_column("Default", style="yellow")
        table.add_column("Range", style="magenta")
        table.add_column("Description", style="white")
        
        for param in metadata.parameters:
            range_str = ""
            if param.min_value is not None and param.max_value is not None:
                range_str = f"{param.min_value} - {param.max_value}"
            
            table.add_row(
                param.display_name,
                param.type.value,
                str(param.default),
                range_str,
                param.description
            )
        
        console.print(table)


# ==================== Backtest Commands ====================

@cli.group()
def backtest():
    """Run and manage backtests"""
    pass


@backtest.command('run')
@click.option('--strategy', '-s', required=True, help='Strategy name')
@click.option('--symbol', '-sym', required=True, help='Trading symbol')
@click.option('--period', '-p', default='1y', help='Data period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y)')
@click.option('--initial-capital', '-c', default=100000, type=float, help='Initial capital')
@click.option('--params', '-pr', help='Strategy parameters as JSON')
def run_backtest(strategy, symbol, period, initial_capital, params):
    """Run a backtest for a strategy"""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Parse parameters
        strategy_params = {}
        if params:
            try:
                strategy_params = json.loads(params)
            except json.JSONDecodeError:
                console.print("[red]Invalid JSON parameters[/red]")
                return
        
        # Get strategy
        task = progress.add_task("Loading strategy...", total=None)
        registry = StrategyRegistry()
        strategy_class = registry.get_strategy(strategy)
        
        if not strategy_class:
            console.print(f"[red]Strategy '{strategy}' not found[/red]")
            return
        
        # Fetch data
        progress.update(task, description="Fetching market data...")
        ticker = yf.Ticker(symbol)
        data = ticker.history(period=period)
        
        if data.empty:
            console.print(f"[red]No data found for {symbol}[/red]")
            return
        
        # Run backtest
        progress.update(task, description="Running backtest...")
        strategy_instance = strategy_class(**strategy_params)
        engine = BacktestEngine(initial_capital=initial_capital)
        results = engine.run(data, strategy_instance)
        
        progress.stop()
    
    # Display results
    result_text = f"""
[bold green]Backtest Results[/bold green]
[bold]Symbol:[/bold] {symbol}
[bold]Strategy:[/bold] {strategy}
[bold]Period:[/bold] {period}
[bold]Data Points:[/bold] {len(data)}

[bold cyan]Performance Metrics:[/bold cyan]
• Initial Capital: ${initial_capital:,.2f}
• Final Value: ${results.get('final_value', 0):,.2f}
• Total Return: {results.get('total_return', 0):.2%}
• Sharpe Ratio: {results.get('sharpe', 0):.2f}
• Max Drawdown: {results.get('max_drawdown', 0):.2%}
• Win Rate: {results.get('win_rate', 0):.2%}
• Total Trades: {results.get('total_trades', 0)}
• Profit Factor: {results.get('profit_factor', 0):.2f}
    """
    console.print(Panel(result_text, title="Backtest Complete"))


# ==================== Optimization Commands ====================

@cli.group()
def optimize():
    """Strategy optimization with GA"""
    pass


@optimize.command('submit')
@click.option('--strategy', '-s', required=True, help='Strategy name')
@click.option('--symbol', '-sym', required=True, help='Trading symbol')
@click.option('--target', '-t', default='sharpe', type=click.Choice(['sharpe', 'return', 'calmar']))
@click.option('--generations', '-g', default=50, type=int, help='Number of generations')
@click.option('--population', '-p', default=30, type=int, help='Population size')
@click.option('--priority', default='normal', type=click.Choice(['low', 'normal', 'high', 'urgent']))
def submit_optimization(strategy, symbol, target, generations, population, priority):
    """Submit an optimization job"""
    
    # Get strategy metadata for parameter space
    registry = StrategyRegistry()
    metadata = registry.get_metadata(strategy)
    
    if not metadata:
        console.print(f"[red]Strategy '{strategy}' not found[/red]")
        return
    
    # Build parameter space from metadata
    param_space = {}
    for param in metadata.parameters:
        if param.min_value is not None and param.max_value is not None:
            param_space[param.name] = (param.min_value, param.max_value)
    
    if not param_space:
        console.print("[red]Strategy has no optimizable parameters[/red]")
        return
    
    # GA parameters
    ga_params = {
        'generations': generations,
        'population_size': population
    }
    
    # Map priority
    priority_map = {
        'low': JobPriority.LOW,
        'normal': JobPriority.NORMAL,
        'high': JobPriority.HIGH,
        'urgent': JobPriority.URGENT
    }
    
    # Submit job asynchronously
    async def submit():
        await optimizer_queue.start()
        job_id = await optimizer_queue.submit_job(
            strategy_name=strategy,
            symbol=symbol,
            param_space=param_space,
            optimization_target=target,
            ga_params=ga_params,
            priority=priority_map[priority]
        )
        return job_id
    
    with console.status("Submitting optimization job..."):
        job_id = asyncio.run(submit())
    
    console.print(f"[green]✓ Optimization job submitted[/green]")
    console.print(f"[cyan]Job ID:[/cyan] {job_id}")
    console.print(f"[cyan]Strategy:[/cyan] {strategy}")
    console.print(f"[cyan]Symbol:[/cyan] {symbol}")
    console.print(f"[cyan]Target:[/cyan] {target}")
    console.print(f"[cyan]Generations:[/cyan] {generations}")
    console.print(f"[cyan]Population:[/cyan] {population}")


@optimize.command('status')
@click.argument('job_id', required=False)
def optimization_status(job_id):
    """Check optimization job status"""
    if job_id:
        # Get specific job
        job = optimizer_queue.get_job(job_id)
        if not job:
            console.print(f"[red]Job '{job_id}' not found[/red]")
            return
        
        status_color = {
            'queued': 'yellow',
            'running': 'cyan',
            'completed': 'green',
            'failed': 'red',
            'cancelled': 'orange'
        }.get(job.status.value, 'white')
        
        info_text = f"""
[bold]Job ID:[/bold] {job.id}
[bold]Status:[/bold] [{status_color}]{job.status.value}[/{status_color}]
[bold]Strategy:[/bold] {job.strategy_name}
[bold]Symbol:[/bold] {job.symbol}
[bold]Target:[/bold] {job.optimization_target}
[bold]Progress:[/bold] {job.progress:.1f}%
[bold]Generation:[/bold] {job.current_generation}
[bold]Best Fitness:[/bold] {job.best_fitness:.4f}
[bold]Created:[/bold] {job.created_at}
        """
        
        if job.best_params:
            info_text += "\n[bold]Best Parameters:[/bold]"
            for k, v in job.best_params.items():
                info_text += f"\n  • {k}: {v}"
        
        console.print(Panel(info_text, title="Optimization Job Status"))
    else:
        # List all jobs
        jobs = optimizer_queue.list_jobs(limit=10)
        
        table = Table(title="Recent Optimization Jobs", show_header=True)
        table.add_column("Job ID", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Strategy", style="yellow")
        table.add_column("Symbol", style="magenta")
        table.add_column("Progress", style="blue")
        
        for job in jobs:
            status_color = {
                'queued': 'yellow',
                'running': 'cyan',
                'completed': 'green',
                'failed': 'red',
                'cancelled': 'orange'
            }.get(job.status.value, 'white')
            
            table.add_row(
                job.id[:8],
                f"[{status_color}]{job.status.value}[/{status_color}]",
                job.strategy_name,
                job.symbol,
                f"{job.progress:.1f}%"
            )
        
        console.print(table)


# ==================== ML Commands ====================

@cli.group()
def ml():
    """Machine Learning predictions"""
    pass


@ml.command('predict')
@click.option('--symbol', '-s', required=True, help='Trading symbol')
@click.option('--model', '-m', default='classification', type=click.Choice(['classification', 'regression']))
@click.option('--algorithm', '-a', default='xgboost', type=click.Choice(['xgboost', 'random_forest']))
@click.option('--horizon', '-h', default=1, type=int, help='Prediction horizon (periods ahead)')
def ml_predict(symbol, model, algorithm, horizon):
    """Predict price movement with ML"""
    with console.status("Training model and making predictions..."):
        # Fetch data
        ticker = yf.Ticker(symbol)
        data = ticker.history(period="3mo")
        
        if data.empty:
            console.print(f"[red]No data found for {symbol}[/red]")
            return
        
        # Train model
        predictor = PricePredictor(model_type=model, algorithm=algorithm)
        train_data = data.iloc[:-20]
        metrics = predictor.train(train_data, prediction_horizon=horizon)
        
        # Make predictions
        recent_data = data.iloc[-20:]
        predictions = predictor.predict(recent_data, return_confidence=True)
    
    # Display results
    console.print(Panel(f"[bold green]ML Predictions for {symbol}[/bold green]", expand=False))
    
    # Model metrics
    if model == 'classification':
        console.print(f"[cyan]Model Accuracy:[/cyan] {metrics.get('test_accuracy', 0):.2%}")
        console.print(f"[cyan]Precision:[/cyan] {metrics.get('precision', 0):.2%}")
        console.print(f"[cyan]Recall:[/cyan] {metrics.get('recall', 0):.2%}")
    else:
        console.print(f"[cyan]R² Score:[/cyan] {metrics.get('test_r2', 0):.2f}")
        console.print(f"[cyan]MAE:[/cyan] {metrics.get('test_mae', 0):.2f}")
    
    # Latest predictions
    console.print("\n[bold]Recent Predictions:[/bold]")
    
    table = Table(show_header=True)
    table.add_column("Date", style="cyan")
    
    if model == 'classification':
        table.add_column("Direction", style="green")
        table.add_column("Confidence", style="yellow")
        
        for idx, row in predictions.tail(5).iterrows():
            direction_color = "green" if row['direction'] == 'UP' else "red"
            table.add_row(
                str(idx.date()),
                f"[{direction_color}]{row['direction']}[/{direction_color}]",
                f"{row['confidence']:.2%}"
            )
    else:
        table.add_column("Predicted Price", style="green")
        table.add_column("Expected Return", style="yellow")
        
        for idx, row in predictions.tail(5).iterrows():
            return_color = "green" if row['predicted_return'] > 0 else "red"
            table.add_row(
                str(idx.date()),
                f"${row['predicted_price']:.2f}",
                f"[{return_color}]{row['predicted_return']:.2%}[/{return_color}]"
            )
    
    console.print(table)
    
    # Top features
    if predictor.feature_importance is not None:
        console.print("\n[bold]Top Features:[/bold]")
        for feature, importance in predictor.get_top_features(5).items():
            console.print(f"  • {feature}: {importance:.3f}")


# ==================== Data Commands ====================

@cli.group()
def data():
    """Data source management"""
    pass


@data.command('sources')
def list_data_sources():
    """Check status of all data sources"""
    provider = MultiSourceDataProvider()
    status = provider.get_source_status()
    
    table = Table(title="Data Source Status", show_header=True)
    table.add_column("Source", style="cyan")
    table.add_column("Status", style="green")
    
    for source, is_connected in status.items():
        status_text = "[green]✓ Connected[/green]" if is_connected else "[red]✗ Disconnected[/red]"
        table.add_row(source, status_text)
    
    console.print(table)


@data.command('fetch')
@click.option('--symbol', '-s', required=True, help='Trading symbol')
@click.option('--timeframe', '-t', default='1d', help='Timeframe (1m, 5m, 1h, 1d, etc.)')
@click.option('--limit', '-l', default=100, type=int, help='Number of candles')
@click.option('--source', help='Specific data source to use')
def fetch_data(symbol, timeframe, limit, source):
    """Fetch market data with fallback"""
    provider = MultiSourceDataProvider()
    
    sources = None
    if source:
        try:
            sources = [DataSource(source)]
        except ValueError:
            console.print(f"[red]Invalid source: {source}[/red]")
            return
    
    with console.status(f"Fetching {symbol} data..."):
        data = provider.fetch_ohlcv(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            sources=sources
        )
    
    if data is None or data.empty:
        console.print("[red]Failed to fetch data from all sources[/red]")
        return
    
    # Display data info
    info_text = f"""
[bold]Symbol:[/bold] {symbol}
[bold]Timeframe:[/bold] {timeframe}
[bold]Data Points:[/bold] {len(data)}
[bold]Start:[/bold] {data.index[0]}
[bold]End:[/bold] {data.index[-1]}
    """
    console.print(Panel(info_text, title="Data Fetched Successfully"))
    
    # Show recent data
    table = Table(title="Recent Data", show_header=True)
    table.add_column("Date", style="cyan")
    table.add_column("Open", style="green")
    table.add_column("High", style="yellow")
    table.add_column("Low", style="red")
    table.add_column("Close", style="blue")
    table.add_column("Volume", style="magenta")
    
    for idx, row in data.tail(5).iterrows():
        table.add_row(
            str(idx),
            f"{row['open']:.2f}",
            f"{row['high']:.2f}",
            f"{row['low']:.2f}",
            f"{row['close']:.2f}",
            f"{row['volume']:.0f}"
        )
    
    console.print(table)


# ==================== Main Server Command ====================

@cli.command('server')
@click.option('--port', '-p', default=8080, help='Port to run on')
@click.option('--host', '-h', default='0.0.0.0', help='Host to bind to')
def run_server(port, host):
    """Start the API server"""
    console.print(f"[green]Starting Sofia API Server on {host}:{port}[/green]")
    
    import uvicorn
    from src.api.main import app
    
    uvicorn.run(app, host=host, port=port)


# ==================== Main Entry Point ====================

if __name__ == '__main__':
    cli()