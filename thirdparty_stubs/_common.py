# thirdparty_stubs/_common.py
from __future__ import annotations

import types


class _DummyMeta(type):
    # ÖNEMLİ: bazı kütüphaneler multiple inheritance sırasında __mro_entries__ çağırır
    def __mro_entries__(cls, bases):
        return ()


class _Dummy(metaclass=_DummyMeta):
    def __init__(self, *a, **k):
        pass

    def __call__(self, *a, **k):
        return _Dummy()

    def __getattr__(self, name):
        return _Dummy()

    def __setattr__(self, name, value):
        pass

    def __getitem__(self, key):
        return _Dummy()

    def __setitem__(self, key, value):
        pass

    def __iter__(self):
        return iter(())

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __len__(self):
        return 0

    def __bool__(self):
        return True

    def __str__(self):
        return "Dummy"

    def __repr__(self):
        return "Dummy()"

    # ML methods
    def fit(self, *a, **k):
        return self

    def predict(self, *a, **k):
        return [0]

    def transform(self, *a, **k):
        return a[0] if a else None

    def fit_transform(self, *a, **k):
        return a[0] if a else None

    def score(self, *a, **k):
        return 1.0

    def predict_proba(self, *a, **k):
        return [[0.5, 0.5]]

    # DB methods
    def execute(self, *a, **k):
        return _Dummy()

    def commit(self, *a, **k):
        pass

    def rollback(self, *a, **k):
        pass

    def close(self, *a, **k):
        pass

    def add(self, *a, **k):
        pass

    def query(self, *a, **k):
        return _Dummy()

    def filter(self, *a, **k):
        return _Dummy()

    def first(self, *a, **k):
        return _Dummy()

    def all(self, *a, **k):
        return []


def _mkmod(name):
    m = types.ModuleType(name)
    m.__all__ = []
    return m
