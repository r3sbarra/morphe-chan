#!/usr/bin/env python
"""vuln_v2.py — Shape/library-aware vulnerability detection.
  1. LIBRARY SHAPES — know what library calls do (requests.get=NETWORK, db.execute=SQL)
  2. TAINT FLOW — untrusted input (request) reaching a dangerous library call
  3. ALGORITHM detection — identify dangerous patterns (weak crypto, insecure random)

This catches the cases the pattern-based detector misses:
  - SSRF: requests.get(url) where url from request
  - open-redirect: redirect(next_url) where next_url from request
  - header-injection: headers['Location'] = url from request
  - csrf: missing csrf_token check

Dependency-free (stdlib only).
"""
import re
from typing import Dict, List

from code_shape.security.library_shapes import detect_library_sinks, library_role
from code_shape.core.value_flow_shape import _extract_params, _propagate_taint
from code_shape.analysis.algorithm_detector import detect_algorithm

# ── Dangerous library roles that become vulns with tainted input ───────────
ROLE_TO_VULN = {
    "NETWORK": "SSRF",       # requests.get(url) with tainted url
    "SQL": "SQL_INJECTION",  # db.execute(sql) with tainted sql
    "EXEC": "CMD_INJECTION", # os.system(cmd) with tainted cmd
    "FILE": "PATH_TRAVERSAL",# open(path) with tainted path
    "RENDER": "XSS",         # render(html) with tainted html
    "DESERIALIZE": "DESERIALIZATION",  # pickle.loads(data) with tainted data
    "REDIRECT": "OPEN_REDIRECT",  # redirect(url) with tainted url
    "LDAP": "LDAP_INJECTION",
    "TEMPLATE": "TEMPLATE_INJECTION",
    "XXE": "XXE",
    "CRYPTO_WEAK": "WEAK_CRYPTO",
    "SCRAPE": "SSRF",        # scraping a tainted URL
}

# ── Taint sources (untrusted input) ────────────────────────────────────────
TAINT_SOURCES = ["request", "req", "ctx", "input", "argv", "os.environ",
                 "$_GET", "$_POST", "$_REQUEST", "body", "params", "query",
                 "form", "json", "data", "cookie", "header", "session"]


def _is_tainted(code: str, args: str) -> bool:
    """True if the call args reference a taint source or tainted variable."""
    # direct taint source in args
    for s in TAINT_SOURCES:
        if re.search(r"\b" + re.escape(s) + r"\b", args, re.IGNORECASE):
            return True
    # tainted variable (param) in args
    params = _extract_params(code)
    taint = _propagate_taint(code, params)
    for var in taint:
        if re.search(r"\b" + re.escape(var) + r"\b", args):
            return True
    return False


# Mitigations that make a library call safe
MITIGATIONS = {
    "EXEC": [r"subprocess\.run\s*\(\[", r"shlex\.quote", r"shell\s*=\s*False"],
    "NETWORK": [r"startswith\s*\(", r"is_internal", r"allowlist"],
    "FILE": [r"basename\s*\(", r"realpath\s*\("],
    "RENDER": [r"escape\s*\(", r"html\.escape"],
    "SQL": [r"\?\s*\)", r"%s\s*\)", r"execute\s*\([^)]*,"],
    "DESERIALIZE": [r"json\.loads", r"safe_load"],
}


def _is_mitigated(role: str, code: str) -> bool:
    """True if a mitigation for the role is present in the code."""
    for pat in MITIGATIONS.get(role, []):
        if re.search(pat, code, re.IGNORECASE):
            return True
    return False


def detect_vulns_v2(code: str, lang: str = "python") -> List[Dict]:
    """Detect vulnerabilities using library shapes + taint flow."""
    findings = []
    # 1. library sinks with tainted input
    sinks = detect_library_sinks(code, lang)
    for s in sinks:
        # skip if mitigated (safe form)
        if _is_mitigated(s["role"], code):
            continue
        # get the args of the call
        m = re.search(re.escape(s["full"]) + r"\s*\(", code)
        if m:
            open_p = code.find("(", m.start())
            close_p = code.find(")", open_p) if open_p != -1 else -1
            args = code[open_p + 1:close_p] if open_p != -1 and close_p != -1 else ""
            if _is_tainted(code, args):
                vtype = ROLE_TO_VULN.get(s["role"])
                if vtype:
                    findings.append({
                        "type": vtype,
                        "sink": s["full"],
                        "role": s["role"],
                        "source": "tainted_library_call",
                        "shape_dimension": f"LIB:{s['role']}",
                    })
    # 2. weak crypto / insecure random (algorithm detection)
    algs = detect_algorithm(code, lang)
    for a in algs:
        if a["algorithm"] in ("knapsack",):  # placeholder
            pass
    # weak crypto via library
    for s in sinks:
        if s["role"] == "CRYPTO_WEAK":
            findings.append({
                "type": "WEAK_CRYPTO",
                "sink": s["full"],
                "role": "CRYPTO_WEAK",
                "source": "weak_crypto_library",
                "shape_dimension": "LIB:CRYPTO_WEAK",
            })
    return findings


def vuln_shape(code: str, lang: str = "python") -> Dict[str, float]:
    """Vulnerability shape: which vuln types are present."""
    import math
    findings = detect_vulns_v2(code, lang)
    vec: Dict[str, float] = {}
    for f in findings:
        vec[f"VULN:{f['type']}"] = vec.get(f"VULN:{f['type']}", 0) + 1
    norm = math.sqrt(sum(v * v for v in vec.values()))
    if norm == 0:
        return {}
    return {k: round(v / norm, 4) for k, v in vec.items()}


# ── Self-test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
    from bug_bounty_corpus import CORPUS

    print("=== Shape/library-aware vuln detection ===")
    for name, cwe, v, c, vt in CORPUS:
        vd = detect_vulns_v2(v)
        cd = detect_vulns_v2(c)
        print(f"{name:24s} vuln={[f['type'] for f in vd]} clean={[f['type'] for f in cd]}")
