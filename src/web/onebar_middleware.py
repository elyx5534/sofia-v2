import re

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import HTMLResponse

NAV_RX = re.compile("<nav[\\s\\S]*?</nav>", re.I)
SIDEBAR_RX = re.compile(
    "<(aside|div)[^>]*(id|class)=[\\\"']?[^\\\"'>]*sidebar[^\\\"'>]*[\\\"']?[^>]*>[\\s\\S]*?</\\1>",
    re.I,
)


def _sanitize(html: str) -> str:
    html = SIDEBAR_RX.sub("", html)
    navs = list(NAV_RX.finditer(html))
    if len(navs) > 1:
        keep_idx = next(
            (
                i
                for i, m in enumerate(navs)
                if re.search("app-navbar|sticky|brand|top-0", m.group(0), re.I)
            ),
            0,
        )
        for i, m in reversed(list(enumerate(navs))):
            if i != keep_idx:
                s, e = m.span()
                html = html[:s] + html[e:]
    return html


class OneBarMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        resp = await call_next(request)
        ctype = resp.headers.get("content-type", "")
        if "text/html" in ctype:
            body = b""
            async for chunk in resp.body_iterator:
                body += chunk
            html = body.decode("utf-8", errors="ignore")
            html = _sanitize(html)
            return HTMLResponse(html, status_code=resp.status_code, headers=dict(resp.headers))
        return resp
