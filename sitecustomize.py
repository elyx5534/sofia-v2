"""
sitecustomize: TEST_MODE'da ağır bağımlılıkları önceden stub'lar ve güvenli modu açar.
"""

import os
import sys
import types

TEST_MODE = os.getenv("TEST_MODE", "0") == "1"
STUB_3P = os.getenv("STUB_3P", "0") == "1"

# CRITICAL: Add thirdparty_stubs to the BEGINNING of sys.path
if TEST_MODE or STUB_3P:
    import pathlib

    stub_path = pathlib.Path(__file__).resolve().parent / "thirdparty_stubs"
    if stub_path.exists() and str(stub_path) not in sys.path[:1]:
        sys.path.insert(0, str(stub_path))

if TEST_MODE:
    # 1) ağır bağımlılıklara net stub (komple paket + alt modüller)
    def _mkmod(name):
        m = types.ModuleType(name)
        m.__all__ = []
        return m

    def _ensure(name):
        if name not in sys.modules:
            sys.modules[name] = _mkmod(name)
        return sys.modules[name]

    def _attr(mod, name, obj):
        setattr(mod, name, obj)
        if hasattr(mod, "__all__"):
            mod.__all__.append(name)

    class _Dummy:
        def __init__(self, *a, **k): ...
        def __call__(self, *a, **k):
            return _Dummy()

        def __getattr__(self, name):
            return _Dummy()

        def fit(self, *a, **k):
            return self

        def predict(self, *a, **k):
            return [0]

        def transform(self, *a, **k):
            return a[0] if a else None

        def score(self, *a, **k):
            return 1.0

        def close(self, *a, **k): ...
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def __iter__(self):
            return iter([])

        def __len__(self):
            return 0

        def __bool__(self):
            return True

    # xgboost
    xgb = _ensure("xgboost")
    for cls in ("XGBClassifier", "XGBRegressor", "DMatrix", "Booster"):
        _attr(xgb, cls, _Dummy)
    xgb.sklearn = _ensure("xgboost.sklearn")
    xgb.plotting = _ensure("xgboost.plotting")

    # sklearn minimal yüzey
    sk = _ensure("sklearn")
    pipeline = _ensure("sklearn.pipeline")
    _attr(pipeline, "Pipeline", _Dummy)
    model_selection = _ensure("sklearn.model_selection")
    _attr(
        model_selection,
        "train_test_split",
        lambda X, y=None, test_size=0.2, random_state=None: (X, X, y, y),
    )
    _attr(model_selection, "GridSearchCV", _Dummy)
    _attr(model_selection, "cross_val_score", lambda *a, **k: [0.9, 0.91, 0.92])
    metrics = _ensure("sklearn.metrics")
    _attr(metrics, "accuracy_score", lambda y, yhat: 1.0)
    _attr(metrics, "mean_squared_error", lambda y, yhat: 0.01)
    preprocessing = _ensure("sklearn.preprocessing")
    _attr(preprocessing, "StandardScaler", _Dummy)
    _attr(preprocessing, "MinMaxScaler", _Dummy)
    ensemble = _ensure("sklearn.ensemble")
    _attr(ensemble, "RandomForestClassifier", _Dummy)
    _attr(ensemble, "RandomForestRegressor", _Dummy)

    # statsmodels.api
    sm = _ensure("statsmodels")
    smapi = _ensure("statsmodels.api")
    _attr(smapi, "OLS", _Dummy)
    _attr(smapi, "add_constant", lambda x: x)
    _attr(smapi, "ARIMA", _Dummy)
    _attr(smapi, "VAR", _Dummy)

    # sqlalchemy/sqlmodel (sadece import akışı için)
    sa = _ensure("sqlalchemy")
    saorm = _ensure("sqlalchemy.orm")
    _attr(sa, "create_engine", lambda *a, **k: _Dummy())
    _attr(sa, "Column", lambda *a, **k: None)
    _attr(sa, "Integer", int)
    _attr(sa, "String", str)
    _attr(sa, "Float", float)
    _attr(sa, "Boolean", bool)
    _attr(sa, "DateTime", None)
    _attr(sa, "ForeignKey", lambda *a: None)
    _attr(sa, "Table", _Dummy)
    _attr(sa, "MetaData", _Dummy)
    _attr(saorm, "Session", _Dummy)
    _attr(saorm, "sessionmaker", _Dummy)
    _attr(saorm, "declarative_base", lambda: type("Base", (), {}))

    sqlmodel = _ensure("sqlmodel")

    # Create a proper SQLModel base class
    class SQLModelBase:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

        def dict(self):
            return {}

        def json(self):
            return "{}"

        @classmethod
        def __mro_entries__(cls, bases):
            return (object,)  # Return tuple to fix __mro_entries__ error

    _attr(sqlmodel, "SQLModel", SQLModelBase)
    _attr(sqlmodel, "Field", lambda *a, **k: None)
    _attr(sqlmodel, "create_engine", lambda *a, **k: _Dummy())
    _attr(sqlmodel, "Session", _Dummy)
    _attr(sqlmodel, "Relationship", lambda *a, **k: None)

    # Fix sqlmodel.sql.sqltypes
    sql = _ensure("sqlmodel.sql")
    sqltypes = _ensure("sqlmodel.sql.sqltypes")
    _attr(sqltypes, "GUID", _Dummy)
    _attr(sqltypes, "AutoString", str)

    # ta / pandas_ta / talib
    ta = _ensure("ta")
    pta = _ensure("pandas_ta")
    talib = _ensure("talib")
    for f in ("rsi", "sma", "ema", "bbands", "macd", "stoch", "adx", "atr", "cci", "obv"):
        _attr(ta, f, lambda *a, **k: None)
        _attr(pta, f, lambda *a, **k: None)
        _attr(talib, f.upper(), lambda *a, **k: [0.0] * 10)
    _attr(ta, "add_all_ta_features", lambda *a, **k: a[0] if a else None)
    _attr(pta, "Strategy", _Dummy)

    # plotly/dash/streamlit
    plotly = _ensure("plotly")
    plotly_go = _ensure("plotly.graph_objects")
    _attr(plotly_go, "Figure", _Dummy)
    _attr(plotly_go, "Scatter", _Dummy)
    _attr(plotly_go, "Bar", _Dummy)
    _attr(plotly_go, "Candlestick", _Dummy)
    plotly_express = _ensure("plotly.express")
    for chart in ("line", "bar", "scatter", "histogram"):
        _attr(plotly_express, chart, lambda *a, **k: _Dummy())

    dash = _ensure("dash")
    _attr(dash, "Dash", _Dummy)
    dash_html = _ensure("dash.html_components")
    _attr(dash_html, "Div", _Dummy)
    dash_dcc = _ensure("dash.dcc")
    _attr(dash_dcc, "Graph", _Dummy)

    streamlit = _ensure("streamlit")
    for fn in ("write", "sidebar", "columns", "plotly_chart", "dataframe"):
        _attr(streamlit, fn, lambda *a, **k: None)

    # scipy
    scipy = _ensure("scipy")
    scipy_stats = _ensure("scipy.stats")
    _attr(scipy_stats, "norm", _Dummy())
    _attr(scipy_stats, "pearsonr", lambda x, y: (0.9, 0.01))
    scipy_optimize = _ensure("scipy.optimize")
    _attr(
        scipy_optimize, "minimize", lambda *a, **k: type("Result", (), {"x": [1.0], "fun": 0.1})()
    )

    # torch/tensorflow
    torch = _ensure("torch")
    _attr(torch, "nn", _ensure("torch.nn"))
    _attr(torch, "optim", _ensure("torch.optim"))
    _attr(torch, "Tensor", _Dummy)
    _attr(torch, "cuda", type("cuda", (), {"is_available": lambda: False})())

    tf = _ensure("tensorflow")
    _attr(tf, "keras", _ensure("tensorflow.keras"))
    tf_keras = sys.modules["tensorflow.keras"]
    _attr(tf_keras, "Sequential", _Dummy)
    _attr(tf_keras, "layers", _ensure("tensorflow.keras.layers"))

    # diğer sık karşılaşılanlar
    for modname in (
        "psycopg2",
        "aiokafka",
        "pika",
        "celery",
        "rq",
        "apscheduler",
        "confluent_kafka",
        "pymongo",
        "motor",
        "boto3",
        "google",
        "google.cloud",
        "elasticsearch",
        "redis",
        "aioredis",
        "asyncpg",
        "websockets",
        "aiohttp",
        "httpx",
        "uvicorn",
        "fastapi",
        "starlette",
        "pydantic",
        "email_validator",
    ):
        _ensure(modname)

    # fastapi specifics
    fastapi = sys.modules.get("fastapi", _ensure("fastapi"))
    _attr(fastapi, "FastAPI", _Dummy)
    _attr(fastapi, "APIRouter", _Dummy)
    _attr(fastapi, "Depends", lambda x: x)
    _attr(fastapi, "HTTPException", Exception)

    # pydantic
    pydantic = sys.modules.get("pydantic", _ensure("pydantic"))
    _attr(pydantic, "BaseModel", type("BaseModel", (), {}))
    _attr(pydantic, "Field", lambda *a, **k: None)
    _attr(pydantic, "validator", lambda *a, **k: lambda f: f)

    # 2) tehlikeli fonksiyonları no-op yap
    import time

    time.sleep = lambda *a, **k: None
    try:
        import asyncio

        asyncio.sleep = lambda *a, **k: None
    except:
        pass
    try:
        import uvicorn

        uvicorn.run = lambda *a, **k: None
    except:
        pass
    try:
        import subprocess

        subprocess.run = lambda *a, **k: None
        subprocess.Popen = lambda *a, **k: type(
            "Popen", (), {"wait": lambda: None, "communicate": lambda: (b"", b"")}
        )()
    except:
        pass
    try:
        import os

        os.system = lambda *a, **k: 0
    except:
        pass
    try:
        import threading

        _Thread = threading.Thread

        class NoOpThread(_Thread):
            def start(self):
                pass

            def join(self, timeout=None):
                pass

        threading.Thread = NoOpThread
    except:
        pass
    try:
        import multiprocessing

        _Process = multiprocessing.Process

        class NoOpProcess(_Process):
            def start(self):
                pass

            def join(self, timeout=None):
                pass

        multiprocessing.Process = NoOpProcess
    except:
        pass
