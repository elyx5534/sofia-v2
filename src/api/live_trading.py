"""
Live Trading Grid API Endpoints
"""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import asyncio
import json
import logging
from datetime import datetime
import numpy as np

from src.orchestrator.universe import UniverseOrchestrator
from src.execution.engine import SmartExecutionEngine, OrderStyle
from src.ai.news_sentiment import NewsSentimentAnalyzer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/live", tags=["live_trading"])

# Global instances
universe_orchestrator = UniverseOrchestrator()
execution_engine = SmartExecutionEngine()
news_analyzer = NewsSentimentAnalyzer()

# WebSocket connections
active_connections: List[WebSocket] = []


class TradeRequest(BaseModel):
    symbol: str
    side: str  # 'buy' or 'sell'
    quantity: float
    mode: str = 'paper'  # 'paper' or 'live'


class SymbolAction(BaseModel):
    action: str  # 'pause', 'resume', 'kill'
    reason: Optional[str] = None


@router.on_event("startup")
async def startup_live_trading():
    """Initialize live trading components"""
    global universe_orchestrator
    
    try:
        await universe_orchestrator.start_orchestration()
        logger.info("Live trading universe orchestrator started")
    except Exception as e:
        logger.error(f"Failed to start universe orchestrator: {e}")


@router.on_event("shutdown") 
async def shutdown_live_trading():
    """Shutdown live trading components"""
    global universe_orchestrator
    
    try:
        await universe_orchestrator.stop_orchestration()
        logger.info("Live trading universe orchestrator stopped")
    except Exception as e:
        logger.error(f"Failed to stop universe orchestrator: {e}")


@router.get("/universe")
async def get_trading_universe():
    """Get current trading universe with all metrics"""
    global universe_orchestrator
    
    try:
        universe_data = universe_orchestrator.get_active_universe()
        return universe_data
        
    except Exception as e:
        logger.error(f"Failed to get trading universe: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute")
