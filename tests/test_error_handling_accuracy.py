"""Regression tests for A10 error-handling detection improvements.

Coverage gaps found once the A10 detector was surfaced in posture:
1. FAILING_OPEN missed generic fail-open vars (`ok = True`, `flag = True`) in
   exception handlers — only named privilege vars like `authorized` matched.
2. ERROR_LEAK missed logging/raising a request object or headers/cookies
   (leaks auth, cookies, IPs) — only literal secret key names matched.
Both fixed; benign cases must stay unflagged.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from code_shape.security.error_handling import find_error_handling_issues


def _types(code):
    return [i["type"] for i in find_error_handling_issues(code)]


def test_failing_open_generic_ok_var():
    code = ("def a(r):\n    try:\n        ok = check(r)\n"
            "    except Exception:\n        ok = True\n    return ok")
    assert "FAILING_OPEN" in _types(code)


def test_failing_open_flag_var():
    code = ("def a(r):\n    try:\n        ok = check(r)\n"
            "    except Exception:\n        flag = True\n    return ok")
    assert "FAILING_OPEN" in _types(code)


def test_failing_open_false_not_flagged():
    code = ("def a(r):\n    try:\n        ok = check(r)\n"
            "    except Exception:\n        ok = False\n    return ok")
    assert "FAILING_OPEN" not in _types(code)  # fails closed, not open


def test_error_leak_logging_headers():
    code = ("def h(r):\n    try:\n        x()\n    except Exception:\n"
            "        logging.error('fail ' + str(r.headers))")
    assert "ERROR_LEAK" in _types(code)


def test_error_leak_still_logs_secret_key():
    code = ("def h():\n    try:\n        x()\n    except Exception:\n"
            "        logging.error('pw=' + password)")
    assert "ERROR_LEAK" in _types(code)


def test_error_leak_benign_not_flagged():
    code = ("def h():\n    try:\n        x()\n    except Exception as e:\n"
            "        logging.error('code ' + str(e))")
    assert "ERROR_LEAK" not in _types(code)
