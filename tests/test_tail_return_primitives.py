#!/usr/bin/env python
"""Regression tests for implicit/tail-expression return detection in the
Rust and Ruby adapters (self-derived cross-language gap, see
research/SELF_DERIVATION_2026-09-20.md).

Before: Rust `fn add(a,b){ a+b }` and Ruby `def add(a,b) ... a+b end` emitted
NO `PRIM:RETURN` (their adapters use implicit/tail-expression returns, not the
`return` keyword), so the unit-normalized enriched vector differed from the
identical Python/JS/Go/etc. version → cross-language clone cosine dropped to
0.707 (Rust) instead of 1.000. Verified: after the fix, all 10 languages score
1.000 for the same `add` function.
"""
import sys, math
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from code_shape.core.enriched_shape import enriched_shape
from code_shape.core.code_shape_core import primitive_similarity


def _prims(code, lang):
    s = enriched_shape(code, lang)
    return sorted(k.split(":", 1)[1] for k, v in s.items()
                  if k.startswith("PRIM:") and v not in (0, 0.0))


def _prim_cos(a_code, a_lang, b_code, b_lang):
    def pv(code, lang):
        s = enriched_shape(code, lang)
        p = {k: v for k, v in s.items()
             if k.startswith("PRIM:") and v not in (0, 0.0)}
        n = math.sqrt(sum(v * v for v in p.values()))
        return {k: v / n for k, v in p.items()}
    va, vb = pv(a_code, a_lang), pv(b_code, b_lang)
    return sum(x * vb.get(k, 0.0) for k, x in va.items())


def test_rust_tail_expression_emits_return():
    d = _prims("fn add(a: i32, b: i32) -> i32 { a + b }", "rust")
    assert "RETURN" in d, d
    assert "ARITH_ADD" in d, d


def test_ruby_tail_expression_emits_return():
    d = _prims("def add(a, b)\n  a + b\nend", "ruby")
    assert "RETURN" in d, d


def test_explicit_return_not_double_counted():
    # explicit `return` still counts exactly one RETURN
    rust = _prims("fn add(a: i32, b: i32) -> i32 { let r = a + b; return r; }", "rust")
    assert rust.count("RETURN") == 1, rust
    ruby = _prims("def add(a, b)\n  return a + b\nend", "ruby")
    assert ruby.count("RETURN") == 1, ruby


def test_ruby_write_not_false_positive_return():
    d = _prims("def greet(name)\n  puts name\nend", "ruby")
    assert "RETURN" not in d, d
    assert "WRITE" in d, d


def test_cross_language_add_primitive_invariant():
    # same logical fn across languages → near-identical primitive vector
    for lang, code in {
        "js": "function add(a, b) { return a + b; }",
        "go": "func add(a, b int) int { return a + b }",
        "java": "int add(int a, int b) { return a + b; }",
        "rust": "fn add(a: i32, b: i32) -> i32 { a + b }",
        "ruby": "def add(a, b)\n  a + b\nend",
    }.items():
        c = _prim_cos(code, lang, "def add(a, b):\n    return a + b", "python")
        assert c > 0.99, (lang, c)


def test_prim_space_discriminates_different_fns():
    # a genuinely different function must be far from `add`
    c = _prim_cos("def add(a, b):\n    return a + b", "python",
                  "def f(x):\n    if x > 0:\n        return x * 2\n    return x", "python")
    assert c < 0.75, c


def test_primitive_similarity_cross_language_invariant():
    # same logical fn across languages -> ~1.0 via the public API
    py = "def add(a, b):\n    return a + b"
    for lang, code in {
        "js": "function add(a, b) { return a + b; }",
        "go": "func add(a, b int) int { return a + b }",
        "rust": "fn add(a: i32, b: i32) -> i32 { a + b }",
        "ruby": "def add(a, b)\n  a + b\nend",
    }.items():
        c = primitive_similarity(py, code, "python", lang)
        assert c > 0.99, (lang, c)


def test_primitive_similarity_discriminates():
    add = "def add(a, b):\n    return a + b"
    mm = "def mm(A,B):\n    n = len(A)\n    C = [[0]*n for _ in range(n)]\n    for i in range(n):\n        for j in range(n):\n            for k in range(n):\n                C[i][j] += A[i][k]*B[k][j]\n    return C"
    assert primitive_similarity(add, mm, "python", "python") < 0.7
