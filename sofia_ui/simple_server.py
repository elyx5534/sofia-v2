"""
Simple static file server for Sofia UI
"""
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.exceptions import HTTPException
from starlette.exceptions import HTTPException as StarletteHTTPException
import os

app = FastAPI()

# Get current directory
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# Mount static directories
app.mount("/static", StaticFiles(directory=os.path.join(CURRENT_DIR, "static")), name="static")
app.mount("/templates", StaticFiles(directory=os.path.join(CURRENT_DIR, "templates")), name="templates")
app.mount("/extensions", StaticFiles(directory=os.path.join(CURRENT_DIR, "extensions")), name="extensions")

@app.get("/")
async def root():
    """Serve homepage.html"""
    homepage_path = os.path.join(CURRENT_DIR, "templates", "homepage.html")
    if os.path.exists(homepage_path):
        return FileResponse(homepage_path)
    else:
        # Try index.html
        index_path = os.path.join(CURRENT_DIR, "templates", "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        else:
            return {"message": "Sofia V2 UI Server", "status": "running", "api": "http://127.0.0.1:8020"}

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "sofia-ui"}

# Core page routes
@app.get("/dashboard")
async def dashboard():
    """Serve dashboard page"""
    template_path = os.path.join(CURRENT_DIR, "templates", "dashboard_unified.html")
    if not os.path.exists(template_path):
        template_path = os.path.join(CURRENT_DIR, "templates", "dashboard_simple.html")
    if not os.path.exists(template_path):
        template_path = os.path.join(CURRENT_DIR, "templates", "homepage.html")
    return FileResponse(template_path)

@app.get("/portfolio")
async def portfolio():
    """Serve portfolio page"""
    template_path = os.path.join(CURRENT_DIR, "templates", "portfolio.html")
    if not os.path.exists(template_path):
        template_path = os.path.join(CURRENT_DIR, "templates", "portfolio_unified.html")
    if os.path.exists(template_path):
        return FileResponse(template_path)
    return FileResponse(os.path.join(CURRENT_DIR, "templates", "homepage.html"))

@app.get("/markets")
async def markets():
    """Serve markets page"""
    template_path = os.path.join(CURRENT_DIR, "templates", "markets.html")
    if not os.path.exists(template_path):
        template_path = os.path.join(CURRENT_DIR, "templates", "markets_simple.html")
    if os.path.exists(template_path):
        return FileResponse(template_path)
    return FileResponse(os.path.join(CURRENT_DIR, "templates", "homepage.html"))

@app.get("/trading")
async def trading():
    """Serve AI trading page"""
    template_path = os.path.join(CURRENT_DIR, "templates", "ai_trading.html")
    if os.path.exists(template_path):
        return FileResponse(template_path)
    return FileResponse(os.path.join(CURRENT_DIR, "templates", "homepage.html"))

@app.get("/manual-trading")
async def manual_trading():
    """Serve manual trading page"""
    template_path = os.path.join(CURRENT_DIR, "templates", "manual_trading.html")
    if not os.path.exists(template_path):
        template_path = os.path.join(CURRENT_DIR, "templates", "manual_trading_simple.html")
    if os.path.exists(template_path):
        return FileResponse(template_path)
    return FileResponse(os.path.join(CURRENT_DIR, "templates", "homepage.html"))

@app.get("/backtest")
async def backtest():
    """Serve backtest page"""
    template_path = os.path.join(CURRENT_DIR, "templates", "backtest.html")
    if os.path.exists(template_path):
        return FileResponse(template_path)
    return FileResponse(os.path.join(CURRENT_DIR, "templates", "homepage.html"))

@app.get("/strategies")
async def strategies():
    """Serve strategies page"""
    template_path = os.path.join(CURRENT_DIR, "templates", "strategies.html")
    if os.path.exists(template_path):
        return FileResponse(template_path)
    return FileResponse(os.path.join(CURRENT_DIR, "templates", "homepage.html"))

@app.get("/reliability")
async def reliability():
    """Serve reliability page"""
    template_path = os.path.join(CURRENT_DIR, "templates", "reliability.html")
    if os.path.exists(template_path):
        return FileResponse(template_path)
    return FileResponse(os.path.join(CURRENT_DIR, "templates", "homepage.html"))

