import requests

# Test unified API
r1 = requests.get("http://localhost:8003/status")
print("Unified API (8003):", r1.json()["portfolio"]["total_balance"])

# Test UI server API
r2 = requests.get("http://localhost:8000/api/trading/portfolio")
print("UI Server API (8000):", r2.json()["total_balance"])