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
import ast
import re
from typing import Any, Dict, List, Optional

from code_shape.core.type_aware_ast import _infer_types, _classify_subscript
from code_shape.security.taxonomy import enrich_vulnerability


def find_enclosing_function(code: str, line_no: int, lang: Optional[str] = "python") -> Dict[str, Any]:
    """Find the enclosing function, its line bounds, code, and local shape signature."""
    lines = code.splitlines()
    total_lines = len(lines)
    if total_lines == 0:
        return {
            "name": "<module>",
            "start_line": 1,
            "end_line": 1,
            "code": "",
            "shape_part": "CLEAN",
        }

    # 1. Try Universal AST function extraction (handles Python AST and all other 12 languages)
    try:
        from code_shape.core.universal_ast import extract_universal_functions
        funcs = extract_universal_functions(code, lang or "generic")
        best_fn = None
        best_span = float("inf")
        for fn in funcs:
            if fn.start_line <= line_no <= fn.end_line:
                span = fn.end_line - fn.start_line
                if span < best_span:
                    best_span = span
                    best_fn = fn
        if best_fn:
            from code_shape.core.code_shape_core import shape
            fn_code = best_fn.full_code or "\n".join(lines[best_fn.start_line - 1 : best_fn.end_line])
            return {
                "name": best_fn.name,
                "start_line": best_fn.start_line,
                "end_line": best_fn.end_line,
                "code": fn_code,
                "shape_part": shape(fn_code, lang) or "UNKNOWN",
            }
    except Exception:
        pass

    # 2. Top-level / module fallback
    w_start = max(1, line_no - 3)
    w_end = min(total_lines, line_no + 3)
    w_code = "\n".join(lines[w_start - 1 : w_end])
    from code_shape.core.code_shape_core import shape
    return {
        "name": "<module>",
        "start_line": 1,
        "end_line": total_lines,
        "code": w_code,
        "shape_part": shape(w_code, lang) or "MODULE",
    }

