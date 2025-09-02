import importlib, pkgutil, pathlib

def iter_modules():
    pkg_path = pathlib.Path(__file__).resolve().parents[2] / "src"
    prefix = "src."
    for m in pkgutil.walk_packages([str(pkg_path)], prefix):
        name = m.name
        # ağır ya da gereksiz importları ayıkla:
        if any(s in name for s in ["deprecated", ".tests", ".__main__"]):
            continue
        yield name

def test_import_all_modules():
    failed = []
    for name in iter_modules():
        try:
            importlib.import_module(name)
        except Exception as e:
            failed.append((name, str(e)))
    assert not failed, f"Import failed: {failed[:8]}"