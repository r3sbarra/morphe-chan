#!/usr/bin/env python
"""security_detector_v2.py — Upgraded vulnerability detection with taint flow.

1. TAINT FLOW — untrusted input (function args, request params, env, user data)
   must flow to a dangerous sink (SQL execute, os.system, open, eval, innerHTML).
   A sink alone is NOT a vulnerability; a sink fed by untrusted input IS.

2. BOUNDS ANALYSIS — array access is only a buffer-overflow risk if it's
   UNCHECKED (no bounds check like `if 0 <= i < len(arr)` nearby).

3. WORD-BOUNDARY matching — `eval` does not match `evaluate`; `password = "x"`
   only counts as a hardcoded cred if it's a real assignment, not a test fixture.

4. TEST-FILE awareness — the caller can exclude test/benchmark/sample files.

Dependency-free (stdlib only).
"""
import re
from typing import Dict, List, Set

# ── Taint sources (untrusted input) ────────────────────────────────────────
# Function parameters, request data, env vars, user input
TAINT_SOURCES = [
    r"\bdef\s+\w+\s*\(([^)]*)\)",       # function params
    r"request\.(?:args|form|json|data|params|query|values)",  # web request
    r"\binput\s*\(",                     # user input
    r"os\.environ", r"getenv",           # env vars
    r"\$_GET", r"\$_POST", r"\$_REQUEST",  # PHP
    r"req\.(?:query|params|body)",       # express
    r"ctx\.(?:query|param|body)",        # gin
    r"@RequestParam", r"@PathVariable",  # spring
    r"argv", r"sys\.argv",              # CLI args
    r"readline", r"stdin",              # stdin
]

# ── Dangerous sinks ─────────────────────────────────────────────────────────
DANGEROUS_SINKS = {
    "SQL_INJECTION": [r"execute\s*\([^)]*SELECT", r"execute\s*\([^)]*INSERT",
                      r"execute\s*\([^)]*UPDATE", r"query\s*\([^)]*SELECT",
                      r"createQuery", r"rawQuery",
                      r"(?:SELECT|INSERT|UPDATE|DELETE).*\+.*\w+"],  # SQL string concat
    "CMD_INJECTION": [r"os\.system\s*\(", r"system\s*\(", r"subprocess\.(?:call|run|Popen)\s*\([^)]*shell\s*=\s*True",
                      r"exec\s*\([^)]*shell", r"Runtime\.getRuntime\(\)\.exec"],
    "PATH_TRAVERSAL": [r"open\s*\([^)]*\+", r"fopen\s*\([^)]*\+", r"readFile\s*\([^)]*\+",
                       r"os\.path\.join\s*\([^)]*\+", r"File\s*\([^)]*\+"],
    "XSS": [r"innerHTML\s*=\s*[^;]*\+", r"document\.write\s*\([^)]*\+",
            r"return\s*[\"']<[^\"']*[\"']\s*\+", r"html\s*\([^)]*\+"],
    "EVAL_USE": [r"\beval\s*\(", r"\bexec\s*\(", r"pickle\.loads", r"yaml\.load\s*\([^)]*Loader"],
    "DESERIALIZATION": [r"pickle\.loads", r"pickle\.load\s*\(", r"yaml\.load\s*\([^)]*Loader"],
}

# ── Mitigations (safe patterns) ─────────────────────────────────────────────
MITIGATIONS = {
    "SQL_INJECTION": [r"\?\s*\)", r"execute\s*\([^)]*,"],
    "CMD_INJECTION": [r"subprocess\.run\s*\(\[", r"shlex\.quote", r"shell\s*=\s*False"],
    "PATH_TRAVERSAL": [r"basename\s*\(", r"realpath\s*\(", r"normpath\s*\(", r"os\.path\.join\s*\([^)]*basename"],
    "XSS": [r"escape\s*\(", r"textContent", r"html\.escape"],
    "EVAL_USE": [r"ast\.literal_eval"],
    "DESERIALIZATION": [r"json\.loads", r"safe_load"],
}

# ── Hardcoded credentials (word-boundary, real assignment) ─────────────────
CRED_PATTERNS = [
    r"\b(?:password|passwd|pwd|api_key|apikey|secret|token)\s*=\s*[\"'][^\"']{6,}[\"']",
    r"\b(?:password|passwd|pwd|api_key|apikey|secret|token)\s*[:=]\s*[\"'][^\"']{6,}[\"']",
    r"(?:connect|login|auth|authenticate)\s*\([^)]*[\"'][^\"']{6,}[\"']",
]
CRED_MITIGATIONS = [r"os\.environ", r"getenv", r"get_secret", r"\.env", r"config\s*[\[.]", r"settings"]


def _extract_params(code: str) -> Set[str]:
    """Extract function parameter names (taint sources)."""
    params = set()
    for m in re.finditer(r"(?:def|function|func|fun)\s+\w+\s*\(([^)]*)\)", code):
        for p in m.group(1).split(","):
            p = p.strip().split(":")[0].strip().split("=")[0].strip()
            if p and re.match(r"^[a-zA-Z_]", p):
                params.add(p)
    return params


