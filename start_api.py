#!/usr/bin/env python3
"""
DEPRECATED: Use `uvicorn src.api.main:app` instead

This file is kept for backward compatibility.
Redirects to the main API entrypoint.
"""

import warnings
import uvicorn

warnings.warn(
    "start_api.py is deprecated. Use 'uvicorn src.api.main:app --port 8000 --reload' instead",
    DeprecationWarning,
    stacklevel=2
)

if __name__ == "__main__":
    # Redirect to main API entrypoint
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)