"""One-Bar Middleware - Ensures single navbar across all pages"""

import re
from fastapi import Request, Response
from fastapi.responses import HTMLResponse
from starlette.middleware.base import BaseHTTPMiddleware


class OneBarMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce single navbar rule"""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Only process HTML responses
        if not isinstance(response, HTMLResponse):
            return response
            
        # Get response body
        body = response.body.decode('utf-8')
        
        # Find all nav elements
        nav_pattern = r'<nav[^>]*>.*?</nav>'
        navbars = re.findall(nav_pattern, body, re.DOTALL | re.IGNORECASE)
        
        if len(navbars) > 1:
            # Keep only the first navbar that has sticky/brand/app-navbar class
            kept_navbar = None
            for navbar in navbars:
                if any(cls in navbar.lower() for cls in ['sticky', 'brand', 'app-navbar']):
                    kept_navbar = navbar
                    break
            
            if not kept_navbar:
                kept_navbar = navbars[0]  # Fallback to first navbar
            
            # Remove all navbars and add back the kept one
            for navbar in navbars:
                body = body.replace(navbar, '')
            
            # Insert kept navbar after <body> tag
            body_match = re.search(r'<body[^>]*>', body, re.IGNORECASE)
            if body_match:
                insert_pos = body_match.end()
                body = body[:insert_pos] + '\n' + kept_navbar + body[insert_pos:]
        
        # Remove any sidebar elements
        sidebar_patterns = [
            r'<[^>]*class="[^"]*sidebar[^"]*"[^>]*>.*?</[^>]+>',
            r'<aside[^>]*>.*?</aside>',
            r'<div[^>]*id="[^"]*sidebar[^"]*"[^>]*>.*?</div>'
        ]
        
        for pattern in sidebar_patterns:
            body = re.sub(pattern, '', body, flags=re.DOTALL | re.IGNORECASE)
        
        # Create new response with modified body
        return HTMLResponse(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type
        )