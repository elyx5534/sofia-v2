from __future__ import annotations

try:
    from src.adapters.db.sqlalchemy_adapter import Session as _Session
    from src.adapters.db.sqlalchemy_adapter import create_engine as _create_engine
    from src.adapters.db.sqlalchemy_adapter import relationship as _relationship
    from src.adapters.db.sqlalchemy_adapter import text as _text

    create_engine = _create_engine
    text = _text
    Session = _Session
    relationship = _relationship
except Exception:

    class _Dummy:
        def __init__(self, *a, **k): ...

        def __call__(self, *a, **k):
            return self

        def execute(self, *a, **k):
            return self

        def close(self, *a, **k): ...

    def create_engine(*a, **k):
        return _Dummy()

    def text(*a, **k):
        return _Dummy()

    class Session(_Dummy):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def relationship(*a, **k):
        return None
