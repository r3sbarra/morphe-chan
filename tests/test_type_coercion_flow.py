"""Regression tests for coercion-based param type inference (variable_shape).

Previously params passed to coercion builtins (`int(data)`, `str(x)`) stayed
UNKNOWN, which left the cascading cross-function type flow completely inert
(no propagation, no type errors). Now the coercion argument is inferred, which
unlocks cross-function propagation and type-error detection.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from code_shape.core.variable_shape import infer_types, cascading_type_flow


def test_int_coercion_infers_arg_numeric():
    t = infer_types("def parse(data):\n    return int(data)", "python")
    assert t.get("data") == "NUM", t


def test_str_coercion_infers_arg_string():
    t = infer_types("def fmt(x):\n    return str(x)", "python")
    assert t.get("x") == "STR", t


def test_cross_function_propagation_now_works():
    # param NUM propagates to an UNKNOWN argument in a caller.
    code = "def parse(data):\n    return int(data)\ndef use(x):\n    y = x\n    return parse(y)"
    r = cascading_type_flow(code, "python")
    assert r["propagations"] >= 1, r


def test_cross_function_type_error_detected():
    # passing a LIST where int is expected -> type error now caught.
    code = "def parse(data):\n    return int(data)\ndef use():\n    items = [1, 2, 3]\n    return parse(items)"
    r = cascading_type_flow(code, "python")
    assert r["type_errors"] >= 1, r
