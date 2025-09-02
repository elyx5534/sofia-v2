"""
News aggregator combining CryptoPanic and GDELT sources
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from .cryptopanic import CryptoPanicClient
from .gdelt import GDELTClient


class NewsAggregator:
    """Aggregate news from multiple sources"""

    def __init__(self, outputs_dir: str = "./outputs"):
        self.cryptopanic = CryptoPanicClient()
        self.gdelt = GDELTClient()
        self.outputs_dir = Path(outputs_dir)
        self.news_dir = self.outputs_dir / "news"
        self.news_dir.mkdir(parents=True, exist_ok=True)

    async def close(self):
        """Close all clients"""
        await self.cryptopanic.close()
        await self.gdelt.close()

    async def fetch_global_news(self, hours_back: int = 24) -> Dict[str, Any]:
        """Fetch global cryptocurrency news from all sources"""
        logger.info("Fetching global crypto news from multiple sources")

        tasks = []

        # CryptoPanic global news
        if self.cryptopanic.api_token:
            tasks.append(self.cryptopanic.fetch_global_news(hours_back=hours_back, limit=30))
        else:
            logger.warning("No CryptoPanic API token, skipping CryptoPanic news")

        # GDELT crypto news
        tasks.append(self.gdelt.fetch_crypto_news(hours_back=hours_back, limit=30))

        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        cryptopanic_news = []
        gdelt_news = []

        # Process CryptoPanic results
        if self.cryptopanic.api_token and len(results) > 0:
            if isinstance(results[0], list):
                cryptopanic_news = results[0]
            else:
                logger.error(f"CryptoPanic fetch error: {results[0]}")

        # Process GDELT results
        gdelt_index = 1 if self.cryptopanic.api_token else 0
        if len(results) > gdelt_index:
            if isinstance(results[gdelt_index], list):
                gdelt_news = results[gdelt_index]
            else:
                logger.error(f"GDELT fetch error: {results[gdelt_index]}")

        # Combine and format news
        all_news = []

        # Add CryptoPanic news
        for news in cryptopanic_news:
            all_news.append(
                {
                    "title": news.get("title", ""),
                    "url": news.get("url", ""),
                    "source": "CryptoPanic",
                    "domain": news.get("domain", ""),
                    "created_at": news.get("created_at", ""),
                    "sentiment_score": news.get("sentiment_score", 0.5),
                    "impact_score": news.get("impact_score", 0),
                    "currencies": news.get("currencies", []),
                    "votes": news.get("votes", {}),
                }
            )

        # Add GDELT news
        for news in gdelt_news:
            all_news.append(
                {
                    "title": news.get("title", ""),
                    "url": news.get("url", ""),
                    "source": "GDELT",
                    "domain": news.get("domain", ""),
                    "created_at": news.get("date", ""),
                    "sentiment_score": self.gdelt.calculate_sentiment_score(news.get("tone", 0)),
                    "tone": news.get("tone", 0),
                    "language": news.get("language", "en"),
                }
            )

        # Sort by timestamp (newest first)
        all_news.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        result = {
            "total_articles": len(all_news),
            "sources": {"cryptopanic": len(cryptopanic_news), "gdelt": len(gdelt_news)},
            "articles": all_news,
            "timestamp": datetime.now().isoformat(),
            "hours_back": hours_back,
        }

        logger.info(
            f"Aggregated {len(all_news)} news articles from {len(result['sources'])} sources"
        )
        return result

    async def fetch_symbol_news(self, symbol: str, hours_back: int = 24) -> Dict[str, Any]:
        """Fetch news for a specific symbol"""
        logger.info(f"Fetching news for {symbol}")

        tasks = []

        # CryptoPanic symbol news
        if self.cryptopanic.api_token:
            tasks.append(self.cryptopanic.fetch_symbol_news(symbol, hours_back=hours_back))
        else:
            logger.warning("No CryptoPanic API token, skipping symbol news")

        # GDELT symbol-specific search
        if "/" in symbol:
            base_symbol = symbol.split("/")[0]
        else:
            base_symbol = symbol

        gdelt_query = (
            f"{base_symbol} cryptocurrency OR {base_symbol} price OR {base_symbol} trading"
        )
        tasks.append(self.gdelt.fetch_summary_news(gdelt_query, hours_back=hours_back, limit=15))

        # Execute tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)

        symbol_news = []

        # Process results
        for i, result in enumerate(results):
            if isinstance(result, list):
                for news in result:
                    formatted_news = {
                        "title": news.get("title", ""),
                        "url": news.get("url", ""),
                        "source": (
                            "CryptoPanic" if i == 0 and self.cryptopanic.api_token else "GDELT"
                        ),
                        "domain": news.get("domain", ""),
                        "created_at": news.get("created_at", news.get("date", "")),
                        "sentiment_score": news.get(
                            "sentiment_score",
                            self.gdelt.calculate_sentiment_score(news.get("tone", 0)),
                        ),
                    }
                    symbol_news.append(formatted_news)
            else:
                logger.error(f"Error fetching symbol news: {result}")

        # Sort and limit
        symbol_news.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        result = {
            "symbol": symbol,
            "total_articles": len(symbol_news),
            "articles": symbol_news[:20],  # Limit to 20 most recent
            "timestamp": datetime.now().isoformat(),
        }

        return result

    def save_global_news(self, news_data: Dict[str, Any]):
        """Save global news to file"""
        global_path = self.news_dir / "global.json"

        with open(global_path, "w", encoding="utf-8") as f:
            json.dump(news_data, f, indent=2, ensure_ascii=False, default=str)

        logger.info(f"Global news saved to {global_path}")

    def save_symbol_news(self, symbol: str, news_data: Dict[str, Any]):
        """Save symbol news to file"""
        safe_symbol = symbol.replace("/", "-")
        symbol_path = self.news_dir / f"{safe_symbol}.json"

        with open(symbol_path, "w", encoding="utf-8") as f:
            json.dump(news_data, f, indent=2, ensure_ascii=False, default=str)

        logger.info(f"News for {symbol} saved to {symbol_path}")

    async def update_all_news(self, symbols: Optional[List[str]] = None, hours_back: int = 24):
        """Update global news and optionally symbol-specific news"""
        try:
            # Fetch global news
            global_news = await self.fetch_global_news(hours_back)
            self.save_global_news(global_news)

            # Fetch symbol-specific news if provided
            if symbols:
                logger.info(f"Fetching news for {len(symbols)} symbols")

                for symbol in symbols[:10]:  # Limit to avoid rate limiting
                    try:
                        symbol_news = await self.fetch_symbol_news(symbol, hours_back)
                        self.save_symbol_news(symbol, symbol_news)

                        # Small delay to avoid rate limiting
                        await asyncio.sleep(1)

                    except Exception as e:
                        logger.error(f"Error fetching news for {symbol}: {e}")

            logger.info("News update completed")

        except Exception as e:
            logger.error(f"Error updating news: {e}")

        finally:
            await self.close()

    def get_latest_news(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get latest global news from saved data"""
        global_path = self.news_dir / "global.json"

        if not global_path.exists():
            return []

        try:
            with open(global_path, encoding="utf-8") as f:
                data = json.load(f)

            articles = data.get("articles", [])
            return articles[:limit]

        except Exception as e:
            logger.error(f"Error loading latest news: {e}")
            return []

    def get_symbol_news(self, symbol: str) -> List[Dict[str, Any]]:
        """Get news for a specific symbol"""
        safe_symbol = symbol.replace("/", "-")
        symbol_path = self.news_dir / f"{safe_symbol}.json"

        if not symbol_path.exists():
            return []

        try:
            with open(symbol_path, encoding="utf-8") as f:
                data = json.load(f)

            return data.get("articles", [])

        except Exception as e:
            logger.error(f"Error loading news for {symbol}: {e}")
            return []


# Global news aggregator instance
news_aggregator = NewsAggregator()
