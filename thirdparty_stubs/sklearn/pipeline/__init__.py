# thirdparty_stubs/sklearn/pipeline/__init__.py
from ..._common import _Dummy

Pipeline = _Dummy
FeatureUnion = _Dummy
make_pipeline = lambda *args, **kwargs: _Dummy()
make_union = lambda *args, **kwargs: _Dummy()

__all__ = ["Pipeline", "FeatureUnion", "make_pipeline", "make_union"]
