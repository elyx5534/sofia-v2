"""Launch script for Sofia Trading Platform Web UI."""

import sys
from pathlib import Path

import uvicorn

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

if __name__ == "__main__":
    print(
        """
    ================================================
         Sofia Trading Platform v2.0 - Web UI
           Professional Trading Dashboard
    ================================================

    Starting web server...
    Dashboard will be available at: http://localhost:8001

    Features:
    - Real-time market data (Yahoo Finance)
    - Live trading simulation
    - WebSocket updates
    - Portfolio tracking
    - AI market analysis

    Press Ctrl+C to stop the server.
    """
    )

    uvicorn.run("src.web_ui.app:app", host="0.0.0.0", port=8001, reload=True, log_level="info")
