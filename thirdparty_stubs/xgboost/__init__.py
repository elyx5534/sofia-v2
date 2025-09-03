# thirdparty_stubs/xgboost/__init__.py
from .._common import _Dummy

__all__ = ["XGBClassifier", "XGBRegressor", "DMatrix", "Booster", "train", "cv"]
__version__ = "0.0.0"

XGBClassifier = _Dummy
XGBRegressor = _Dummy
DMatrix = _Dummy
Booster = _Dummy


def train(*args, **kwargs):
    return _Dummy()


def cv(*args, **kwargs):
    return {}
