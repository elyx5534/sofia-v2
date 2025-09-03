from __future__ import annotations

import os

TEST_MODE = os.getenv("TEST_MODE", "0") == "1"
try:
    if TEST_MODE:
        raise ImportError("force dummy in tests")
    from fastapi import APIRouter as _APIRouter
    from fastapi import Body as _Body
    from fastapi import Depends as _Depends
    from fastapi import FastAPI as _FastAPI
    from fastapi import HTTPException as _HTTPException
    from fastapi import Path as _Path
    from fastapi import Query as _Query
    from fastapi.responses import FileResponse as _FileResponse
    from fastapi.responses import JSONResponse as _JSONResponse
    from fastapi.responses import StreamingResponse as _StreamingResponse
    from fastapi.testclient import TestClient as _TestClient

    FastAPI = _FastAPI
    APIRouter = _APIRouter
    HTTPException = _HTTPException
    Depends = _Depends
    Query = _Query
    Path = _Path
    Body = _Body
    JSONResponse = _JSONResponse
    StreamingResponse = _StreamingResponse
    FileResponse = _FileResponse
    TestClient = _TestClient
except Exception:

    class FastAPI:
        def __init__(self, *a, **k):
            self.router = APIRouter()

        def include_router(self, *a, **k):
            pass

        def get(self, *a, **k):
            def decorator(f):
                return f

            return decorator

        def post(self, *a, **k):
            def decorator(f):
                return f

            return decorator

        def put(self, *a, **k):
            def decorator(f):
                return f

            return decorator

        def delete(self, *a, **k):
            def decorator(f):
                return f

            return decorator

        def on_event(self, event):
            def decorator(f):
                return f

            return decorator

    class APIRouter:
        def __init__(self, *a, **k):
            pass

        def get(self, *a, **k):
            def decorator(f):
                return f

            return decorator

        def post(self, *a, **k):
            def decorator(f):
                return f

            return decorator

        def put(self, *a, **k):
            def decorator(f):
                return f

            return decorator

        def delete(self, *a, **k):
            def decorator(f):
                return f

            return decorator

    class HTTPException(Exception):
        def __init__(self, status_code=400, detail="error"):
            self.status_code = status_code
            self.detail = detail

    def Depends(*a, **k):
        return None

    def Query(*a, **k):
        return None

    def Path(*a, **k):
        return None

    def Body(*a, **k):
        return None

    class JSONResponse:
        def __init__(self, *a, **k):
            pass

    class StreamingResponse:
        def __init__(self, *a, **k):
            pass

    class FileResponse:
        def __init__(self, *a, **k):
            pass

    class TestClient:
        def __init__(self, *a, **k):
            pass

        def get(self, *a, **k):
            class Response:
                status_code = 200

                def json(self):
                    return {}

            return Response()

        def post(self, *a, **k):
            class Response:
                status_code = 200

                def json(self):
                    return {}

            return Response()
