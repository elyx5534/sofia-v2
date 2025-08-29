# Sofia V2 UI Routes Inventory

## Route Status Report
**Generated:** 2025-08-29
**UI Server:** http://127.0.0.1:8002
**API Server:** http://127.0.0.1:8020

## Available Templates

### Core Pages
| Route | Template | Status | Description |
|-------|----------|--------|-------------|
| `/` | homepage.html | ✅ Working | Main dashboard with sidebar and portfolio overview |
| `/dashboard` | dashboard_*.html | ❌ Not Routed | Various dashboard versions available |
| `/portfolio` | portfolio.html | ❌ Not Routed | Portfolio management page |
| `/markets` | markets.html | ❌ Not Routed | Live market data display |
| `/trading` | ai_trading.html | ❌ Not Routed | AI-powered trading interface |
| `/manual-trading` | manual_trading.html | ❌ Not Routed | Manual trading interface |
| `/backtest` | backtest.html | ❌ Not Routed | Strategy backtesting tool |
| `/strategies` | strategies.html | ❌ Not Routed | AI trading strategies |
| `/reliability` | reliability.html | ❌ Not Routed | System reliability metrics |
| `/pricing` | pricing.html | ❌ Not Routed | Platform pricing plans |
| `/login` | login.html | ❌ Not Routed | User authentication |

### Extended Pages
| Route | Template | Status | Description |
|-------|----------|--------|-------------|
| `/bist-analysis` | bist_analysis.html | ❌ Not Routed | BIST market analysis |
| `/bist-markets` | bist_markets.html | ❌ Not Routed | BIST market data |
| `/data-collection` | data_collection.html | ❌ Not Routed | Data gathering interface |
| `/showcase` | showcase.html | ❌ Not Routed | Feature showcase |
| `/welcome` | welcome.html | ❌ Not Routed | Welcome/onboarding page |
| `/test` | test.html | ❌ Not Routed | Testing interface |

### Asset Detail Pages
| Route | Template | Status | Description |
|-------|----------|--------|-------------|
| `/asset/{symbol}` | asset_detail.html | ❌ Not Routed | Individual asset details |
| `/assets` | assets_ultra.html | ❌ Not Routed | All assets overview |

### Dashboard Variants
- dashboard_next.html
- dashboard_simple.html
- dashboard_ultimate.html
- dashboard_ultra.html
- dashboard_unified.html

### Portfolio Variants
- portfolio_next.html
- portfolio_realtime.html
- portfolio_ultra.html
- portfolio_unified.html

### Market Variants
- markets_simple.html

### Trading Variants
- manual_trading_simple.html
- trading_recommendations.html

## API Endpoints (Backend)

| Endpoint | Method | Status | Description |
|----------|--------|--------|-------------|
| `/health` | GET | ✅ Working | Health check |
| `/api/health` | GET | ✅ Working | API health check |
| `/ai/score` | POST | ✅ Working | AI scoring endpoint |
| `/trade/account` | GET | ✅ Working | Trading account info |
| `/trade/order` | POST | ✅ Working | Place trading order |
| `/metrics` | GET | ✅ Working | System metrics |
| `/ws` | WebSocket | ✅ Working | Real-time data stream |

## Static Resources

| Path | Type | Status | Description |
|------|------|--------|-------------|
| `/static/css/` | CSS | ✅ Mounted | Stylesheets |
| `/static/js/` | JavaScript | ✅ Mounted | Client scripts |
| `/extensions/` | JavaScript | ✅ Mounted | UI extensions |
| `/templates/` | HTML | ✅ Mounted | Template files |

## Issues Identified

### Critical Issues
1. **No Route Handlers:** Only `/` and `/health` have route handlers
2. **Broken Navigation:** All navigation links return 404
3. **No Error Handling:** Missing 404 and error pages
4. **Duplicate Elements:** Multiple sidebars and headers in homepage

### UI Cleanup Required
1. **Homepage.html:**
   - Has both top navbar AND sidebar (duplicate navigation)
   - Sidebar should be removed per requirements
   - Keep only top navigation bar

### Missing Components
1. **Error Pages:**
   - 404 Not Found page
   - 500 Error page
   - Error boundary component

2. **Route Handlers:**
   - Need to add route handlers for all pages
   - Implement dynamic routing for assets

## Recommended Fixes

### Phase 1: Route Implementation
```python
# Add route handlers for all pages
@app.get("/dashboard")
async def dashboard():
    return FileResponse("templates/dashboard_unified.html")

@app.get("/portfolio")
async def portfolio():
    return FileResponse("templates/portfolio.html")

# ... etc for all routes
```

### Phase 2: UI Cleanup
1. Remove sidebar from homepage.html
2. Ensure consistent navigation across all pages
3. Remove duplicate headers/menus

### Phase 3: Error Handling
1. Create 404.html template
2. Create error.html template
3. Add error handlers to server

### Phase 4: Testing
1. Unit tests for all routes
2. E2E tests with Playwright
3. Performance testing with Lighthouse

## Navigation Flow

```
Homepage (/)
├── Dashboard (/dashboard)
├── Portfolio (/portfolio)
├── Markets (/markets)
├── AI Trading (/trading)
├── Manual Trading (/manual-trading)
├── Backtest (/backtest)
├── Strategies (/strategies)
├── Reliability (/reliability)
├── Pricing (/pricing)
└── Login (/login)
```

## Next Steps

1. ✅ Document all routes (this file)
2. ⏳ Fix route handlers in simple_server.py
3. ⏳ Clean up homepage.html (remove sidebar)
4. ⏳ Create error pages
5. ⏳ Add route tests
6. ⏳ Run E2E tests
7. ⏳ Generate performance report