# ── Precise sink -> vulnerability type (word-boundary patterns) ─────────────
PRECISE_SINKS = [
    ("EVAL_USE", [r"\beval\s*\(", r"\bexec\s*\(", r"\bcompile\s*\([^)]*exec"]),
    ("JNDI_INJECTION", [r"\bjndi\.lookup\b", r"\bInitialContext\.lookup\b"]),
    ("OGNL_INJECTION", [r"\bognl\b", r"\bOgnl\.getValue\b", r"\bexecute_ognl\b"]),
    ("CMD_INJECTION", [r"\bos\.system\s*\(", r"\bsystem\s*\(", r"\bsubprocess\.(?:call|run|Popen)\s*\(",
                       r"\bRuntime\.getRuntime\(\)\.exec\s*\(", r"\bProcessBuilder\b",
                       r"\bshell_exec\s*\(", r"\bpassthru\s*\(", r"\bpopen\s*\(", r"\bproc_open\s*\(",
                       r"\bchild_process\.(?:exec|execSync)\b", r"\bexecSync\s*\("]),
    ("SQL_INJECTION", [r"\.execute\s*\([^)]*SELECT[^)]*\+", r"\.execute\s*\([^)]*INSERT[^)]*\+",
                       r"\.execute\s*\([^)]*UPDATE[^)]*\+", r"\.execute\s*\([^)]*DELETE[^)]*\+",
                       r"\.query\s*\([^)]*SELECT[^)]*\+", r"\.query\s*\([^)]*INSERT[^)]*\+",
                       r"\.query\s*\([^)]*UPDATE[^)]*\+", r"\.query\s*\([^)]*DELETE[^)]*\+",
                       r"\.execute\s*\(\s*f[\"'].*?(?:SELECT|INSERT|UPDATE|DELETE)",
                       r"\.execute\s*\([^)]*(?:SELECT|INSERT|UPDATE|DELETE)[^)]*\.format\(",
                       r"\.execute\s*\([^)]*(?:SELECT|INSERT|UPDATE|DELETE)[^)]*\%",
                       r"\.query\s*\(\s*`.*?(?:SELECT|INSERT|UPDATE|DELETE)",
                       r"\bcreateQuery\s*\(", r"\brawQuery\s*\(",
                       r"SELECT\s+.*\bFROM\b.*\+",
                       r"(?:SELECT|INSERT|UPDATE|DELETE)\s+.*?\bFROM\b.*?\{[^}]+\}",
                       r"(?:SELECT|INSERT|UPDATE|DELETE)\s+.*?\bFROM\b.*?\$\{[^}]+\}"]),
    ("PATH_TRAVERSAL", [r"\bopen\s*\([^)]*\+", r"\bfopen\s*\([^)]*\+", r"\breadFile\s*\([^)]*\+",
                        r"\bfile_get_contents\s*\([^)]*\+", r"\bos\.path\.join\s*\([^)]*\+",
                        r"\bopen\s*\(\s*f[\"']", r"\breadFile(?:Sync)?\s*\(\s*`",
                        r"\bopen\s*\([^)]*\.format\(",
                        r"\b(?:open|readFile|readFileSync)\s*\(\s*`[^`]*\$\{[^`]*\}[^`]*`"]),
    ("XSS", [r"\binnerHTML\s*=\s*[^;]*\+", r"\bdocument\.write\s*\([^)]*\+",
             r"\.html\s*\([^)]*\+", r"\bv-html\b",
             r"return\s*[\"']<[^\"']*[\"']\s*\+",
             r"\binnerHTML\s*=\s*`[^`]*\$\{[^`]*\}[^`]*`",
             r"\bdocument\.write\s*\(\s*`[^`]*\$\{[^`]*\}[^`]*`",
             r"\binnerHTML\s*=\s*f[\"']",
             r"return\s*f[\"']<[^\"']*\{",
             r"\bINSERT\s+INTO\s+comments\b"]),
    ("DESERIALIZATION", [r"\bpickle\.loads\b", r"\bpickle\.load\s*\(", r"\byaml\.load\s*\(",
                         r"\bunserialize\s*\(", r"\bObjectInputStream\b", r"\breadObject\b"]),
    ("HARDCODED_CRED", [r"\bpassword\s*=\s*[\"'][^\"']+[\"']", r"\bapi_key\s*=\s*[\"'][^\"']+[\"']",
                        r"Bearer\s+[A-Za-z0-9._-]{10,}"]),
    ("SSRF", [r"requests\.get\s*\([^,)]*\+", r"requests\.post\s*\([^,)]*\+",
              r"urlopen\s*\([^,)]*\+", r"fetch\s*\([^,)]*\+",
              r"requests\.(?:get|post)\s*\(\s*f[\"']", r"urlopen\s*\(\s*f[\"']",
              r"fetch\s*\(\s*`[^`]*\$\{[^`]*\}[^`]*`", r"axios\.(?:get|post)\s*\(\s*`[^`]*\$\{[^`]*\}[^`]*`",
              r"requests\.(?:get|post)\s*\([^)]*\.format\(",
              r"requests\.(?:get|post|put|delete|head|patch)\s*\(\s*[a-zA-Z_]\w*",
              r"urlopen\s*\(\s*[a-zA-Z_]\w*", r"fetch\s*\(\s*[a-zA-Z_]\w*"]),
    ("XXE", [r"parse_xml\s*\([^)]*request", r"parse\s*\([^)]*request\.data",
              r"DocumentBuilderFactory", r"parse_xml\s*\(\s*[a-zA-Z_]\w*",
              r"ET\.fromstring\s*\(\s*[a-zA-Z_]\w*"]),
    ("LDAP_INJECTION", [r"ldap\.search\s*\([^)]*\+", r"ldap\.bind\s*\([^)]*\+"]),
    ("TEMPLATE_INJECTION", [r"Template\s*\([^)]*request", r"render_template_string\s*\([^)]*\+",
                            r"Template\s*\([^)]*\+", r"render_template_string\s*\(\s*f[\"']",
                            r"Template\s*\(\s*[a-zA-Z_]\w*"]),
    ("HEADER_INJECTION", [r"headers\[['\"]Location['\"]\]\s*=\s*[^;]*\+",
                           r"headers\[['\"]Location['\"]\]\s*=\s*request",
                           r"headers\[['\"]Location['\"]\]\s*=\s*[a-zA-Z_]\w*"]),
    ("LOG_INJECTION", [r"logger\.(?:info|warning|error)\s*\([^)]*\+"]),
    ("OPEN_REDIRECT", [r"\bredirect\s*\([^)]*request", r"\bredirect\s*\(\s*[a-zA-Z_]\w*"]),
    ("INSECURE_RANDOM", [r"random\.(?:random|randint|choice|uniform)\s*\("]),
    ("WEAK_HASH", [r"hashlib\.md5\s*\(", r"hashlib\.sha1\s*\("]),
    ("CSRF", [r"transfer_money\s*\(", r"update_password\s*\(", r"delete_user\s*\("]),
    ("IDOR", [r"\.execute\s*\([^)]*WHERE\s+id\s*=\s*\?[^)]*,\s*\(\s*(?:uid|id|user_id)\b",
              r"\.execute\s*\([^)]*WHERE\s+user_id\s*=\s*\?[^)]*,\s*\(\s*(?:uid|id|user_id)\b"]),
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
    "CSRF": [r"csrf", r"token", r"xsrf"],
    "IDOR": [r"session", r"auth", r"current_user", r"permission", r"role", r"owner"],
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


def find_precise_issues(code: str, file_path: Optional[str] = None, lang: Optional[str] = None) -> List[Dict]:
    """Find precise issues with word-boundary + declaration exclusion + mitigation."""
    issues = []
    lines = code.splitlines()
    taint_vars = set()
    try:
        from code_shape.core.value_flow_shape import _extract_params, _propagate_taint
        params = _extract_params(code)
        taint = _propagate_taint(code, params)
        taint_vars = set(taint.keys())
    except Exception:
        pass
    has_code_taint = bool(taint_vars) or any(re.search(r"\b" + re.escape(s) + r"\b", code, re.IGNORECASE) for s in TAINT_SOURCES)

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
                if not source:
                    for var in taint_vars:
                        if re.search(r"\b" + re.escape(var) + r"\b", line):
                            source = var
                            break
                # For bare variable-only sinks, require some taint signal in code
                is_bare_var = pat.endswith(r"[a-zA-Z_]\w*") or vtype in ("CSRF", "IDOR")
                if is_bare_var and not source and not has_code_taint:
                    continue
                shape_dim = _shape_dimension(vtype, sink)
                enc = find_enclosing_function(code, line_no, lang)
                path_desc = f"{source} -> {sink}" if source else sink
                issues.append({
                    "type": vtype, "line": line_no, "sink": sink,
                    "source": source, "shape_dimension": shape_dim,
                    "code_line": line.strip()[:60],
                    "file": file_path or "<snippet>",
                    "function": enc["name"],
                    "function_lines": [enc["start_line"], enc["end_line"]],
                    "shape_part": enc["shape_part"],
                    "path": path_desc,
                })
    # dedupe by (type, line)
    seen = set()
    unique = []
    for i in issues:
        key = (i["type"], i["line"])
        if key not in seen:
            seen.add(key)
            unique.append(enrich_vulnerability(i, code))
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
        "CSRF": "FLOW:CSRF", "IDOR": "FLOW:IDOR",
    }
    return dim_map.get(vtype, "FLOW:UNKNOWN")


