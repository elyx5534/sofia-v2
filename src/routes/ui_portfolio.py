"""
Portfolio UI Route
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/portfolio", response_class=HTMLResponse)
async def portfolio(request: Request):
    """Portfolio page"""
    return templates.TemplateResponse(
        "clean_portfolio.html", {"request": request, "current_page": "portfolio"}
    )
