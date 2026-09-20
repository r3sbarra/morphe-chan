"""Regression tests for the agnostic_shape tokenizer rewrite.

Locks in fixes for the old substring-count decompose() which produced
false positives (verified empirically):
  * bare `=` firing inside `!=` / `<=` / `>=` / `==`
  * double-counting of `<=` as both `<` and `<=`
  * primitives detected from string literals and comments
  * `forEach` / `format` matching the `for` keyword
  * `-=` counting ASSIGN twice
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from code_shape.core.agnostic_shape import decompose, shape, agnostic_similarity


def test_no_assign_from_ne():
    # `=` inside `!=` must not register as an assignment.
    d = decompose("if a != b:\n    return a")
    assert d["ASSIGN"] == 0, d
    assert d["COMPARE_NE"] == 1, d


def test_le_not_double_counted():
    # `<=` must register once as LE, not also as LT, and not as ASSIGN.
    d = decompose("while a <= b:\n    pass")
    assert d["COMPARE_LE"] == 1, d
    assert d["COMPARE_LT"] == 0, d
    assert d["ASSIGN"] == 0, d


def test_compound_assignment_not_double_counted():
    d = decompose("a -= 1")
    assert d["ASSIGN"] == 1, d
    assert d["STATE"] == 1, d
    assert d["ARITH_SUB"] == 0, d  # `-=` is compound, not bare subtraction


def test_no_primitive_from_string_literal():
    d = decompose('print("a + b")')
    assert d["ARITH_ADD"] == 0, d
    assert d["WRITE"] == 1, d


def test_no_branch_from_comment():
    d = decompose("# if foo: just a comment\nreturn 1")
    assert d["BRANCH"] == 0, d
    assert d["RETURN"] == 1, d


def test_foreach_is_not_loop_keyword():
    d = decompose("s.forEach(x => f(x))")
    assert d["LOOP"] == 0, d


def test_format_is_not_loop():
    d = decompose("return format(x)")
    assert d["LOOP"] == 0, d


def test_real_for_loop_detected():
    d = decompose("for n in nums:\n    total += n")
    assert d["LOOP"] == 1, d


def test_cross_language_equivalence():
    py = "def sum_list(nums):\n    total = 0\n    for n in nums:\n        total += n\n    return total"
    js = "function sumList(nums) {\n    let total = 0;\n    for (let n of nums) {\n        total += n;\n    }\n    return total;\n}"
    sim = agnostic_similarity(py, js)
    assert sim > 0.9, sim
