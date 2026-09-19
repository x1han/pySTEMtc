"""Float-discipline guard (spec 03 §1.5 / HANDOFF D7).

Java-ordered accumulation is replicated with explicit scalar loops; NumPy
reductions may reorder additions and flip tie decisions at the last ulp, so
they are banned outright in the numeric paths under ``src/pystemtc``.

This is an AST scan (not a regex) so mentions of these names inside
docstrings/comments — this file's own docstring included — never match, and
method-form reductions (``arr.sum()``) are caught as well as ``np.sum(arr)``.
"""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "pystemtc"

# numpy function forms: np.<name>(...) / numpy.<name>(...)
NUMPY_FUNCS = {
    "sum", "mean", "std", "var", "dot", "corrcoef", "cov", "average",
    "median", "percentile", "quantile", "nansum", "nanmean", "nanstd",
    "einsum", "add.reduce", "linalg.norm",
}

# method forms: <anything>.<name>(...)
METHOD_REDUCTIONS = {
    "sum", "mean", "std", "var", "dot", "cumsum", "cumprod",
}


def _attr_chain(node: ast.AST) -> list[str]:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    parts.reverse()
    return parts


def _banned_calls(tree: ast.AST) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        chain = _attr_chain(node.func)
        if len(chain) >= 2 and chain[0] in ("np", "numpy"):
            callee = ".".join(chain[1:])
            if callee in NUMPY_FUNCS:
                found.append(("numpy." + callee, f"line {node.lineno}"))
        tail = chain[-1]
        if tail in METHOD_REDUCTIONS:
            found.append((f"...{tail}()", f"line {node.lineno}"))
    return found


def test_no_banned_numpy_reductions_in_src():
    violations = []
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for name, where in _banned_calls(tree):
            violations.append(f"{path.name}: {name} ({where})")
    assert not violations, "banned float-reordering reductions in src/pystemtc:\n" + "\n".join(violations)
