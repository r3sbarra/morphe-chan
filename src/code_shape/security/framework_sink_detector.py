#!/usr/bin/env python
"""framework_sink_detector.py — No-sink-call vulnerability classes.

These vuln classes have NO dangerous sink CALL — the sink is a *framework
construct* (redirect header, response header write, log line, regex compile).
A regex sink-matcher structurally cannot see them, so they map naturally to
Morphe-chan's taint + pattern layer.

Detected (each requires tainted input flowing to the sink, mirroring
security_detector_v2's taint discipline to minimize false positives):

  OPEN_REDIRECT   : tainted URL/param -> redirect/location/wp_redirect sink
  HEADER_INJECTION: tainted input with CR/LF -> response-header write
  LOG_INJECTION   : tainted newline -> logger output
  REGEX_INJECTION : tainted pattern -> re.compile/search (ReDoS / logic rewrite)
  HEADER_REDIRECT : redirect built from Host / X-Forwarded-Host header
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

#: External input sources (taint origins).
INPUT_SOURCES = [
    "request", "req", "ctx", "input", "get", "post", "environ", "getenv",
    "argv", "$_GET", "$_POST", "$_REQUEST", "params", "query", "form", "json",
    "data", "cookie", "header", "session", "PathVariable", "RequestParam", "body",
]

#: Sink signatures per vuln class -> detection regex.
SINK_PATTERNS: Dict[str, List[str]] = {
    "OPEN_REDIRECT": [
        r"\bredirect\s*\(", r"\bRedirect\s*\.\s*To", r"location\s*=\s*['\"]",  # Flask/ASP
        r"res\.redirect\s*\(", r"response\.redirect\s*\(", r"wp_redirect\s*\(",   # Express/PHP
        r"window\.location\s*=\s*", r"window\.location\.href\s*=",               # JS/DOM
        r"Location\s*:\s*", r"headers\[\s*['\"]Location['\"]\s*\]",             # raw header
        r"sendRedirect\s*\(", r"setHeader\s*\(\s*['\"]Location",                  # Java
        r"Redirect\s*\(", r"return Redirect",                                     # ASP.NET
    ],
    "HEADER_INJECTION": [
        r"setHeader\s*\(", r"addHeader\s*\(", r"Header\s*\(\s*['\"]",           # Java / PHP
        r"headers\s*\[\s*['\"][A-Za-z-]+['\"]\s*\]\s*=", r"set\s*\(\s*['\"][A-Za-z-]+",
        r"appendHeader\s*\(", r"response\.setHeader", r"\.setRawHeader",
    ],
    "LOG_INJECTION": [
        r"logger\.(info|debug|warn|error|critical)\s*\(", r"log\.(info|debug|warn|error)",
        r"print\s*\(\s*.*\buser\b|logging\.(info|debug|warn|error|critical)\s*\(",
        r"console\.log\s*\(", r"fatal\s*\(", r"warn\s*\(",
    ],
    "REGEX_INJECTION": [
        r"re\.compile\s*\(", r"re\.search\s*\(", r"re\.match\s*\(", r"re\.sub\s*\(",
        r"new\s+RegExp\s*\(", r"re\.fullmatch\s*\(", r"Pattern\.compile\s*\(",
    ],
    "HEADER_REDIRECT": [
        r"request\.(host|headers)\s*\[\s*['\"](?:Host|X-Forwarded-Host)['\"]",
        r"req\.headers\.(?:host|x-forwarded-host)", r"getHeader\s*\(\s*['\"]Host['\"]",
        r"\bscheme\s*\+\s*['\"]://['\"]\s*\+\s*(?:host|request\.host)",
    ],
}

#: Regex for CR/LF characters in a tainted line (header/log injection marker).
_CRLF = re.compile(r"(?:\\r|\\n|%0d|%0a|\r|\n)", re.IGNORECASE)


def _extract_tainted(code: str) -> Set[str]:
    """Extract param names + vars reachable from inputs (conservative)."""
    params = set()
    for m in re.finditer(r"(?:def|function|func)\s+\w+\s*\(([^)]*)\)", code):
        for p in m.group(1).split(","):
            p = p.strip().split(":")[0].strip().split("=")[0].strip()
            if p and re.match(r"^[a-zA-Z_]", p):
                params.add(p)
    # propagate assignments
    tainted = set(params)
    assigns = {m.group(1): m.group(2) for m in re.finditer(r"(\w+)\s*=\s*([^;\n]+)", code)}
    changed = True
    while changed:
        changed = False
        for var, rhs in list(assigns.items()):
            if var in tainted:
                continue
            if any(re.search(r"\b" + re.escape(t) + r"\b", rhs) for t in tainted) or \
               any(re.search(r"\b" + re.escape(s) + r"\b", rhs, re.I) for s in INPUT_SOURCES):
                tainted.add(var)
                changed = True
    return tainted


def find_framework_sink_issues(code: str, file_path: Optional[str] = None,
                               lang: Optional[str] = None) -> List[Dict[str, Any]]:
    """Detect no-sink-call vuln classes (open redirect, header/log/regex injection).

    Returns findings shaped like find_precise_issues (type/line/sink/source/path).
    """
    issues: List[Dict[str, Any]] = []
    lines = code.splitlines()
    tainted = _extract_tainted(code)

    for vtype, patterns in SINK_PATTERNS.items():
        for pat in patterns:
            for m in re.finditer(pat, code, re.IGNORECASE):
                line_no = code[:m.start()].count("\n") + 1
                line = lines[line_no - 1] if line_no <= len(lines) else ""
                sink = m.group(0).strip()[:40]

                # HEADER_INJECTION / LOG_INJECTION: require CR/LF in the tainted line.
                if vtype in ("HEADER_INJECTION", "LOG_INJECTION") and not _CRLF.search(line):
                    continue

                # Requires a tainted value in the same line (or a tainted var/param).
                has_taint = any(re.search(r"\b" + re.escape(t) + r"\b", line, re.I) for t in tainted)
                if not has_taint:
                    continue

                # Header-based redirect: source is the Host header, not a param line.
                source = None
                for t in tainted:
                    if re.search(r"\b" + re.escape(t) + r"\b", line, re.I):
                        source = t
                        break
                if not source and vtype == "HEADER_REDIRECT":
                    source = "Host/X-Forwarded-Host-header"

                issues.append({
                    "type": vtype,
                    "line": line_no,
                    "sink": sink,
                    "source": source or "tainted-input",
                    "shape_dimension": _shape_dim(vtype),
                    "code_line": line.strip()[:60],
                    "file": file_path or "<snippet>",
                    "path": f"{source or 'tainted-input'} -> {sink}",
                    "path_hops": [source or "tainted-input",
                                  *(t for t in tainted if re.search(r"\b" + re.escape(t) + r"\b", line, re.I)),
                                  sink],
                    "description": _DESC[vtype],
                })

    # dedupe by (type, line)
    seen = set()
    unique = []
    for i in issues:
        key = (i["type"], i["line"])
        if key not in seen:
            seen.add(key)
            unique.append(i)
    return unique


_DESC = {
    "OPEN_REDIRECT": "Tainted URL flows into a redirect/location sink: attacker-controlled redirect target.",
    "HEADER_INJECTION": "Tainted input with CR/LF flows into a response header write (CRLF/header injection).",
    "LOG_INJECTION": "Tainted input with newline flows into a log sink (log injection / log forging).",
    "REGEX_INJECTION": "Attacker-controlled pattern flows into a regex compile/search (regex injection / ReDoS).",
    "HEADER_REDIRECT": "Redirect URL built from Host/X-Forwarded-Host header (header-based open redirect).",
}


def _shape_dim(vtype: str) -> str:
    return {
        "OPEN_REDIRECT": "VULN_OPEN_REDIRECT",
        "HEADER_INJECTION": "VULN_HEADER_INJECTION",
        "LOG_INJECTION": "VULN_LOG_INJECTION",
        "REGEX_INJECTION": "VULN_REGEX_INJECTION",
        "HEADER_REDIRECT": "VULN_HEADER_REDIRECT",
    }.get(vtype, "VULN")

# Re-export convenience
find_framework_sinks = find_framework_sink_issues
