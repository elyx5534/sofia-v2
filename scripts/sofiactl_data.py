"""
Sofia Data Control CLI
"""

import argparse
import asyncio
import sys
from pathlib import Path
import httpx

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def get_status(symbols: list, base_url: str = "http://localhost:8001"):
    """Get status for specified symbols"""
    
    async with httpx.AsyncClient() as client:
        try:
            # Get debug data
            response = await client.get(f"{base_url}/data/debug")
            if response.status_code != 200:
                print(f"ERROR: Failed to get debug data: HTTP {response.status_code}")
                return
            
            debug_data = response.json()
            
            # Print header
            print(f"WebSocket: {'CONNECTED' if debug_data.get('websocket_connected') else 'DISCONNECTED'}")
            print("-" * 60)
            
            # Process each requested symbol
            for requested_symbol in symbols:
                found = False
                
                for symbol_data in debug_data.get('symbols', []):
                    if symbol_data['symbol'] == requested_symbol or symbol_data.get('ui_symbol') == requested_symbol:
                        found = True
                        
                        symbol = symbol_data['symbol']
                        price = symbol_data.get('price', 'N/A')
                        freshness = symbol_data.get('freshness_seconds', 999)
                        source = symbol_data.get('source', 'unknown')
                        
                        # Format freshness
                        if freshness < 1:
                            freshness_str = f"{freshness:.1f}s"
                        elif freshness < 60:
                            freshness_str = f"{freshness:.0f}s"
                        else:
                            freshness_str = f"{freshness/60:.1f}m"
                        
                        # One-line status
                        if isinstance(price, (int, float)):
                            print(f"{symbol:10s} ${price:10.2f} freshness={freshness_str:6s} source={source}")
                        else:
                            print(f"{symbol:10s} ${price:10s} freshness={freshness_str:6s} source={source}")
                        
                        break
                
                if not found:
                    print(f"{requested_symbol:10s} NOT FOUND")
            
        except Exception as e:
            print(f"ERROR: {e}")


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Sofia Data Control CLI')
    parser.add_argument(
        'command',
        choices=['status'],
        help='Command to execute'
    )
    parser.add_argument(
        '--symbols',
        type=str,
        default='BTCUSDT,ETHUSDT',
        help='Comma-separated list of symbols (default: BTCUSDT,ETHUSDT)'
    )
    parser.add_argument(
        '--url',
        type=str,
        default='http://localhost:8001',
        help='API base URL (default: http://localhost:8001)'
    )
    
    args = parser.parse_args()
    
    if args.command == 'status':
        symbols = args.symbols.split(',')
        await get_status(symbols, args.url)


if __name__ == '__main__':
    asyncio.run(main())