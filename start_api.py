#!/usr/bin/env python3
"""
Sofia V2 API Server Startup Script
Starts the FastAPI server with proper configuration and environment setup
"""

import os
import sys
import uvicorn
import logging
from dotenv import load_dotenv
from pathlib import Path

def setup_logging():
    """Configure logging for the API server"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('sofia_api.log', mode='a')
        ]
    )
    return logging.getLogger(__name__)

def load_environment():
    """Load environment variables from .env file"""
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"[OK] Loaded environment from: {env_path}")
    else:
        print(f"[WARN] No .env file found at: {env_path}")
    
    # Set default values if not present
    os.environ.setdefault('API_PORT', '8023')
    os.environ.setdefault('LOG_LEVEL', 'INFO')
    os.environ.setdefault('ENVIRONMENT', 'development')

def main():
    """Main entry point for the API server"""
    logger = setup_logging()
    load_environment()
    
    # Get configuration from environment
    host = os.getenv('API_HOST', '127.0.0.1')
    port = int(os.getenv('API_PORT', 8023))
    log_level = os.getenv('LOG_LEVEL', 'info').lower()
    reload = os.getenv('ENVIRONMENT', 'development') == 'development'
    
    logger.info("[START] Starting Sofia V2 API Server")
    logger.info(f"[HOST] Host: {host}")
    logger.info(f"[PORT] Port: {port}")
    logger.info(f"[LOG] Log Level: {log_level}")
    logger.info(f"[RELOAD] Reload: {reload}")
    logger.info(f"[ENV] Environment: {os.getenv('ENVIRONMENT', 'development')}")
    
    try:
        # Start the server
        uvicorn.run(
            "src.api.main:app",
            host=host,
            port=port,
            log_level=log_level,
            reload=reload,
            reload_dirs=["src"] if reload else None,
            access_log=True,
            use_colors=True
        )
    except KeyboardInterrupt:
        logger.info("[STOP] Server shutdown requested by user")
    except Exception as e:
        logger.error(f"[ERROR] Server startup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()