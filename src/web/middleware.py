"""One-Bar Middleware - Ensures single navbar across all pages"""

import re

from starlette.middleware.base import BaseHTTPMiddleware

from src.adapters.web.fastapi_adapter import HTMLResponse, Request


class OneBarMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce single navbar rule"""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if not isinstance(response, HTMLResponse):
            return response
        body = response.body.decode("utf-8")
        nav_pattern = "<nav[^>]*>.*?</nav>"
        navbars = re.findall(nav_pattern, body, re.DOTALL | re.IGNORECASE)
        if len(navbars) > 1:
            kept_navbar = None
            for navbar in navbars:
                if any(cls in navbar.lower() for cls in ["sticky", "brand", "app-navbar"]):
                    kept_navbar = navbar
                    break
            if not kept_navbar:
                kept_navbar = navbars[0]
            for navbar in navbars:
                body = body.replace(navbar, "")
            body_match = re.search("<body[^>]*>", body, re.IGNORECASE)
            if body_match:
                insert_pos = body_match.end()
                body = body[:insert_pos] + "\n" + kept_navbar + body[insert_pos:]
        sidebar_patterns = [
            '<[^>]*class="[^"]*sidebar[^"]*"[^>]*>.*?</[^>]+>',
            "<aside[^>]*>.*?</aside>",
            '<div[^>]*id="[^"]*sidebar[^"]*"[^>]*>.*?</div>',
        ]
        for pattern in sidebar_patterns:
            body = re.sub(pattern, "", body, flags=re.DOTALL | re.IGNORECASE)
        return HTMLResponse(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )
