"""
ML Prediction API endpoints
"""

from fastapi import APIRouter, Query, HTTPException, Response
from typing import Dict, Any
import pandas as pd
import logging

from src.ml.predictor import predictor, get_ml_enabled, set_ml_enabled
from src.services.market_data import market_data_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ml", tags=["ml"])


@router.get("/predict", response_model=Dict[str, Any])
async def predict_direction(
    symbol: str = Query(..., description="Symbol to predict (e.g., BTC/USDT)"),
    timeframe: str = Query(default="1h", description="Timeframe for data"),
    response: Response = Response()
) -> Dict[str, Any]:
    """
    Get ML prediction for symbol direction
    
    Returns direction (up/down) and probability
    """
    # Check if ML is enabled
    if not get_ml_enabled():
        response.headers["X-Feature-Flag"] = "off"
        raise HTTPException(
            status_code=503,
            detail="ML Predictor is disabled. Enable it in Settings.",
            headers={"X-Feature-Flag": "off"}
        )
    
    try:
        # Fetch OHLCV data
        data = await market_data_service.get_ohlcv(symbol, timeframe, 200)
        
        if not data.get('bars'):
            raise HTTPException(status_code=404, detail="No data available for symbol")
        
        # Convert to DataFrame
        bars = data['bars']
        df_data = {
            'open': [float(bar['open']) for bar in bars],
            'high': [float(bar['high']) for bar in bars],
            'low': [float(bar['low']) for bar in bars],
            'close': [float(bar['close']) for bar in bars],
            'volume': [float(bar['volume']) for bar in bars]
        }
        
        ohlcv = pd.DataFrame(df_data)
        ohlcv.index = pd.DatetimeIndex([bar['timestamp'] for bar in bars])
        
        # Get prediction
        result = predictor.train_predict(ohlcv, symbol)
        
        response.headers["X-Feature-Flag"] = "on"
        response.headers["X-ML-Model"] = result.get('model', 'unknown')
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", response_model=Dict[str, Any])
async def get_ml_status() -> Dict[str, Any]:
    """
    Get ML predictor status
    """
    return predictor.get_status()


@router.patch("/enabled")
async def set_ml_enabled_flag(enabled: bool = Query(..., description="Enable or disable ML predictor")) -> Dict[str, str]:
    """
    Enable or disable ML predictor
    """
    new_state = set_ml_enabled(enabled)
    return {
        "message": f"ML Predictor {'enabled' if new_state else 'disabled'}",
        "enabled": str(new_state)
    }