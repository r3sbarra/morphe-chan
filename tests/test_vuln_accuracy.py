"""Regression tests for vuln-detection accuracy fixes in precise_issues.

Two verified accuracy fixes:
1. LOG_INJECTION: a `+` concat in a log is only an injection when a tainted/
   untrusted source is present. `logger.info('started' + str(port))` (no
   param/untrusted input) must NOT be flagged, while `req.form[...]` must.
2. XSS: the compound `el.innerHTML += html` sink was missed (only `=` matched);
   and template-literal interpolation `${...}` INTO a DOM sink is itself an
   untrusted signal, so it must be flagged regardless of identifier name.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from code_shape.security.precise_issues import find_precise_issues


def _types(code):
    return [i["type"] for i in find_precise_issues(code)]


def test_log_injection_requires_taint():
    # Safe module-level string conversion: no untrusted source -> not flagged.
    assert "LOG_INJECTION" not in _types('logger.info("started" + str(port))')
    # A tainted source (request) in the log line -> flagged.
    assert "LOG_INJECTION" in _types(
        "def log(req):\n    logger.info('user ' + req.form['u'])")


def test_log_injection_plain_var_clean():
    # Plain identifier (no + concat, no taint) is not flagged.
    assert "LOG_INJECTION" not in _types("def log(name):\n    logger.info(name)")


def test_xss_compound_assignment_detected():
    # `innerHTML += html` is a common XSS sink (was missed; only `=` matched).
    assert "XSS" in _types("def f(html):\n    el.innerHTML += html")


def test_xss_template_literal_self_taint():
    # `${...}` interpolation into a DOM sink is itself the untrusted signal,
    # even when the interpolated var isn't named like request/req/input.
    assert "XSS" in _types('document.write(`<div>${name}</div>`)')


def test_real_cves_still_detected():
    # Guard: taint gating must not regress canonical sink detection.
    assert "CMD_INJECTION" in _types('os.system(cmd)')
    assert "EVAL_USE" in _types("def f(x):\n    return eval(x)")
    assert "SQL_INJECTION" in _types(
        "def f(uid):\n    cur.execute('SELECT * FROM t WHERE id=' + str(uid))")
