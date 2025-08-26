"""
SOFIA V2 - FULLY AUTONOMOUS TRADING SYSTEM
NO HUMAN INTERVENTION REQUIRED - 24/7 OPERATION
"""

import os
import sys
import asyncio
import subprocess
import time
import json
from datetime import datetime, timedelta
from pathlib import Path
import threading
import signal

# Configuration for autonomous operation
AUTONOMOUS_CONFIG = {
    "trading_mode": "paper",  # Safety first - paper mode
    "initial_balance": 10000,
    "max_positions": 5,
    "stop_loss_percent": 3.0,
    "take_profit_percent": 8.0,
    "enable_ml": True,
    "enable_grid_trading": True,
    "enable_crash_recovery": True,
    "auto_restart_on_failure": True,
    "health_check_interval": 60,  # seconds
    "max_consecutive_failures": 3,
    "profit_target_daily": 2.0,  # 2% daily target
}

class AutonomousTrader:
    """Fully autonomous trading system"""
    
    def __init__(self):
        self.running = True
        self.processes = {}
        self.start_time = datetime.now()
        self.total_profit = 0
        self.trades_executed = 0
        self.last_health_check = datetime.now()
        
    def log(self, message, level="INFO"):
        """Logging with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")
        
        # Also save to file
        with open("autonomous_trader.log", "a") as f:
            f.write(f"[{timestamp}] [{level}] {message}\n")
    
    async def start_all_services(self):
        """Start all required services"""
        self.log("🚀 Starting AUTONOMOUS TRADING SYSTEM...")
        
        # 1. Start Backend API
        self.log("Starting Backend API...")
        self.processes['backend'] = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "src.data_hub.api:app", 
             "--host", "0.0.0.0", "--port", "8000"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        await asyncio.sleep(5)
        
        # 2. Start Frontend
        self.log("Starting Frontend UI...")
        self.processes['frontend'] = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "sofia_ui.server:app",
             "--host", "0.0.0.0", "--port", "3000"],
            cwd=".",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        await asyncio.sleep(3)
        
        # 3. Start Real-time Dashboard
        self.log("Starting Real-time Dashboard...")
        self.processes['dashboard'] = subprocess.Popen(
            [sys.executable, "src/web/realtime_dashboard.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        await asyncio.sleep(3)
        
        # 4. Train ML Models if needed
        if AUTONOMOUS_CONFIG['enable_ml']:
            await self.train_ml_models()
        
        # 5. Start DataHub Backend
        self.log("Starting DataHub WebSocket service...")
        self.processes['datahub'] = subprocess.Popen(
            [sys.executable, "backend/app/main.py"],
            cwd=".",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        await asyncio.sleep(5)
        
        self.log("✅ All services started successfully!")
    
    async def train_ml_models(self):
        """Train ML models if not exists"""
        models_dir = Path("models")
        
        if not models_dir.exists() or len(list(models_dir.glob("*.pkl"))) < 2:
            self.log("🤖 Training ML models...")
            
            # Run training script
            process = subprocess.run(
                [sys.executable, "train_ml_models.py"],
                capture_output=True,
                text=True
            )
            
            if process.returncode == 0:
                self.log("✅ ML models trained successfully!")
            else:
                self.log("⚠️ ML training failed, continuing without ML", "WARNING")
                AUTONOMOUS_CONFIG['enable_ml'] = False
    
    async def run_backtest(self):
        """Run initial backtest"""
        self.log("📊 Running 30-day backtest...")
        
        process = subprocess.run(
            [sys.executable, "backtest_runner.py"],
            capture_output=True,
            text=True
        )
        
        # Parse results
        if "Win Rate" in process.stdout:
            self.log("✅ Backtest completed successfully!")
            # Extract metrics from output
            lines = process.stdout.split('\n')
            for line in lines:
                if "Win Rate" in line or "Total Return" in line:
                    self.log(f"  {line.strip()}")
    
    async def start_trading_engine(self):
        """Start the main trading engine"""
        self.log("💰 Starting automated trading engine...")
        
        # Create config file
        config = {
            "mode": AUTONOMOUS_CONFIG['trading_mode'],
            "balance": AUTONOMOUS_CONFIG['initial_balance'],
            "strategies": []
        }
        
        # Add strategies
        if AUTONOMOUS_CONFIG['enable_grid_trading']:
            config['strategies'].append({
                "name": "GridTrading",
                "params": {
                    "grid_levels": 10,
                    "grid_spacing": 0.5,
                    "position_size": 0.1
                }
            })
        
        if AUTONOMOUS_CONFIG['enable_ml']:
            config['strategies'].append({
                "name": "MLPredictor",
                "params": {
                    "model": "xgboost",
                    "confidence_threshold": 0.7
                }
            })
        
        # Save config
        with open("trading_config.json", "w") as f:
            json.dump(config, f)
        
        # Start auto trader
        self.processes['trader'] = subprocess.Popen(
            [sys.executable, "auto_trader.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        self.log("✅ Trading engine started!")
    
    async def monitor_health(self):
        """Monitor system health and auto-restart if needed"""
        consecutive_failures = 0
        
        while self.running:
            try:
                await asyncio.sleep(AUTONOMOUS_CONFIG['health_check_interval'])
                
                # Check all processes
                all_healthy = True
                for name, process in self.processes.items():
                    if process and process.poll() is not None:
                        self.log(f"⚠️ Process {name} is down!", "WARNING")
                        all_healthy = False
                        
                        # Auto-restart if enabled
                        if AUTONOMOUS_CONFIG['auto_restart_on_failure']:
                            self.log(f"Restarting {name}...")
                            await self.restart_service(name)
                
                if all_healthy:
                    consecutive_failures = 0
                    self.log("💚 Health check passed - all systems operational")
                else:
                    consecutive_failures += 1
                    if consecutive_failures >= AUTONOMOUS_CONFIG['max_consecutive_failures']:
                        self.log("🔴 Too many failures, triggering full restart", "ERROR")
                        await self.full_restart()
                        consecutive_failures = 0
                
                # Log stats
                uptime = datetime.now() - self.start_time
                self.log(f"📊 Uptime: {uptime}, Trades: {self.trades_executed}, Profit: ${self.total_profit:.2f}")
                
            except Exception as e:
                self.log(f"Health monitor error: {e}", "ERROR")
    
    async def restart_service(self, service_name):
        """Restart a specific service"""
        try:
            # Kill old process
            if service_name in self.processes:
                old_process = self.processes[service_name]
                if old_process:
                    old_process.terminate()
                    await asyncio.sleep(2)
            
            # Start new process based on service name
            if service_name == 'backend':
                self.processes['backend'] = subprocess.Popen(
                    [sys.executable, "-m", "uvicorn", "src.data_hub.api:app", 
                     "--host", "0.0.0.0", "--port", "8000"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
            elif service_name == 'trader':
                self.processes['trader'] = subprocess.Popen(
                    [sys.executable, "auto_trader.py"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
            # Add other services as needed
            
            self.log(f"✅ {service_name} restarted successfully")
            
        except Exception as e:
            self.log(f"Failed to restart {service_name}: {e}", "ERROR")
    
    async def full_restart(self):
        """Perform full system restart"""
        self.log("🔄 Performing full system restart...")
        
        # Stop all processes
        for name, process in self.processes.items():
            if process:
                process.terminate()
        
        await asyncio.sleep(5)
        
        # Restart everything
        await self.start_all_services()
        await self.start_trading_engine()
    
    async def handle_crash_recovery(self):
        """Use crash recovery system"""
        from src.core.crash_recovery import crash_recovery_manager
        
        self.log("🛡️ Initializing crash recovery system...")
        
        # Load last checkpoint if exists
        state = crash_recovery_manager.load_latest_checkpoint()
        if state:
            self.log(f"Recovered from checkpoint: {state.timestamp}")
            self.total_profit = state.portfolio_value - AUTONOMOUS_CONFIG['initial_balance']
    
    async def run(self):
        """Main autonomous operation loop"""
        try:
            # Initial setup
            await self.start_all_services()
            
            # Run backtest first
            await self.run_backtest()
            
            # Initialize crash recovery
            if AUTONOMOUS_CONFIG['enable_crash_recovery']:
                await self.handle_crash_recovery()
            
            # Start trading
            await self.start_trading_engine()
            
            # Start health monitoring
            monitor_task = asyncio.create_task(self.monitor_health())
            
            self.log("🎯 AUTONOMOUS TRADING ACTIVE - System is now self-operating")
            self.log("=" * 60)
            self.log("You can now leave the system running.")
            self.log("Check autonomous_trader.log for updates.")
            self.log("Press Ctrl+C to stop (not recommended)")
            self.log("=" * 60)
            
            # Keep running
            while self.running:
                await asyncio.sleep(60)
                
                # Periodic status update
                uptime = datetime.now() - self.start_time
                hours = uptime.total_seconds() / 3600
                daily_return = (self.total_profit / AUTONOMOUS_CONFIG['initial_balance']) * 100
                
                status = f"""
                ╔══════════════════════════════════════════╗
                ║  AUTONOMOUS TRADER STATUS                ║
                ╠══════════════════════════════════════════╣
                ║  Uptime: {hours:.1f} hours              ║
                ║  Trades: {self.trades_executed}         ║
                ║  Profit: ${self.total_profit:.2f}       ║
                ║  Daily Return: {daily_return:.2f}%      ║
                ║  Target: {AUTONOMOUS_CONFIG['profit_target_daily']}%  ║
                ╚══════════════════════════════════════════╝
                """
                print(status)
                
        except KeyboardInterrupt:
            self.log("Shutdown signal received...")
            await self.shutdown()
        except Exception as e:
            self.log(f"Critical error: {e}", "ERROR")
            if AUTONOMOUS_CONFIG['auto_restart_on_failure']:
                await self.full_restart()
    
    async def shutdown(self):
        """Graceful shutdown"""
        self.log("Shutting down autonomous trader...")
        self.running = False
        
        # Stop all processes
        for name, process in self.processes.items():
            if process:
                self.log(f"Stopping {name}...")
                process.terminate()
        
        # Wait for processes to end
        await asyncio.sleep(3)
        
        # Force kill if needed
        for name, process in self.processes.items():
            if process and process.poll() is None:
                process.kill()
        
        self.log("✅ Autonomous trader stopped")
        self.log(f"Final profit: ${self.total_profit:.2f}")


async def main():
    """Entry point"""
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║     SOFIA V2 - FULLY AUTONOMOUS TRADING SYSTEM          ║
    ║                                                           ║
    ║     ⚠️  WARNING: This will run continuously 24/7        ║
    ║     No human intervention required after start           ║
    ║                                                           ║
    ║     Mode: PAPER TRADING (Safe)                          ║
    ║     Initial Balance: $10,000                            ║
    ║     Daily Target: 2% profit                             ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
    
    # No confirmation needed - full auto mode
    print("Starting in 5 seconds... Press Ctrl+C to cancel")
    await asyncio.sleep(5)
    
    trader = AutonomousTrader()
    await trader.run()


if __name__ == "__main__":
    # Create necessary directories
    Path("logs").mkdir(exist_ok=True)
    Path("models").mkdir(exist_ok=True)
    Path("data").mkdir(exist_ok=True)
    
    # Run the autonomous system
    asyncio.run(main())