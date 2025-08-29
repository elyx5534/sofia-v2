#!/usr/bin/env python3
"""
Sofia V2 Full Stack Startup Script
Starts both API and UI servers with proper orchestration
"""

import os
import sys
import time
import signal
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from pathlib import Path

class SofiaOrchestrator:
    def __init__(self):
        self.processes = []
        self.shutdown = False
        
    def load_environment(self):
        """Load all environment configurations"""
        # Load root .env
        root_env = Path(__file__).parent / '.env'
        if root_env.exists():
            load_dotenv(root_env)
            print(f"✅ Loaded root environment from: {root_env}")
        
        # Load UI .env
        ui_env = Path(__file__).parent / 'sofia_ui' / '.env'
        if ui_env.exists():
            load_dotenv(ui_env)
            print(f"✅ Loaded UI environment from: {ui_env}")
        
        # Set defaults
        os.environ.setdefault('API_PORT', '8023')
        os.environ.setdefault('UI_PORT', '8004')
    
    def start_api_server(self):
        """Start the API server"""
        print("🚀 Starting Sofia V2 API Server...")
        try:
            process = subprocess.Popen([
                sys.executable, 'start_api.py'
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.processes.append(('API', process))
            
            # Wait a moment for startup
            time.sleep(2)
            if process.poll() is None:
                print("✅ API Server started successfully")
            else:
                stdout, stderr = process.communicate()
                print(f"❌ API Server failed to start: {stderr}")
                return False
            return True
        except Exception as e:
            print(f"❌ Failed to start API server: {e}")
            return False
    
    def start_ui_server(self):
        """Start the UI server"""
        print("🎨 Starting Sofia V2 UI Server...")
        try:
            process = subprocess.Popen([
                sys.executable, 'start_ui.py'
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.processes.append(('UI', process))
            
            # Wait a moment for startup
            time.sleep(2)
            if process.poll() is None:
                print("✅ UI Server started successfully")
            else:
                stdout, stderr = process.communicate()
                print(f"❌ UI Server failed to start: {stderr}")
                return False
            return True
        except Exception as e:
            print(f"❌ Failed to start UI server: {e}")
            return False
    
    def check_health(self):
        """Check health of all services"""
        import requests
        api_port = int(os.getenv('API_PORT', 8023))
        ui_port = int(os.getenv('UI_PORT', 8004))
        
        services = {
            'API': f'http://127.0.0.1:{api_port}/health',
            'UI': f'http://127.0.0.1:{ui_port}/'
        }
        
        for service, url in services.items():
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    print(f"✅ {service} is healthy")
                else:
                    print(f"⚠️ {service} returned status {response.status_code}")
            except Exception as e:
                print(f"❌ {service} health check failed: {e}")
    
    def shutdown_all(self):
        """Shutdown all processes gracefully"""
        print("\n🛑 Shutting down Sofia V2...")
        self.shutdown = True
        
        for name, process in self.processes:
            if process.poll() is None:  # Still running
                print(f"🔄 Stopping {name} server...")
                try:
                    process.terminate()
                    process.wait(timeout=10)
                    print(f"✅ {name} server stopped")
                except subprocess.TimeoutExpired:
                    print(f"⚠️ Force killing {name} server...")
                    process.kill()
        
        print("👋 Sofia V2 shutdown complete")
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\n📡 Received signal {signum}")
        self.shutdown_all()
        sys.exit(0)
    
    def run(self):
        """Main orchestration loop"""
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        print("🌟 Sofia V2 Full Stack Starting...")
        print("=" * 50)
        
        # Load environment
        self.load_environment()
        
        # Start services
        if not self.start_api_server():
            print("❌ Failed to start API server. Exiting.")
            return False
            
        time.sleep(3)  # Give API time to fully start
        
        if not self.start_ui_server():
            print("❌ Failed to start UI server. Shutting down API...")
            self.shutdown_all()
            return False
        
        # Services started successfully
        time.sleep(5)  # Give UI time to start
        
        print("\n" + "=" * 50)
        print("🎉 Sofia V2 is running!")
        print(f"🔗 API: http://127.0.0.1:{os.getenv('API_PORT', 8023)}")
        print(f"🔗 UI:  http://127.0.0.1:{os.getenv('UI_PORT', 8004)}")
        print("=" * 50)
        
        # Health check
        print("\n🔍 Performing health checks...")
        self.check_health()
        
        # Keep running until shutdown
        try:
            while not self.shutdown:
                time.sleep(1)
                # Check if any process died
                for name, process in self.processes:
                    if process.poll() is not None:
                        print(f"❌ {name} server died unexpectedly")
                        self.shutdown_all()
                        return False
        except KeyboardInterrupt:
            self.shutdown_all()
        
        return True

def main():
    """Main entry point"""
    orchestrator = SofiaOrchestrator()
    success = orchestrator.run()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()