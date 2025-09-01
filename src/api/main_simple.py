"""Simplified API for dashboard and P&L tracking"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

# Import only the working routers
from src.api.live_proof import router as live_router
from src.api.pnl import router as pnl_router
from src.api.dashboard import router as dashboard_router

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)