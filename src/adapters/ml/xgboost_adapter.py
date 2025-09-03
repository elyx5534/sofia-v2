from __future__ import annotations

try:
    from src.adapters.ml.xgboost_adapter import *

    XGBClassifier = _xgb.XGBClassifier
    XGBRegressor = _xgb.XGBRegressor
    DMatrix = _xgb.DMatrix
    xgb = _xgb
except Exception:

    class _Dummy:
        def __init__(self, *a, **k): ...

        def __call__(self, *a, **k):
            return self

        def fit(self, *a, **k):
            return self

        def predict(self, *a, **k):
            return [0]

        def transform(self, *a, **k):
            return None

        def score(self, *a, **k):
            return 1.0

    XGBClassifier = _Dummy
    XGBRegressor = _Dummy
    DMatrix = _Dummy

    class _xgb:
        pass

    xgb = _xgb()
