"""Simple server without any dependencies"""
import os
import sys

# Clear all problematic env vars
for key in list(os.environ.keys()):
    if any(x in key.upper() for x in ['CORS', 'VITE', 'BASE_CURRENCY', 'REFRESH']):
        del os.environ[key]

# Add path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Disable auth
os.environ["AUTH_DISABLED"] = "true"

# Start server
os.chdir("sofia_ui")
os.system("python server.py")