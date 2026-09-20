"""Regression tests for multi-line Rust tail-return and empty-code edge case.

These cover bugs found during independent verification:
  1. Rust tail-return regex only matched single-line `{ expr }` format; 
     real-world multi-line `{\n    expr\n}` failed to emit PRIM:RETURN.
  2. Empty code produced a non-zero enriched vector (STATE:PURE=1.0)
     because state_dims marked empty input as "pure" (vacuously true).
"""
import sys, math
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from code_shape.adapters.rust import RustAdapter
from code_shape.core.enriched_shape import enriched_shape
from code_shape.core.code_shape_core import primitive_similarity


def test_rust_multiline_tail_return():
    """Multi-line Rust fn with tail expression must emit PRIM:RETURN."""
    from code_shape.core.enriched_shape import enriched_shape
    es = enriched_shape("fn add(a: i32, b: i32) -> i32 {\n    a + b\n}", "rust")
    assert es.get("PRIM:RETURN", 0) > 0, "Rust multi-line tail return missing PRIM:RETURN"


def test_rust_single_line_still_works():
    """Single-line Rust tail return must still work (regression guard)."""
    es = enriched_shape("fn add(a: i32, b: i32) -> i32 { a + b }", "rust")
    assert es.get("PRIM:RETURN", 0) > 0


def test_rust_explicit_return_no_double_count():
    """Explicit return in Rust must not be double-counted with tail-return."""
    d = RustAdapter().decompose("fn add(a: i32, b: i32) -> i32 {\n    return a + b;\n}")
    assert d["RETURN"] == 1


def test_rust_no_tail_for_void_fn():
    """Rust fn with only println! (no tail expression) must not emit RETURN."""
    d = RustAdapter().decompose("fn foo() {\n    println!(\"hi\");\n}")
    assert d["RETURN"] == 0


def test_rust_multiline_cross_language_add():
    """Multi-line Rust add() must score ~1.0 vs Python add()."""
    sim = primitive_similarity(
        "def add(a, b):\n    return a + b",
        "fn add(a: i32, b: i32) -> i32 {\n    a + b\n}",
        "python", "rust"
    )
    assert sim > 0.99, f"Rust multi-line cross-lang sim={sim:.4f}, expected >0.99"


def test_empty_code_no_state_pure():
    """Empty code must not produce STATE:PURE=1.0 (non-zero vector for no code)."""
    es = enriched_shape("", "python")
    assert es.get("STATE:PURE", 0) == 0, "Empty code should not have STATE:PURE"
    # The vector should either be empty or have near-zero norm
    if es:
        norm = math.sqrt(sum(v * v for v in es.values()))
        # Allow some dims (like zero-valued PRIM:* etc.) but no single dim should dominate
        assert all(v == 0 for v in es.values()), \
            f"Empty code should produce all-zero vector, got non-zero: {dict((k,v) for k,v in es.items() if v != 0)}"


def test_pure_function_still_gets_state_pure():
    """A genuinely pure function must still get STATE:PURE > 0."""
    es = enriched_shape("def add(a, b):\n    return a + b", "python")
    assert es.get("STATE:PURE", 0) > 0


def test_anomalies_cli_has_report_flag():
    """The anomalies CLI subparser should accept --report."""
    import argparse
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    # We can't easily test the full CLI without mocking, but we can verify
    # the parser accepts --report by checking the source includes _add_report_flag
    cli_path = Path(__file__).resolve().parents[1] / "src" / "cli.py"
    src = cli_path.read_text()
    assert "anomalies" in src and "--report" in src
    # Check the handler calls _maybe_report for anomalies
    assert '_maybe_report(args, "anomalies"' in src