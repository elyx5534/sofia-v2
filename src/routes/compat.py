from fastapi import APIRouter
from fastapi.responses import RedirectResponse

router = APIRouter()
MAP = {
    "/manual-trading": "/trade/manual",
    "/ai-trading": "/trade/ai",
    "/trading": "/trade/ai",
    "/manual": "/trade/manual",
    "/bist/analiz": "/bist/analysis",
}


def _mk(dst):
    async def _r():
        return RedirectResponse(url=dst, status_code=307)

    return _r


for src, dst in MAP.items():
    router.add_api_route(src, _mk(dst), include_in_schema=False)
