# thirdparty_stubs/sqlalchemy/__init__.py
from .._common import _Dummy


def create_engine(*args, **kwargs):
    return _Dummy()


Column = _Dummy
Integer = _Dummy
String = _Dummy
Float = _Dummy
Boolean = _Dummy
DateTime = _Dummy
Date = _Dummy
Time = _Dummy
Text = _Dummy
ForeignKey = _Dummy
Table = _Dummy
MetaData = _Dummy

__all__ = [
    "create_engine",
    "Column",
    "Integer",
    "String",
    "Float",
    "Boolean",
    "DateTime",
    "Date",
    "Time",
    "Text",
    "ForeignKey",
    "Table",
    "MetaData",
]
