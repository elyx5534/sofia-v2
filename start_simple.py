"""Simple server starter without auth dependencies"""

import os
import sys

import uvicorn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Disable auth by setting env
os.environ["AUTH_ENABLED"] = "false"

if __name__ == "__main__":
    uvicorn.run("sofia_ui.server:app", host="127.0.0.1", port=8000, reload=True)
