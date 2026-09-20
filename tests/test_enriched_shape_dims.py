"""Regression tests for lexer-aware enriched_shape properties + new derived data.

The _data/_control/_io/_derived helpers feed the multi-dimensional shape. They
were regex-on-raw-text and corrupted derived dims: `a != b` + a string `"x = y"`
inflated VAL:FLOW_DEPTH, `dict.get(...)` was misdetected as PROP:IO, a string
`"if we go"` inflated PROP:BRANCHES, and VAL:RISK used detect_vulns_v2 (empty on
common cases) so risk was near-useless. Now VERIFIED: FLOW_DEPTH/IO/BRANCHES are
lexer-accurate, and VAL:RISK/VAL:SEVERITY come from the precise-issues pipeline
(severity/exploitability-weighted).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from code_shape.core.enriched_shape import (
    _derived_values, _io_properties, _control_properties, _risk_score,
)


def test_flow_depth_not_inflated_by_ne_or_string():
    d = _derived_values('if a != b:\n    return "x = y"', "python")
    assert d.get("VAL:FLOW_DEPTH") == 0, d


def test_dict_get_is_not_io():
    p = _io_properties('name = d.get("x")')
    assert p.get("PROP:IO", 0) == 0, p


def test_string_if_not_branches():
    p = _control_properties('s = "if we go"\nwhile x:\n    y = 1')
    assert p.get("PROP:BRANCHES", 0) == 0, p


def test_real_assignment_counts():
    d = _derived_values("a = 1\nb = a + 1\nreturn b", "python")
    assert d.get("VAL:FLOW_DEPTH") == 2, d


def test_risk_score_from_precise_issues():
    # SQLi: worst-case severity/exploitability is CRITICAL.
    code = "def f(request):\n    name = request.form['name']\n    return db.execute('SELECT * FROM users WHERE name = ' + name)"
    risk, sev = _risk_score(code)
    assert risk > 0.5 and sev == "CRITICAL", (risk, sev)
    # clean code: no risk
    assert _risk_score("def add(a, b):\n    return a + b") == (0.0, None)


def test_coupling_counts_imports():
    d = _derived_values("import requests\nimport os\ndef f():\n    return 1", "python")
    assert d.get("VAL:COUPLING") == 2, d


def test_enriched_shape_normalizes_with_vuln():
    # A vuln-carrying function must not crash enriched_shape normalization
    # (VAL:SEVERITY is numeric rank so the vector stays numeric-normalizable).
    from code_shape.core.enriched_shape import enriched_shape
    code = "def f(request):\n    name = request.form['name']\n    return db.execute('SELECT * FROM users WHERE name = ' + name)"
    vec = enriched_shape(code, "python")
    assert vec.get("VAL:RISK", 0) > 0
    assert vec.get("VAL:SEVERITY", 0) > 0


def test_vuln_dim_from_precise_issues_single_run():
    # The VULN:<type> dim must now come from precise-issues (previously
    # detect_vulns_v2 returned empty, so this dim was missing on real SQLi).
    from code_shape.core.enriched_shape import enriched_shape
    code = "def f(request):\n    name = request.form['name']\n    return db.execute('SELECT * FROM users WHERE name = ' + name)"
    vec = enriched_shape(code, "python")
    assert any(k.startswith("VULN:") for k in vec), \
        [k for k in vec if k.startswith("VULN:")]
