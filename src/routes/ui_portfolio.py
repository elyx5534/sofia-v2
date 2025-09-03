"""
Portfolio UI Route
"""

from fastapi.templating import Jinja2Templates

from src.adapters.web.fastapi_adapter import APIRouter, HTMLResponse, Request

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/portfolio", response_class=HTMLResponse)
async def portfolio(request: Request):
    """Portfolio page"""
    return templates.TemplateResponse(
        "clean_portfolio.html", {"request": request, "current_page": "portfolio"}
    )
