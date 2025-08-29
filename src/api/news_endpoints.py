"""
News API endpoints
"""

from fastapi import APIRouter, Query, HTTPException
from typing import List, Dict, Any
import logging

from src.news.rss_aggregator import rss_aggregator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/news", tags=["news"])


@router.get("", response_model=List[Dict[str, Any]])
async def get_news(
    symbol: str = Query(default="all", description="Symbol to filter news (BTC, ETH, AAPL, etc.)"),
    limit: int = Query(default=10, ge=1, le=50, description="Maximum number of news items"),
    use_cache: bool = Query(default=True, description="Use cached results if available")
) -> List[Dict[str, Any]]:
    """
    Get news from RSS feeds
    
    Returns list of news items with title, link, source, timestamp, and summary
    """
    try:
        news_items = rss_aggregator.fetch_news(symbol, limit, use_cache)
        return news_items
    except Exception as e:
        logger.error(f"Error fetching news: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sources", response_model=List[Dict[str, str]])
async def get_news_sources() -> List[Dict[str, str]]:
    """
    Get list of RSS news sources
    """
    try:
        sources = rss_aggregator.get_sources()
        return sources
    except Exception as e:
        logger.error(f"Error getting sources: {e}")
        raise HTTPException(status_code=500, detail=str(e))