"""Tests for no-sink-call vuln classes (open redirect, header/log/regex injection)."""

from code_shape.security.framework_sink_detector import (
    find_framework_sinks, _extract_tainted,
)


def test_extract_tainted_propagates_aliases():
    code = "def h(user_input):\n    target = user_input\n    return redirect(target)\n"
    tainted = _extract_tainted(code)
    assert "user_input" in tainted
    assert "target" in tainted


def test_open_redirect_detected():
    code = "def h(url):\n    return redirect(url)\n"
    issues = find_framework_sinks(code)
    assert any(i["type"] == "OPEN_REDIRECT" for i in issues)


def test_open_redirect_requires_taint():
    # redirect to a hardcoded value: no tainted input -> no finding
    code = "def h():\n    return redirect('/home')\n"
    issues = find_framework_sinks(code)
    assert not any(i["type"] == "OPEN_REDIRECT" for i in issues)


def test_header_injection_requires_crlf():
    # tainted input contains CRLF into a header write
    code = "def h(user_input):\n    response.setHeader('X-Foo', user_input + '\\r\\nInjected: 1')\n"
    issues = find_framework_sinks(code)
    assert any(i["type"] == "HEADER_INJECTION" for i in issues)


def test_header_injection_no_false_positive_without_crlf():
    code = "def h(user_input):\n    response.setHeader('X-Foo', user_input)\n"
    issues = find_framework_sinks(code)
    # No CR/LF in the line -> not a header-injection finding
    assert not any(i["type"] == "HEADER_INJECTION" for i in issues)


def test_log_injection_detected():
    code = "def h(user_input):\n    logger.info('user=' + user_input + '\\n')\n"
    issues = find_framework_sinks(code)
    assert any(i["type"] == "LOG_INJECTION" for i in issues)


def test_regex_injection_detected():
    code = "def h(pattern):\n    return re.compile(pattern)\n"
    issues = find_framework_sinks(code)
    assert any(i["type"] == "REGEX_INJECTION" for i in issues)
