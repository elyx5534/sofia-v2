"""FastAPI application for the data-hub module."""

from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .cache import cache_manager
from .claude_service import MarketAnalysisRequest, MarketAnalysisResponse, claude_service
from .models import AssetType, ErrorResponse, HealthResponse, OHLCVResponse, SymbolSearchResponse
from .providers import CCXTProvider, YFinanceProvider
from .settings import settings
from src.backtester.api import router as backtester_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    await cache_manager.init_db()
    yield
    # Shutdown
    await cache_manager.close()
    # Close any open providers
    if hasattr(app.state, "ccxt_provider"):
        await app.state.ccxt_provider.close()


# Create FastAPI app
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description=settings.api_description,
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_credentials,
    allow_methods=settings.cors_methods,
    allow_headers=settings.cors_headers,
)

# Initialize providers
yfinance_provider = YFinanceProvider()
ccxt_provider = CCXTProvider()

# Mount backtester router
app.include_router(backtester_router, prefix="/backtester", tags=["Backtester"])


@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    """Handle ValueError exceptions."""
    return JSONResponse(
        status_code=404,
        content=ErrorResponse(
            error="Not Found",
            detail=str(exc),
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def general_error_handler(request, exc):
    """Handle general exceptions."""
    return JSONResponse(
        status_code=503,
        content=ErrorResponse(
            error="Service Unavailable",
            detail=str(exc),
        ).model_dump(),
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        version=settings.api_version,
    )


@app.get("/symbols", response_model=SymbolSearchResponse)
async def search_symbols(
    query: str = Query(..., description="Search query for symbols"),
    asset_type: AssetType = Query(..., description="Type of asset to search"),
    limit: int = Query(10, ge=1, le=100, description="Maximum results to return"),
):
    """
    Search for symbols by query string.

    - **query**: Search term (e.g., 'AAPL', 'BTC')
    - **asset_type**: 'equity' or 'crypto'
    - **limit**: Maximum number of results (1-100)
    """
    try:
        if asset_type == AssetType.EQUITY:
            results = await yfinance_provider.search_symbols(query, limit)
        else:  # CRYPTO
            results = await ccxt_provider.search_symbols(query, limit)

        return SymbolSearchResponse(
            query=query,
            asset_type=asset_type,
            results=results,
            count=len(results),
        )

    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@app.get("/ohlcv", response_model=OHLCVResponse)
async def get_ohlcv(
    symbol: str = Query(..., description="Symbol ticker (e.g., AAPL, BTC/USDT)"),
    asset_type: AssetType = Query(..., description="Type of asset"),
    timeframe: str = Query("1h", description="Timeframe (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w, 1M)"),
    exchange: str | None = Query(None, description="Exchange name for crypto"),
    start_date: datetime | None = Query(None, description="Start date for data"),
    end_date: datetime | None = Query(None, description="End date for data"),
    limit: int = Query(500, ge=1, le=1000, description="Maximum candles to return"),
    nocache: bool = Query(False, description="Bypass cache if True"),
):
    """
    Get OHLCV (candlestick) data for a symbol.

    - **symbol**: Ticker symbol (AAPL for equity, BTC/USDT for crypto)
    - **asset_type**: 'equity' or 'crypto'
    - **timeframe**: Data interval (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w, 1M)
    - **exchange**: Exchange name (only for crypto, e.g., 'binance')
    - **start_date**: Start date for historical data
    - **end_date**: End date for historical data
    - **limit**: Maximum number of candles (1-1000)
    - **nocache**: Set to true to bypass cache
    """
    try:
        cached = False
        ohlcv_data = None

        # Check cache first (unless nocache is set)
        if not nocache:
            ohlcv_data = await cache_manager.get_ohlcv_cache(
                symbol=symbol,
                asset_type=asset_type,
                timeframe=timeframe,
                exchange=exchange,
                start_date=start_date,
                end_date=end_date,
            )
            if ohlcv_data:
                cached = True

        # Fetch from provider if not cached
        if not ohlcv_data:
            if asset_type == AssetType.EQUITY:
                ohlcv_data = await yfinance_provider.fetch_ohlcv(
                    symbol=symbol,
                    timeframe=timeframe,
                    start_date=start_date,
                    end_date=end_date,
                    limit=limit,
                )
            else:  # CRYPTO
                # Use specified exchange or default
                provider = ccxt_provider
                if exchange and exchange != settings.default_exchange:
                    provider = CCXTProvider(exchange)
                    try:
                        ohlcv_data = await provider.fetch_ohlcv(
                            symbol=symbol,
                            timeframe=timeframe,
                            start_date=start_date,
                            end_date=end_date,
                            limit=limit,
                        )
                    finally:
                        await provider.close()
                else:
                    ohlcv_data = await ccxt_provider.fetch_ohlcv(
                        symbol=symbol,
                        timeframe=timeframe,
                        start_date=start_date,
                        end_date=end_date,
                        limit=limit,
                    )

            # Store in cache
            if ohlcv_data:
                await cache_manager.set_ohlcv_cache(
                    symbol=symbol,
                    asset_type=asset_type,
                    timeframe=timeframe,
                    data=ohlcv_data,
                    exchange=exchange,
                    start_date=start_date,
                    end_date=end_date,
                )

        return OHLCVResponse(
            symbol=symbol,
            asset_type=asset_type,
            timeframe=timeframe,
            data=ohlcv_data,
            cached=cached,
            timestamp=datetime.utcnow(),
        )

    except ValueError as e:
        # Symbol not found
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        # Provider error
        raise HTTPException(status_code=503, detail=str(e)) from e


@app.delete("/cache")
async def clear_expired_cache():
    """Clear expired cache entries."""
    try:
        deleted_count = await cache_manager.clear_expired_cache()
        return {
            "message": f"Cleared {deleted_count} expired cache entries",
            "timestamp": datetime.utcnow(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/analyze", response_model=MarketAnalysisResponse)
async def analyze_market_data(
    symbol: str = Query(..., description="Symbol ticker (e.g., AAPL, BTC/USDT)"),
    asset_type: AssetType = Query(..., description="Type of asset"),
    timeframe: str = Query("1h", description="Timeframe (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w, 1M)"),
    analysis_type: str = Query("technical", description="Analysis type (technical, fundamental, sentiment)"),
    limit: int = Query(100, ge=10, le=500, description="Number of candles for analysis"),
):
    """
    Get AI-powered market analysis using Claude.
    
    This endpoint combines OHLCV data retrieval with Claude AI analysis to provide:
    - Technical analysis insights
    - Risk assessment
    - Trading recommendations
    - Market sentiment analysis
    
    **Requirements:**
    - Claude API key must be configured
    - Valid symbol and asset type
    - Sufficient OHLCV data available
    """
    try:
        # Check if Claude service is available
        if not claude_service:
            raise HTTPException(
                status_code=503, 
                detail="Claude AI service not configured. Please set CLAUDE_API_KEY environment variable."
            )
        
        # First, get OHLCV data
        ohlcv_data = None
        
        # Check cache first
        ohlcv_data = await cache_manager.get_ohlcv_cache(
            symbol=symbol,
            asset_type=asset_type,
            timeframe=timeframe,
        )
        
        # Fetch from provider if not cached
        if not ohlcv_data:
            if asset_type == AssetType.EQUITY:
                ohlcv_data = await yfinance_provider.fetch_ohlcv(
                    symbol=symbol,
                    timeframe=timeframe,
                    limit=limit,
                )
            else:  # CRYPTO
                ohlcv_data = await ccxt_provider.fetch_ohlcv(
                    symbol=symbol,
                    timeframe=timeframe,
                    limit=limit,
                )
            
            # Cache the data
            if ohlcv_data:
                await cache_manager.set_ohlcv_cache(
                    symbol=symbol,
                    asset_type=asset_type,
                    timeframe=timeframe,
                    data=ohlcv_data,
                )
        
        if not ohlcv_data:
            raise HTTPException(status_code=404, detail=f"No data available for {symbol}")
        
        # Limit data for analysis (use most recent candles)
        analysis_data = ohlcv_data[-limit:] if len(ohlcv_data) > limit else ohlcv_data
        
        # Create analysis request
        analysis_request = MarketAnalysisRequest(
            symbol=symbol,
            asset_type=asset_type,
            ohlcv_data=analysis_data,
            timeframe=timeframe,
            analysis_type=analysis_type
        )
        
        # Get AI analysis
        analysis = await claude_service.analyze_market_data(analysis_request)
        
        return analysis
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "title": settings.api_title,
        "version": settings.api_version,
        "description": settings.api_description,
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "/health": "Health check",
            "/symbols": "Search symbols",
            "/ohlcv": "Get OHLCV data",
            "/analyze": "AI-powered market analysis",
            "/cache": "Cache management",
        },
    }


# Add shutdown handler for providers
@app.on_event("shutdown")
async def shutdown_event():
    """Clean up providers on shutdown."""
    await ccxt_provider.close()
