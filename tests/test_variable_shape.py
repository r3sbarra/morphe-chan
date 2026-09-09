"""Tests for variable_shape.py — param/variable shape enrichment.

Covers:
  1. Smart type inference (AST-based for Python)
  2. Param/variable shape dimensions
  3. Type profile (compact comparison representation)
  4. Cascading type flow across the call graph
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from code_shape.core.variable_shape import (
    infer_types, variable_shape, variable_shape_normalized,
    type_profile, type_profile_normalized, cascading_type_flow,
    merge_variable_shape,
)
from code_shape.core.code_shape_core import cosine


def test_infer_types_annotations():
    """Type annotations are honored."""
    types = infer_types("def f(data: List[int], factor: float) -> List[int]:\n    return data")
    assert types["data"] == "LIST"
    assert types["factor"] == "FLOAT"


def test_infer_types_assignment():
    """Assignment RHS infers type."""
    types = infer_types("def f():\n    x = [1, 2, 3]\n    return x")
    assert types["x"] == "LIST"


def test_infer_types_usage_refinement():
    """Usage refinement resolves UNKNOWN params."""
    # for-loop iteration -> LIST
    types = infer_types("def f(items):\n    for item in items:\n        pass")
    assert types["items"] == "LIST"
    # .get() -> DICT
    types = infer_types("def f(config):\n    return config.get('k')")
    assert types["config"] == "DICT"
    # .upper() -> STR
    types = infer_types("def f(name):\n    return name.upper()")
    assert types["name"] == "STR"


def test_infer_types_cascading():
    """Cascading propagation: f(x) where f's param is LIST -> x is LIST."""
    code = "def helper(items):\n    return len(items)\ndef main(data):\n    return helper(data)"
    types = infer_types(code)
    assert types["items"] == "LIST"
    assert types["data"] == "LIST"


def test_variable_shape_dims():
    """Variable shape has PARAM/VAR dims with types and roles."""
    vs = variable_shape("def f(items, threshold):\n    result = []\n    for item in items:\n        if item > threshold:\n            result.append(item)\n    return result")
    assert any(k.startswith("PARAM:items:LIST") for k in vs)
    assert any(k.startswith("PARAM:items:ROLE:IN") for k in vs)
    assert any(k.startswith("VAR:result:LIST") for k in vs)
    assert vs["PARAM_COUNT"] == 2
    assert vs["VAR_COUNT"] >= 2


def test_type_profile_robust_to_renaming():
    """Type profile is invariant to variable renaming."""
    a = "def f(items, threshold):\n    result = []\n    for item in items:\n        if item > threshold:\n            result.append(item)\n    return result"
    b = "def g(data, limit):\n    out = []\n    for x in data:\n        if x > limit:\n            out.append(x)\n    return out"
    sim = cosine(type_profile_normalized(a), type_profile_normalized(b))
    assert sim > 0.9


def test_type_profile_distinguishes_types():
    """Different type profiles -> lower similarity."""
    list_fn = "def f(items):\n    return len(items)"
    dict_fn = "def f(config):\n    return config.get('k')"
    sim = cosine(type_profile_normalized(list_fn), type_profile_normalized(dict_fn))
    assert sim < 0.9


def test_cascading_type_flow():
    """Cascading flow detects propagations and type errors."""
    code = (
        "def bad(x):\n    return x.upper()\n"
        "def caller():\n    y = 42\n    return bad(y)"
    )
    cf = cascading_type_flow(code)
    assert cf["type_errors"] == 1
    assert any(c["callee"] == "bad" for c in cf["calls"])


def test_merge_variable_shape():
    """merge_variable_shape adds var dims to an enriched vector."""
    enriched = {"PRIM:LOOP": 0.5, "VAL:FLOW_DEPTH": 0.8}
    merged = merge_variable_shape(enriched, "def f(items):\n    return len(items)")
    assert "PRIM:LOOP" in merged
    assert any(k.startswith("PARAM:") or k.startswith("VAR:") for k in merged)
    assert merged["PRIM:LOOP"] == 0.5  # original preserved


def test_variable_shape_normalized():
    """Normalized variable shape is L2-normalized."""
    vs = variable_shape_normalized("def f(items):\n    return len(items)")
    assert vs  # non-empty
    norm = sum(v * v for v in vs.values()) ** 0.5
    assert abs(norm - 1.0) < 0.01


# ── Bug-catching ──────────────────────────────────────────────────────────
def test_catches_type_mismatch():
    """Passing INT to a STR param is a type error."""
    code = (
        "def format_user(name, age):\n"
        "    return name + str(age)\n"
        "def main():\n"
        "    return format_user(30, 'Alice')\n"
    )
    cf = cascading_type_flow(code)
    assert cf["type_errors"] >= 1


def test_catches_wrong_type_arg():
    """Passing INT to a LIST param is a type error."""
    code = (
        "def process_list(items):\n"
        "    return len(items)\n"
        "def main():\n"
        "    return process_list(42)\n"
    )
    cf = cascading_type_flow(code)
    assert cf["type_errors"] >= 1


def test_no_error_on_correct_call():
    """Correct calls produce no type errors."""
    code = (
        "def process_list(items):\n"
        "    return len(items)\n"
        "def main():\n"
        "    return process_list([1, 2, 3])\n"
    )
    cf = cascading_type_flow(code)
    assert cf["type_errors"] == 0


def test_catches_cascading_type_error():
    """Type error propagates across the call graph."""
    code = (
        "def helper(text):\n"
        "    return text.upper()\n"
        "def main():\n"
        "    x = 42\n"
        "    return helper(x)\n"
    )
    cf = cascading_type_flow(code)
    assert cf["type_errors"] >= 1


def test_numeric_compatibility():
    """INT/FLOAT/NUM are mutually compatible (no false positive)."""
    code = (
        "def divide(numerator, denominator):\n"
        "    return numerator / denominator\n"
        "def main():\n"
        "    return divide(10, 2)\n"
    )
    cf = cascading_type_flow(code)
    assert cf["type_errors"] == 0


def test_sum_infers_list():
    """sum(items) infers items as LIST (catches DICT->LIST mismatch)."""
    code = (
        "def sum_items(items):\n"
        "    return sum(items)\n"
        "def main():\n"
        "    return sum_items({'a': 1})\n"
    )
    cf = cascading_type_flow(code)
    assert cf["type_errors"] >= 1
