"""
Free Whale Alert System
Tracks large cryptocurrency transactions using free blockchain explorers
"""

import asyncio
import aiohttp
import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone
import json

logger = logging.getLogger(__name__)

class FreeWhaleTracker:
    """Track whale transactions without paid APIs"""
    
    def __init__(self, config):
        self.config = config
        self.session = None
        self.api_key_index = 0
        
        # Known exchange and whale addresses to monitor
        self.whale_addresses = {
            'bitcoin': [
                '1P5ZEDWTKTFGxQjZphgWPQUpe554WKDfHQ',  # Bitfinex cold wallet
                '1FeexV6bAHb8ybZjqQMjJrcCrHGW9sb6uF',  # Bitcoin rich list
                '3Cbq7aT1tY8kMxWLbitaG7yT6bPbKChq64'   # Known whale
            ],
            'ethereum': [
                '0xBE0eB53F46cd790Cd13851d5EFf43D12404d33E8',  # Binance hot wallet
                '0x8315177aB297bA92A06054cE80a67Ed4DBd7ed3a',  # Bitfinex wallet
                '0x267be1C1D684F78cb4F6a176C4911b741E4Ffdc0',  # Kraken wallet
                '0x6262998Ced04146fA42253a5C0AF90CA02dfd2A3',  # Crypto.com wallet
            ]
        }
        
    async def start(self):
        """Start whale tracking"""
        self.session = aiohttp.ClientSession()
        logger.info("Whale Tracker started")
        
    async def stop(self):
        """Stop whale tracking"""
        if self.session:
            await self.session.close()
        logger.info("Whale Tracker stopped")
        
    def rotate_etherscan_key(self) -> str:
        """Rotate through free Etherscan API keys"""
        key = self.config.ETHERSCAN_API_KEYS[self.api_key_index]
        self.api_key_index = (self.api_key_index + 1) % len(self.config.ETHERSCAN_API_KEYS)
        return key
        
    async def track_ethereum_whales(self) -> List[Dict]:
        """Track Ethereum whale transactions using free Etherscan API"""
        whale_transactions = []
        
        try:
            api_key = self.rotate_etherscan_key()
            
            for address in self.whale_addresses['ethereum']:
                url = "https://api.etherscan.io/api"
                params = {
                    'module': 'account',
                    'action': 'txlist',
                    'address': address,
                    'startblock': '0',
                    'endblock': 'latest',
                    'page': '1',
                    'offset': '10',  # Last 10 transactions
                    'sort': 'desc',
                    'apikey': api_key
                }
                
                async with self.session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get('status') == '1':
                            for tx in data.get('result', []):
                                value_eth = int(tx.get('value', 0)) / (10**18)  # Wei to ETH
                                
                                if value_eth >= self.config.WHALE_THRESHOLD_ETH:
                                    # Get ETH price to calculate USD value
                                    eth_price = await self.get_eth_price()
                                    value_usd = value_eth * eth_price
                                    
                                    whale_tx = {
                                        'blockchain': 'ethereum',
                                        'hash': tx.get('hash'),
                                        'from': tx.get('from'),
                                        'to': tx.get('to'),
                                        'value_eth': value_eth,
                                        'value_usd': value_usd,
                                        'timestamp': datetime.fromtimestamp(int(tx.get('timeStamp', 0))).isoformat(),
                                        'block_number': tx.get('blockNumber'),
                                        'gas_used': tx.get('gasUsed'),
                                        'status': 'success' if tx.get('txreceipt_status') == '1' else 'failed'
                                    }
                                    
                                    whale_transactions.append(whale_tx)
                    
                # Rate limiting between requests
                await asyncio.sleep(0.2)  # 5 requests per second max
                
        except Exception as e:
            logger.error(f"Ethereum whale tracking error: {e}")
            
        return whale_transactions
        
    async def track_bitcoin_whales(self) -> List[Dict]:
        """Track Bitcoin whale transactions using free BlockCypher API"""
        whale_transactions = []
        
        try:
            for address in self.whale_addresses['bitcoin']:
                url = f"https://api.blockcypher.com/v1/btc/main/addrs/{address}/txs"
                params = {'limit': 10}  # Last 10 transactions
                
                headers = {
                    'User-Agent': self.config.get_random_user_agent()
                }
                
                async with self.session.get(url, params=params, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        for tx in data:
                            # Calculate transaction value
                            total_value = sum(output.get('value', 0) for output in tx.get('outputs', []))
                            value_btc = total_value / (10**8)  # Satoshi to BTC
                            
                            if value_btc >= self.config.WHALE_THRESHOLD_BTC:
                                # Get BTC price
                                btc_price = await self.get_btc_price()
                                value_usd = value_btc * btc_price
                                
                                whale_tx = {
                                    'blockchain': 'bitcoin',
                                    'hash': tx.get('hash'),
                                    'value_btc': value_btc,
                                    'value_usd': value_usd,
                                    'timestamp': tx.get('received', ''),
                                    'block_height': tx.get('block_height'),
                                    'confirmations': tx.get('confirmations', 0)
                                }
                                
                                whale_transactions.append(whale_tx)
                
                # Rate limiting
                await asyncio.sleep(1.0)  # 1 request per second
                
        except Exception as e:
            logger.error(f"Bitcoin whale tracking error: {e}")
            
        return whale_transactions
        
    async def get_btc_price(self) -> float:
        """Get current BTC price for USD calculations"""
        try:
            url = f"{self.config.COINGECKO_BASE_URL}/simple/price?ids=bitcoin&vs_currencies=usd"
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('bitcoin', {}).get('usd', 50000)
        except:
            return 50000  # Fallback price
            
    async def get_eth_price(self) -> float:
        """Get current ETH price for USD calculations"""
        try:
            url = f"{self.config.COINGECKO_BASE_URL}/simple/price?ids=ethereum&vs_currencies=usd"
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('ethereum', {}).get('usd', 3000)
        except:
            return 3000  # Fallback price
            
    async def analyze_whale_impact(self, whale_tx: Dict) -> Dict:
        """Analyze potential market impact of whale transaction"""
        impact_score = 0
        impact_level = "low"
        
        # Calculate impact based on transaction size
        value_usd = whale_tx.get('value_usd', 0)
        
        if value_usd > 10000000:  # $10M+
            impact_score = 95
            impact_level = "extreme"
        elif value_usd > 5000000:  # $5M+
            impact_score = 80
            impact_level = "very_high"
        elif value_usd > 1000000:  # $1M+
            impact_score = 60
            impact_level = "high"
        elif value_usd > 500000:   # $500K+
            impact_score = 40
            impact_level = "medium"
        else:
            impact_score = 20
            impact_level = "low"
            
        # Check if it's exchange movement (less impactful)
        from_exchange = any(whale_tx.get('from', '').lower() in addr.lower() 
                           for addr in self.whale_addresses.values() for addr_list in addr for addr in addr_list)
        to_exchange = any(whale_tx.get('to', '').lower() in addr.lower() 
                         for addr in self.whale_addresses.values() for addr_list in addr for addr in addr_list)
        
        if from_exchange or to_exchange:
            impact_score *= 0.7  # Exchange movements less impactful
            
        whale_tx.update({
            'impact_score': impact_score,
            'impact_level': impact_level,
            'is_exchange_movement': from_exchange or to_exchange,
            'analysis_timestamp': datetime.now(timezone.utc).isoformat()
        })
        
        return whale_tx
        
    async def get_whale_alerts(self) -> List[Dict]:
        """Get all whale alerts from multiple blockchains"""
        whale_alerts = []
        
        # Collect from multiple blockchains
        eth_whales = await self.track_ethereum_whales()
        btc_whales = await self.track_bitcoin_whales()
        
        # Combine and analyze
        all_whales = eth_whales + btc_whales
        
        for whale_tx in all_whales:
            analyzed_whale = await self.analyze_whale_impact(whale_tx)
            
            # Only include significant transactions
            if analyzed_whale['impact_score'] >= 40:
                whale_alerts.append(analyzed_whale)
                
        # Sort by impact score
        whale_alerts.sort(key=lambda x: x['impact_score'], reverse=True)
        
        return whale_alerts[:20]  # Top 20 whale alerts