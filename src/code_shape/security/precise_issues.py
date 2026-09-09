#!/usr/bin/env python
"""precise_issues.py — Precise issue finding (v2: word-boundary + type-aware).

1. WORD-BOUNDARY matching — `\bexec\b` does not match `curl_multi_exec`;
   `createQuery` does not match `CreateQueryExecutor`.
2. EXCLUDE function declarations — `fun exec(`, `def eval(` are declarations,
   not sink usage.
3. TYPE-AWARE BUFFER_OVERFLOW — uses type_aware_ast to only flag LIST_INDEX
   (array indexing), not dict access / ORM / Swift array types.

For each finding: precise type, line, sink, taint source, shape dimension.
"""
import re
from typing import Dict, List, Optional

from code_shape.core.type_aware_ast import _infer_types, _classify_subscript

# ── Precise sink -> vulnerability type (word-boundary patterns) ─────────────
PRECISE_SINKS = [
    ("EVAL_USE", [r"\beval\s*\(", r"\bexec\s*\(", r"\bcompile\s*\([^)]*exec"]),
    ("JNDI_INJECTION", [r"\bjndi\.lookup\b", r"\bInitialContext\.lookup\b"]),
    ("OGNL_INJECTION", [r"\bognl\b", r"\bOgnl\.getValue\b", r"\bexecute_ognl\b"]),
    ("CMD_INJECTION", [r"\bos\.system\s*\(", r"\bsystem\s*\(", r"\bsubprocess\.(?:call|run|Popen)\s*\(",
                       r"\bRuntime\.getRuntime\(\)\.exec\s*\(", r"\bProcessBuilder\b",
                       r"\bshell_exec\s*\(", r"\bpassthru\s*\(", r"\bpopen\s*\(", r"\bproc_open\s*\("]),
    ("SQL_INJECTION", [r"\.execute\s*\([^)]*SELECT[^)]*\+", r"\.execute\s*\([^)]*INSERT[^)]*\+",
                       r"\.execute\s*\([^)]*UPDATE[^)]*\+", r"\.query\s*\([^)]*SELECT[^)]*\+",
                       r"\bcreateQuery\s*\(", r"\brawQuery\s*\(",
                       r"SELECT\s+.*\bFROM\b.*\+"]),
    ("PATH_TRAVERSAL", [r"\bopen\s*\([^)]*\+", r"\bfopen\s*\([^)]*\+", r"\breadFile\s*\([^)]*\+",
                        r"\bfile_get_contents\s*\([^)]*\+", r"\bos\.path\.join\s*\([^)]*\+"]),
    ("XSS", [r"\binnerHTML\s*=\s*[^;]*\+", r"\bdocument\.write\s*\([^)]*\+",
             r"\.html\s*\([^)]*\+", r"\bv-html\b",
             r"return\s*[\"']<[^\"']*[\"']\s*\+"]),
    ("DESERIALIZATION", [r"\bpickle\.loads\b", r"\bpickle\.load\s*\(", r"\byaml\.load\s*\(",
                         r"\bunserialize\s*\(", r"\bObjectInputStream\b", r"\breadObject\b"]),
    ("HARDCODED_CRED", [r"\bpassword\s*=\s*[\"'][^\"']+[\"']", r"\bapi_key\s*=\s*[\"'][^\"']+[\"']",
                        r"Bearer\s+[A-Za-z0-9._-]{10,}"]),
    ("SSRF", [r"requests\.get\s*\([^,)]*\+", r"requests\.post\s*\([^,)]*\+",
               r"urlopen\s*\([^,)]*\+", r"fetch\s*\([^,)]*\+"]),
    ("XXE", [r"parse_xml\s*\([^)]*request", r"parse\s*\([^)]*request\.data",
              r"DocumentBuilderFactory"]),
    ("LDAP_INJECTION", [r"ldap\.search\s*\([^)]*\+", r"ldap\.bind\s*\([^)]*\+"]),
    ("TEMPLATE_INJECTION", [r"Template\s*\([^)]*request", r"render_template_string\s*\([^)]*\+",
                             r"Template\s*\([^)]*\+"]),
    ("HEADER_INJECTION", [r"headers\[['\"]Location['\"]\]\s*=\s*[^;]*\+",
                           r"headers\[['\"]Location['\"]\]\s*=\s*request"]),
    ("LOG_INJECTION", [r"logger\.(?:info|warning|error)\s*\([^)]*\+"]),
    ("OPEN_REDIRECT", [r"\bredirect\s*\([^)]*request"]),
    ("INSECURE_RANDOM", [r"random\.(?:random|randint|choice|uniform)\s*\("]),
    ("WEAK_HASH", [r"hashlib\.md5\s*\(", r"hashlib\.sha1\s*\("]),
]

