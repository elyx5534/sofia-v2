#!/usr/bin/env python3
"""
Sofia V2 UI Server Startup Script
Starts the Flask UI server with proper configuration
"""

import os
import sys
import subprocess
from dotenv import load_dotenv
from pathlib import Path

def load_environment():
    """Load environment variables"""
    # Load root .env first
    root_env = Path(__file__).parent / '.env'
    if root_env.exists():
        load_dotenv(root_env)
        print(f"[OK] Loaded root environment from: {root_env}")
    
    # Load UI-specific .env
    ui_env = Path(__file__).parent / 'sofia_ui' / '.env'
    if ui_env.exists():
        load_dotenv(ui_env)
        print(f"[OK] Loaded UI environment from: {ui_env}")
    
    # Set defaults
    os.environ.setdefault('UI_PORT', '8004')
    os.environ.setdefault('FLASK_ENV', 'development')

def main():
    """Main entry point for the UI server"""
    load_environment()
    
    ui_port = int(os.getenv('UI_PORT', 8004))
    flask_env = os.getenv('FLASK_ENV', 'development')
    
    print("[START] Starting Sofia V2 UI Server")
    print(f"[PORT] Port: {ui_port}")
    print(f"[ENV] Environment: {flask_env}")
    
    # Change to UI directory
    ui_dir = Path(__file__).parent / 'sofia_ui'
    os.chdir(ui_dir)
    
    try:
        # Start the UI server
        subprocess.run([
            sys.executable, 'server.py'
        ], check=True)
    except KeyboardInterrupt:
        print("[STOP] UI server shutdown requested by user")
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] UI server startup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()