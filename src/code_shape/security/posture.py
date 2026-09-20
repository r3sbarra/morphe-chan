#!/usr/bin/env python
"""posture.py — Project security posture: aggregate, score, and rank findings.

A way to USE the precise vulnerability findings, not just list them. Scans a
directory (or list of files) with the accurate find_precise_issues pipeline and
produces:

  * a security-posture report (severity counts, risk score 0..1, exposure grade)
  * a per-type breakdown (which vulnerability classes are most common)
  * per-file risk ranking (which files to fix first)
  * per-finding remediation guidance (from taxonomy.REMEDIATION_GUIDE)

Severity weighting (matches exploitability.py + taxonomy):
  CRITICAL=1.0, HIGH=0.7, MEDIUM=0.4, LOW=0.2. The posture score is the
  max-severity-weighted finding, clamped 0..1.

Dependency-free (stdlib only).
"""
import os
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

SEVERITY_WEIGHT = {"CRITICAL": 1.0, "HIGH": 0.7, "MEDIUM": 0.4, "LOW": 0.2}

# File extensions handled by the 13 language adapters.
SOURCE_EXTS = {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp", ".h",
               ".hpp", ".cs", ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".m"}

# Directories conventionally not scanned (deps, builds, vendored code).
SKIP_DIRS = {"node_modules", ".git", ".venv", "venv", "vendor", "dist", "build",
             "target", "__pycache__", "coverage", ".github", "out", "obj", "bin",
             "test", "tests", "spec", "specs", "examples", "docs", "third_party",
             "third-party", "external", "deps", "assets", "static", "bench",
             "benchmark", "benchmarks"}


def _scan_text(code: str, file_path: str) -> List[Dict]:
    """Find issues from all per-file detectors in one code string.

    Combines precise issues (injection/XSS/SSRF/...), buffer overflows, and —
    for Python — OWASP A10 mishandled-exception issues + framework sink issues.
    Each finding is tagged with its detector for provenance."""
    from code_shape.security.precise_issues import (
        find_precise_issues, find_buffer_overflows,
    )
    try:
        prec = find_precise_issues(code, file_path=file_path)
        buf = find_buffer_overflows(code, file_path=file_path)
    except Exception:
        prec, buf = [], []
    for i in prec + buf:
        i.setdefault("file", file_path)
        i.setdefault("detector", "precise_issues")
    # OWASP A10 error-handling + framework sinks (Python-aware; AST-based).
    a10 = framework = []
    try:
        from code_shape.security.error_handling import find_error_handling_issues
        a10 = [i for i in find_error_handling_issues(code, file_path=file_path) if i]
    except Exception:
        a10 = []
    try:
        from code_shape.security.framework_sink_detector import find_framework_sink_issues
        framework = [i for i in find_framework_sink_issues(code, file_path=file_path) if i]
    except Exception:
        framework = []
    for i in a10:
        i.setdefault("file", file_path)
        i.setdefault("detector", "error_handling")
        i.setdefault("severity", _A10_SEVERITY.get((i.get("type") or "").upper(), "MEDIUM"))
        if not i.get("remediation"):
            i["remediation"] = "Review this error/flow path: fail closed, handle the exception explicitly, and do not leak sensitive data."
    for i in framework:
        i.setdefault("file", file_path)
        i.setdefault("detector", "framework_sink")
        i.setdefault("severity", _A10_SEVERITY.get((i.get("type") or "").upper(), "MEDIUM"))
        # ensure a remediation line so posture/remediation surfaces guidance
        if not i.get("remediation"):
            i["remediation"] = "Review this error/flow path: fail closed, handle the exception explicitly, and do not leak sensitive data."
    return prec + buf + a10 + framework


#: Severity default for error-handling/framework findings (OWASP A10 class).
_A10_SEVERITY = {
    "FAILING_OPEN": "HIGH", "ERROR_LEAK": "HIGH", "NULL_DEREF": "MEDIUM",
    "SWALLOWED": "LOW", "MISSING_PARAM": "LOW",
}


