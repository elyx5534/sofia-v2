"""
Local AI endpoints - hooks for future integration
Currently returns stubs for UI development
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai", tags=["ai"])

class ExplainRequest(BaseModel):
    signal_id: Optional[str] = None
    trade_id: Optional[str] = None
    market_data: Optional[Dict[str, Any]] = None
    context: Optional[str] = None

class AnalyzeRequest(BaseModel):
    symbol: str
    timeframe: str = "1h"
    indicators: Optional[list] = None

class PredictRequest(BaseModel):
    symbol: str
    horizon: str = "24h"
    features: Optional[Dict[str, Any]] = None

@router.post("/explain")
async def explain_signal(request: ExplainRequest):
    """
    Explain trading signal using local AI
    Future: Will use Ollama/llama.cpp for local inference
    """
    return {
        "ok": True,
        "status": "disabled",
        "note": "Local AI integration coming soon",
        "message": "This feature will explain trading signals using a locally-run LLM",
        "requirements": {
            "model": "llama2-7b or mistral-7b",
            "vram": "6GB minimum",
            "backend": "Ollama or llama.cpp"
        },
        "timestamp": datetime.utcnow().isoformat()
    }

@router.post("/analyze")
async def analyze_market(request: AnalyzeRequest):
    """
    Analyze market conditions using local AI
    Future: Technical analysis with local model
    """
    return {
        "ok": True,
        "status": "disabled",
        "symbol": request.symbol,
        "timeframe": request.timeframe,
        "note": "Local market analysis coming soon",
        "placeholder_analysis": {
            "trend": "neutral",
            "strength": 0.5,
            "signals": [],
            "confidence": 0.0
        },
        "timestamp": datetime.utcnow().isoformat()
    }

@router.post("/predict")
async def predict_price(request: PredictRequest):
    """
    Predict price movements using local AI
    Future: Time series prediction with local model
    """
    return {
        "ok": True,
        "status": "disabled",
        "symbol": request.symbol,
        "horizon": request.horizon,
        "note": "Local price prediction coming soon",
        "placeholder_prediction": {
            "direction": "sideways",
            "target_price": None,
            "confidence": 0.0,
            "risk_level": "medium"
        },
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/status")
async def get_ai_status():
    """
    Check local AI service status
    """
    return {
        "enabled": False,
        "backend": None,
        "model": None,
        "status": "Not configured",
        "message": "Local AI will be available in future release",
        "setup_guide": "/docs/ai-local.md",
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/models")
async def list_available_models():
    """
    List available local AI models
    """
    return {
        "installed": [],
        "recommended": [
            {
                "name": "llama2-7b",
                "size": "3.8GB",
                "vram": "6GB",
                "use_case": "General analysis and explanations"
            },
            {
                "name": "mistral-7b",
                "size": "4.1GB",
                "vram": "6GB",
                "use_case": "Technical analysis and trading signals"
            },
            {
                "name": "phi-2",
                "size": "1.7GB",
                "vram": "3GB",
                "use_case": "Lightweight analysis for low-resource systems"
            }
        ],
        "note": "Models will be downloadable through settings page",
        "timestamp": datetime.utcnow().isoformat()
    }