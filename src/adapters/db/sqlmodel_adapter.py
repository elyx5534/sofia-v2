from __future__ import annotations

import os

TEST_MODE = os.getenv("TEST_MODE", "0") == "1"
try:
    if TEST_MODE:
        raise ImportError("force dummy in tests")
    from sqlmodel import Field as _Field
    from sqlmodel import Session as _SESS
    from sqlmodel import SQLModel as _SQLModel
    from sqlmodel import create_engine as _ce

    SQLModel = _SQLModel
    Field = _Field
    create_engine = _ce
    Session = _SESS
except Exception:

    class BaseModel:
        def model_dump(self):
            return {}

    class SQLModel(BaseModel): ...

    def Field(*a, **k):
        return None

    def create_engine(*a, **k):
        class _E:
            def dispose(self): ...

        return _E()

    class Session:
        def __init__(self, *a, **k): ...

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def add(self, *a, **k): ...

        def commit(self, *a, **k): ...
