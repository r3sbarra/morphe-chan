#!/usr/bin/env python
"""Tests that the STATE/DATA/CTRL/IFACE/RES dimensions (new_shape_dims) are wired
into the enriched shape — a self-derived improvement (they were defined but never
integrated into enriched_shape).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from code_shape.core.enriched_shape import enriched_shape


def _dim(code, name):
    return {k: v for k, v in enriched_shape(code).items() if k == name}.get(name, 0.0)


def test_cyclomatic_present_and_ranks():
    simple = _dim("def add(a, b):\n    return a + b", "CTRL:CYCLOMATIC")
    branched = _dim("def f(x):\n    if x > 0: return 1\n    elif x < 0: return -1\n    return 0", "CTRL:CYCLOMATIC")
    assert simple > 0
    assert branched > simple  # more branches -> higher cyclomatic


def test_exceptions_dim():
    v = _dim("def g(x):\n    try:\n        return int(x)\n    except Exception:\n        return 0", "CTRL:EXCEPTIONS")
    assert v > 0


def test_state_pure_vs_mutates():
    pure = _dim("def add(a, b):\n    return a + b", "STATE:PURE")
    mut = _dim("def f(items):\n    items.append(1)\n    return items", "STATE:MUTATES")
    assert pure > 0 and mut > 0


def test_interface_arity():
    v = _dim("def f(a, b, c):\n    return a + b + c", "IFACE:ARITY")
    assert v > 0


def test_extra_dims_do_not_break_enriched():
    # adding the new dims must keep the vector unit-normalized
    import math
    s = enriched_shape("def f(x):\n    return x + 1")
    nrm = math.sqrt(sum(v * v for v in s.values()))
    assert abs(nrm - 1.0) < 1e-3  # 4-decimal per-dim rounding -> ~0.9999