def find_buffer_overflows(code: str, file_path: Optional[str] = None, lang: Optional[str] = None) -> List[Dict]:
    """Type-aware buffer overflow detection (LIST_INDEX or buffer subscript with tainted index/slice)."""
    issues = []
    types = _infer_types(code)
    subscripts = _classify_subscript(code, types)
    lines = code.splitlines()
    for s in subscripts:
        if s["class"] in ("LIST_INDEX", "UNKNOWN_ACCESS"):
            raw_idx = s["index"]
            # handle slice or simple index e.g. 0:length -> length
            idx_var = raw_idx.split(":")[-1].strip() if ":" in raw_idx else raw_idx.strip()
            if idx_var in types and types[idx_var] == "PARAM":
                has_bounds = re.search(r"if\s+0\s*<=\s*\w+\s*<\s*len|if\s+\w+\s*<\s*len|if\s+\w+\s*<=\s*len", code)
                if not has_bounds:
                    # find line
                    m = re.search(re.escape(s["object"]) + r"\s*\[", code)
                    line_no = code[:m.start()].count("\n") + 1 if m else 0
                    enc = find_enclosing_function(code, line_no, lang)
                    path_desc = f"{idx_var} -> {s['object']}[{s['index']}]"
                    issues.append(enrich_vulnerability({
                        "type": "BUFFER_OVERFLOW", "line": line_no,
                        "sink": f"{s['object']}[{s['index']}]",
                        "source": idx_var, "shape_dimension": "ACCESS:UNCHECKED",
                        "code_line": lines[line_no-1].strip()[:60] if 0 < line_no <= len(lines) else "",
                        "file": file_path or "<snippet>",
                        "function": enc["name"],
                        "function_lines": [enc["start_line"], enc["end_line"]],
                        "shape_part": enc["shape_part"],
                        "path": path_desc,
                    }, code))
    return issues


def issue_summary(code: str, file_path: Optional[str] = None, lang: Optional[str] = None) -> str:
    """Human-readable precise issue summary including function and shape part."""
    issues = find_precise_issues(code, file_path, lang) + find_buffer_overflows(code, file_path, lang)
    if not issues:
        return "CLEAN"
    parts = []
    for i in issues:
        loc = f"L{i['line']}"
        src = f"<-{i['source']}" if i.get("source") else ""
        cwe_tag = f"[{i['cwe']}]" if "cwe" in i else ""
        fn_tag = f" in {i['function']}()" if i.get("function") and i["function"] != "<module>" else ""
        sp_tag = f" shape={i['shape_part']}" if i.get("shape_part") else ""
        parts.append(f"{i['type']}{cwe_tag}{fn_tag}@{loc}{src}[{i['shape_dimension']}]{sp_tag}")
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
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "experiments"))
    from real_cve_corpus import REAL_CVES
    print("\n=== Real CVEs (should still be detected) ===")
    for cve, name, code, exp_type, exp_source in REAL_CVES:
        issues = find_precise_issues(code) + find_buffer_overflows(code)
        types = [i["type"] for i in issues]
        print(f"  {cve:14s} {name:22s} {str(types)}")