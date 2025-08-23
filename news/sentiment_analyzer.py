"""
News and Sentiment Analysis System
Real-time news aggregation with NLP sentiment analysis
"""

import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging
import re
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class SentimentScore(Enum):
    VERY_POSITIVE = 1.0
    POSITIVE = 0.5
    NEUTRAL = 0.0
    NEGATIVE = -0.5
    VERY_NEGATIVE = -1.0

@dataclass
class NewsArticle:
    title: str
    url: str
    source: str
    published_at: datetime
    content: Optional[str] = None
    symbols: List[str] = None
    sentiment: Optional[SentimentScore] = None
    importance: float = 0.5  # 0-1 scale
    metadata: Dict = None

class NewsAggregator:
    """
    Aggregates news from multiple sources with sentiment analysis
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or self._default_config()
        self.cache = {}
        self.cache_duration = 300  # 5 minutes
        self.sentiment_analyzer = SentimentAnalyzer()
        
    def _default_config(self):
        return {
            'sources': {
                'cryptocompare': {
                    'enabled': True,
                    'api_key': None,  # Add your API key
                    'base_url': 'https://min-api.cryptocompare.com/data/v2/news/'
                },
                'cryptopanic': {
                    'enabled': False,  # Requires API key
                    'api_key': None,
                    'base_url': 'https://cryptopanic.com/api/v1/posts/'
                }
            },
            'keywords': {
                'bullish': ['surge', 'rally', 'bull', 'pump', 'moon', 'ath', 'breakout', 
                           'adoption', 'partnership', 'upgrade', 'positive'],
                'bearish': ['crash', 'dump', 'bear', 'sell', 'fud', 'hack', 'ban', 
                           'regulation', 'lawsuit', 'scam', 'fraud']
            },
            'important_sources': ['reuters', 'bloomberg', 'coindesk', 'cointelegraph'],
            'alert_keywords': ['hack', 'exploit', 'sec', 'etf', 'regulation', 'ban']
        }
    
    async def fetch_news(self, symbols: List[str] = None) -> List[NewsArticle]:
        """
        Fetch news from all enabled sources
        """
        all_news = []
        
        # Check cache first
        cache_key = f"news_{','.join(symbols) if symbols else 'all'}"
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]['data']
        
        # Fetch from each source
        tasks = []
        
        if self.config['sources']['cryptocompare']['enabled']:
            tasks.append(self._fetch_cryptocompare(symbols))
            
        if self.config['sources']['cryptopanic']['enabled']:
            tasks.append(self._fetch_cryptopanic(symbols))
            
        # Gather results
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, list):
                    all_news.extend(result)
                elif isinstance(result, Exception):
                    logger.error(f"News fetch error: {str(result)}")
        
        # Sort by importance and recency
        all_news.sort(key=lambda x: (x.importance, x.published_at), reverse=True)
        
        # Analyze sentiment
        for article in all_news:
            if article.sentiment is None:
                article.sentiment = self.sentiment_analyzer.analyze(
                    article.title, 
                    article.content
                )
        
        # Cache results
        self.cache[cache_key] = {
            'data': all_news,
            'timestamp': datetime.now()
        }
        
        return all_news
    
    async def _fetch_cryptocompare(self, symbols: List[str] = None) -> List[NewsArticle]:
        """
        Fetch news from CryptoCompare
        """
        articles = []
        
        try:
            url = self.config['sources']['cryptocompare']['base_url']
            params = {'lang': 'EN'}
            
            if symbols:
                params['categories'] = ','.join([s.split('-')[0] for s in symbols])
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        for item in data.get('Data', [])[:20]:  # Limit to 20 articles
                            article = NewsArticle(
                                title=item.get('title', ''),
                                url=item.get('url', ''),
                                source=item.get('source', 'CryptoCompare'),
                                published_at=datetime.fromtimestamp(item.get('published_on', 0)),
                                content=item.get('body', ''),
                                symbols=self._extract_symbols(item.get('title', '') + ' ' + item.get('body', '')),
                                importance=self._calculate_importance(item)
                            )
                            articles.append(article)
                            
        except Exception as e:
            logger.error(f"CryptoCompare fetch error: {str(e)}")
            
        return articles
    
    async def _fetch_cryptopanic(self, symbols: List[str] = None) -> List[NewsArticle]:
        """
        Fetch news from CryptoPanic (requires API key)
        """
        articles = []
        
        if not self.config['sources']['cryptopanic']['api_key']:
            return articles
            
        try:
            url = self.config['sources']['cryptopanic']['base_url']
            params = {
                'auth': self.config['sources']['cryptopanic']['api_key'],
                'public': 'true'
            }
            
            if symbols:
                params['currencies'] = ','.join([s.split('-')[0].lower() for s in symbols])
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        for item in data.get('results', [])[:20]:
                            article = NewsArticle(
                                title=item.get('title', ''),
                                url=item.get('url', ''),
                                source=item.get('source', {}).get('title', 'CryptoPanic'),
                                published_at=datetime.fromisoformat(item.get('published_at', '')),
                                symbols=self._extract_symbols(item.get('title', '')),
                                importance=self._calculate_importance_cryptopanic(item),
                                metadata={'votes': item.get('votes', {})}
                            )
                            articles.append(article)
                            
        except Exception as e:
            logger.error(f"CryptoPanic fetch error: {str(e)}")
            
        return articles
    
    def _extract_symbols(self, text: str) -> List[str]:
        """
        Extract cryptocurrency symbols from text
        """
        symbols = []
        
        # Common crypto symbols
        symbol_patterns = [
            r'\bBTC\b', r'\bETH\b', r'\bBNB\b', r'\bSOL\b', r'\bADA\b',
            r'\bDOGE\b', r'\bXRP\b', r'\bDOT\b', r'\bUNI\b', r'\bLINK\b',
            r'Bitcoin', r'Ethereum', r'Binance', r'Solana', r'Cardano'
        ]
        
        for pattern in symbol_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                # Map to standard symbol
                if 'BTC' in pattern or 'Bitcoin' in pattern:
                    symbols.append('BTC-USD')
                elif 'ETH' in pattern or 'Ethereum' in pattern:
                    symbols.append('ETH-USD')
                elif 'BNB' in pattern or 'Binance' in pattern:
                    symbols.append('BNB-USD')
                # Add more mappings as needed
                    
        return list(set(symbols))
    
    def _calculate_importance(self, article_data: Dict) -> float:
        """
        Calculate article importance score
        """
        importance = 0.5
        
        # Check source credibility
        source = article_data.get('source', '').lower()
        if any(imp_src in source for imp_src in self.config['important_sources']):
            importance += 0.2
            
        # Check for alert keywords
        text = (article_data.get('title', '') + ' ' + article_data.get('body', '')).lower()
        if any(keyword in text for keyword in self.config['alert_keywords']):
            importance += 0.3
            
        # Normalize to 0-1
        importance = min(1.0, importance)
        
        return importance
    
    def _calculate_importance_cryptopanic(self, article_data: Dict) -> float:
        """
        Calculate importance for CryptoPanic articles
        """
        importance = 0.5
        
        votes = article_data.get('votes', {})
        
        # Use voting data
        positive = votes.get('positive', 0)
        negative = votes.get('negative', 0)
        total = positive + negative
        
        if total > 10:
            importance += 0.2
        if total > 50:
            importance += 0.2
            
        # Check if it's marked as important
        if votes.get('important', 0) > 5:
            importance += 0.1
            
        return min(1.0, importance)
    
    def _is_cache_valid(self, key: str) -> bool:
        """
        Check if cached data is still valid
        """
        if key not in self.cache:
            return False
            
        cache_time = self.cache[key].get('timestamp')
        if not cache_time:
            return False
            
        return (datetime.now() - cache_time).seconds < self.cache_duration
    
    async def get_market_sentiment(self, symbols: List[str] = None) -> Dict:
        """
        Get overall market sentiment
        """
        news = await self.fetch_news(symbols)
        
        if not news:
            return {
                'sentiment': 'neutral',
                'score': 0,
                'article_count': 0
            }
        
        # Calculate weighted sentiment
        total_weight = 0
        weighted_sentiment = 0
        
        for article in news:
            weight = article.importance
            sentiment_value = article.sentiment.value if article.sentiment else 0
            
            weighted_sentiment += sentiment_value * weight
            total_weight += weight
            
        if total_weight > 0:
            avg_sentiment = weighted_sentiment / total_weight
        else:
            avg_sentiment = 0
            
        # Determine sentiment label
        if avg_sentiment > 0.3:
            sentiment_label = 'bullish'
        elif avg_sentiment < -0.3:
            sentiment_label = 'bearish'
        else:
            sentiment_label = 'neutral'
            
        return {
            'sentiment': sentiment_label,
            'score': avg_sentiment,
            'article_count': len(news),
            'top_articles': news[:5]  # Top 5 most important
        }


class SentimentAnalyzer:
    """
    Analyze sentiment of news articles
    """
    
    def __init__(self):
        self.positive_words = {
            'surge', 'rally', 'bull', 'bullish', 'pump', 'moon', 'ath', 
            'breakout', 'adoption', 'partnership', 'upgrade', 'positive',
            'gain', 'rise', 'increase', 'growth', 'profit', 'success',
            'breakthrough', 'innovation', 'support', 'boost', 'optimistic'
        }
        
        self.negative_words = {
            'crash', 'dump', 'bear', 'bearish', 'sell', 'fud', 'hack',
            'ban', 'regulation', 'lawsuit', 'scam', 'fraud', 'loss',
            'decline', 'drop', 'fall', 'plunge', 'risk', 'warning',
            'investigation', 'concern', 'weakness', 'failure', 'pessimistic'
        }
        
        self.intensifiers = {
            'very', 'extremely', 'highly', 'significantly', 'major',
            'massive', 'huge', 'tremendous', 'severe', 'critical'
        }
        
    def analyze(self, title: str, content: str = None) -> SentimentScore:
        """
        Analyze sentiment of text
        """
        # Combine title and content
        text = title.lower()
        if content:
            text += ' ' + content.lower()
            
        # Count positive and negative words
        positive_count = 0
        negative_count = 0
        intensifier_count = 0
        
        words = text.split()
        
        for i, word in enumerate(words):
            # Remove punctuation
            word = re.sub(r'[^\w\s]', '', word)
            
            if word in self.positive_words:
                positive_count += 1
                # Check for intensifier before
                if i > 0 and words[i-1] in self.intensifiers:
                    positive_count += 0.5
                    
            elif word in self.negative_words:
                negative_count += 1
                # Check for intensifier before
                if i > 0 and words[i-1] in self.intensifiers:
                    negative_count += 0.5
                    
            elif word in self.intensifiers:
                intensifier_count += 1
        
        # Calculate sentiment score
        total = positive_count + negative_count
        
        if total == 0:
            return SentimentScore.NEUTRAL
            
        sentiment_ratio = (positive_count - negative_count) / total
        
        # Apply intensifier boost
        if intensifier_count > 0:
            sentiment_ratio *= (1 + intensifier_count * 0.1)
            
        # Map to sentiment categories
        if sentiment_ratio > 0.5:
            return SentimentScore.VERY_POSITIVE
        elif sentiment_ratio > 0.2:
            return SentimentScore.POSITIVE
        elif sentiment_ratio < -0.5:
            return SentimentScore.VERY_NEGATIVE
        elif sentiment_ratio < -0.2:
            return SentimentScore.NEGATIVE
        else:
            return SentimentScore.NEUTRAL
    
    def analyze_batch(self, articles: List[NewsArticle]) -> List[NewsArticle]:
        """
        Analyze sentiment for multiple articles
        """
        for article in articles:
            if article.sentiment is None:
                article.sentiment = self.analyze(article.title, article.content)
                
        return articles


class NewsAlertSystem:
    """
    Alert system for critical news events
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.alert_handlers = []
        self.sent_alerts = set()  # Track sent alerts to avoid duplicates
        
    def add_handler(self, handler):
        """
        Add alert handler (e.g., Telegram, Email)
        """
        self.alert_handlers.append(handler)
        
    async def check_alerts(self, news_articles: List[NewsArticle]):
        """
        Check news for alert conditions
        """
        critical_keywords = [
            'hack', 'exploit', 'stolen', 'sec', 'etf', 
            'ban', 'delisted', 'lawsuit', 'arrested'
        ]
        
        for article in news_articles:
            # Skip if already alerted
            alert_id = f"{article.url}_{article.published_at}"
            if alert_id in self.sent_alerts:
                continue
                
            # Check for critical keywords
            text = (article.title + ' ' + (article.content or '')).lower()
            
            is_critical = False
            triggered_keywords = []
            
            for keyword in critical_keywords:
                if keyword in text:
                    is_critical = True
                    triggered_keywords.append(keyword)
                    
            # Check sentiment for extreme cases
            if article.sentiment in [SentimentScore.VERY_NEGATIVE, SentimentScore.VERY_POSITIVE]:
                if article.importance > 0.7:
                    is_critical = True
                    
            if is_critical:
                await self._send_alert(article, triggered_keywords)
                self.sent_alerts.add(alert_id)
                
    async def _send_alert(self, article: NewsArticle, keywords: List[str]):
        """
        Send alert through all handlers
        """
        alert_message = f"""
🚨 CRITICAL NEWS ALERT 🚨

Title: {article.title}
Source: {article.source}
Time: {article.published_at}
Symbols: {', '.join(article.symbols) if article.symbols else 'General'}
Sentiment: {article.sentiment.name if article.sentiment else 'Unknown'}
Keywords: {', '.join(keywords) if keywords else 'N/A'}

URL: {article.url}
"""
        
        for handler in self.alert_handlers:
            try:
                await handler.send(alert_message)
            except Exception as e:
                logger.error(f"Alert handler error: {str(e)}")
                
    def clear_old_alerts(self, hours: int = 24):
        """
        Clear old alerts to allow re-alerting after time period
        """
        # This would need timestamp tracking in sent_alerts
        # For now, just clear all after specified time
        self.sent_alerts.clear()