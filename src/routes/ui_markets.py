"""
Markets UI Route
"""

from fastapi.templating import Jinja2Templates

from src.adapters.web.fastapi_adapter import APIRouter, HTMLResponse, Request

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/markets", response_class=HTMLResponse)
async def markets(request: Request):
    """Markets page"""
    return templates.TemplateResponse(
        "clean_markets.html", {"request": request, "current_page": "markets"}
    )