# Taint sources
TAINT_SOURCES = ["request", "req", "ctx", "input", "argv", "os.environ",
                 "$_GET", "$_POST", "$_REQUEST", "body", "params", "query",
                 "form", "json", "data", "cookie", "header", "session"]


def _is_declaration(code: str, match_start: int) -> bool:
    """True if the match is a function/class declaration, not a sink usage.

    Handles generic type params: 'fun <T : Any> exec(' is a declaration.
    """
    prefix = code[max(0, match_start - 40):match_start]
    # declaration if preceded by def/function/func/fun (possibly with generics)
    return bool(re.search(r"(?:def|function|func|fun)\s*(?:<[^>]*>)?\s*$", prefix))


# Mitigations per vuln type (sanitizers that make the sink safe)
MITIGATIONS = {
    "CMD_INJECTION": [r"subprocess\.run\s*\(\[", r"shlex\.quote", r"shell\s*=\s*False"],
    "PATH_TRAVERSAL": [r"basename\s*\(", r"realpath\s*\(", r"normpath\s*\("],
    "XSS": [r"escape\s*\(", r"textContent", r"html\.escape"],
    "SQL_INJECTION": [r"\?\s*\)", r"%s\s*\)", r"execute\s*\([^)]*,"],
    "EVAL_USE": [r"ast\.literal_eval"],
    "DESERIALIZATION": [r"json\.loads", r"safe_load"],
    "LDAP_INJECTION": [r"escape\s*\(", r"ldap\.escape"],
    "LOG_INJECTION": [r"replace\s*\(", r"sanitize"],
    "OPEN_REDIRECT": [r"startswith\s*\(", r"urlparse", r"is_safe_url"],
    "SSRF": [r"startswith\s*\(", r"is_internal", r"allowlist"],
    "TEMPLATE_INJECTION": [r"safe\s*=\s*True", r"sandbox"],
    "XXE": [r"resolve_entities\s*=\s*False", r"disable_external"],
}


def _has_mitigation(vtype: str, line: str) -> bool:
    """True if a sanitizer/mitigation for the vuln type is present.

    Checks the sink line AND nearby lines (mitigations like 'if not
    startswith' are often on a prior line).
    """
    # check the line + a window around it (up to 3 lines before)
    context = line
    for pat in MITIGATIONS.get(vtype, []):
        if re.search(pat, context, re.IGNORECASE):
            return True
    return False


