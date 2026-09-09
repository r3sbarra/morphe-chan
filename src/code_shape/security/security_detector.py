#!/usr/bin/env python
"""security_detector.py — Security vulnerability detection via shape analysis.
combining shape analysis with vulnerability-specific pattern detection.

The key idea: vulnerabilities have characteristic SHAPE signatures — the
combination of primitives (string concat + dangerous sink, unsafe call,
hardcoded secret, unchecked bounds) forms a recognizable composite shape.

Detects:
  SQL_INJECTION   (CWE-89)  — string concat into SQL query
  XSS             (CWE-79)  — unsanitized input into HTML
  CMD_INJECTION   (CWE-78)  — user input into shell command
  PATH_TRAVERSAL  (CWE-22)  — user input into file path
  BUFFER_OVERFLOW (CWE-120) — unchecked array access
  DESERIALIZATION (CWE-502) — pickle.loads / unsafe deserialization
  HARDCODED_CRED  (CWE-798) — hardcoded password/secret
  EVAL_USE        (CWE-95)  — eval/exec dynamic code execution

Dependency-free (stdlib only).
"""
import re
from typing import Dict, List

# ── Vulnerability pattern rules ────────────────────────────────────────────
# Each: (vuln_type, cwe, [dangerous_sink_patterns], [mitigation_patterns])
RULES = [
    ("SQL_INJECTION", "CWE-89",
     [r"execute\s*\([^)]*\+", r"query\s*=\s*[\"'][^\"']*\+", r"SELECT.*\+.*username"],
     [r"\?\s*\)", r"execute\s*\([^)]*,"]),
    ("XSS", "CWE-79",
     [r"return\s*[\"']<[^\"']*\+", r"innerHTML\s*=\s*[^;]*\+", r"<div>.*\+.*name"],
     [r"escape\s*\(", r"textContent"]),
    ("CMD_INJECTION", "CWE-78",
     [r"os\.system\s*\([^)]*\+", r"system\s*\([^)]*\+", r"subprocess.*shell\s*=\s*True"],
     [r"subprocess\.run\s*\(\[", r"shlex\.quote"]),
    ("PATH_TRAVERSAL", "CWE-22",
     [r"open\s*\([^)]*\+", r"read\s*\([^)]*\+", r"os\.path\.join\s*\([^)]*\+"],
     [r"basename\s*\(", r"realpath\s*\(", r"normpath\s*\("]),
    ("BUFFER_OVERFLOW", "CWE-120",
     [r"return\s+\w+\[[^\]]*\]", r"arr\[[^\]]*\]\s*="],
     [r"if\s+0\s*<=\s*\w+\s*<\s*len", r"bounds"]),
    ("DESERIALIZATION", "CWE-502",
     [r"pickle\.loads", r"pickle\.load\s*\(", r"yaml\.load\s*\([^)]*Loader"],
     [r"json\.loads", r"safe_load"]),
    ("HARDCODED_CRED", "CWE-798",
     [r"password\s*=\s*[\"'][^\"']+[\"']", r"passwd\s*=\s*[\"'][^\"']+[\"']",
      r"api_key\s*=\s*[\"'][^\"']+[\"']", r"secret\s*=\s*[\"'][^\"']+[\"']",
      r"connect\s*\([^)]*[\"'][^\"']+[\"']", r"login\s*\([^)]*[\"'][^\"']+[\"']"],
     [r"os\.environ", r"getenv", r"get_secret"]),
    ("EVAL_USE", "CWE-95",
     [r"\beval\s*\(", r"\bexec\s*\(", r"compile\s*\([^)]*exec"],
     [r"ast\.literal_eval"]),
]


def detect_vulns(code: str) -> List[Dict]:
    """Detect vulnerabilities in a code snippet. Returns list of {type, cwe, message}."""
    findings: List[Dict] = []
    for vuln_type, cwe, sinks, mitigations in RULES:
        # check for dangerous sink
        sink_hit = any(re.search(p, code) for p in sinks)
        if not sink_hit:
            continue
        # check for mitigation (if present, not vulnerable)
        mitigated = any(re.search(p, code) for p in mitigations)
        if mitigated:
            continue
        findings.append({
            "type": vuln_type,
            "cwe": cwe,
            "message": f"potential {vuln_type} ({cwe})",
        })
    return findings


def vuln_score(code: str) -> float:
    """Vulnerability severity score in [0, 1]."""
    findings = detect_vulns(code)
    if not findings:
        return 0.0
    # each finding contributes; cap at 1.0
    return min(1.0, 0.3 * len(findings))


def vuln_shape_signature(code: str) -> str:
    """The composite shape signature of a vulnerability: the primitives that
    form the dangerous pattern (e.g. 'CONCAT>SQL_SINK')."""
    parts = []
    if re.search(r"\+", code) and re.search(r"execute|system|open|return.*<", code):
        parts.append("CONCAT>DANGEROUS_SINK")
    if re.search(r"pickle\.loads|eval\s*\(|exec\s*\(", code):
        parts.append("UNSAFE_CALL")
    if re.search(r"password\s*=|api_key\s*=|secret\s*=|connect\s*\([^)]*[\"']", code):
        parts.append("HARDCODED_SECRET")
    if re.search(r"\[\w+\]", code) and not re.search(r"if\s+0\s*<=", code):
        parts.append("UNCHECKED_INDEX")
    return ">".join(parts) if parts else "CLEAN"


# ── Self-test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys
    from pathlib import Path as _P
    _sys.path.insert(0, str(_P(__file__).resolve().parents[1] / "experiments"))
    from vuln_corpus import CORPUS
    print("=== Security detection on vulnerability corpus ===")
    print(f"{'name':20s} {'vuln':>5s} {'clean':>5s} {'vuln_shape':30s}")
    for name, cwe, v, c, vt in CORPUS:
        vd = detect_vulns(v)
        cd = detect_vulns(c)
        print(f"{name:20s} {str(bool(vd)):>5s} {str(bool(cd)):>5s} {vuln_shape_signature(v):30s}")
