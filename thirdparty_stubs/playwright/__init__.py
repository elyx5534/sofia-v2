# thirdparty_stubs/playwright/__init__.py
class _Dummy:
    def __init__(self, *a, **k):
        pass

    def __call__(self, *a, **k):
        return _Dummy()

    def __getattr__(self, name):
        return _Dummy()


sync_playwright = lambda: _Dummy()
async_playwright = lambda: _Dummy()

__all__ = ["sync_playwright", "async_playwright"]