def scan_string(code: str, file_path: str = "<input>") -> List[Dict]:
    """Return precise findings (with remediation) for a single code string."""
    return _scan_text(code, file_path)


def scan_dir(path: str, max_file_bytes: int = 500_000,
             skip_dirs: Optional[List[str]] = None) -> List[Dict]:
    """Scan a directory tree and return ALL findings across source files."""
    skips = set(skip_dirs) if skip_dirs else SKIP_DIRS
    root = Path(path)
    all_issues: List[Dict] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skips]
        for fn in filenames:
            if not any(fn.endswith(e) for e in SOURCE_EXTS):
                continue
            full = Path(dirpath) / fn
            try:
                if full.stat().st_size > max_file_bytes:
                    continue
                code = full.read_text(errors="replace")
            except Exception:
                continue
            all_issues.extend(_scan_text(code, str(full)))
    return all_issues


def scan_cross_file(path: str) -> List[Dict]:
    """Aggregate cross-file taint findings for a Python project dir.

    Uses the cross-file taint analyzer (CrossFileTaint) which propagates taint
    across function/module boundaries, catching sinks that single-snippet
    precise-issues misses (source in one file, dangerous sink in another).
    Each flow is converted to a posture-compatible finding dict with source
    metadata and a best-effort severity tag.
    """
    try:
        from code_shape.security.cross_file_taint import CrossFileTaint, prune_false_positives
        cft = CrossFileTaint()
        cft.index(path)
        flows = cft.propagate()
    except Exception:
        return []
    issues: List[Dict] = []
    for f in flows:
        if not getattr(f, "vulnerable", True):
            continue
        sev = "HIGH" if any(m in (f.sink_name or "").lower() for m in
                            ("execute", "system", "eval", "exec", "popen", "pickle")) else "MEDIUM"
        issues.append({
            "type": "CROSS_FILE_TAINT",
            "line": getattr(f, "sink_line", 0) or 0,
            "sink": f.sink_name,
            "source": f"{f.source_kind}:{f.source_var}",
            "shape_dimension": "FLOW:CROSS_FILE",
            "code_line": f"{f.source_var} -> {f.callee}() -> {f.sink_name}",
            "file": f.callee_file or f.source_file,
            "function": f.callee,
            "function_lines": [max(0, (getattr(f, "sink_line", 0) or 1) - 1), (getattr(f, "sink_line", 0) or 1) + 1],
            "shape_part": "FLOW:CROSS_FILE",
            "path": " -> ".join([f.source_var, f.callee, f.sink_name]),
            "path_hops": [f.source_var, f.callee, f.sink_name],
            "severity": sev,
            "remediation": "Trace the tainted input to the sink across files: validate/parameterize at the sink and ensure the source can't reach it unmitigated.",
            "detector": "cross_file_taint",
        })
    return issues


def scan_project(path: str, max_file_bytes: int = 500_000,
                 skip_dirs: Optional[List[str]] = None) -> List[Dict]:
    """Full project security scan: per-file precise issues + cross-file taint.

    Returns findings from both detectors so a project posture reflects
    interprocedural as well as single-snippet vulnerabilities."""
    issues = scan_dir(path, max_file_bytes, skip_dirs)
    issues += scan_cross_file(path)
    return issues


def _risk_score(issues: List[Dict]) -> float:
    """Worst-severity-weighted risk score (0..1) across all findings."""
    if not issues:
        return 0.0
    worst = 0.0
    for i in issues:
        sev = (i.get("severity") or "MEDIUM").upper()
        w = SEVERITY_WEIGHT.get(sev, 0.4)
        # use precise exploitability score when present
        expl = i.get("exploitability") or {}
        s = expl.get("score") if isinstance(expl, dict) else None
        if isinstance(s, (int, float)):
            w = max(w, min(1.0, s))
        worst = max(worst, w)
    return round(worst, 3)


