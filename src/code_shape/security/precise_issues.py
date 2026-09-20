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
                       r"\bchild_process\.(?:exec|execSync)\b", r"\bexecSync\s*\(",
                       # reflective invocation: getattr(os, "system")(...) / getattr built dynamically.
                       r"\bgetattr\s*\(\s*\w+\s*,\s*['\"]\s*(?:system|exec|eval|popen|call|run|check_output|popen|spawn)\s*['\"]\s*\)",
                       # reflective on __builtins__ / dynamic import of dangerous modules
                       r"\bgetattr\s*\(\s*__builtins__\s*,\s*['\"]\s*(?:eval|exec|compile)['\"]\s*\)",
                       r"\b__import__\s*\(\s*['\"](?:os|subprocess|pty)['\"]"]),
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
    ("XSS", [r"\binnerHTML\s*=\s*[^;]*\+", r"\binnerHTML\s*\+=\s*[^;]*", r"\bdocument\.write\s*\([^)]*\+",
             r"\.html\s*\([^)]*\+", r"\bv-html\b",
             r"\.outerHTML\s*=\s*[^;\n]*[+\w]|[A-Za-z0-9\]].?\)?\s*\bouterHTML\s*=", r"\.setAttribute\s*\([^)]*(?:href|src|style)", r"\.insertAdjacentHTML\s*\([^)]*,\s*[A-Za-z_]\w*",
             r"return\s*[\"']<[^\"']*[\"']\s*\+",
             r"\binnerHTML\s*=\s*`[^`]*\$\{[^`]*\}[^`]*`",
             r"\bdocument\.write\s*\(\s*`[^`]*\$\{[^`]*\}[^`]*`",
             r"\binnerHTML\s*=\s*f[\"']",
             r"return\s*f[\"']<[^\"']*\{",
             r"\bINSERT\s+INTO\s+comments\b"]),
    ("DESERIALIZATION", [r"\bpickle\.loads\b", r"\bpickle\.load\s*\(", r"\byaml\.load\s*\(",
                         r"\bunserialize\s*\(", r"\bObjectInputStream\b", r"\breadObject\b",
                         r"\b\.unpackb\s*\(", r"\bmarshal\.loads\b", r"\bshelve\.open\b"]),
    ("HARDCODED_CRED", [r"\bpassword\s*=\s*[\"'][^\"']+[\"']", r"\bapi_key\s*=\s*[\"'][^\"']+[\"']",
                        r"Bearer\s+[A-Za-z0-9._-]{10,}",
                        # secret-bearing var assignments (TOKEN/SECRET/API_*/JWT/KEY)
                        r"\b\w*(?:token|secret|apikey|api_key|jwt|credential|passwd|password)\w*\s*=\s*['\"][^'\"]{8,}['\"]",
                        # OpenAI-style sk-... and JWT (eyJ...) bearer secrets
                        r"['\"]sk-(?:live|test|proj)-[A-Za-z0-9_-]{16,}['\"]",
                        r"['\"]eyJ[A-Za-z0-9_-]{6,}\.(?:[A-Za-z0-9_-]{6,}\.)?[A-Za-z0-9_-]{4,}['\"]",
                        # PEM private keys (RSA/EC/OPENSSH/etc.)
                        r"-----BEGIN [A-Z ]*PRIVATE KEY-----"]),
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
    ("LOG_INJECTION", [r"logger\.(?:info|warning|error|debug|critical)\s*\([^)]*\+",
                        r"logging\.(?:info|warning|error|debug|critical)\s*\([^)]*\+",
                        r"console\.log\s*\([^)]*\+", r"log\.(?:info|debug|warn|error)\s*\([^)]*\+",
                        r"print\s*\([^)]*\+.*\b(user|req|request|input|query|id)\b"]),
    ("OPEN_REDIRECT", [r"\bredirect\s*\([^)]*request", r"\bredirect\s*\(\s*[a-zA-Z_]\w*"]),
    ("INSECURE_RANDOM", [r"random\.(?:random|randint|choice|uniform)\s*\("]),
    ("WEAK_HASH", [r"hashlib\.md5\s*\(", r"hashlib\.sha1\s*\(", 
                   # weak crypto primitives: DES/3DES/RC4/Blowfish/MD2/MD4 insecure modes
                   r"\bDES\.new\b", r"\b3DES\.new\b", r"\bARC4\.new\b", r"\bBlowfish\.new\b",
                   r"\bmd2\s*\(", r"\bmd4\s*\(", r"\bECB\.new\b",
                   # cross-language weak hashing: CryptoJS.MD5 (JS), openssl md5 (PHP),
                   # MessageDigest MD5 (Java), digest('md5', ...) (many).
                   r"CryptoJS\.(?:MD5|SHA1)\b", r"MessageDigest.*(?:MD5|SHA-1)",
                   r"(?:openssl::digest|hash_init|digest)\s*\(\s*['\"]md5['\"]",
                   r"'md5'\s*,\s*[A-Za-z_]\w*", r"\bmd5\s*\(",
                   # small/insecure key sizes (RSA/DSA <2048 bits deprecated)
                   r"\bRSA\.generate\s*\(\s*(?:512|768|1024)\b",
                   r"\bkey_length\s*=\s*(?:512|768|1024)\b"]),
    ("CSRF", [r"transfer_money\s*\(", r"update_password\s*\(", r"delete_user\s*\("]),
    ("IDOR", [r"\.execute\s*\([^)]*WHERE\s+id\s*=\s*\?[^)]*,\s*\(\s*(?:uid|id|user_id)\b",
              r"\.execute\s*\([^)]*WHERE\s+user_id\s*=\s*\?[^)]*,\s*\(\s*(?:uid|id|user_id)\b"]),
]

