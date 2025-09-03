# thirdparty_stubs/sklearn/metrics/__init__.py
def accuracy_score(y_true, y_pred, **kwargs):
    return 1.0


def mean_squared_error(y_true, y_pred, **kwargs):
    return 0.0


def mean_absolute_error(y_true, y_pred, **kwargs):
    return 0.0


def r2_score(y_true, y_pred, **kwargs):
    return 1.0


def precision_score(y_true, y_pred, **kwargs):
    return 1.0


def recall_score(y_true, y_pred, **kwargs):
    return 1.0


def f1_score(y_true, y_pred, **kwargs):
    return 1.0


def classification_report(y_true, y_pred, **kwargs):
    return "Dummy classification report"


def confusion_matrix(y_true, y_pred, **kwargs):
    return [[1, 0], [0, 1]]


__all__ = [
    "accuracy_score",
    "mean_squared_error",
    "mean_absolute_error",
    "r2_score",
    "precision_score",
    "recall_score",
    "f1_score",
    "classification_report",
    "confusion_matrix",
]