@app.get("/pricing")
async def pricing():
    """Serve pricing page"""
    template_path = os.path.join(CURRENT_DIR, "templates", "pricing.html")
    if os.path.exists(template_path):
        return FileResponse(template_path)
    return FileResponse(os.path.join(CURRENT_DIR, "templates", "homepage.html"))

@app.get("/login")
async def login():
    """Serve login page"""
    template_path = os.path.join(CURRENT_DIR, "templates", "login.html")
    if os.path.exists(template_path):
        return FileResponse(template_path)
    return FileResponse(os.path.join(CURRENT_DIR, "templates", "homepage.html"))

# Extended page routes
@app.get("/bist-analysis")
async def bist_analysis():
    """Serve BIST analysis page"""
    template_path = os.path.join(CURRENT_DIR, "templates", "bist_analysis.html")
    if os.path.exists(template_path):
        return FileResponse(template_path)
    return FileResponse(os.path.join(CURRENT_DIR, "templates", "homepage.html"))

@app.get("/bist-markets")
async def bist_markets():
    """Serve BIST markets page"""
    template_path = os.path.join(CURRENT_DIR, "templates", "bist_markets.html")
    if os.path.exists(template_path):
        return FileResponse(template_path)
    return FileResponse(os.path.join(CURRENT_DIR, "templates", "homepage.html"))

@app.get("/data-collection")
async def data_collection():
    """Serve data collection page"""
    template_path = os.path.join(CURRENT_DIR, "templates", "data_collection.html")
    if os.path.exists(template_path):
        return FileResponse(template_path)
    return FileResponse(os.path.join(CURRENT_DIR, "templates", "homepage.html"))

@app.get("/showcase")
async def showcase():
    """Serve showcase page"""
    template_path = os.path.join(CURRENT_DIR, "templates", "showcase.html")
    if os.path.exists(template_path):
        return FileResponse(template_path)
    return FileResponse(os.path.join(CURRENT_DIR, "templates", "homepage.html"))

@app.get("/welcome")
async def welcome():
    """Serve welcome page"""
    template_path = os.path.join(CURRENT_DIR, "templates", "welcome.html")
    if os.path.exists(template_path):
        return FileResponse(template_path)
    return FileResponse(os.path.join(CURRENT_DIR, "templates", "homepage.html"))

@app.get("/test")
async def test_page():
    """Serve test page"""
    template_path = os.path.join(CURRENT_DIR, "templates", "test.html")
    if os.path.exists(template_path):
        return FileResponse(template_path)
    return FileResponse(os.path.join(CURRENT_DIR, "templates", "homepage.html"))

# Asset routes
@app.get("/assets")
async def assets():
    """Serve assets page"""
    template_path = os.path.join(CURRENT_DIR, "templates", "assets_ultra.html")
    if os.path.exists(template_path):
        return FileResponse(template_path)
    return FileResponse(os.path.join(CURRENT_DIR, "templates", "homepage.html"))

@app.get("/asset/{symbol}")
async def asset_detail(symbol: str):
    """Serve asset detail page"""
    template_path = os.path.join(CURRENT_DIR, "templates", "asset_detail.html")
    if not os.path.exists(template_path):
        template_path = os.path.join(CURRENT_DIR, "templates", "asset_detail_enhanced.html")
    if not os.path.exists(template_path):
        template_path = os.path.join(CURRENT_DIR, "templates", "assets_detail.html")
    if os.path.exists(template_path):
        return FileResponse(template_path)
    return FileResponse(os.path.join(CURRENT_DIR, "templates", "homepage.html"))

# 404 Handler
@app.exception_handler(StarletteHTTPException)
async def custom_404_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        error_page = os.path.join(CURRENT_DIR, "templates", "404.html")
        if os.path.exists(error_page):
            return FileResponse(error_page, status_code=404)
        return HTMLResponse(
            content="""
            <html>
            <body style="background: #111; color: #fff; font-family: monospace; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0;">
                <div style="text-align: center;">
                    <h1 style="font-size: 72px; margin: 0;">404</h1>
                    <p>Page not found</p>
                    <a href="/" style="color: #3b82f6;">Go home</a>
                </div>
            </body>
            </html>
            """,
            status_code=404
        )
    return HTMLResponse(content=str(exc.detail), status_code=exc.status_code)

if __name__ == "__main__":
    import uvicorn
    print("Starting Sofia UI Server on http://127.0.0.1:8004")
    print("API Server should be running on http://127.0.0.1:8020")
    uvicorn.run(app, host="127.0.0.1", port=8004)