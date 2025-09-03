# thirdparty_stubs/sqlalchemy/ext/declarative/__init__.py
from ..._common import _Dummy

declarative_base = lambda *args, **kwargs: _Dummy

__all__ = ["declarative_base"]
