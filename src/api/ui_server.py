"""
UI Server - Serves HTML templates with FastAPI
"""

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Get paths
BASE_DIR = Path(__file__).parent.parent
TEMPLATES_DIR = BASE_DIR / "ui" / "templates"
STATIC_DIR = BASE_DIR / "ui" / "static"

# Create FastAPI app for UI
ui_app = FastAPI(title="Sofia V2 UI")

# Mount static files
ui_app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Setup templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

@ui_app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Redirect to dashboard"""
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "active_page": "dashboard"
    })

@ui_app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Dashboard page"""
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "active_page": "dashboard"
    })

@ui_app.get("/showcase/{symbol}", response_class=HTMLResponse)
async def showcase(request: Request, symbol: str):
    """Showcase page for a symbol"""
    # Convert symbol format
    display_symbol = symbol.replace("-", "/")
    
    return templates.TemplateResponse("showcase.html", {
        "request": request,
        "active_page": "showcase",
        "symbol": display_symbol
    })

@ui_app.get("/analysis/{symbol}", response_class=HTMLResponse)
async def analysis(request: Request, symbol: str):
    """Analysis page for a symbol"""
    display_symbol = symbol.replace("-", "/")
    
    return templates.TemplateResponse("analysis.html", {
        "request": request,
        "active_page": "analysis",
        "symbol": display_symbol
    })

@ui_app.get("/backtest-studio", response_class=HTMLResponse)
async def backtest_studio(request: Request):
    """Backtest studio page"""
    return templates.TemplateResponse("backtest_studio.html", {
        "request": request,
        "active_page": "backtest"
    })

def mount_ui_routes(app: FastAPI):
    """Mount UI routes to main FastAPI app"""
    # Mount static files
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    
    # Add UI routes
    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "active_page": "dashboard"
        })
    
    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard(request: Request):
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "active_page": "dashboard"
        })
    
    @app.get("/showcase/{symbol}", response_class=HTMLResponse)
    async def showcase(request: Request, symbol: str):
        display_symbol = symbol.replace("-", "/")
        return templates.TemplateResponse("showcase.html", {
            "request": request,
            "active_page": "showcase",
            "symbol": display_symbol
        })
    
    @app.get("/analysis/{symbol}", response_class=HTMLResponse)
    async def analysis(request: Request, symbol: str):
        display_symbol = symbol.replace("-", "/")
        return templates.TemplateResponse("analysis.html", {
            "request": request,
            "active_page": "analysis",
            "symbol": display_symbol
        })
    
    @app.get("/backtest-studio", response_class=HTMLResponse)
    async def backtest_studio(request: Request):
        return templates.TemplateResponse("backtest_studio.html", {
            "request": request,
            "active_page": "backtest"
        })
    
    logger.info("UI routes mounted successfully")