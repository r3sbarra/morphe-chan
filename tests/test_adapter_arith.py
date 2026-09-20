"""Regression tests for lexer-aware arithmetic in the base adapter decompose.

The adapters counted arithmetic with SPACED regexes (` \+ `, ` \* `), so compact
operators (`lo+hi`, `a*b`) were missed — weakening cross-language similarity (a
Python binary search showed 0 arithmetic dims while the identical Go version
showed 3). Now arithmetic is counted by TOKEN: compact operators fire, string
literals (already stripped) never do, and `*` correctly excludes pointer
deref `*p`, `SELECT * FROM`, and `import java.util.*`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from code_shape.core.code_shape_core import get_adapter, true_similarity


def _dims(code, lang):
    a = get_adapter(code, lang)
    return {k: v for k, v in a.decompose(code).items() if v}


def test_compact_arithmetic_detected():
    d = _dims("def f(a, b):\n    return a*b", "python")
    assert d.get("ARITH_MUL") == 1, d


def test_compact_sub_and_div_detected():
    d = _dims("def f(arr, t):\n    hi = len(arr)-1\n    mid = (lo+hi)//2\n    return mid", "python")
    assert d.get("ARITH_SUB", 0) >= 1, d
    assert d.get("ARITH_DIV", 0) >= 1, d  # // counts as division


def test_pointer_deref_not_mul():
    d = _dims("int f() { *p = 5; return *p; }", "c")
    assert d.get("ARITH_MUL", 0) == 0, d


def test_select_star_is_not_mul():
    d = _dims("SELECT * FROM users WHERE id=1", "python")
    assert d.get("ARITH_MUL", 0) == 0, d


def test_spaced_mul_still_detected():
    d = _dims("def f(a, b):\n    return a * b", "python")
    assert d.get("ARITH_MUL") == 1, d


def test_cross_language_discrimination_improved():
    # Same algorithm (binary search) across languages must score well above a
    # genuinely different algorithm, so the discriminator is usable.
    bs_py = "def binary_search(arr, t):\n    lo, hi = 0, len(arr)-1\n    while lo <= hi:\n        mid = (lo+hi)//2\n        if arr[mid] == t:\n            return mid\n        else:\n            hi = mid-1\n    return -1"
    bs_go = "func binarySearch(arr []int, t int) int {\n    lo, hi := 0, len(arr)-1\n    for lo <= hi {\n        mid := (lo + hi) / 2\n        if arr[mid] == t {\n            return mid\n        } else {\n            hi = mid - 1\n        }\n    }\n    return -1\n}"
    sum_py = "def sum_list(nums):\n    total = 0\n    for n in nums:\n        total += n\n    return total"
    same = true_similarity(bs_py, bs_go, "python", "go")
    diff = true_similarity(sum_py, bs_py, "python", "python")
    assert same - diff > 0.1, (same, diff)  # clear separation
