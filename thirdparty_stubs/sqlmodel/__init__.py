# thirdparty_stubs/sqlmodel/__init__.py
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from _common import _Dummy, _DummyMeta


class BaseModel(metaclass=_DummyMeta):
    """Pydantic-like base model"""

    def model_dump(self, *args, **kwargs):
        return {}

    def model_dump_json(self, *args, **kwargs):
        return "{}"

    def dict(self, *args, **kwargs):
        return {}

    def json(self, *args, **kwargs):
        return "{}"


class SQLModel(BaseModel):
    """SQLModel base class"""

    metadata = _Dummy()
    __table__ = None
    __tablename__ = None

    @classmethod
    def parse_obj(cls, obj):
        return cls()

    @classmethod
    def from_orm(cls, obj):
        return cls()


def Field(*args, **kwargs):
    return None


def Relationship(*args, **kwargs):
    return None


def create_engine(*args, **kwargs):
    return _Dummy()


class Session:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def add(self, *args, **kwargs):
        pass

    def commit(self, *args, **kwargs):
        pass

    def rollback(self, *args, **kwargs):
        pass

    def close(self, *args, **kwargs):
        pass

    def query(self, *args, **kwargs):
        return _Dummy()

    def execute(self, *args, **kwargs):
        return _Dummy()

    def get(self, *args, **kwargs):
        return _Dummy()


select = lambda *args, **kwargs: _Dummy()

__all__ = ["SQLModel", "Field", "Relationship", "create_engine", "Session", "BaseModel", "select"]