# Sink types that must be driven by a tainted source. Their patterns can match
# benign code (e.g. `logger.info('u ' + str(name))` concatenates a `+` but has no
# untrusted input), so we require a tainted source on the sink line (or a
# code-wide taint signal) before reporting — exactly like the bare-var guard.
REQUIRES_TAINT = {
    "LOG_INJECTION", "OPEN_REDIRECT", "XSS", "HEADER_INJECTION",
}

# Taint sources
TAINT_SOURCES = ["request", "req", "ctx", "input", "argv", "os.environ",
                 "$_GET", "$_POST", "$_REQUEST", "body", "params", "query",
                 "form", "json", "data", "cookie", "header", "session"]

# Words that are CLEAR standalone entry signals for a code-wide taint check.
# `json`/`data`/`form`/`query` etc. are too common as generic code tokens or
# filenames (e.g. `app.json`, `query = ...`) to set a code-wide taint flag —
# they still count as sources when they appear ON the actual sink line.
_CODE_WIDE_TAINT_SOURCES = ["request", "req", "argv", "os.environ",
                            "$_GET", "$_POST", "$_REQUEST", "stdin",
                            "get", "input", "raw_input", "body", "environ"]


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


# Dangerous callable names whose aliasing (alias = eval, run = os.system) is a
# direct obfuscation of a dangerous sink, mapped to the vuln type they cause.
_ALIASABLE_SINKS = {
    "eval": "EVAL_USE", "compile": "EVAL_USE", "exec": "EVAL_USE",
    "system": "CMD_INJECTION", "popen": "CMD_INJECTION", "execvp": "CMD_INJECTION",
    "call": "CMD_INJECTION", "run": "CMD_INJECTION", "check_output": "CMD_INJECTION",
    "Popen": "CMD_INJECTION", "spawn": "CMD_INJECTION", "shell": "CMD_INJECTION",
    "pickle.loads": "DESERIALIZATION", "pickle.load": "DESERIALIZATION",
    "yaml.load": "DESERIALIZATION", "unserialize": "DESERIALIZATION",
    "render_template_string": "TEMPLATE_INJECTION", "loads": "DESERIALIZATION", "load": "DESERIALIZATION",
}

# Reflective builtins that become dangerous when INVOKED with a dangerous
# function/module name (an alias to getattr/__import__ used for RCE evasion).
_REFLECTIVE_ALIASES = {"getattr": "getattr", "__import__": "__import__"}


