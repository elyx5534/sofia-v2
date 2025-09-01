"""
Paper Trading main module for Sofia V2.
Runs the paper trading engine with configured strategies.
"""

import asyncio
import logging
import os
import sys
import signal
from pathlib import Path
from typing import Dict, Any

import redis.asyncio as redis
import yaml
import httpx  # Use HTTP API instead of driver
from dotenv import load_dotenv
from nats.aio.client import Client as NATS

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sofia_backtest.paper.engine import PaperTradingEngine, Order, OrderSide
from sofia_strategies import GridStrategy, TrendStrategy

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PaperTradingRunner:
    """Orchestrates paper trading with strategies"""
    
    def __init__(self):
        self.engine = None
        self.strategies = {}
        self.nats_client = None
        self.redis_client = None
        self.ch_url = "http://localhost:8123"
        self.running = False
        
    async def initialize(self):
        """Initialize all components"""
        # Load environment
        load_dotenv(".env.paper")
        
        # Load configuration
        config = self.load_config()
        
        # Initialize connections
        await self.setup_connections()
        
        # Initialize engine
        self.engine = PaperTradingEngine(config.get("engine", {}))
        await self.engine.initialize(
            self.nats_client,
            self.redis_client,
            self.ch_url
        )
        
        # Initialize strategies
        await self.setup_strategies(config.get("strategies", {}))
        
        logger.info("Paper trading runner initialized")
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from files"""
        config = {
            "engine": {
                "paper_balance_usd": float(os.getenv("PAPER_BALANCE_USD", "10000")),
                "fee_bps": 10,
                "slippage_bps": 3,
                "risk": {
                    "max_position_usd": 100,
                    "max_drawdown_pct": 15,
                    "risk_pair_pct": 1.0,
                    "total_risk_pct": 10.0
                }
            },
            "strategies": {}
        }
        
        # Load strategy configs if available
        strategy_dir = Path("configs/strategies")
        if strategy_dir.exists():
            for config_file in strategy_dir.glob("*.yaml"):
                with open(config_file) as f:
                    strategy_config = yaml.safe_load(f)
                    strategy_name = config_file.stem
                    config["strategies"][strategy_name] = strategy_config.get("default", {})
        
        return config
    
    async def setup_connections(self):
        """Setup external connections"""
        # NATS
        self.nats_client = NATS()
        nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
        await self.nats_client.connect(nats_url)
        logger.info(f"Connected to NATS: {nats_url}")
        
        # Redis
        self.redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            decode_responses=False
        )
        await self.redis_client.ping()
        logger.info("Connected to Redis")
        
        # ClickHouse HTTP endpoint
        self.ch_url = f"http://{os.getenv('CLICKHOUSE_HOST', 'localhost')}:8123"
        logger.info(f"Using ClickHouse HTTP API: {self.ch_url}")
    
    async def setup_strategies(self, configs: Dict[str, Any]):
        """Initialize trading strategies"""
        # Get symbols from environment
        symbols_str = os.getenv("SYMBOLS", "BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT")
        symbols = [s.strip() for s in symbols_str.split(",")]
        
        # Load portfolio config if available
        portfolio_file = Path("configs/portfolio/paper_default.yaml")
        portfolio_config = {}
        
        if portfolio_file.exists():
            with open(portfolio_file) as f:
                portfolio_data = yaml.safe_load(f)
                allocations = portfolio_data.get("allocations", {})
                
                for symbol, allocation in allocations.items():
                    strategy_type = allocation.get("strategy", "grid")
                    config_profile = allocation.get("config_profile", "default")
                    
                    # Get strategy config
                    if strategy_type in configs:
                        strategy_config = configs[strategy_type].get(config_profile, {})
                    else:
                        strategy_config = {}
                    
                    # Create strategy instance
                    if strategy_type == "grid":
                        strategy = GridStrategy(strategy_config)
                    elif strategy_type == "trend":
                        strategy = TrendStrategy(strategy_config)
                    else:
                        logger.warning(f"Unknown strategy type: {strategy_type}")
                        continue
                    
                    strategy.initialize(symbol, None)
                    self.strategies[symbol] = strategy
                    logger.info(f"Initialized {strategy_type} strategy for {symbol}")
        else:
            # Default: Grid for ETH/BNB, Trend for BTC/SOL
            for symbol in symbols:
                if symbol in ["BTCUSDT", "SOLUSDT"]:
                    strategy = TrendStrategy(configs.get("trend", {}).get("default", {}))
                else:
                    strategy = GridStrategy(configs.get("grid", {}).get("default", {}))
                
                strategy.initialize(symbol, None)
                self.strategies[symbol] = strategy
                logger.info(f"Initialized {strategy.__class__.__name__} for {symbol}")
    
    async def process_signals(self):
        """Process strategy signals and submit orders"""
        
        async def handle_tick(msg):
            """Handle incoming tick and generate signals"""
            try:
                import orjson
                tick_data = orjson.loads(msg.data)
                symbol = tick_data.get("symbol")
                
                if symbol not in self.strategies:
                    return
                
                strategy = self.strategies[symbol]
                
                # Generate signals from tick
                signals = strategy.on_tick(tick_data)
                
                # Submit orders for each signal
                for signal in signals:
                    order = Order(
                        symbol=signal.symbol,
                        side=OrderSide.BUY if signal.signal_type.value == "buy" else OrderSide.SELL,
                        price=signal.price or tick_data["price"],
                        quantity=signal.quantity,
                        strategy=signal.strategy
                    )
                    
                    success = await self.engine.submit_order(order)
                    
                    if success:
                        logger.info(f"Order submitted: {signal.symbol} {signal.signal_type.value} "
                                  f"{signal.quantity:.6f} @ {order.price:.2f}")
                    
            except Exception as e:
                logger.error(f"Error processing signal: {e}")
        
        # Subscribe to tick data
        await self.nats_client.subscribe("ticks.*", cb=handle_tick)
        logger.info("Signal processor started")
    
    async def run(self):
        """Main run loop"""
        self.running = True
        
        # Start engine
        engine_task = asyncio.create_task(self.engine.run())
        
        # Start signal processor
        await self.process_signals()
        
        # Keep running
        try:
            while self.running:
                await asyncio.sleep(1)
                
                # Periodic status update
                if int(asyncio.get_event_loop().time()) % 30 == 0:
                    await self.engine.log_metrics()
                    
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            self.running = False
            await self.engine.stop()
            engine_task.cancel()
    
    async def shutdown(self):
        """Clean shutdown"""
        self.running = False
        
        if self.engine:
            await self.engine.stop()
        
        if self.nats_client:
            await self.nats_client.close()
        
        if self.redis_client:
            await self.redis_client.close()
        
        # No need to disconnect HTTP client
        
        logger.info("Paper trading runner shutdown complete")


async def main():
    """Main entry point"""
    logger.info("Starting Sofia V2 Paper Trading")
    
    runner = PaperTradingRunner()
    
    # Setup signal handlers
    def signal_handler(sig, frame):
        logger.info("Received shutdown signal")
        asyncio.create_task(runner.shutdown())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await runner.initialize()
        await runner.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await runner.shutdown()


if __name__ == "__main__":
    # Windows event loop policy
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main())