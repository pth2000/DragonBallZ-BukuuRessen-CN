"""Locate the repository root, and make `dbzbr` importable without an install.

Every tool in this directory needs the project root to resolve its default
paths. Deriving it from this file's location is more reliable than deriving it
from the installed package, because the tools only make sense inside a checkout.

The `sys.path` entry is a fallback. After `uv sync` the package is installed in
editable mode and `import dbzbr` already works; this keeps a bare
`python tools/<name>.py` working in a checkout that was never synced.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if SRC.is_dir() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
