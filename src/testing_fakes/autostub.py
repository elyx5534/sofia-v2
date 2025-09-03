"""AutoStub - Automatic stubbing for missing external dependencies."""

from __future__ import annotations

import builtins
import sys

DEFAULT_EXPORTS = {
    "redis": ["Redis", "StrictRedis", "ConnectionPool"],
    "psycopg2": ["connect", "extensions"],
    "sqlalchemy": ["create_engine", "text", "MetaData", "Table", "Column", "Integer", "String"],
    "aiokafka": ["AIOKafkaProducer", "AIOKafkaConsumer"],
    "pika": ["BlockingConnection", "ConnectionParameters", "PlainCredentials"],
    "celery": ["Celery", "Task", "group", "chain"],
    "rq": ["Queue", "Worker", "Connection"],
    "apscheduler": ["BackgroundScheduler", "AsyncIOScheduler"],
    "confluent_kafka": ["Producer", "Consumer", "KafkaError"],
    "pymongo": ["MongoClient", "Collection", "Database"],
    "motor": ["MotorClient", "MotorDatabase"],
    "boto3": ["client", "resource", "Session"],
    "google": ["auth", "cloud"],
    "google.cloud": ["storage", "bigquery", "pubsub"],
    "elasticsearch": ["Elasticsearch", "helpers"],
    "websockets": ["serve", "connect"],
    "aiohttp": ["ClientSession", "web"],
    "uvicorn": ["run", "Config"],
    "fastapi": ["FastAPI", "APIRouter", "Depends", "HTTPException"],
    "starlette": ["Starlette", "Request", "Response"],
    "httpx": ["AsyncClient", "Client"],
    "pandas_ta": ["Strategy"],
    "ta": ["add_all_ta_features"],
    "talib": ["SMA", "EMA", "RSI", "MACD", "BBANDS"],
    "scipy": ["stats", "optimize"],
    "sklearn": ["preprocessing", "model_selection", "ensemble"],
    "torch": ["nn", "optim", "Tensor"],
    "tensorflow": ["keras", "nn"],
    "plotly": ["graph_objects", "express"],
    "dash": ["Dash", "html", "dcc", "callback"],
    "streamlit": ["write", "sidebar", "columns"],
}


class _Dummy:
    """Universal dummy object that can be anything."""

    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, *args, **kwargs):
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

    def __len__(self):
        return 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __await__(self):
        return self.__aenter__().__await__()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def __bool__(self):
        return True

    def __str__(self):
        return "DummyStub"

    def __repr__(self):
        return "DummyStub()"


class AutoStubFinder:
    """Module finder that creates stubs for missing dependencies."""

    def find_spec(self, fullname, path, target=None):
        if fullname.startswith(
            (
                "src.",
                "tests.",
                "pytest",
                "unittest",
                "importlib",
                "asyncio",
                "concurrent",
                "multiprocessing",
                "threading",
            )
        ):
            return None
        if fullname in sys.modules or fullname in dir(builtins):
            return None
        parts = fullname.split(".")
        root = parts[0]
        if root in DEFAULT_EXPORTS or root in (
            "ccxt",
            "requests",
            "yfinance",
            "websocket",
            "aioredis",
            "asyncpg",
            "httpcore",
            "h11",
        ):
            from importlib.machinery import ModuleSpec

            spec = ModuleSpec(fullname, self)
            return spec
        return None

    def create_module(self, spec):
        """Create the module object."""
        return None

    def exec_module(self, module):
        """Execute the module (populate it with stubs)."""
        root = module.__name__.split(".")[0]
        exports = DEFAULT_EXPORTS.get(root, [])
        for name in exports:
            setattr(module, name, _Dummy)
        module.__all__ = exports
        module.__version__ = "0.0.0-stub"
        module.__author__ = "AutoStub"

        def _getattr(name):
            return _Dummy()

        module.__getattr__ = _getattr


def install():
    """Install the AutoStub finder."""
    if not any(isinstance(f, AutoStubFinder) for f in sys.meta_path):
        sys.meta_path.insert(0, AutoStubFinder())


install()