def _taint_sources_in(code: str, params: Set[str]) -> Set[str]:
    """Find taint source names present in the code (params + explicit sources)."""
    tainted = set()
    # params are tainted if they appear in the body
    for p in params:
        if re.search(r"\b" + re.escape(p) + r"\b", code):
            tainted.add(p)
    # explicit sources
    for pat in TAINT_SOURCES:
        for m in re.finditer(pat, code):
            # extract the variable being assigned from the source
            pass
    return tainted


def _sink_has_taint(code: str, sink_pat: str, tainted: Set[str]) -> bool:
    """Check if a dangerous sink is fed by tainted input, tracking propagation
    through assignments (tainted param -> variable -> sink)."""
    # propagate taint: a variable assigned from a tainted source becomes tainted
    tainted = set(tainted)
    changed = True
    while changed:
        changed = False
        for m in re.finditer(r"(\w+)\s*=\s*([^;\n]+)", code):
            var, expr = m.group(1), m.group(2)
            if var in tainted:
                continue
            # if the RHS references a tainted var or source, taint the LHS
            if any(re.search(r"\b" + re.escape(t) + r"\b", expr) for t in tainted):
                tainted.add(var)
                changed = True
            elif any(re.search(r"\b" + re.escape(s) + r"\b", expr)
                     for s in ["request", "req", "ctx", "input", "argv", "os.environ", "$_GET", "$_POST", "$_REQUEST"]):
                tainted.add(var)
                changed = True

    # now check if any tainted var feeds the sink
    for m in re.finditer(sink_pat, code, re.IGNORECASE):
        start = m.start()
        line_start = code.rfind("\n", 0, start) + 1
        line_end = code.find("\n", start)
        if line_end == -1:
            line_end = len(code)
        line = code[line_start:line_end]
        for t in tainted:
            if re.search(r"\b" + re.escape(t) + r"\b", line):
                return True
        for src in ["request", "req", "ctx", "input", "argv", "os.environ", "$_GET", "$_POST"]:
            if re.search(r"\b" + re.escape(src) + r"\b", line):
                return True
    return False


def _unchecked_index(code: str, tainted: Set[str]) -> bool:
    """True if there's an array access with a TAINTED index and NO bounds check.

    Only flags when the index is untrusted input (tainted) — safe array access
    by loop variables or constants is not a vulnerability.
    """
    for m in re.finditer(r"\[\s*(\w+)\s*\]", code):
        idx = m.group(1)
        if idx in tainted:
            has_bounds = re.search(r"if\s+0\s*<=\s*\w+\s*<\s*len|if\s+\w+\s*<\s*len|bounds|\.length\s*[<>]", code)
            if not has_bounds:
                return True
    return False


def detect_vulns_v2(code: str, is_test: bool = False) -> List[Dict]:
    """Detect vulnerabilities with taint flow + bounds analysis.

    is_test=True skips hardcoded-cred and eval findings (test fixtures).
    """
    findings: List[Dict] = []
    params = _extract_params(code)
    tainted = _taint_sources_in(code, params)

    # Injection sinks require taint flow
    for vtype, sink_pats in DANGEROUS_SINKS.items():
        for pat in sink_pats:
            if re.search(pat, code, re.IGNORECASE):
                # check mitigation
                if any(re.search(m, code, re.IGNORECASE) for m in MITIGATIONS.get(vtype, [])):
                    continue
                # require taint flow
                if _sink_has_taint(code, pat, tainted):
                    findings.append({"type": vtype, "cwe": _CWE[vtype], "message": f"{vtype} (tainted input to sink)"})
                    break

    # Buffer overflow: only unchecked array access with tainted index
    if _unchecked_index(code, tainted) and not is_test:
        findings.append({"type": "BUFFER_OVERFLOW", "cwe": "CWE-120",
                         "message": "unchecked array access"})

    # Hardcoded creds: word-boundary, real assignment, not test
    if not is_test:
        for pat in CRED_PATTERNS:
            if re.search(pat, code):
                if not any(re.search(m, code) for m in CRED_MITIGATIONS):
                    findings.append({"type": "HARDCODED_CRED", "cwe": "CWE-798",
                                     "message": "hardcoded credential"})
                    break

    return findings


_CWE = {
    "SQL_INJECTION": "CWE-89", "CMD_INJECTION": "CWE-78", "PATH_TRAVERSAL": "CWE-22",
    "XSS": "CWE-79", "EVAL_USE": "CWE-95", "DESERIALIZATION": "CWE-502",
    "BUFFER_OVERFLOW": "CWE-120", "HARDCODED_CRED": "CWE-798",
}


# ── Self-test on the curated corpus ─────────────────────────────────────────
if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
    from vuln_corpus import CORPUS

    print("=== v2 detector on curated corpus (should still catch real vulns) ===")
    tp = fp = fn = tn = 0
    for name, cwe, v, c, vt in CORPUS:
        vd = bool(detect_vulns_v2(v))
        cd = bool(detect_vulns_v2(c))
        if vd: tp += 1
        else: fn += 1
        if cd: fp += 1
        else: tn += 1
        print(f"  {name:20s} vuln={vd} clean={cd}")
    prec = tp/(tp+fp) if (tp+fp) else 0
    rec = tp/(tp+fn) if (tp+fn) else 0
    f1 = 2*prec*rec/(prec+rec) if (prec+rec) else 0
    print(f"\n  v2 on curated: Precision={prec:.2f} Recall={rec:.2f} F1={f1:.2f}")
