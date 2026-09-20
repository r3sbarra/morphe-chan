#!/usr/bin/env python
"""Tests for language-aware synthesis (self-derived fix for the synthesizer
ignoring its `language` arg).

Before: synthesize(shape, "js") returned Python-flavored code. Now `js` emits
valid JavaScript (function signature + brace blocks) that round-trips through
the JS adapter. Python output is unchanged (regression guard).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from code_shape.synthesis.code_synthesizer import synthesize
from code_shape.core.enriched_shape import enriched_shape


def _prims(code, lang):
    s = enriched_shape(code, lang)
    return sorted(k.split(":", 1)[1] for k, v in s.items()
                  if k.startswith("PRIM:") and v not in (0, 0.0))


def test_js_signature_and_braces():
    code = synthesize("LOOP>ARITH_ADD>ASSIGN>RETURN", "js")
    assert code.startswith("function fn(items) {")
    assert code.rstrip().endswith("}")


def test_js_roundtrip_preserves_primitives():
    for shape, target in {
        "LOOP>ARITH_ADD>ASSIGN>RETURN": {"LOOP", "ARITH_ADD", "ASSIGN", "RETURN"},
        "BRANCH>COMPARE_GT>RETURN": {"BRANCH", "COMPARE_GT", "RETURN"},
        "LOOP>COMPARE_EQ>BRANCH>RETURN": {"LOOP", "COMPARE_EQ", "BRANCH", "RETURN"},
    }.items():
        code = synthesize(shape, "js")
        got = set(_prims(code, "js"))
        assert target <= got, (shape, target, got)


def test_python_output_unchanged():
    # python must still use the def signature (regression)
    code = synthesize("LOOP>ARITH_ADD>ASSIGN>RETURN", "python")
    assert code.startswith("def fn(items):")
    assert "for item in items:" in code


def test_js_differs_from_python():
    py = synthesize("ARITH_ADD>RETURN", "python")
    js = synthesize("ARITH_ADD>RETURN", "js")
    assert py != js
    assert "function" in js and "def " in py


def test_lang_alias_consistency():
    # 'js' and 'javascript' must agree across synthesis paths (code_synthesizer
    # uses 'js'; shape_library_synth uses 'javascript').
    from code_shape.synthesis.shape_library_synth import synthesize_any
    js_bin = synthesize_any("binary_search", "LOOP>BRANCH>RETURN", "js", "f")
    js_full = synthesize_any("binary_search", "LOOP>BRANCH>RETURN", "javascript", "f")
    assert js_bin and js_full and js_bin == js_full
    assert "function" in js_bin
    py_ali = synthesize_any("read_file", "READ>RETURN", "py", "f")
    py_full = synthesize_any("read_file", "READ>RETURN", "python", "f")
    assert py_ali and py_full and py_ali == py_full


def test_all_library_intents_synthesize_in_js():
    # previously send_email was the only intent without a JS library template
    from code_shape.synthesis.shape_library_synth import synthesize as slsynthesize
    for intent in ("fetch_api", "scrape_web", "query_db", "read_file", "exec_cmd",
                   "write_file", "hash_password", "send_email", "parse_json", "render_html"):
        code = slsynthesize(intent, "READ>RETURN", "js", "f")
        assert code and "function" in code, (intent, code)