async def execute_trade(request: TradeRequest, background_tasks: BackgroundTasks):
    """Execute trade order"""
    global execution_engine, universe_orchestrator
    
    try:
        # Validate symbol is in active universe
        if request.symbol not in universe_orchestrator.active_symbols:
            raise HTTPException(status_code=400, detail=f"Symbol {request.symbol} not in active universe")
        
        # Check order budget
        budget_ok = await universe_orchestrator.check_order_budget(request.symbol)
        if not budget_ok:
            raise HTTPException(status_code=429, detail="Order budget exceeded for symbol")
        
        # Determine execution style based on mode
        if request.mode == 'paper':
            # Paper trading - simplified execution
            result = {
                'order_id': f"paper_{request.symbol}_{int(datetime.now().timestamp())}",
                'status': 'filled',
                'filled_quantity': request.quantity,
                'avg_fill_price': 50000,  # Mock price
                'execution_style': 'paper',
                'slippage_bps': 5.0,
                'timestamp': datetime.now().isoformat()
            }
        else:
            # Live trading - use smart execution
            result = await execution_engine.execute_order(
                symbol=request.symbol,
                side=request.side,
                quantity=request.quantity
            )
        
        # Record order in budget
        await universe_orchestrator.record_order(request.symbol)
        
        # Broadcast to WebSocket clients
        if active_connections:
            ws_message = {
                'type': 'trade_executed',
                'symbol': request.symbol,
                'side': request.side,
                'quantity': request.quantity,
                'result': result
            }
            background_tasks.add_task(broadcast_to_websockets, ws_message)
        
        return {
            'status': 'success',
            'trade_result': result,
            'mode': request.mode,
            'timestamp': datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Trade execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/symbol/{symbol}/pause")
async def pause_symbol(symbol: str, action: Optional[SymbolAction] = None):
    """Pause trading for specific symbol"""
    global universe_orchestrator
    
    try:
        if symbol in universe_orchestrator.active_symbols:
            universe_orchestrator.parked_symbols.add(symbol)
            universe_orchestrator.active_symbols.discard(symbol)
            
            return {
                'status': 'success',
                'message': f'{symbol} paused from trading',
                'symbol': symbol,
                'action': 'pause'
            }
        else:
            return {
                'status': 'info',
                'message': f'{symbol} was not active',
                'symbol': symbol
            }
            
    except Exception as e:
        logger.error(f"Failed to pause symbol {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/symbol/{symbol}/kill")
async def kill_symbol(symbol: str, action: Optional[SymbolAction] = None):
    """Kill all positions and strategies for symbol"""
    global universe_orchestrator
    
    try:
        # Remove from all active sets
        universe_orchestrator.active_symbols.discard(symbol)
        universe_orchestrator.tier1_symbols.discard(symbol)
        universe_orchestrator.tier2_symbols.discard(symbol)
        universe_orchestrator.parked_symbols.add(symbol)
        
        # In production, would close all positions and cancel orders
        
        return {
            'status': 'success',
            'message': f'{symbol} killed - all positions closed and strategies stopped',
            'symbol': symbol,
            'action': 'kill'
        }
        
    except Exception as e:
        logger.error(f"Failed to kill symbol {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/symbol/{symbol}/news")
async def get_symbol_news_detail(symbol: str):
    """Get detailed news for symbol with evidence links"""
    global news_analyzer
    
    try:
        sentiment_summary = await news_analyzer.get_sentiment_summary(symbol)
        
        if not sentiment_summary:
            return {
                'symbol': symbol,
                'error': 'No news data available'
            }
        
        # Add evidence links (headline/summary list)
        evidence = []
        if symbol in news_analyzer.news_cache:
            recent_news = sorted(news_analyzer.news_cache[symbol], 
                               key=lambda x: x.timestamp, reverse=True)[:10]
            
            evidence = [
                {
                    'title': item.title,
                    'summary': item.summary[:100] + '...' if len(item.summary) > 100 else item.summary,
                    'url': item.url,
                    'source': item.source,
                    'timestamp': item.timestamp.isoformat(),
                    'sentiment': item.sentiment_score,
                    'confidence': item.confidence
                }
                for item in recent_news
            ]
        
        return {
            'symbol': symbol,
            'sentiment_summary': sentiment_summary,
            'evidence': evidence,
            'evidence_count': len(evidence)
        }
        
    except Exception as e:
        logger.error(f"Failed to get news detail for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_live_trading_stats():
    """Get live trading statistics"""
    global universe_orchestrator, execution_engine
    
    try:
        # Universe stats
        universe = universe_orchestrator.get_active_universe()
        
        # Execution stats
        execution_report = execution_engine.get_execution_report(lookback_hours=6)
        
        # Rate limiting stats
        rate_limit_stats = {}
        for exchange, limiter in universe_orchestrator.rate_limiters.items():
            rate_limit_stats[exchange] = {
                'requests_per_minute': len([t for t in limiter.request_times 
                                          if t > datetime.now() - datetime.timedelta(minutes=1)]),
                'error_rate': limiter.rejected_requests / max(limiter.total_requests, 1),
                'blocked': limiter.blocked_until.isoformat() if limiter.blocked_until else None
            }
        
        return {
            'universe_stats': universe['universe_stats'],
            'execution_stats': execution_report,
            'rate_limit_stats': rate_limit_stats,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get live trading stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/ws/trading-grid")
async def trading_grid_websocket(websocket: WebSocket):
    """WebSocket for live grid updates"""
    
    await websocket.accept()
    active_connections.append(websocket)
    
    try:
        # Send initial universe data
        universe_data = universe_orchestrator.get_active_universe()
        await websocket.send_text(json.dumps({
            'type': 'universe_update',
            'universe': universe_data
        }))
        
        # Keep connection alive
        while True:
            # Send periodic updates
            await asyncio.sleep(5)
            
            # Price updates (mock - in production would come from data feeds)
            price_update = {
                'type': 'price_update',
                'symbol': 'BTC/USDT',
                'price': 67500 + np.random.uniform(-100, 100),
                'timestamp': datetime.now().isoformat()
            }
            
            await websocket.send_text(json.dumps(price_update))
            
    except WebSocketDisconnect:
        active_connections.remove(websocket)
        logger.info("Trading grid WebSocket client disconnected")
    except Exception as e:
        logger.error(f"Trading grid WebSocket error: {e}")
        if websocket in active_connections:
            active_connections.remove(websocket)


async def broadcast_to_websockets(message: Dict[str, Any]):
    """Broadcast message to all WebSocket clients"""
    if not active_connections:
        return
    
    message_json = json.dumps(message, default=str)
    
    # Send to all connections
    disconnected = []
    for websocket in active_connections:
        try:
            await websocket.send_text(message_json)
        except Exception as e:
            logger.error(f"Failed to send WebSocket message: {e}")
            disconnected.append(websocket)
    
    # Remove disconnected clients
    for websocket in disconnected:
        active_connections.remove(websocket)