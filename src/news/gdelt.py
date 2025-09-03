"""
GDELT API integration for global news analysis
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List

import httpx
from loguru import logger


class GDELTClient:
    """Client for GDELT Summary API"""

    def __init__(self):
        self.base_url = "https://api.gdeltproject.org/api/v2"
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

    async def fetch_summary_news(
        self, query: str, hours_back: int = 24, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Fetch news summary from GDELT"""
        try:
            session = await self.get_session()
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours_back)
            params = {
                "query": query,
                "mode": "artlist",
                "maxrecords": limit,
                "sort": "hybridrel",
                "format": "json",
                "startdatetime": start_time.strftime("%Y%m%d%H%M%S"),
                "enddatetime": end_time.strftime("%Y%m%d%H%M%S"),
            }
            response = await session.get(f"{self.base_url}/summary/summary", params=params)
            response.raise_for_status()
            data = response.json()
            articles = data.get("articles", [])
            formatted_articles = []
            for article in articles:
                try:
                    formatted_articles.append(
                        {
                            "title": article.get("title", ""),
                            "url": article.get("url", ""),
                            "domain": article.get("domain", ""),
                            "language": article.get("language", "en"),
                            "date": article.get("seendate", ""),
                            "social_image": article.get("socialimage", ""),
                            "tone": float(article.get("tone", 0)),
                            "source": "gdelt",
                        }
                    )
                except Exception as e:
                    logger.warning(f"Error parsing GDELT article: {e}")
                    continue
            logger.info(f"Fetched {len(formatted_articles)} articles from GDELT")
            return formatted_articles
        except Exception as e:
            logger.error(f"Error fetching GDELT summary: {e}")
            return []

    async def fetch_crypto_news(
        self, hours_back: int = 24, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Fetch cryptocurrency-related news from GDELT"""
        crypto_queries = [
            "cryptocurrency OR bitcoin OR ethereum OR crypto OR blockchain",
            "SEC cryptocurrency OR SEC bitcoin OR SEC crypto",
            "ETF bitcoin OR ETF cryptocurrency",
            "binance OR coinbase OR kraken",
            "DeFi OR decentralized finance",
            "NFT OR non-fungible token",
        ]
        all_articles = []
        for query in crypto_queries:
            try:
                articles = await self.fetch_summary_news(
                    query, hours_back=hours_back, limit=limit // len(crypto_queries)
                )
                all_articles.extend(articles)
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.warning(f"Error fetching GDELT news for query '{query}': {e}")
                continue
        seen_urls = set()
        unique_articles = []
        for article in all_articles:
            url = article.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_articles.append(article)
        unique_articles.sort(key=lambda x: x.get("date", ""), reverse=True)
        logger.info(f"Collected {len(unique_articles)} unique crypto articles from GDELT")
        return unique_articles[:limit]

    async def fetch_doc_search(
        self, query: str, hours_back: int = 24, limit: int = 25
    ) -> List[Dict[str, Any]]:
        """Fetch documents using GDELT Doc 2.0 API"""
        try:
            session = await self.get_session()
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours_back)
            params = {
                "query": query,
                "mode": "artlist",
                "maxrecords": limit,
                "sort": "datedesc",
                "format": "json",
                "startdatetime": start_time.strftime("%Y%m%d%H%M%S"),
                "enddatetime": end_time.strftime("%Y%m%d%H%M%S"),
                "trans": "googletrans",
            }
            response = await session.get(f"{self.base_url}/doc/doc", params=params)
            response.raise_for_status()
            data = response.json()
            articles = data.get("articles", [])
            formatted_articles = []
            for article in articles:
                try:
                    formatted_articles.append(
                        {
                            "title": article.get("title", ""),
                            "url": article.get("url", ""),
                            "domain": article.get("domain", ""),
                            "language": article.get("language", "en"),
                            "date": article.get("seendate", ""),
                            "tone": float(article.get("tone", 0)),
                            "source": "gdelt_doc",
                        }
                    )
                except Exception as e:
                    logger.warning(f"Error parsing GDELT doc: {e}")
                    continue
            return formatted_articles
        except Exception as e:
            logger.error(f"Error fetching GDELT docs: {e}")
            return []

    def calculate_sentiment_score(self, tone: float) -> float:
        """Convert GDELT tone to 0-1 sentiment score"""
        return max(0, min(1, (tone + 100) / 200))

    async def get_trending_crypto_topics(self, hours_back: int = 6) -> List[Dict[str, Any]]:
        """Get trending cryptocurrency topics"""
        trending_queries = [
            "bitcoin price surge",
            "ethereum upgrade",
            "cryptocurrency regulation",
            "crypto market crash",
            "altcoin rally",
            "DeFi hack",
            "NFT marketplace",
        ]
        trending_news = []
        for query in trending_queries:
            try:
                articles = await self.fetch_summary_news(query, hours_back=hours_back, limit=5)
                if articles:
                    trending_news.append(
                        {
                            "topic": query.title(),
                            "article_count": len(articles),
                            "latest_article": articles[0] if articles else None,
                            "avg_tone": sum(a.get("tone", 0) for a in articles) / len(articles),
                        }
                    )
                await asyncio.sleep(0.3)
            except Exception as e:
                logger.warning(f"Error fetching trending topic '{query}': {e}")
                continue
        return trending_news
