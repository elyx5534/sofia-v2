"""
Free Crypto News Collector
Collects crypto news from multiple free RSS feeds and sources
"""

import asyncio
import aiohttp
import feedparser
import logging
from typing import Dict, List
from datetime import datetime, timezone
from bs4 import BeautifulSoup
import re

logger = logging.getLogger(__name__)

class FreeCryptoNewsCollector:
    """Collect crypto news from free sources"""
    
    def __init__(self, config):
        self.config = config
        self.session = None
        
        # Extended RSS feeds list
        self.news_sources = {
            **config.RSS_FEEDS,
            'crypto_news': 'https://cryptonews.com/news/feed/',
            'u_today': 'https://u.today/rss',
            'crypto_potato': 'https://cryptopotato.com/feed/',
            'ambcrypto': 'https://ambcrypto.com/feed/',
            'crypto_briefing': 'https://cryptobriefing.com/feed/',
            'the_block': 'https://www.theblock.co/rss.xml',
            'coin_speaker': 'https://www.coinspeaker.com/feed/',
            'finbold': 'https://finbold.com/category/cryptocurrency/feed/',
            'crypto_news_flash': 'https://www.crypto-news-flash.com/feed/',
            'bitcoin_com': 'https://news.bitcoin.com/feed/'
        }
        
        # Keywords for filtering important news
        self.important_keywords = [
            'bitcoin', 'btc', 'ethereum', 'eth', 'pump', 'dump', 'rally', 'crash',
            'bull', 'bear', 'whale', 'adoption', 'regulation', 'sec', 'etf', 
            'halving', 'merge', 'upgrade', 'hack', 'exploit', 'defi', 'nft'
        ]
        
    async def start(self):
        """Start news collection"""
        self.session = aiohttp.ClientSession()
        logger.info("Crypto News Collector started")
        
    async def stop(self):
        """Stop news collection"""
        if self.session:
            await self.session.close()
        logger.info("Crypto News Collector stopped")
        
    async def fetch_rss_feed(self, source_name: str, url: str) -> List[Dict]:
        """Fetch and parse RSS feed"""
        try:
            headers = {
                'User-Agent': self.config.get_random_user_agent()
            }
            
            async with self.session.get(url, headers=headers, timeout=10) as response:
                if response.status == 200:
                    content = await response.text()
                    
                    # Parse RSS feed
                    feed = feedparser.parse(content)
                    
                    articles = []
                    for entry in feed.entries[:10]:  # Latest 10 articles
                        article = {
                            'source': source_name,
                            'title': entry.get('title', ''),
                            'description': entry.get('description', ''),
                            'link': entry.get('link', ''),
                            'published': entry.get('published', ''),
                            'published_parsed': entry.get('published_parsed'),
                            'author': entry.get('author', ''),
                            'tags': [tag.term for tag in entry.get('tags', [])],
                            'timestamp': datetime.now(timezone.utc).isoformat()
                        }
                        
                        # Calculate importance score
                        article['importance_score'] = self.calculate_importance_score(article)
                        
                        articles.append(article)
                        
                    logger.info(f"{source_name}: Collected {len(articles)} articles")
                    return articles
                    
        except Exception as e:
            logger.error(f"RSS feed error for {source_name}: {e}")
            
        return []
        
    def calculate_importance_score(self, article: Dict) -> int:
        """Calculate news importance score (0-100)"""
        score = 0
        text = f"{article['title']} {article['description']}".lower()
        
        # Keywords scoring
        for keyword in self.important_keywords:
            if keyword in text:
                score += 5
                
        # Title keywords get higher score
        title_text = article['title'].lower()
        for keyword in ['bitcoin', 'ethereum', 'btc', 'eth']:
            if keyword in title_text:
                score += 10
                
        # Urgent news indicators
        urgent_words = ['breaking', 'alert', 'urgent', 'crash', 'pump', 'surge']
        for word in urgent_words:
            if word in title_text:
                score += 15
                
        # Whale/large transaction news
        whale_words = ['whale', 'large transaction', 'moved', 'transferred']
        for word in whale_words:
            if word in text:
                score += 20
                
        return min(score, 100)  # Cap at 100
        
    async def scrape_coindesk_headlines(self) -> List[Dict]:
        """Scrape CoinDesk for breaking news"""
        try:
            url = "https://www.coindesk.com/livewire/"
            headers = {
                'User-Agent': self.config.get_random_user_agent()
            }
            
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Find news articles
                    articles = []
                    news_items = soup.find_all('article', limit=20)
                    
                    for item in news_items:
                        title_elem = item.find(['h1', 'h2', 'h3'])
                        link_elem = item.find('a')
                        time_elem = item.find('time')
                        
                        if title_elem and link_elem:
                            article = {
                                'source': 'coindesk_scrape',
                                'title': title_elem.get_text(strip=True),
                                'link': link_elem.get('href', ''),
                                'published': time_elem.get('datetime', '') if time_elem else '',
                                'timestamp': datetime.now(timezone.utc).isoformat(),
                                'type': 'breaking_news'
                            }
                            
                            # Calculate importance
                            article['importance_score'] = self.calculate_importance_score(article)
                            articles.append(article)
                            
                    logger.info(f"CoinDesk scrape: {len(articles)} articles")
                    return articles
                    
        except Exception as e:
            logger.error(f"CoinDesk scraping error: {e}")
            
        return []
        
    async def get_crypto_panic_alternative(self) -> List[Dict]:
        """Free alternative to CryptoPanic using multiple sources"""
        try:
            # Aggregate from multiple free sources
            sources_to_check = [
                'https://cryptopotato.com/feed/',
                'https://www.newsbtc.com/feed/',
                'https://bitcoinist.com/feed/',
                'https://cryptoslate.com/feed/',
                'https://beincrypto.com/feed/'
            ]
            
            all_news = []
            
            for url in sources_to_check:
                try:
                    async with self.session.get(url, timeout=10) as response:
                        if response.status == 200:
                            content = await response.text()
                            feed = feedparser.parse(content)
                            
                            for entry in feed.entries[:5]:  # Top 5 from each source
                                article = {
                                    'title': entry.get('title', ''),
                                    'description': entry.get('description', ''),
                                    'link': entry.get('link', ''),
                                    'published': entry.get('published', ''),
                                    'source': url.split('/')[2],  # Extract domain
                                    'timestamp': datetime.now(timezone.utc).isoformat()
                                }
                                
                                # Add sentiment analysis
                                article['sentiment'] = self.analyze_sentiment(article['title'])
                                article['importance_score'] = self.calculate_importance_score(article)
                                
                                all_news.append(article)
                                
                    await asyncio.sleep(0.5)  # Rate limiting between sources
                    
                except Exception as e:
                    logger.error(f"Error fetching from {url}: {e}")
                    continue
            
            # Sort by importance and recency
            all_news.sort(key=lambda x: (x['importance_score'], x['timestamp']), reverse=True)
            
            return all_news[:50]  # Top 50 news items
            
        except Exception as e:
            logger.error(f"Crypto panic alternative error: {e}")
            return []
            
    def analyze_sentiment(self, text: str) -> str:
        """Basic sentiment analysis without paid APIs"""
        text_lower = text.lower()
        
        positive_words = ['pump', 'rally', 'surge', 'bull', 'up', 'gain', 'rise', 'green', 'moon', 'adoption']
        negative_words = ['dump', 'crash', 'bear', 'down', 'fall', 'red', 'hack', 'exploit', 'ban', 'regulation']
        
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        if positive_count > negative_count:
            return 'bullish'
        elif negative_count > positive_count:
            return 'bearish' 
        else:
            return 'neutral'
            
    async def collect_all_news(self) -> Dict:
        """Collect news from all free sources"""
        all_news = {}
        
        # Collect RSS feeds
        rss_tasks = []
        for source_name, url in self.news_sources.items():
            task = self.fetch_rss_feed(source_name, url)
            rss_tasks.append(task)
            
        # Collect scraped news
        scrape_tasks = [
            self.scrape_coindesk_headlines(),
            self.get_crypto_panic_alternative()
        ]
        
        # Execute all tasks
        rss_results = await asyncio.gather(*rss_tasks, return_exceptions=True)
        scrape_results = await asyncio.gather(*scrape_tasks, return_exceptions=True)
        
        # Combine results
        all_articles = []
        
        for result in rss_results:
            if isinstance(result, list):
                all_articles.extend(result)
                
        for result in scrape_results:
            if isinstance(result, list):
                all_articles.extend(result)
        
        # Remove duplicates and sort
        seen_titles = set()
        unique_articles = []
        
        for article in all_articles:
            title = article.get('title', '')
            if title not in seen_titles:
                seen_titles.add(title)
                unique_articles.append(article)
                
        # Sort by importance and recency
        unique_articles.sort(key=lambda x: x.get('importance_score', 0), reverse=True)
        
        return {
            'articles': unique_articles[:100],  # Top 100 articles
            'total_sources': len(self.news_sources),
            'collection_timestamp': datetime.now(timezone.utc).isoformat(),
            'sentiment_summary': self.get_overall_sentiment(unique_articles[:20])
        }
        
    def get_overall_sentiment(self, articles: List[Dict]) -> Dict:
        """Calculate overall market sentiment from news"""
        sentiments = [article.get('sentiment', 'neutral') for article in articles]
        
        bullish_count = sentiments.count('bullish')
        bearish_count = sentiments.count('bearish')
        neutral_count = sentiments.count('neutral')
        
        total = len(sentiments)
        
        if total == 0:
            return {'overall': 'neutral', 'confidence': 0}
            
        bullish_percent = (bullish_count / total) * 100
        bearish_percent = (bearish_count / total) * 100
        
        if bullish_percent > 60:
            overall = 'very_bullish'
        elif bullish_percent > 40:
            overall = 'bullish'
        elif bearish_percent > 60:
            overall = 'very_bearish'
        elif bearish_percent > 40:
            overall = 'bearish'
        else:
            overall = 'neutral'
            
        confidence = max(bullish_percent, bearish_percent)
        
        return {
            'overall': overall,
            'confidence': confidence,
            'bullish_percent': bullish_percent,
            'bearish_percent': bearish_percent,
            'neutral_percent': (neutral_count / total) * 100,
            'total_articles': total
        }