#!/usr/bin/env python
"""error_handling.py — Mishandling of Exceptional Conditions (OWASP A10:2025) detector.

OWASP Top 10:2025 added A10 "Mishandling of Exceptional Conditions" (24 CWEs), a
class standard injection/access-control SAST rules miss because there is no
dangerous sink call. Patterns detected (deterministic, taint-light, low-FP):

  1. FAILING_OPEN   (CWE-636 "Not Failing Securely"): an exception handler responds
                    by defaulting to an INSECURE state — grants access, returns
                    success/True/200, or falls through to allow the action — instead
                    of denying (fail closed). Detect: `except:` sets an auth/access
                    var to True/allow, or returns success right after a security check
                    failed.
  2. SWALLOWED      (CWE-390 "Detection of Error Condition Without Action"): an
                    `except: pass` (or bare except with only pass/continue) that does
                    nothing — the caller proceeds as if the operation succeeded.
  3. NULL_DEREF     (CWE-476 "NULL Pointer Dereference"): dereferencing the result of
                    a fallible call (`.first()`, `.find()`, `.get()`, `get(name,None)`,
                    dict `[]`) without a None-check first.
  4. ERROR_LEAK     (CWE-209 "Generation of Error Message Containing Sensitive Info"):
                    logging or raising an exception that includes secrets / raw SQL /
                    stack traces / internal paths.
  5. MISSING_PARAM  (CWE-234 "Failure to Handle Missing Parameter"): indexing into a
                    request/dict param (`req['x']`, `params['x']`) without a presence
                    or None check.

Dependency-free; uses the `ast` module for real control-flow (not regex).
"""
from __future__ import annotations

import ast
import re
from typing import Any, Dict, List, Optional

#: Patterns that make a FALLIBLE call (may legally return None/"not found").
#: Deliberately EXCLUDES dict/`dict.get(key, default)` (safe: returns default) and
#: only keeps DB/ORM "maybe-None" lookups that cause NULL deref when unchecked.
_FALLIBLE_CALLS = (".first()", ".fetchone()", ".find(", ".safe_get", ".get_or_none", ".query.get(", ".get_or_fail", ".lookup")

#: Dict/map `.get(key[, default])` access is safe (returns default) — never a
#: null-deref source. Used to exclude dict.get from the fallible set.
_DICT_GET_RE = re.compile(r"\.get\s*\(\s*(['\"][^'\"]*['\"]|\w+)")

#: Error messages that leak sensitive data.
_LEAK_MARKERS = [
    "password", "token", "secret", "api_key", "apikey", "authorization",
    "stack trace", "traceback", "internal server error", "select *", "from ",
    "sql", "dsn", "credential", "private_key", "session",
]
#: Keys that, if leaked into an error, are especially sensitive.
_SENSITIVE_KEYS = ("password", "token", "secret", "api_key", "credential", "auth")

#: Exception bodies that count as "swallowed" (no meaningful action).
_SWALLOWED_BODIES = {"pass", "continue", "return None"}
#: Exception bodies that FAIL OPEN (grant access / return success).
_FAIL_OPEN_BODIES = {
    "return true", "return 200", "return ok", "return 'ok'", "return \"ok\"",
    "return success", "authorized = true", "allowed = true", "access = true",
    "return redirect", "pass",  # pass alone still lets execution continue
}

#: Variables typically holding a privilege/access decision. `ok`/`flag`/`success`
#: are very common generic fail-open vars (`except: ok = True`); adding them is
#: safe because the check is scoped to the exception-handler body AND requires
#: assignment to a truthy privilege value.
_PRIVILEGE_VARS = ("authorized", "allowed", "access", "authenticated", "is_admin",
                   "permission", "granted", "valid", "ok", "flag", "success",
                   "status", "authenticated_user")


def _is_fallible_call(expr: str) -> bool:
    # A call is "fallible" (may return None / not-found) only if it is a DB/ORM
    # maybe-None lookup (e.g. .first(), .fetchone(), .find(), .get_or_none()).
    # Plain dict/`dict.get(key, default)` is SAFE (returns default) and must not
    # be treated as a null-deref source.
    if not any(fc in expr for fc in _FALLIBLE_CALLS):
        return False
    # Exclude safe dict `.get(...)` (has a dict/key context, not a DB call).
    if re.search(r"\.get\s*\(", expr) and not re.search(r"(?:db|session|query|orm|model|repo|record|row)\.get\(", expr, re.IGNORECASE):
        return False
    return True


