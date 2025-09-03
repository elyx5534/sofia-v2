# scripts/rewrite_imports_to_adapters.py
from __future__ import annotations

import ast
import io
import pathlib

MAPPING = {
    "xgboost": "src.adapters.ml.xgboost_adapter",
    "sklearn": "src.adapters.ml.sklearn_adapter",
    "sklearn.pipeline": "src.adapters.ml.sklearn_adapter",
    "sklearn.model_selection": "src.adapters.ml.sklearn_adapter",
    "sklearn.metrics": "src.adapters.ml.sklearn_adapter",
    "statsmodels.api": "src.adapters.stats.statsmodels_adapter",
    "sqlalchemy": "src.adapters.db.sqlalchemy_adapter",
    "sqlalchemy.orm": "src.adapters.db.sqlalchemy_adapter",
    "sqlmodel": "src.adapters.db.sqlmodel_adapter",
    "ta": "src.adapters.ta.ta_adapter",
    "pandas_ta": "src.adapters.ta.ta_adapter",
    "fastapi": "src.adapters.web.fastapi_adapter",
    "fastapi.responses": "src.adapters.web.fastapi_adapter",
    "fastapi.testclient": "src.adapters.web.fastapi_adapter",
}


class Rewriter(ast.NodeTransformer):
    def visit_Import(self, node: ast.Import):
        new_names = []
        replaced = False
        for alias in node.names:
            n = alias.name
            tgt = MAPPING.get(n)
            if tgt:
                # import xgboost as xgb -> from adapters import xgb (module aliasını koruyamayız; kullanıcı genelde xgboost.XGB... kullanıyorsa sorun olmaz)
                new = ast.ImportFrom(module=tgt, names=[ast.alias(name="*", asname=None)], level=0)
                replaced = True
                return ast.fix_missing_locations(new)
            else:
                new_names.append(alias)
        node.names = new_names
        return node

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module is None:
            return node
        tgt = MAPPING.get(node.module)
        if tgt:
            node.module = tgt
            node.level = 0
            return ast.fix_missing_locations(node)
        return node


def rewrite_file(p: pathlib.Path):
    src = p.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return False
    new = Rewriter().visit(tree)
    ast.fix_missing_locations(new)
    code = compile(new, str(p), "exec")
    out = io.StringIO()
    # ast.unparse Python 3.9+:
    try:
        new_text = ast.unparse(new)
    except Exception:
        # fallback: no change
        return False
    if new_text != src:
        p.write_text(new_text, encoding="utf-8")
        return True
    return False


def main():
    root = pathlib.Path("src")
    changed = 0
    for p in root.rglob("*.py"):
        if any(s in str(p) for s in ("/ui/", "\\ui\\", "/tests/", "\\tests\\")):
            continue
        if rewrite_file(p):
            changed += 1
    print(f"rewritten: {changed} files")


if __name__ == "__main__":
    main()
