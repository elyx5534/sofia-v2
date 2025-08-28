#!/usr/bin/env python3
"""
Sofia V2 Infrastructure Startup Script
Orchestrates the startup of all system components
"""

import asyncio
import logging
import os
import signal
import sys
from typing import List, Dict, Any
import subprocess
import time
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ProcessManager:
    """Manages multiple processes for Sofia V2 infrastructure"""
    
    def __init__(self):
        self.processes = {}
        self.running = False
        self.shutdown_event = asyncio.Event()
        
        # Component configurations
        self.components = {
            'metrics_server': {
                'command': ['python', '-m', 'monitoring.metrics_server'],
                'description': 'Prometheus metrics server',
                'priority': 1,
                'health_check': 'http://localhost:8000/health'
            },
            'crypto_ws': {
                'command': ['python', '-m', 'ingestors.crypto_ws'],
                'description': 'Crypto WebSocket ingester',
                'priority': 2,
                'enabled': os.getenv('ENABLE_CRYPTO_WS', 'true').lower() == 'true'
            },
            'ts_writer': {
                'command': ['python', '-m', 'writers.ts_writer'],
                'description': 'Time-series database writer',
                'priority': 2,
                'enabled': True
            },
            'equities_pull': {
                'command': ['python', '-m', 'ingestors.equities_pull'],
                'description': 'Equity data puller',
                'priority': 3,
                'enabled': os.getenv('ENABLE_EQUITIES_PULL', 'true').lower() == 'true'
            },
            'news_rss': {
                'command': ['python', '-m', 'news.rss_agg'],
                'description': 'RSS news aggregator',
                'priority': 3,
                'enabled': os.getenv('ENABLE_NEWS_RSS', 'true').lower() == 'true'
            },
            'whale_monitor': {
                'command': ['python', '-m', 'alerts.whale_trade'],
                'description': 'Whale trade monitor',
                'priority': 4,
                'enabled': os.getenv('ENABLE_WHALE_MONITOR', 'true').lower() == 'true'
            },
            'ai_featurizer': {
                'command': ['python', '-m', 'src.ai.featurizer'],
                'description': 'AI feature extractor',
                'priority': 4,
                'enabled': os.getenv('ENABLE_AI_MODELS', 'true').lower() == 'true'
            },
            'ai_model': {
                'command': ['python', '-m', 'src.ai.model'],
                'description': 'AI model manager',
                'priority': 5,
                'enabled': os.getenv('ENABLE_AI_MODELS', 'true').lower() == 'true'
            },
            'paper_trading': {
                'command': ['python', '-m', 'src.trade.paper'],
                'description': 'Paper trading engine',
                'priority': 5,
                'enabled': os.getenv('ENABLE_PAPER_TRADING', 'true').lower() == 'true'
            }
        }
    
    def check_dependencies(self) -> bool:
        """Check if required dependencies are available"""
        logger.info("Checking system dependencies...")
        
        # Check Redis
        try:
            import redis
            r = redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379'))
            r.ping()
            logger.info("✓ Redis connection successful")
        except Exception as e:
            logger.error(f"✗ Redis connection failed: {e}")
            return False
        
        # Check Python packages
        required_packages = [
            'fastapi', 'uvicorn', 'websockets', 'asyncpg', 'pandas', 
            'numpy', 'lightgbm', 'scikit-learn', 'prometheus_client'
        ]
        
        missing_packages = []
        for package in required_packages:
            try:
                __import__(package.replace('-', '_'))
                logger.debug(f"✓ {package} available")
            except ImportError:
                missing_packages.append(package)
        
        if missing_packages:
            logger.error(f"✗ Missing packages: {', '.join(missing_packages)}")
            logger.error("Run: pip install -r requirements.txt")
            return False
        
        logger.info("✓ All dependencies available")
        return True
    
    def check_configuration(self) -> bool:
        """Check if configuration is valid"""
        logger.info("Checking configuration...")
        
        # Check .env file
        env_path = Path('.env')
        if not env_path.exists():
            logger.warning("✗ .env file not found. Using .env.example defaults")
            logger.info("Consider copying .env.example to .env and customizing")
        
        # Check required directories
        required_dirs = ['logs', 'models', 'backups']
        for dir_name in required_dirs:
            dir_path = Path(dir_name)
            if not dir_path.exists():
                logger.info(f"Creating directory: {dir_name}")
                dir_path.mkdir(exist_ok=True)
        
        logger.info("✓ Configuration check complete")
        return True
    
    async def start_component(self, name: str, config: Dict[str, Any]) -> bool:
        """Start a single component"""
        if not config.get('enabled', True):
            logger.info(f"⏸️  {name}: Disabled by configuration")
            return True
        
        try:
            logger.info(f"🚀 Starting {name}: {config['description']}")
            
            # Create log directory for component
            log_dir = Path('logs')
            log_dir.mkdir(exist_ok=True)
            
            # Start process
            process = subprocess.Popen(
                config['command'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=os.getcwd(),
                env=os.environ.copy()
            )
            
            self.processes[name] = {
                'process': process,
                'config': config,
                'start_time': time.time(),
                'restart_count': 0
            }
            
            # Give process time to start
            await asyncio.sleep(2)
            
            # Check if process is still running
            if process.poll() is None:
                logger.info(f"✓ {name} started successfully (PID: {process.pid})")
                return True
            else:
                stdout, stderr = process.communicate()
                logger.error(f"✗ {name} failed to start")
                logger.error(f"STDOUT: {stdout.decode()}")
                logger.error(f"STDERR: {stderr.decode()}")
                return False
                
        except Exception as e:
            logger.error(f"✗ Failed to start {name}: {e}")
            return False
    
    async def start_all_components(self):
        """Start all components in priority order"""
        logger.info("🎯 Starting Sofia V2 Infrastructure...")
        
        # Group components by priority
        priority_groups = {}
        for name, config in self.components.items():
            priority = config.get('priority', 999)
            if priority not in priority_groups:
                priority_groups[priority] = []
            priority_groups[priority].append((name, config))
        
        # Start components in priority order
        for priority in sorted(priority_groups.keys()):
            logger.info(f"📈 Starting priority {priority} components...")
            
            # Start all components in this priority group
            tasks = []
            for name, config in priority_groups[priority]:
                task = asyncio.create_task(self.start_component(name, config))
                tasks.append(task)
            
            # Wait for all components in this priority group to start
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Check results
            failed_components = []
            for i, result in enumerate(results):
                name, _ = priority_groups[priority][i]
                if isinstance(result, Exception) or not result:
                    failed_components.append(name)
            
            if failed_components:
                logger.error(f"✗ Failed to start components: {', '.join(failed_components)}")
                # Continue anyway for non-critical components
            
            # Wait between priority groups
            if priority < max(priority_groups.keys()):
                logger.info("⏳ Waiting for components to stabilize...")
                await asyncio.sleep(5)
        
        logger.info(f"🎉 Started {len(self.processes)} components")
    
    async def monitor_components(self):
        """Monitor running components and restart if needed"""
        while self.running:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                for name, proc_info in list(self.processes.items()):
                    process = proc_info['process']
                    config = proc_info['config']
                    
                    # Check if process is still running
                    if process.poll() is not None:
                        logger.warning(f"⚠️  {name} process has stopped")
                        
                        # Get exit info
                        stdout, stderr = process.communicate()
                        exit_code = process.returncode
                        
                        logger.error(f"✗ {name} exited with code {exit_code}")
                        if stderr:
                            logger.error(f"STDERR: {stderr.decode()}")
                        
                        # Restart if enabled and not too many restarts
                        if (proc_info['restart_count'] < 5 and 
                            config.get('auto_restart', True)):
                            
                            logger.info(f"🔄 Restarting {name}...")
                            proc_info['restart_count'] += 1
                            
                            # Start new process
                            success = await self.start_component(name, config)
                            if success:
                                logger.info(f"✓ {name} restarted successfully")
                            else:
                                logger.error(f"✗ Failed to restart {name}")
                        else:
                            logger.error(f"💀 {name} disabled due to too many restarts")
                            del self.processes[name]
            
            except Exception as e:
                logger.error(f"Monitor error: {e}")
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"📡 Received signal {signum}, initiating shutdown...")
        self.running = False
        asyncio.create_task(self.shutdown())
    
    async def shutdown(self):
        """Gracefully shutdown all components"""
        logger.info("🛑 Shutting down Sofia V2 Infrastructure...")
        
        # Stop all processes
        for name, proc_info in self.processes.items():
            process = proc_info['process']
            
            logger.info(f"🔻 Stopping {name}...")
            
            try:
                # Try graceful shutdown first
                process.terminate()
                
                # Wait up to 10 seconds for graceful shutdown
                try:
                    process.wait(timeout=10)
                    logger.info(f"✓ {name} stopped gracefully")
                except subprocess.TimeoutExpired:
                    # Force kill if graceful shutdown fails
                    logger.warning(f"⚡ Force killing {name}")
                    process.kill()
                    process.wait()
                    logger.info(f"✓ {name} force stopped")
                    
            except Exception as e:
                logger.error(f"Error stopping {name}: {e}")
        
        logger.info("👋 All components stopped")
        self.shutdown_event.set()
    
    async def run(self):
        """Main run loop"""
        # Register signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        # Pre-flight checks
        if not self.check_dependencies():
            logger.error("❌ Dependency check failed")
            return False
        
        if not self.check_configuration():
            logger.error("❌ Configuration check failed")
            return False
        
        self.running = True
        
        try:
            # Start all components
            await self.start_all_components()
            
            # Start monitoring
            monitor_task = asyncio.create_task(self.monitor_components())
            
            logger.info("🎯 Sofia V2 Infrastructure is running!")
            logger.info("📊 Metrics available at: http://localhost:8000/metrics")
            logger.info("🏥 Health check at: http://localhost:8000/health")
            logger.info("Press Ctrl+C to shutdown")
            
            # Wait for shutdown signal
            await self.shutdown_event.wait()
            
            # Cancel monitoring
            monitor_task.cancel()
            
        except Exception as e:
            logger.error(f"Runtime error: {e}")
            await self.shutdown()
        
        return True


def main():
    """Main entry point"""
    print("🚀 Sofia V2 Real-Time Data Infrastructure")
    print("=" * 50)
    
    # Create and run process manager
    manager = ProcessManager()
    
    try:
        asyncio.run(manager.run())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()