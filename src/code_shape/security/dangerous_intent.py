#!/usr/bin/env python
"""dangerous_intent.py — Dangerous intent shape detection.
input flows to a call that COULD be dangerous, even if the sink is unknown or
has an innocuous name.

The intent is in the FLOW, not the name:
  tainted input -> call that could execute/query/file/render/deserialize

We detect the intent by the SHAPE of the call site:
  - the call receives tainted input (untrusted data)
  - the call's ARGUMENTS suggest a dangerous operation (string being executed,
    a query string, a file path, data being deserialized)

This catches NOVEL sinks that name-based detection misses (e.g. a function
named `process_data` that internally calls eval, or a custom `run()` that
executes its argument).

Dependency-free (stdlib only).
"""
import re
from typing import Dict, List, Set

from code_shape.core.value_flow_shape import _extract_params, _propagate_taint

# ── Dangerous intent signatures (what the call's ARGUMENTS suggest) ────────
# A call is dangerous-intent if its argument looks like:
INTENT_SIGNATURES = {
    "CODE_EXEC": [
        r"[\"'][^\"']*(?:;|&&|\|\||`|>|>>|rm |cat |curl |wget |nc |bash |sh )",  # shell metachars
        r"[\"'](?:python|perl|ruby|node|php|bash|sh|cmd|powershell)[\"']",  # interpreter
    ],
    "SQL": [
        r"[\"']SELECT\b", r"[\"']INSERT\b", r"[\"']UPDATE\b", r"[\"']DELETE\b",
        r"[\"']\w+\s*=\s*[\"']\s*\+",  # string concat in query
    ],
    "FILE": [
        r"[\"'](?:/|\./|\.\./|~/)",  # path-like
        r"[\"']\w+\.(?:txt|log|json|xml|html|py|js|db|sql)[\"']",  # file ext
    ],
    "RENDER": [
        r"[\"']<[^\"']*>",  # HTML tag
        r"[\"'](?:<div|<span|<p|<a |<script)",  # HTML
    ],
    "DESERIALIZE": [
        r"[\"'](?:pickle|yaml|json|xml|base64)[\"']",  # serialization format
    ],
}


def _call_args(code: str, call_start: int) -> str:
    """Extract the arguments of a call starting at call_start."""
    # find the opening paren
    open_paren = code.find("(", call_start)
    if open_paren == -1:
        return ""
    # find matching close paren (naive, no nesting)
    close_paren = code.find(")", open_paren)
    if close_paren == -1:
        return ""
    return code[open_paren + 1:close_paren]


def detect_dangerous_intent(code: str) -> List[Dict]:
    """Detect dangerous intent shapes: tainted input -> call with dangerous
    name OR dangerous argument.

    A call is dangerous-intent if it receives tainted input AND either:
      - the call NAME suggests danger (run, execute, load, query, read, ...)
      - the ARGUMENT looks dangerous (shell metachars, SQL, path, HTML)
    """
    findings = []
    params = _extract_params(code)
    taint = _propagate_taint(code, params)
    tainted_vars = set(taint.keys())

    # dangerous call-name keywords (suggest the call could be dangerous)
    DANGER_NAME = {"run", "execute", "exec", "system", "eval", "load", "loads",
                   "query", "read", "write", "open", "render", "html",
                   "process", "invoke", "call", "lookup", "deserialize",
                   "unserialize", "parse", "compile", "spawn", "popen"}

    for m in re.finditer(r"([a-zA-Z_]\w*)\s*\(", code):
        name = m.group(1)
        if name in ("if", "for", "while", "return", "def", "function", "func",
                    "fun", "print", "range", "len", "sum", "sorted", "import",
                    "from", "int", "str", "float", "list", "dict", "set", "new",
                    "class", "self", "this", "assert", "raise", "with", "not",
                    "and", "or", "in", "is", "lambda", "yield", "pass", "break",
                    "continue", "try", "except", "finally", "else", "elif",
                    "switch", "case", "catch", "throw", "typeof", "var", "let",
                    "const", "void", "bool", "char", "double", "long", "short",
                    "unsigned", "signed", "static", "public", "private",
                    "protected", "package", "namespace", "using", "require",
                    "include", "echo", "puts", "printf", "scanf", "console",
                    "document", "window", "Math", "String", "Integer", "Object",
                    "Array", "List", "Map", "Set", "File", "Path", "System",
                    "Runtime", "Process", "Thread", "Exception", "Error"):
            continue
        args = _call_args(code, m.start())
        if not args:
            continue
        # is the call fed by tainted input?
        tainted_feed = any(re.search(r"\b" + re.escape(v) + r"\b", args) for v in tainted_vars)
        if not tainted_feed:
            continue  # not dangerous intent (no untrusted input)
        # dangerous call name?
        name_danger = name.lower() in DANGER_NAME or any(
            k in name.lower() for k in ["exec", "system", "eval", "query", "load",
                                        "read", "write", "open", "render", "html",
                                        "deserialize", "unserialize", "parse", "compile"])
        # dangerous argument?
        arg_danger = False
        arg_cat = None
        for category, patterns in INTENT_SIGNATURES.items():
            for pat in patterns:
                if re.search(pat, args, re.IGNORECASE):
                    arg_danger = True
                    arg_cat = category
                    break
            if arg_danger:
                break
        if name_danger or arg_danger:
            # mitigation check: skip if the call has a safe form
            if _intent_mitigated(name, args):
                continue
            category = arg_cat or _name_category(name)
            findings.append({
                "category": category,
                "call": name,
                "intent": "tainted_input_to_dangerous_call",
                "tainted": True,
                "args": args.strip()[:40],
            })
    return findings


