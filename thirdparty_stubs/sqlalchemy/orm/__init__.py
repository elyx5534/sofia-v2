# thirdparty_stubs/sqlalchemy/orm/__init__.py
from ..._common import _Dummy

Session = _Dummy
sessionmaker = lambda *args, **kwargs: _Dummy
relationship = lambda *args, **kwargs: None
backref = lambda *args, **kwargs: None
Query = _Dummy
declarative_base = lambda *args, **kwargs: _Dummy

__all__ = ["Session", "sessionmaker", "relationship", "backref", "Query", "declarative_base"]