def find_precise_issues(code: str) -> List[Dict]:
    """Find precise issues with word-boundary + declaration exclusion + mitigation."""
    issues = []
    lines = code.splitlines()
    for vtype, patterns in PRECISE_SINKS:
        for pat in patterns:
            for m in re.finditer(pat, code, re.IGNORECASE):
                if _is_declaration(code, m.start()):
                    continue  # it's a declaration, not a sink usage
                line_no = code[:m.start()].count("\n") + 1
                line = lines[line_no - 1] if line_no <= len(lines) else ""
                # mitigation check: skip if a sanitizer is present nearby
                context = "\n".join(lines[max(0, line_no - 4):line_no])
                if _has_mitigation(vtype, context):
                    continue
                sink = m.group(0).strip()[:40]
                source = None
                for s in TAINT_SOURCES:
                    if re.search(r"\b" + re.escape(s) + r"\b", line, re.IGNORECASE):
                        source = s
                        break
                shape_dim = _shape_dimension(vtype, sink)
                issues.append({
                    "type": vtype, "line": line_no, "sink": sink,
                    "source": source, "shape_dimension": shape_dim,
                    "code_line": line.strip()[:60],
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


def _shape_dimension(vtype: str, sink: str) -> str:
    dim_map = {
        "EVAL_USE": "FLOW:EVAL", "JNDI_INJECTION": "FLOW:JNDI",
        "OGNL_INJECTION": "FLOW:OGNL", "CMD_INJECTION": "FLOW:CMD",
        "SQL_INJECTION": "FLOW:SQL", "PATH_TRAVERSAL": "FLOW:FILE",
        "XSS": "FLOW:RENDER", "DESERIALIZATION": "FLOW:DESERIALIZE",
        "BUFFER_OVERFLOW": "ACCESS:UNCHECKED", "HARDCODED_CRED": "IN:SECRET",
        "SSRF": "FLOW:SSRF", "XXE": "FLOW:XXE", "LDAP_INJECTION": "FLOW:LDAP",
        "TEMPLATE_INJECTION": "FLOW:TEMPLATE", "HEADER_INJECTION": "FLOW:HEADER",
        "LOG_INJECTION": "FLOW:LOG", "OPEN_REDIRECT": "FLOW:REDIRECT",
        "INSECURE_RANDOM": "CRYPTO:RANDOM", "WEAK_HASH": "CRYPTO:HASH",
    }
    return dim_map.get(vtype, "FLOW:UNKNOWN")


def find_buffer_overflows(code: str) -> List[Dict]:
    """Type-aware buffer overflow detection (only LIST_INDEX, not any x[y])."""
    issues = []
    types = _infer_types(code)
    subscripts = _classify_subscript(code, types)
    lines = code.splitlines()
    for s in subscripts:
        if s["class"] == "LIST_INDEX":
            # tainted index + no bounds check
            idx = s["index"]
            if idx in types and types[idx] == "PARAM":
                has_bounds = re.search(r"if\s+0\s*<=\s*\w+\s*<\s*len|if\s+\w+\s*<\s*len", code)
                if not has_bounds:
                    # find line
                    m = re.search(re.escape(s["object"]) + r"\s*\[", code)
                    line_no = code[:m.start()].count("\n") + 1 if m else 0
                    issues.append({
                        "type": "BUFFER_OVERFLOW", "line": line_no,
                        "sink": f"{s['object']}[{s['index']}]",
                        "source": idx, "shape_dimension": "ACCESS:UNCHECKED",
                        "code_line": lines[line_no-1].strip()[:60] if 0 < line_no <= len(lines) else "",
                    })
    return issues


def issue_summary(code: str) -> str:
    """Human-readable precise issue summary."""
    issues = find_precise_issues(code) + find_buffer_overflows(code)
    if not issues:
        return "CLEAN"
    parts = []
    for i in issues:
        loc = f"L{i['line']}"
        src = f"<-{i['source']}" if i["source"] else ""
        parts.append(f"{i['type']}@{loc}{src}[{i['shape_dimension']}]")
    return "; ".join(parts)


# ── Self-test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # False positives that v1 caught (should now be clean)
    fp_cases = {
        "efcore-method": "public virtual Func<QueryContext, TResult> CreateQueryExecutor<TResult>(Expression query)",
        "composer-curl": "return \\extension_loaded('curl') && \\function_exists('curl_multi_exec')",
        "exposed-fun": "fun <T : Any> exec(",
        "swift-array": "private var headers: [HTTPHeader] = []",
    }
    print("=== v2 false-positive fixes (should all be CLEAN) ===")
    for name, code in fp_cases.items():
        print(f"  {name:18s}: {issue_summary(code)}")

    # Real CVEs (should still be detected)
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
    from real_cve_corpus import REAL_CVES
    print("\n=== Real CVEs (should still be detected) ===")
    for cve, name, code, exp_type, exp_source in REAL_CVES:
        issues = find_precise_issues(code) + find_buffer_overflows(code)
        types = [i["type"] for i in issues]
        print(f"  {cve:14s} {name:22s} {str(types)}")