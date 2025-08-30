"""
Dashboard UI Route
"""

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def dashboard_root(request: Request):
    """Dashboard root page redirect"""
    return templates.TemplateResponse("clean_dashboard.html", {
        "request": request,
        "current_page": "dashboard"
    })

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page"""
    return templates.TemplateResponse("clean_dashboard.html", {
        "request": request,
        "current_page": "dashboard"
    })