def _find_alias_sinks(code: str, lines: List[str], file_path: str,
                      taint_vars, has_code_taint) -> List[Dict]:
    """Detect aliased dangerous-sink calls: `run = os.system; run(c)` and
    `execute = eval; execute(x)`. When a variable is assigned a dangerous
    callable and later invoked with an argument, that's the same sink — an
    obfuscation pattern static sink-regexes miss."""
    from code_shape.security.taxonomy import enrich_vulnerability
    issues = []
    aliases = {}
    # 1. collect alias assignments: var = <dangerous callable>
    for m in re.finditer(r"\b(\w+)\s*=\s*([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?)\s*$", code, re.MULTILINE):
        var, rhs = m.group(1), m.group(2).strip()
        base = rhs.split(".")[-1] if "." in rhs else rhs
        if var in ("self", "cls"):
            continue
        if base in _ALIASABLE_SINKS:
            aliases[var] = ("sink", _ALIASABLE_SINKS[base])
        elif base in _REFLECTIVE_ALIASES:
            # g = getattr / gi = __import__ — dangerous only when invoked
            # reflectively, so store the reflective base to match args against.
            aliases[var] = ("reflective", base)
    if not aliases:
        return []
    # 2. report alias invocations alias(...) that reach a tainted arg or have taint.
    for alias, (kind, vtype) in aliases.items():
        for m in re.finditer(r"\b" + re.escape(alias) + r"\s*\((.*?)\)", code):
            line_no = code[: m.start()].count("\n") + 1
            arg = m.group(1).strip()
            # an alias call of a dangerous sink only matters if it has an argument
            # (a real invocation) and ideally a taint signal.
            if not arg:
                continue
            # skip if it's the assignment line itself (`run = os.system` line)
            if line_no == code[: code.find(alias)].count("\n") + 1:
                continue
            src = None
            for s in TAINT_SOURCES:
                if re.search(r"\b" + re.escape(s) + r"\b", lines[line_no - 1] if 0 < line_no <= len(lines) else "", re.IGNORECASE):
                    src = s
                    break
            if not src:
                for v in taint_vars:
                    if re.search(r"\b" + re.escape(v) + r"\b", arg):
                        src = v
                        break
            # reflective alias (g = getattr / gi = __import__): only fires when
            # the invocation args name a dangerous function/module.
            if kind == "reflective":
                call = f"{alias}({arg})"
                if vtype == "getattr":
                    if not re.search(r"(?:eval|exec|compile|system|popen|calls?)\b", arg):
                        continue
                else:  # __import__
                    if not re.search(r"['\"](?:os|subprocess|pty|commands)['\"]", arg):
                        continue
                vtype = "CMD_INJECTION"
            needs_taint = vtype in REQUIRES_TAINT
            if not src and (needs_taint or not has_code_taint) and vtype not in _SELF_TAINTED_ALIAS:
                continue
            from code_shape.core.code_shape_core import shape
            enc_name = "<module>"
            enc_shape = "ALIAS"
            issues.append({
                "type": vtype, "line": line_no, "sink": f"{alias}({arg[:20]})",
                "source": src, "shape_dimension": _shape_dimension(vtype, alias),
                "code_line": lines[line_no - 1].strip()[:60] if 0 < line_no <= len(lines) else "",
                "file": file_path or "<snippet>",
                "function": enc_name, "function_lines": [1, len(lines)],
                "shape_part": enc_shape,
                "path": (src + " -> " if src else "") + f"{alias}()",
                "path_hops": [src or "?", alias],
            })
    return [enrich_vulnerability(i, code) for i in issues]


_SELF_TAINTED_ALIAS = {"EVAL_USE", "CMD_INJECTION", "DESERIALIZATION"}

# Map of sink SHAPE role -> vulnerability type for the shape-driven pass.
_SHAPE_ROLE_TO_VULN = {
    "CODE_EXEC": "CMD_INJECTION",
    "SQL": "SQL_INJECTION",
    "FILE": "PATH_TRAVERSAL",
    "RENDER": "XSS",
    "DESERIALIZE": "DESERIALIZATION",
    "MEMORY": "BUFFER_OVERFLOW",
}

# Common call names that are NOT sinks even if their shape is role-like (avoid
# false positives: e.g. `query` used for an in-memory filter, `fetch` for a
# network client that validates). Only flag when the role score is strong AND a
# tainted argument reaches the call.
_NON_SINK_CALLS = {
    "query", "fetch", "load", "open", "read", "write", "get", "post", "put",
    "delete", "filter", "map", "reduce", "search", "find", "getattr",
    "str", "int", "float", "list", "dict", "set", "len", "print", "input",
    "requests.get", "requests.post", "urlopen",  # handled by SSRF/other paths
    # polymorphic names already handled by exact precise-sink regexes — the
    # shape pass is for OBSCURE custom sink names, not re-flagging these.
    "execute", "exec", "system", "eval", "popen", "call", "run", "check_output",
    "Popen", "spawn", "render_template_string", "pickle", "md5", "sha1",
}


