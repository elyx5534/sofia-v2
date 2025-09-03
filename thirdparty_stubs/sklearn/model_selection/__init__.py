# thirdparty_stubs/sklearn/model_selection/__init__.py
from ..._common import _Dummy


def train_test_split(X, y=None, test_size=0.2, random_state=None, **kwargs):
    return X, X, y, y


GridSearchCV = _Dummy
RandomizedSearchCV = _Dummy
cross_val_score = lambda *args, **kwargs: [1.0, 1.0, 1.0]
KFold = _Dummy
StratifiedKFold = _Dummy

__all__ = [
    "train_test_split",
    "GridSearchCV",
    "RandomizedSearchCV",
    "cross_val_score",
    "KFold",
    "StratifiedKFold",
]
