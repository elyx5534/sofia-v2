#!/usr/bin/env python3
"""
Launch the Sofia V2 Developer Dashboard
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    import uvicorn
    from src.monitoring.dev_dashboard import app
    
    print("[INFO] Starting Sofia V2 Developer Dashboard...")
    print("[INFO] Open http://localhost:8001 in your browser")
    print("[INFO] Press Ctrl+C to stop")
    
    uvicorn.run("src.monitoring.dev_dashboard:app", host="0.0.0.0", port=8001, reload=True)