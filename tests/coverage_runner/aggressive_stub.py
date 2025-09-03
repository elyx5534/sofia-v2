"""Aggressive stub system using sys.meta_path to intercept ALL imports."""

import importlib.abc
import importlib.machinery
import os
import sys
from types import ModuleType

# Set test mode
os.environ["TEST_MODE"] = "1"

# Heavy dependencies to stub completely
STUB_PACKAGES = {
    "xgboost",
    "sklearn",
    "sqlmodel",
    "sqlalchemy",
    "statsmodels",
    "tensorflow",
    "torch",
    "keras",
    "lightgbm",
    "catboost",
    "plotly",
    "matplotlib",
    "seaborn",
    "bokeh",
    "dash",
    "ray",
    "dask",
    "pyspark",
    "airflow",
    "prefect",
    "transformers",
    "spacy",
    "nltk",
    "gensim",
    "ta",
    "talib",
    "tulipy",
    "ta-lib",
    "onnx",
    "onnxruntime",
    "tensorrt",
    "prophet",
    "pmdarima",
    "arch",
    "optuna",
    "hyperopt",
    "skopt",
    "mlflow",
    "wandb",
    "neptune",
    "comet_ml",
    "kubernetes",
    "docker",
    "boto3",
    "azure",
    "confluent_kafka",
    "redis",
    "celery",
    "rabbitmq",
}


class DummyModule(ModuleType):
    """A dummy module that returns dummy objects for all attributes."""

    def __init__(self, name):
        super().__init__(name)
        self.__path__ = []
        self.__file__ = f"<dummy {name}>"

    def __getattr__(self, name):
        if name.startswith("__") and name.endswith("__"):
            # Return standard module attributes
            if name == "__all__":
                return []
            if name == "__version__":
                return "0.0.0"
            if name == "__author__":
                return "dummy"
            return None
        return DummyObject()


class DummyObject:
    """Universal dummy object that handles all operations."""

    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, *args, **kwargs):
        return DummyObject()

    def __getattr__(self, name):
        return DummyObject()

    def __setattr__(self, name, value):
        pass

    def __getitem__(self, key):
        return DummyObject()

    def __setitem__(self, key, value):
        pass

    def __contains__(self, item):
        return False

    def __len__(self):
        return 0

    def __iter__(self):
        return iter([])

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def __str__(self):
        return "DummyObject"

    def __repr__(self):
        return "DummyObject()"

    def __bool__(self):
        return True

    def __int__(self):
        return 0

    def __float__(self):
        return 0.0

    def __add__(self, other):
        return DummyObject()

    def __sub__(self, other):
        return DummyObject()

    def __mul__(self, other):
        return DummyObject()

    def __truediv__(self, other):
        return DummyObject()

    def __eq__(self, other):
        return False

    def __lt__(self, other):
        return False

    def __gt__(self, other):
        return False

    # Common ML methods
    def fit(self, *args, **kwargs):
        return self

    def predict(self, *args, **kwargs):
        return [0]

    def transform(self, *args, **kwargs):
        return [[0]]

    def fit_transform(self, *args, **kwargs):
        return [[0]]

    def score(self, *args, **kwargs):
        return 0.5

    # SQLModel specific
    def __mro_entries__(self, bases):
        return (DummyObject,)

    @classmethod
    def __class_getitem__(cls, params):
        return DummyObject()


class StubFinder(importlib.abc.MetaPathFinder):
    """Meta path finder that intercepts imports of heavy dependencies."""

    def find_spec(self, fullname, path, target=None):
        # Check if this is a heavy dependency
        root_module = fullname.split(".")[0]
        if root_module in STUB_PACKAGES:
            # Return a spec that will load our dummy module
            return importlib.machinery.ModuleSpec(
                fullname, StubLoader(), origin=f"<stubbed {fullname}>", is_package=True
            )
        return None


class StubLoader(importlib.abc.Loader):
    """Loader that creates dummy modules."""

    def create_module(self, spec):
        return DummyModule(spec.name)

    def exec_module(self, module):
        # Module is already configured in create_module
        pass


def install_aggressive_stubs():
    """Install the aggressive stub system."""
    # Insert at the beginning to intercept before standard importers
    if not any(isinstance(finder, StubFinder) for finder in sys.meta_path):
        sys.meta_path.insert(0, StubFinder())

    # Also pre-populate sys.modules for immediate stubbing
    for package in STUB_PACKAGES:
        if package not in sys.modules:
            sys.modules[package] = DummyModule(package)
            # Also stub common submodules
            for submodule in ["models", "preprocessing", "metrics", "utils", "core", "api"]:
                full_name = f"{package}.{submodule}"
                sys.modules[full_name] = DummyModule(full_name)


# Auto-install on import
install_aggressive_stubs()