def _intent_mitigated(name: str, args: str) -> bool:
    """True if the call has a safe form (mitigation present)."""
    n = name.lower()
    # subprocess list-form is safe (no shell)
    if "subprocess" in n or n in ("run", "call", "popen"):
        if args.strip().startswith("["):
            return True
    # escape/basename/sanitize/quote in args (sanitizers)
    if re.search(r"escape\s*\(|basename\s*\(|sanitize|quote\s*\(|replace\s*\(", args):
        return True
    # json.loads is safe deserialization
    if "loads" in n and "json" in args:
        return True
    # safe=True / resolve_entities=False (safe template/xxe)
    if re.search(r"safe\s*=\s*True|resolve_entities\s*=\s*False", args):
        return True
    return False


def _name_category(name: str) -> str:
    """Infer the sink category from a dangerous call name."""
    n = name.lower()
    if any(k in n for k in ["exec", "system", "eval", "run", "process", "invoke", "spawn", "popen", "compile"]):
        return "CODE_EXEC"
    if any(k in n for k in ["query", "select", "insert", "update", "delete", "sql"]):
        return "SQL"
    if any(k in n for k in ["open", "read", "write", "file"]):
        return "FILE"
    if any(k in n for k in ["render", "html", "template"]):
        return "RENDER"
    if any(k in n for k in ["load", "deserialize", "unserialize", "parse"]):
        return "DESERIALIZE"
    return "UNKNOWN"


def dangerous_intent_shape(code: str) -> Dict[str, float]:
    """Dangerous-intent shape: which intent categories are present."""
    import math
    findings = detect_dangerous_intent(code)
    vec: Dict[str, float] = {}
    for f in findings:
        vec[f"INTENT:{f['category']}"] = vec.get(f"INTENT:{f['category']}", 0) + 1
    norm = math.sqrt(sum(v * v for v in vec.values()))
    if norm == 0:
        return {}
    return {k: round(v / norm, 4) for k, v in vec.items()}


# ── Self-test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Novel/unknown sinks with innocuous names but dangerous intent
    cases = {
        "innocuous-exec": "def process_data(data):\n    return run(data)",
        "shell-metachar": "def handle(user_input):\n    return execute('ls ' + user_input)",
        "sql-concat": "def lookup(name):\n    return query('SELECT * FROM users WHERE name = ' + name)",
        "file-path": "def load(path):\n    return read('/var/data/' + path)",
        "html-render": "def show(name):\n    return render('<div>' + name + '</div>')",
        "deserialize": "def parse(data):\n    return loads(data)",
        "safe": "def add(a, b):\n    return a + b",
    }
    print("=== Dangerous intent shape detection (novel sinks) ===")
    for name, code in cases.items():
        findings = detect_dangerous_intent(code)
        cats = sorted(set(f["category"] for f in findings))
        print(f"{name:18s} intent={cats} {[f['call'] for f in findings]}")
