"""Regression tests for lexer-aware value_flow_shape transforms.

Confirmed bugs before the fix: (1) string-method transforms (.strip/.upper)
produced NO FLOW dims; (2) compact arithmetic `a=b+c` (no spaces) missed
FLOW:ARITH because the pattern required spaces; (3) a `"a + b"` string literal
false-positived as FLOW:ARITH + FLOW:CONCAT. Now lexer-aware.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from code_shape.core.value_flow_shape import value_flow_shape


def _flow(code):
    return {k: v for k, v in value_flow_shape(code).items() if k.startswith("FLOW:")}


def test_string_method_transform_detected():
    f = _flow("s = x.strip()\nreturn s.upper()")
    assert "FLOW:STRING_TRANSFORM" in f, f


def test_compact_arithmetic_detected():
    f = _flow("a = b+c\nreturn a")
    assert "FLOW:ARITH" in f, f


def test_string_literal_not_arithmetic():
    f = _flow('m = "a + b"\nreturn m')
    assert "FLOW:ARITH" not in f, f
    assert "FLOW:CONCAT" not in f, f


def test_cast_and_aggregate_preserved():
    assert "FLOW:CAST" in _flow("n = int(x)")
    assert "FLOW:AGGREGATE" in _flow("t = sum(nums)")


def test_comprehension_is_filter():
    f = _flow("ev = [n for n in nums if n % 2 == 0]")
    assert "FLOW:FILTER" in f, f


def test_slice_detected():
    assert "FLOW:SLICE" in _flow("x = arr[1:3]")
