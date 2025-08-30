"""
Portfolio UI Route
"""

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/portfolio", response_class=HTMLResponse)
async def portfolio(request: Request):
    """Portfolio page"""
    return templates.TemplateResponse("clean_portfolio.html", {
        "request": request,
        "current_page": "portfolio"
    })