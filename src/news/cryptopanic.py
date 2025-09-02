"""
CryptoPanic API integration for cryptocurrency news
"""

import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger


class CryptoPanicClient:
    """Client for CryptoPanic API"""

    def __init__(self, api_token: Optional[str] = None):
        self.api_token = api_token or os.getenv("CRYPTOPANIC_TOKEN")
        self.base_url = "https://cryptopanic.com/api/v1"
        self.session = None

    async def get_session(self):
        """Get or create HTTP session"""
        if self.session is None:
            self.session = httpx.AsyncClient(timeout=30.0)
        return self.session

    async def close(self):
        """Close HTTP session"""
        if self.session:
            await self.session.aclose()
            self.session = None

    async def fetch_posts(
        self, symbols: Optional[List[str]] = None, hours_back: int = 24, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Fetch news posts from CryptoPanic"""
        try:
            session = await self.get_session()

            params = {
                "auth_token": self.api_token,
                "kind": "news",
                "filter": "rising",
                "limit": limit,
            }

            # Add specific currencies if provided
            if symbols:
                # Convert symbols to CryptoPanic currency format
                currencies = []
                for symbol in symbols:
                    if "/" in symbol:
                        base = symbol.split("/")[0].lower()
                        currencies.append(base)

                if currencies:
                    params["currencies"] = ",".join(currencies[:10])  # API limit

            response = await session.get(f"{self.base_url}/posts/", params=params)
            response.raise_for_status()

            data = response.json()
            posts = data.get("results", [])

            # Filter by time
            cutoff_time = datetime.now() - timedelta(hours=hours_back)
            recent_posts = []

            for post in posts:
                try:
                    post_time = datetime.fromisoformat(post["created_at"].replace("Z", "+00:00"))

                    if post_time >= cutoff_time:
                        recent_posts.append(
                            {
                                "id": post.get("id"),
                                "title": post.get("title", ""),
                                "url": post.get("url", ""),
                                "created_at": post.get("created_at"),
                                "domain": post.get("domain", ""),
                                "votes": {
                                    "negative": post.get("votes", {}).get("negative", 0),
                                    "positive": post.get("votes", {}).get("positive", 0),
                                    "important": post.get("votes", {}).get("important", 0),
                                    "liked": post.get("votes", {}).get("liked", 0),
                                    "disliked": post.get("votes", {}).get("disliked", 0),
                                },
                                "currencies": [c["title"] for c in post.get("currencies", [])],
                                "source": "cryptopanic",
                            }
                        )

                except Exception as e:
                    logger.warning(f"Error parsing post: {e}")
                    continue

            logger.info(f"Fetched {len(recent_posts)} recent posts from CryptoPanic")
            return recent_posts

        except Exception as e:
            logger.error(f"Error fetching CryptoPanic posts: {e}")
            return []

    async def fetch_symbol_news(
        self, symbol: str, hours_back: int = 24, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Fetch news for a specific symbol"""
        try:
            if "/" in symbol:
                base_currency = symbol.split("/")[0].lower()
            else:
                base_currency = symbol.lower()

            session = await self.get_session()

            params = {
                "auth_token": self.api_token,
                "currencies": base_currency,
                "kind": "news",
                "limit": limit,
            }

            response = await session.get(f"{self.base_url}/posts/", params=params)
            response.raise_for_status()

            data = response.json()
            posts = data.get("results", [])

            # Filter by time and format
            cutoff_time = datetime.now() - timedelta(hours=hours_back)
            symbol_news = []

            for post in posts:
                try:
                    post_time = datetime.fromisoformat(post["created_at"].replace("Z", "+00:00"))

                    if post_time >= cutoff_time:
                        symbol_news.append(
                            {
                                "title": post.get("title", ""),
                                "url": post.get("url", ""),
                                "created_at": post.get("created_at"),
                                "domain": post.get("domain", ""),
                                "sentiment_score": self._calculate_sentiment_score(
                                    post.get("votes", {})
                                ),
                                "impact_score": post.get("votes", {}).get("important", 0),
                                "source": "cryptopanic",
                            }
                        )

                except Exception as e:
                    logger.warning(f"Error parsing symbol news: {e}")
                    continue

            return symbol_news

        except Exception as e:
            logger.error(f"Error fetching {symbol} news: {e}")
            return []

    def _calculate_sentiment_score(self, votes: Dict[str, int]) -> float:
        """Calculate sentiment score from votes"""
        positive = votes.get("positive", 0) + votes.get("liked", 0)
        negative = votes.get("negative", 0) + votes.get("disliked", 0)

        if positive + negative == 0:
            return 0.5  # Neutral

        return positive / (positive + negative)

    async def fetch_global_news(
        self, hours_back: int = 24, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Fetch global cryptocurrency news"""
        return await self.fetch_posts(symbols=None, hours_back=hours_back, limit=limit)
