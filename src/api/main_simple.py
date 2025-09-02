"""Simplified API for dashboard and P&L tracking"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from datetime import datetime
from pathlib import Path

# Import only the working routers
from src.api.live_proof import router as live_router
from src.api.pnl import router as pnl_router
from src.api.dashboard import router as dashboard_router
from src.api.dev_actions import router as dev_actions_router
from src.api.dev_status import router as dev_status_router
from src.api.strategies import router as strategies_router

# Create FastAPI app
app = FastAPI(
    title="Sofia V2 Dashboard API",
    description="P&L Dashboard and Live Proof API",
    version="2.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(live_router)
app.include_router(pnl_router)
app.include_router(dashboard_router)
app.include_router(dev_actions_router)
app.include_router(dev_status_router)
app.include_router(strategies_router)

@app.get("/api/health")
async def api_health_check():
    """API health check endpoint."""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.get("/health")
async def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "dashboard": "active",
            "pnl_api": "active",
            "live_proof": "active"
        }
    }

@app.get("/")
async def root():
    """Root endpoint redirects to dashboard."""
    return {
        "message": "Sofia V2 API",
        "dashboard": "http://localhost:8000/dashboard",
        "docs": "http://localhost:8000/docs"
    }

@app.get("/dev", response_class=HTMLResponse)
async def dev_console():
    """Serve developer console."""
    dev_html = Path(__file__).parent.parent.parent / "templates" / "dev.html"
    if dev_html.exists():
        return HTMLResponse(content=dev_html.read_text())
    else:
        return HTMLResponse(content="<h1>Dev Console not found</h1>")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)