def _has_none_guard(block: str) -> bool:
    """True if the block guards against None/not-found before deref."""
    return any(g in block for g in ("is not none", "is None", "is not None", "if none", "if not", "!= none", "or []", "or {}"))


def find_error_handling_issues(code: str, file_path: Optional[str] = None,
                               lang: Optional[str] = None) -> List[Dict[str, Any]]:
    """Detect mishandled-exception vulnerabilities (A10:2025 / CWEs 636,390,476,209,234)."""
    issues: List[Dict[str, Any]] = []
    if lang and lang != "python":
        return issues
    try:
        tree = ast.parse(code)
    except Exception:
        return issues

    lines = code.splitlines()

    # 1. Pass 1: try/except handlers -> failing-open + swallowed exceptions.
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        for handler in node.handlers:
            body_text = "\n".join(lines[handler.lineno - 1:handler.end_lineno] if handler.end_lineno else [])
            # Normalize.
            norm = " ".join(body_text.lower().split())
            # Swallowed: ONLY a bare `except:` or `except Exception:` catch-all with
            # no real recovery (high FP if we flag specific typed catches, which are
            # often intentional). This keeps precision high.
            is_catch_all = handler.type is None or (isinstance(handler.type, ast.Name) and handler.type.id == "Exception")
            body_nodes = [n for n in handler.body if not (isinstance(n, ast.Pass) or isinstance(n, ast.Continue))]
            is_logged = _handler_logs(body_text)
            if is_catch_all and len(body_nodes) == 0 and not is_logged:
                issues.append(_mk("SWALLOWED", node, handler, lines, file_path,
                                  "Bare/Exception catch-all handled with no recovery action (pass/continue) — caller proceeds as if success (CWE-390)."))
            # Failing open: handler grants access or returns success.
            for priv in _PRIVILEGE_VARS:
                if re_search(rf"\bexcept\b.*\b{priv}\s*=\s*(?:true|1|yes)", body_text) or \
                   re_search(rf"\b{priv}\s*=\s*true", body_text):
                    issues.append(_mk("FAILING_OPEN", node, handler, lines, file_path,
                                      f"Exception handler sets '{priv}=True' (fails OPEN), granting access on error (CWE-636)."))
                    break
            # Failing open via HTTP status 200 / 'ok' assigned in the handler.
            if re_search(r"\b(?:status|code)\s*=\s*200\b", body_text) and \
               _in_security_context(code, handler.end_lineno or node.end_lineno):
                issues.append(_mk("FAILING_OPEN", node, handler, lines, file_path,
                                  "Exception handler sets status=200 (fails OPEN), reporting success on error (CWE-636)."))
            # Failing open: handler returns success directly.
            if re_search(r"\breturn\s+(?:true|200|'ok'|\"ok\"|success)", body_text.lower()) \
               and _in_security_context(code, handler.end_lineno or node.end_lineno):
                issues.append(_mk("FAILING_OPEN", node, handler, lines, file_path,
                                  "Exception handler returns success/True after an operation, failing OPEN instead of denying (CWE-636)."))

    # 2. Pass 2: NULL deref after fallible call (CWE-476).
    # Track variables assigned from a fallible call, then flag later deref without
    # a None guard. Also handles chained `.first().name`.
    # (a) vars assigned from fallible calls
    fallible_vars: Dict[str, int] = {}  # var -> line where assigned from fallible call
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and isinstance(node.value, ast.Call):
                    if _is_fallible_call(_render(node.value)):
                        fallible_vars[tgt.id] = node.lineno
    # (b) chained `.first().name` (Attribute whose value is a fallible Call)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Call):
            calltext = _render(node.value)
            if _is_fallible_call(calltext):
                enclosing = _enclosing_block(code, node.lineno)
                if not _has_none_guard(enclosing):
                    issues.append(_mk("NULL_DEREF", node, node, lines, file_path,
                                      f"Dereferencing result of fallible call `{calltext}` without a None/not-found check (CWE-476)."))
    # (c) variables from (a) dereferenced without guard
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            var = node.value.id
            if var in fallible_vars and var.lower() not in ("self",):
                enclosing = _enclosing_block(code, node.lineno)
                assigned_line = fallible_vars[var]
                # Only flag if deref happens AFTER assignment and no guard between
                if node.lineno > assigned_line and not _has_none_guard(enclosing):
                    issues.append(_mk("NULL_DEREF", node, node, lines, file_path,
                                      f"Dereferencing `{var}` (assigned from fallible call at line {assigned_line}) without a None check (CWE-476)."))

    # 3. Pass 3: sensitive info in error messages (logging/raise).
    for node in ast.walk(tree):
        if isinstance(node, (ast.Raise, ast.Call)):
            text = _render(node)
            low = text.lower()
            if "log" in low or "raise" in low or "error" in low:
                # Direct secret keys, raw SQL, OR a request/response object or
                # headers/cookies/session being logged (leaks auth, cookies, IPs).
                leaks_request = any(k in low for k in
                                    ("request", "req", "headers", "cookies",
                                     "session", "environ", "response"))
                if (any(k in low for k in _SENSITIVE_KEYS)
                        or ("select " in low and ";" in text)
                        or leaks_request):
                    issues.append(_mk("ERROR_LEAK", node, node, lines, file_path,
                                      "Exception/error message contains sensitive data (CWE-209): " + text[:50]))

    # 4. Pass 4: missing-parameter handling (index request/user dict without check).
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript):
            text = _render(node)
            # Only flag USER-CONTROLLED containers (request/params/args/json/data),
            # not trusted locals (avoid FP on known-safe dicts).
            if not re_search(r"(req|request|params|args|data|body|json|form)\s*\[", text):
                continue
            enclosing = _enclosing_block(code, node.lineno)
            # Skip if a presence/ternary/None guard exists within this block
            if not _has_presence_guard(enclosing):
                issues.append(_mk("MISSING_PARAM", node, node, lines, file_path,
                                  "User-controlled dict/request access without a presence or None check (CWE-234): " + text[:50]))

    # Dedupe by (type, line)
    seen = set()
    unique = []
    for i in issues:
        key = (i["type"], i["line"])
        if key not in seen:
            seen.add(key)
            unique.append(i)
    return unique


