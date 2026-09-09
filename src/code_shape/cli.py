"""Thin wrapper so the `morphe-chan` console script entry point works.

The real CLI lives at `src/cli.py` (top-level, runnable via
`python3 src/cli.py`). This module re-exports its `main` so the
`[project.scripts] morphe-chan = "code_shape.cli:main"` entry point resolves.
"""

import sys
from pathlib import Path

_src = Path(__file__).resolve().parents[1]
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from cli import main  # noqa: E402,F401

__all__ = ["main"]
