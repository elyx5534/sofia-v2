from __future__ import annotations

try:
    import statsmodels.api as _sm

    OLS = _sm.OLS
    add_constant = _sm.add_constant
except Exception:

    class _Dummy:
        def __init__(self, *a, **k): ...

        def fit(self, *a, **k):
            return self

        def summary(self):
            return "N/A"

    def add_constant(x):
        return x

    OLS = _Dummy
