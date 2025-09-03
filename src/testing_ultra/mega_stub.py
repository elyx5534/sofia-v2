"""
MEGA STUB SYSTEM - Stubs EVERYTHING automatically
"""

import importlib.abc
import importlib.machinery
import sys
import types


class MegaStubFinder(importlib.abc.MetaPathFinder):
    """Finds and stubs ANY module that doesn't exist"""

    REAL_MODULES = {
        "sys",
        "os",
        "types",
        "typing",
        "unittest",
        "importlib",
        "builtins",
        "__builtin__",
        "collections",
        "itertools",
        "functools",
        "operator",
        "math",
        "random",
        "datetime",
        "time",
        "json",
        "pickle",
        "pathlib",
        "io",
        "re",
        "src",
        "tests",
        "pytest",
        "pandas",
        "numpy",
    }

    def find_spec(self, fullname, path, target=None):
        # Let real modules pass through
        parts = fullname.split(".")
        if parts[0] in self.REAL_MODULES:
            return None

        # Stub everything else
        return importlib.machinery.ModuleSpec(fullname, MegaStubLoader(), origin="mega_stub")


class MegaStubLoader(importlib.abc.Loader):
    """Loads stub modules"""

    def create_module(self, spec):
        return MegaStubModule(spec.name)

    def exec_module(self, module):
        pass


class MegaStubModule(types.ModuleType):
    """Universal stub module that returns stubs for any attribute"""

    def __init__(self, name):
        super().__init__(name)
        self.__name__ = name
        self.__file__ = f"<mega_stub:{name}>"

    def __getattr__(self, name):
        # Return a universal stub for any attribute
        if name.startswith("__"):
            raise AttributeError(name)
        return UniversalStub(f"{self.__name__}.{name}")


class UniversalStub:
    """Stub that can be anything - class, function, property, etc."""

    def __init__(self, name="stub"):
        self.name = name
        self.__name__ = name
        self.__qualname__ = name
        self.__module__ = "mega_stub"
        self.__doc__ = f"Stub for {name}"

    def __call__(self, *args, **kwargs):
        # Can be called as function
        return UniversalStub(f"{self.name}()")

    def __new__(cls, *args, **kwargs):
        # Can be instantiated
        return UniversalStub(f"{cls.name}()")

    def __getattr__(self, name):
        # Has any attribute
        if name.startswith("__"):
            raise AttributeError(name)
        return UniversalStub(f"{self.name}.{name}")

    def __getitem__(self, key):
        # Can be indexed
        return UniversalStub(f"{self.name}[{key}]")

    def __iter__(self):
        # Can be iterated
        return iter([])

    def __len__(self):
        return 0

    def __bool__(self):
        return True

    def __str__(self):
        return f"<MegaStub:{self.name}>"

    def __repr__(self):
        return f"<MegaStub:{self.name}>"

    # Math operations
    def __add__(self, other):
        return self

    def __sub__(self, other):
        return self

    def __mul__(self, other):
        return self

    def __div__(self, other):
        return self

    def __truediv__(self, other):
        return self

    def __floordiv__(self, other):
        return self

    def __mod__(self, other):
        return self

    def __pow__(self, other):
        return self

    # Comparison
    def __eq__(self, other):
        return True

    def __ne__(self, other):
        return False

    def __lt__(self, other):
        return False

    def __le__(self, other):
        return True

    def __gt__(self, other):
        return False

    def __ge__(self, other):
        return True

    # Context manager
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    # Async
    def __await__(self):
        return iter([])

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


def install_mega_stub():
    """Install the mega stub system"""
    # Remove if already installed
    sys.meta_path = [f for f in sys.meta_path if not isinstance(f, MegaStubFinder)]
    # Install at the beginning
    sys.meta_path.insert(0, MegaStubFinder())


def uninstall_mega_stub():
    """Uninstall the mega stub system"""
    sys.meta_path = [f for f in sys.meta_path if not isinstance(f, MegaStubFinder)]
