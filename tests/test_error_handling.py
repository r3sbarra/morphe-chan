"""Tests for the Mishandling-of-Exceptional-Conditions (OWASP A10:2025) detector.

Covers the 5 falsifiable detection patterns + the false-positive guard cases,
per research/2026-09-18 (lab-ass session c42e0f6f).
"""

from code_shape.security.error_handling import find_error_handling_issues


def _types(code):
    return sorted(set(i["type"] for i in find_error_handling_issues(code, lang="python")))


# ── True-positive detection ──────────────────────────────────────────────────

def test_failing_open_grants_access_on_error():
    code = """def handler(req):
    try:
        authorized = check_auth(req.token)
    except Exception:
        authorized = True  # fails OPEN
    return do_action(authorized)
"""
    assert "FAILING_OPEN" in _types(code)


def test_swallowed_exception():
    code = """def save(req):
    try:
        db.execute('INSERT...', req.data)
    except Exception:
        pass  # swallowed, caller thinks it succeeded
    return 'ok'
"""
    assert "SWALLOWED" in _types(code)


def test_null_deref_after_fallible_call():
    code = """def get_name(req):
    user = db.query('SELECT ...', req.id).first()
    return user.name  # deref possibly-None
"""
    assert "NULL_DEREF" in _types(code)


def test_error_leaks_sensitive_data():
    code = """def login(req):
    try:
        verify(req.password)
    except Exception:
        raise Exception('login failed password=' + req.password)
"""
    assert "ERROR_LEAK" in _types(code)


def test_missing_param_unguarded_request_access():
    code = """def handler(req):
    name = req['name']
    return name
"""
    assert "MISSING_PARAM" in _types(code)


# ── False-positive guards (must stay CLEAN) ─────────────────────────────────

def test_typed_catch_not_flagged_as_swallowed():
    # A specific, intentional typed catch is NOT the broad "swallow everything".
    code = """def f():
    try:
        do_io()
    except OSError:
        pass  # intentional, specific
"""
    assert "SWALLOWED" not in _types(code)


def test_none_guard_prevents_null_deref():
    code = """def safe(req):
    user = db.query('...', req.id).first()
    if user is None:
        return ''
    return user.name
"""
    assert "NULL_DEREF" not in _types(code)


def test_dict_get_with_default_not_null_deref():
    code = """def score():
    return item.get('exploitability', {}).get('score', 0.0)
"""
    assert "NULL_DEREF" not in _types(code)


def test_get_guard_prevents_missing_param():
    code = """def handler(req):
    name = req.get('name', '')
    return name
"""
    assert "MISSING_PARAM" not in _types(code)


def test_owasp_meta_present():
    code = """def handler(req):
    try:
        authorized = check_auth(req.token)
    except Exception:
        authorized = True
"""
    issues = find_error_handling_issues(code, lang="python", file_path="x.py")
    failing = [i for i in issues if i["type"] == "FAILING_OPEN"]
    assert failing
    assert failing[0]["owasp"] == "A10:2025-Mishandling of Exceptional Conditions"
