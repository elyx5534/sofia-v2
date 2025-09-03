# thirdparty_stubs/psycopg2/__init__.py
from .._common import _Dummy

connect = lambda *args, **kwargs: _Dummy()

__all__ = ["connect"]
