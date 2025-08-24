#!/usr/bin/env python
"""Run the Data Hub API server."""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "src.data_hub.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