def _shape_sinks(code: str, lines: List[str], file_path: str,
                 taint_vars, has_code_taint) -> List[Dict]:
    """Shape-driven dangerous-call detection.

    Finds custom/obscure sink NAMES (e.g. `invoke_process`, `query_users`,
    `copy_buffer`) whose CODE SHAPE — the semantic-role vector from
    sink_shape_vector — matches a dangerous role AND which receive a tainted
    argument. This catches vulnerabilities by geometric shape, not exact-function
    enumeration: a function named `query_users` concatenating a tainted var into
    a SQL string is a SQL injection even if `execute`/`query` never appear
    literally as a known sink.
    """
    from code_shape.security.sink_shape_vector import classify_sink
    issues = []
    try:
        from code_shape.core.agnostic_shape import _tokenize
        toks = _tokenize(code)
    except Exception:
        return []
    # cross-language function parameters (Java `void f(String c)`, PHP
    # `function f($v)`, Go `func f(c string)`, ...) — a shape-role sink
    # receiving such a param is tainted (params are entry points), even when
    # _propagate_taint (Python-centric) didn't mark them.
    param_names = set(taint_vars)
    # def/function/func/fun name(params) — Python/JS/Ruby/Go/Rust
    for m in re.finditer(r"(?:def|function|func|fun)\s+[\w:]+\s*\(([^)]*)\)", code):
        for p in m.group(1).split(","):
            p = p.strip()
            tok = re.split(r"[:\s=]", p)[0]
            tok = re.sub(r"[\$@]", "", tok)
            if re.match(r"^[A-Za-z_]\w*$", tok):
                param_names.add(tok)
    # Java/C/Go-style typed definitions: only when guarded by an access modifier
    # (which never appears before a CALL) or a Go `func` — `void f(String c)`,
    # `public String run(String c)`, `private void helper(int n)`. Requiring the
    # modifier (or func) avoids mistaking `return query_users(x)` for a def.
    # line-start typed def: `void f(String c)`, `int main(int n)`, or with an
    # access modifier `public void f(String c)`. Line-anchored + modifier
    # guards against treating a CALL (mid-statement) as a definition.
    for sig in re.finditer(
        r"(?m)^\s*(?:(public|private|protected|static)\s+)?(\S+)\s+([A-Za-z_]\w*)\s*\(([^)]*)\)", code):
        typeword, fname, plist = sig.group(2), sig.group(3), sig.group(4)
        # skip statement-verbs that would make a CALL look like a definition
        # (`return foo(x)`, `throw e`, `echo ...`), and language keywords.
        if typeword.lower() in ("return", "throw", "yield", "await", "echo",
                                "print", "printf", "new", "if", "for", "while",
                                "switch", "catch", "import", "from", "using",
                                "namespace", "package", "require", "include",
                                "return", "break", "continue", "else", "elif"):
            continue
        if fname.lower() in ("if", "for", "while", "switch", "catch", "new", "return"):
            continue
        for p in plist.split(","):
            p = p.strip()
            # last whitespace-separated token is the param name in typed langs
            tok = p.split()[-1] if p.split() else ""
            tok = tok.replace("$", "").replace("*", "")
            if re.match(r"^[A-Za-z_]\w*$", tok):
                param_names.add(tok)

    # walk calls `name(` and pair with their closing paren to capture args.
    i = 0
    n = len(toks)
    while i < n:
        t = toks[i]
        if i + 1 < n and toks[i + 1] == "(" and (t.isidentifier() or "." in t):
            # skip function DEFINITIONS (def/function/func/fun name(...) —
            # these are not sink invocations and their names often look like
            # sinks, e.g. `def executeSearch(...)`).
            if i > 0 and toks[i - 1] in ("def", "function", "func", "fun",
                                         "fn", "const", "let", "var", "class"):
                i += 1
                continue
            name = t
            # capture args until matching close paren
            depth = 1
            j = i + 2
            arg_toks = []
            while j < n and depth > 0:
                if toks[j] == "(":
                    depth += 1
                elif toks[j] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                arg_toks.append(toks[j])
                j += 1
            args = " ".join(arg_toks)[:120]
            # classify by SHAPE
            try:
                cls = classify_sink(name, args)
            except Exception:
                cls = {"is_sink": False}
            if not cls.get("is_sink"):
                i += 1
                continue
            role = cls["role"]
            if role not in _SHAPE_ROLE_TO_VULN:
                i += 1
                continue
            if name in _NON_SINK_CALLS:
                i += 1
                continue
            vtype = _SHAPE_ROLE_TO_VULN[role]
            # taint gate: only flag when a tainted source flows into the call.
            line_no = code[: code.find(name)].count("\n") + 1 if name in code else 1
            src = None
            # strip string literals from the line first so a source keyword
            # inside a filename/string (e.g. `load_config('app.json')`) isn't
            # mistaken for an input source.
            _sline = lines[line_no - 1] if 0 < line_no <= len(lines) else ""
            try:
                from code_shape.core.agnostic_shape import _strip_strings_and_comments
                _sline = _strip_strings_and_comments(_sline)
            except Exception:
                pass
            for s in TAINT_SOURCES:
                if re.search(r"\b" + re.escape(s) + r"\b", _sline, re.IGNORECASE):
                    src = s
                    break
            if not src:
                for v in taint_vars:
                    if re.search(r"\b" + re.escape(v) + r"\b", args):
                        src = v
                        break
            if not src:
                # any function param flowing into a shape-role sink is tainted
                for p in param_names:
                    if re.search(r"\b" + re.escape(p) + r"\b", args):
                        src = p
                        break
            if not src and not has_code_taint:
                i += 1
                continue
            issues.append({
                "type": vtype, "line": line_no, "sink": f"{name}({args[:30]})",
                "source": src, "shape_dimension": f"SHAPE:{role}",
                "code_line": lines[line_no - 1].strip()[:60] if 0 < line_no <= len(lines) else "",
                "file": file_path or "<snippet>",
                "function": "<module>", "function_lines": [1, len(lines)],
                "shape_part": f"SHAPE>{role}",
                "path": (src + " -> " if src else "") + f"{name}()",
                "path_hops": [src or "?", name],
            })
        i += 1
    return issues


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
    # Code-wide taint uses the CLEAR entry signals only. Common words like
    # `json`/`data`/`form`/`query` appearing anywhere (e.g. the filename
    # `app.json`, an in-memory `query` var) must NOT set code-wide taint or
    # every JSON-using file becomes tainted — a systemic false-positive source.
    has_code_taint = bool(taint_vars) or any(
        re.search(r"\b" + re.escape(s) + r"\b", code, re.IGNORECASE)
        for s in _CODE_WIDE_TAINT_SOURCES)

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
                # For bare variable-only sinks, require some taint signal in code.
                # Template-literal interpolation (${...}) INTO a DOM/exec sink,
                # or a direct DOM mutation (innerHTML=, innerHTML+=, document.write,
                # .html()) is itself the dangerous action — the sink is
                # unambiguously an XSS vector regardless of the assigned variable,
                # so it counts as self-taint rather than being gated on a named
                # TAINT_SOURCE.
                is_bare_var = pat.endswith(r"[a-zA-Z_]\w*") or vtype in ("CSRF", "IDOR")
                sink_self_tainted = ("${" in sink) or ("f" in (m.group(0)[:1] if m.group(0) else ""))
                if vtype == "XSS" and re.search(r"innerHTML\s*(?:=|\+=)|document\.write|\.html\s*\(|v-html", sink):
                    sink_self_tainted = True
                if (is_bare_var or vtype in REQUIRES_TAINT) and not source and not has_code_taint and not sink_self_tainted:
                    continue
                shape_dim = _shape_dimension(vtype, sink)
                enc = find_enclosing_function(code, line_no, lang)
                # Emit the FULL source->sink data-flow path (Route Sixty-Sink style),
                # not just a shallow 2-hop string.
                try:
                    from code_shape.core.value_flow_shape import trace_taint_path, _extract_params
                    chain = trace_taint_path(code, line, _extract_params(code))
                    path_desc = " -> ".join(str(x) for x in chain)
                    path_hops = [str(x) for x in chain]
                except Exception:
                    path_desc = f"{source} -> {sink}" if source else sink
                    path_hops = [source or "UNKNOWN", sink]
                issues.append({
                    "type": vtype, "line": line_no, "sink": sink,
                    "source": source, "shape_dimension": shape_dim,
                    "code_line": line.strip()[:60],
                    "file": file_path or "<snippet>",
                    "function": enc["name"],
                    "function_lines": [enc["start_line"], enc["end_line"]],
                    "shape_part": enc["shape_part"],
                    "path": path_desc,
                    "path_hops": path_hops,
                })
    # aliased dangerous-sink calls (run = os.system; run(x) / execute = eval)
    issues += _find_alias_sinks(code, lines, file_path, taint_vars, has_code_taint)
    # shape-driven dangerous calls: flag custom/obscure sink NAMES whose code
    # SHAPE (role vector) matches a dangerous role with a tainted argument,
    # even when no exact sink regex matches.
    issues += _shape_sinks(code, lines, file_path, taint_vars, has_code_taint)
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
            # handle slice or simple index: check the LOWER bound first (the
            # attacker-controlled start), then the upper bound for a param.
            parts = [p.strip() for p in raw_idx.split(":")]
            if len(parts) == 1:
                idx_var = parts[0]
            else:
                idx_var = next((p for p in parts if p in types and types[p] == "PARAM"), parts[0] or "")
            if idx_var and idx_var in types and types[idx_var] == "PARAM":
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