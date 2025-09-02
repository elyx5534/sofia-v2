"""FastAPI router for backtester endpoints."""

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from src.data_hub.models import AssetType

from .data_adapters.data_hub import DataHubAdapter
from .engine import BacktestEngine
from .metrics import calculate_metrics
from .strategies.sma import SMAStrategy

router = APIRouter()


@router.get("/backtest")
async def run_backtest(
    symbol: str = Query(..., description="Trading symbol"),
    asset_type: AssetType = Query(..., description="Asset type"),
    timeframe: str = Query("1d", description="Data timeframe"),
    start: Optional[datetime] = Query(None, description="Start date"),
    end: Optional[datetime] = Query(None, description="End date"),
    strategy: str = Query("sma", description="Strategy name"),
    params: str = Query("{}", description="Strategy parameters as JSON string"),
) -> Dict[str, Any]:
    """
    Run a backtest with specified parameters.

    Args:
        symbol: Trading symbol to test
        asset_type: Type of asset (crypto, stock, etc.)
        timeframe: Data timeframe (1m, 5m, 1h, 1d, etc.)
        start: Start date for backtest
        end: End date for backtest
        strategy: Strategy to use (currently only 'sma')
        params: Strategy parameters as JSON string

    Returns:
        Backtest results including metrics, equity curve, and trades
    """
    try:
        # Parse strategy parameters
        import json

        try:
            strategy_params = json.loads(params) if params else {}
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid strategy parameters JSON")

        # Initialize data adapter
        adapter = DataHubAdapter()

        # Fetch data
        try:
            data = adapter.fetch_ohlcv(
                symbol=symbol,
                asset_type=asset_type,
                timeframe=timeframe,
                start_date=start,
                end_date=end,
                limit=1000,
            )
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch data: {e!s}")

        if data.empty:
            raise HTTPException(status_code=404, detail=f"No data found for {symbol}")

        # Select strategy
        if strategy.lower() == "sma":
            strategy_instance = SMAStrategy()
        else:
            raise HTTPException(status_code=400, detail=f"Unknown strategy: {strategy}")

        # Run backtest
        engine = BacktestEngine(
            initial_capital=strategy_params.get("initial_capital", 10000.0),
            commission=strategy_params.get("commission", 0.001),
            slippage=strategy_params.get("slippage", 0.0),
        )

        results = engine.run(data, strategy_instance, **strategy_params)

        # Calculate metrics
        metrics = calculate_metrics(
            equity_curve=results["equity_curve"],
            trades=results["trades"],
            initial_capital=engine.initial_capital,
        )

        # Format trades for JSON serialization
        formatted_trades = []
        for trade in results["trades"]:
            formatted_trade = {
                "timestamp": (
                    trade["timestamp"].isoformat()
                    if hasattr(trade["timestamp"], "isoformat")
                    else str(trade["timestamp"])
                ),
                "type": trade["type"],
                "price": trade["price"],
                "quantity": trade["quantity"],
                "value": trade["value"],
                "commission": trade["commission"],
            }
            formatted_trades.append(formatted_trade)

        return {
            "metrics": metrics,
            "equity_curve": results["equity_curve"],
            "trades": formatted_trades,
            "summary": {
                "symbol": symbol,
                "asset_type": asset_type.value,
                "timeframe": timeframe,
                "strategy": strategy,
                "start_date": data.index[0].isoformat() if len(data) > 0 else None,
                "end_date": data.index[-1].isoformat() if len(data) > 0 else None,
                "data_points": len(data),
                "initial_capital": engine.initial_capital,
                "final_equity": results["final_equity"],
                "total_return": results["return"],
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backtest failed: {e!s}")