def _grade(score: float) -> str:
    if score >= 0.8:
        return "F"
    if score >= 0.6:
        return "D"
    if score >= 0.4:
        return "C"
    if score >= 0.2:
        return "B"
    if score > 0:
        return "A"
    return "A+"


def analyze(issues: List[Dict]) -> Dict[str, Any]:
    """Aggregate a flat list of findings into a security-posture profile."""
    by_type: Counter = Counter()
    by_severity: Counter = Counter()
    per_file: Dict[str, List[Dict]] = {}
    cwes: Counter = Counter()
    for i in issues:
        by_type[i.get("type", "UNKNOWN")] += 1
        sev = (i.get("severity") or "MEDIUM").upper()
        by_severity[sev] += 1
        f = i.get("file", "<unknown>")
        per_file.setdefault(f, []).append(i)
        if i.get("cwe_id"):
            cwes[i["cwe_id"]] += 1

    # per-file risk: max finding score in that file
    file_risks = {}
    for f, fis in per_file.items():
        file_risks[f] = {
            "findings": len(fis),
            "risk": _risk_score(fis),
            "severities": {s: v for s, v in sorted(Counter(
                (x.get("severity") or "MEDIUM").upper() for x in fis).items(),
                key=lambda kv: -SEVERITY_WEIGHT.get(kv[0], 0.4))},
        }
    ranked_files = sorted(file_risks.items(), key=lambda kv: -kv[1]["risk"])

    total_score = _risk_score(issues)
    return {
        "total_findings": len(issues),
        "risk_score": total_score,
        "grade": _grade(total_score),
        "by_severity": {s: by_severity.get(s, 0) for s in
                        ("CRITICAL", "HIGH", "MEDIUM", "LOW")},
        "by_type": dict(by_type.most_common()),
        "by_cwe": dict(cwes.most_common()),
        "file_count": len(per_file),
        "top_files": [
            {"file": f, "findings": r["findings"], "risk": r["risk"],
             "severities": r["severities"]}
            for f, r in ranked_files[:10]
        ],
    }


def severity_counts(issues: List[Dict]) -> Dict[str, int]:
    """Quick severity histogram: {CRITICAL: n, HIGH: n, ...}."""
    c: Counter = Counter((i.get("severity") or "MEDIUM").upper() for i in issues)
    return {s: c.get(s, 0) for s in ("CRITICAL", "HIGH", "MEDIUM", "LOW")}


def report(issues: List[Dict]) -> str:
    """Human-readable security-posture report for a set of findings."""
    if not issues:
        return "CLEAN — no findings."
    prof = analyze(issues)
    lines = [
        f"Security posture: grade {prof['grade']} (risk {prof['risk_score']})",
        f"  {prof['total_findings']} findings across {prof['file_count']} files",
        "  by severity: "
        + ", ".join(f"{s}={prof['by_severity'][s]}"
                    for s in ("CRITICAL", "HIGH", "MEDIUM", "LOW")
                    if prof["by_severity"][s]),
        "  by type: " + ", ".join(f"{k} ({v})" for k, v in
                                  list(prof["by_type"].items())[:8]),
    ]
    if prof["top_files"]:
        lines.append("  riskiest files:")
        for tf in prof["top_files"][:5]:
            lines.append(f"    {tf['file']}: {tf['findings']} finding(s), "
                         f"risk {tf['risk']}")
    return "\n".join(lines)


def remediations(issues: List[Dict], by_file: bool = False) -> Dict[str, Any]:
    """Group findings into fix actions: {file or type: [remediation strings]}.

    by_file=True groups per file (what to fix in each file); by_file=False
    groups per type (unique remediation guidance per vulnerability class).
    """
    out: Dict[str, List[str]] = {}
    key = (lambda i: i.get("file", "<unknown>")) if by_file else \
        (lambda i: i.get("type", "UNKNOWN"))
    for i in issues:
        k = key(i)
        rem = i.get("remediation") or "Review this code path."
        lines = out.setdefault(k, [])
        line = f"L{i.get('line')} {i.get('type')}: {rem}"
        if line not in lines:
            lines.append(line)
    return out
