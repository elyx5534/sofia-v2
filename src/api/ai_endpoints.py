"""
AI Score Endpoints
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import random
import time
from datetime import datetime

router = APIRouter(prefix="/ai", tags=["ai"])

class ScoreRequest(BaseModel):
    symbol: str
    horizon: str = "15m"

class ScoreResponse(BaseModel):
    score0_100: float
    prob_up: float
    features_used: list
    ts: str
    symbol: str
    horizon: str

# Cache for scores
score_cache = {}
CACHE_TTL = 5  # seconds

@router.post("/score", response_model=ScoreResponse)
async def get_ai_score(request: ScoreRequest):
    """Get AI score for a symbol"""
    cache_key = f"{request.symbol}_{request.horizon}"
    current_time = time.time()
    
    # Check cache
    if cache_key in score_cache:
        cached_score, cached_time = score_cache[cache_key]
        if current_time - cached_time < CACHE_TTL:
            return cached_score
    
    # Generate score (mock for now, replace with real model)
    score = random.uniform(30, 90)
    prob_up = score / 100.0
    
    response = ScoreResponse(
        score0_100=round(score, 2),
        prob_up=round(prob_up, 3),
        features_used=["r_1m", "r_5m", "r_1h", "zscore_20", "ATR%", "momentum"],
        ts=datetime.now().isoformat(),
        symbol=request.symbol,
        horizon=request.horizon
    )
    
    # Cache the response
    score_cache[cache_key] = (response, current_time)
    
    return response

@router.get("/features/{symbol}")
async def get_features(symbol: str):
    """Get feature values for a symbol"""
    return {
        "symbol": symbol,
        "features": {
            "r_1m": round(random.uniform(-0.02, 0.02), 4),
            "r_5m": round(random.uniform(-0.05, 0.05), 4),
            "r_1h": round(random.uniform(-0.10, 0.10), 4),
            "zscore_20": round(random.uniform(-2, 2), 2),
            "ATR%": round(random.uniform(1, 5), 2),
            "momentum": round(random.uniform(-50, 50), 2),
            "vol_sigma_1h": round(random.uniform(0.5, 3), 2),
            "obv_30": round(random.uniform(-100, 100), 2),
            "sent_score": round(random.uniform(-1, 1), 2),
            "whale_notional_5m": round(random.uniform(0, 500000), 2)
        },
        "timestamp": datetime.now().isoformat()
    }