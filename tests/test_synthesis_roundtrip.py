#!/usr/bin/env python
"""Regression tests for synthesis round-trip fidelity fixes.

Derived from the self-consistency audit (experiments/self_derive_roundtrip.py):
single-primitive shapes READ / ARITH_ADD / SEARCH / FILTER did not round-trip
(synthesize -> re-analyze preserved the target primitive). The templates fired
only ASSIGN or the wrong primitives. After template fixes all four now
round-trip (overlap >= 0.5).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from code_shape.synthesis.code_synthesizer import synthesize, verify_roundtrip


def test_read_roundtrip():
    rt = verify_roundtrip("READ")
    assert rt["ok"], rt
    assert "READ" in rt["actual"], rt


def test_arith_add_roundtrip():
    rt = verify_roundtrip("ARITH_ADD")
    assert rt["ok"], rt
    assert "ARITH_ADD" in rt["actual"], rt


def test_search_roundtrip():
    rt = verify_roundtrip("SEARCH")
    assert rt["ok"], rt
    assert "SEARCH" in rt["actual"], rt


def test_filter_roundtrip():
    rt = verify_roundtrip("FILTER")
    assert rt["ok"], rt
    assert "FILTER" in rt["actual"], rt


def test_common_composites_roundtrip():
    for shape in [
        "READ>BRANCH>COMPARE_GT>RETURN",
        "LOOP>COMPARE_EQ>BRANCH>RETURN",
        "READ>AGGREGATE>ARITH_ADD>RETURN",
    ]:
        rt = verify_roundtrip(shape)
        assert rt["ok"], (shape, rt)
