# thirdparty_stubs/statsmodels/api/__init__.py
import numpy as np

from ..._common import _Dummy


def add_constant(x):
    return x


OLS = _Dummy
WLS = _Dummy
GLS = _Dummy
GLSAR = _Dummy
Logit = _Dummy
Probit = _Dummy

tsa = _Dummy()

__all__ = ["add_constant", "OLS", "WLS", "GLS", "GLSAR", "Logit", "Probit", "tsa"]