def _mk(vtype: str, node: ast.AST, detail: ast.AST, lines: List[str],
        file_path: Optional[str], desc: str) -> Dict[str, Any]:
    return {
        "type": vtype,
        "line": getattr(node, "lineno", 1),
        "sink": type(node).__name__,
        "code_line": (lines[getattr(detail, "lineno", 1) - 1] if lines and getattr(detail, "lineno", 1) - 1 < len(lines) else "").strip()[:80],
        "path": f"except-handler -> {vtype}",
        "description": desc,
        "file": file_path or "<snippet>",
        "owasp": "A10:2025-Mishandling of Exceptional Conditions",
    }


def _handler_logs(text: str) -> bool:
    return any(k in text.lower() for k in ("log", "logger", "print", "logging."))


def _in_security_context(code: str, upto: int) -> bool:
    """True if the code up to line `upto` contains security-critical keywords."""
    lines = code.splitlines()
    window = "\n".join(lines[:upto]).lower()
    return any(k in window for k in ("auth", "login", "authorize", "check", "verify",
                                     "permission", "token", "access", "validate", "authenticate"))


def _render(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def _enclosing_block(code: str, lineno: int) -> str:
    lines = code.splitlines()
    start = max(0, lineno - 6)
    return "\n".join(lines[start:lineno])


def _has_presence_guard(block: str) -> bool:
    b = block.lower()
    if ".get(" in b or "or none" in b or "is none" in b or "is not none" in b:
        return True
    if " in " in b and ("'" in b or '\"' in b):
        return True
    if "missing" in b or "has_key" in b:
        return True
    return False


def re_search(pattern: str, text: str) -> Optional["re.Match"]:
    try:
        return re.search(pattern, text, re.IGNORECASE)
    except Exception:
        return None


# re-export for convenience
find_error_issues = find_error_handling_issues
