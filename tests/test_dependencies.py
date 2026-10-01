"""Every module-level third-party import in src/timbro must be a declared dependency (#141)."""

from __future__ import annotations

import ast
import importlib.metadata
import sys
import tomllib
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "timbro"
PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def _canonical(name: str) -> str:
    return name.lower().replace("_", "-")


def _walk_module_level(tree: ast.AST):
    """Yield nodes at module scope: descend into blocks, never into functions."""
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        yield node
        yield from _walk_module_level(node)


def _top_module(name: str) -> str:
    return name.split(".")[0]


def _module_level_imports() -> set[str]:
    tops: set[str] = set()
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in _walk_module_level(tree):
            if isinstance(node, ast.Import):
                tops.update(_top_module(alias.name) for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                tops.add(_top_module(node.module))
    return tops


class TestDependencies(unittest.TestCase):
    def test_module_level_imports_are_declared(self):
        module_dists = importlib.metadata.packages_distributions()
        declared = {
            _canonical(dep.split(">")[0].split("<")[0].split("=")[0].strip())
            for dep in tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"][
                "dependencies"
            ]
        }
        tops = {
            t
            for t in _module_level_imports()
            if t not in sys.stdlib_module_names and t != "timbro"
        }
        undeclared = []
        for top in sorted(tops):
            dists = module_dists.get(top)
            if not dists:
                undeclared.append(f"{top} (no distribution mapping)")
                continue
            for dist in dists:
                if _canonical(dist) not in declared:
                    undeclared.append(f"{top} -> {dist}")
        self.assertEqual([], undeclared)


if __name__ == "__main__":
    unittest.main()
