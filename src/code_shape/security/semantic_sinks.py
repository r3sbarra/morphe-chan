#!/usr/bin/env python
"""semantic_sinks.py — Semantic sink detection (catch ALL sinks).

Why fixed lists fail: sinks are recognized by their SEMANTIC ROLE, not exact
names. A sink is dangerous if its name/behavior indicates a security-sensitive
capability. To catch ALL sinks (custom, aliased, renamed, new), we:

1. Extract ALL function calls in the code.
2. Check if each call name contains a DANGEROUS KEYWORD (exec, system, eval,
   query, execute, open, read, write, load, render, html, deserialize, etc.).
   This catches `dangerous_exec`, `execute_ognl`, `run_command`, etc.
3. Handle ALIASING: track `s = os.system` so `s(cmd)` is recognized as a sink.
4. Classify by semantic role (CODE_EXEC/SQL/FILE/RENDER/DESERIALIZE/MEMORY).

Dependency-free (stdlib only).
"""
import re
from typing import Dict, List, Set

# ── Dangerous keywords by semantic role ─────────────────────────────────────
# A call is a sink if its name contains any of these keywords.
SINK_KEYWORDS = {
    "CODE_EXEC": ["exec", "system", "eval", "ognl", "jndi", "shell", "popen",
                  "passthru", "proc_open", "run_command", "command", "process",
                  "spawn", "fork", "lookup", "invoke", "call", "backtick"],
    "SQL": ["execute", "query", "select", "insert", "update", "delete", "sql",
            "createquery", "rawquery", "preparestatement", "createstatement"],
    "FILE": ["open", "read", "write", "file", "fopen", "unlink", "remove",
             "path", "readfile", "writefile", "get_contents", "put_contents"],
    "RENDER": ["render", "html", "innerhtml", "write", "appendchild",
               "insertadjacent", "template", "markup"],
    "DESERIALIZE": ["pickle", "yaml", "unserialize", "deserialize", "readobject",
                    "load", "marshal", "objectinputstream"],
    "MEMORY": ["memcpy", "strcpy", "strcat", "sprintf", "buffer", "slice",
               "substring", "index", "offset"],
}

# Aliasing: `s = os.system` -> s is a sink alias
ALIAS_PATTERNS = [
    r"(\w+)\s*=\s*(?:os\.)?(system|popen|exec|eval)\b",
    r"(\w+)\s*=\s*(\w+\.\w+)\b",  # general alias
]


def _extract_calls(code: str) -> List[Dict]:
    """Extract all function calls: {name, full, start}."""
    calls = []
    for m in re.finditer(r"([a-zA-Z_]\w*)\s*\(", code):
        name = m.group(1)
        # skip control-flow / builtins
        if name in ("if", "for", "while", "return", "def", "function", "func",
                    "fun", "print", "range", "len", "sum", "sorted", "import",
                    "from", "int", "str", "float", "list", "dict", "set", "new",
                    "class", "self", "this", "super", "assert", "raise", "with",
                    "not", "and", "or", "in", "is", "lambda", "yield", "pass",
                    "break", "continue", "try", "except", "finally", "else",
                    "elif", "switch", "case", "catch", "throw", "typeof", "var",
                    "let", "const", "void", "bool", "char", "double", "long",
                    "short", "unsigned", "signed", "static", "public", "private",
                    "protected", "package", "namespace", "using", "require",
                    "include", "echo", "puts", "printf", "scanf", "console",
                    "document", "window", "Math", "String", "Integer", "Object",
                    "Array", "List", "Map", "Set", "File", "Path", "System",
                    "Runtime", "Process", "Thread", "Exception", "Error"):
            continue
        calls.append({"name": name, "full": m.group(0), "start": m.start()})
    return calls


def _find_aliases(code: str) -> Dict[str, str]:
    """Find sink aliases: {alias: original_sink}."""
    aliases = {}
    for pat in ALIAS_PATTERNS:
        for m in re.finditer(pat, code):
            alias, target = m.group(1), m.group(2)
            # is the target a known sink?
            if any(k in target.lower() for k in ["system", "exec", "eval", "popen", "query", "execute", "open", "load"]):
                aliases[alias] = target
    return aliases


def detect_sinks(code: str) -> List[Dict]:
    """Detect ALL sinks by semantic role (keyword-in-name + aliasing)."""
    sinks = []
    calls = _extract_calls(code)
    aliases = _find_aliases(code)

    for call in calls:
        name = call["name"].lower()
        # check if the call is an alias of a known sink
        if call["name"] in aliases:
            sinks.append({
                "category": "CODE_EXEC",
                "sink": f"{call['name']} (alias of {aliases[call['name']]})",
                "impact": 1.0,
                "via_alias": True,
            })
            continue
        # check if the name contains a dangerous keyword
        for category, keywords in SINK_KEYWORDS.items():
            for kw in keywords:
                if kw in name:
                    sinks.append({
                        "category": category,
                        "sink": call["name"],
                        "impact": _impact(category),
                        "via_alias": False,
                    })
                    break
            else:
                continue
            break
    # dedupe
    seen = set()
    unique = []
    for s in sinks:
        key = (s["category"], s["sink"])
        if key not in seen:
            seen.add(key)
            unique.append(s)
    return unique


def _impact(category: str) -> float:
    return {"CODE_EXEC": 1.0, "SQL": 1.0, "DESERIALIZE": 0.9,
            "MEMORY": 0.9, "FILE": 0.8, "RENDER": 0.7}.get(category, 0.5)


def sink_shape(code: str) -> Dict[str, float]:
    """Sink-aware shape: which sink categories are present."""
    import math
    sinks = detect_sinks(code)
    vec: Dict[str, float] = {}
    for s in sinks:
        vec[f"SINK:{s['category']}"] = vec.get(f"SINK:{s['category']}", 0) + s["impact"]
    norm = math.sqrt(sum(v * v for v in vec.values()))
    if norm == 0:
        return {}
    return {k: round(v / norm, 4) for k, v in vec.items()}


# ── Self-test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    cases = {
        "aliased": "import os\ns = os.system\ns(cmd)",
        "custom-sink": "def process(data):\n    return execute_ognl(data)",
        "jndi": "def log(msg):\n    return jndi.lookup(msg)",
        "new-lib": "def run(data):\n    return dangerous_exec(data)",
        "obfuscated": "def a(b):\n    return eval(b)",
        "method-chain": "def f(x):\n    return obj.execute(x)",
        "template": "def f(x):\n    return render_template(x)",
        "deserialize": "def f(x):\n    return pickle.loads(x)",
        "run-command": "def f(x):\n    return run_command(x)",
        "safe": "def add(a,b):\n    return a+b",
    }
    print("=== Semantic sink detection (catch ALL sinks) ===")
    for name, code in cases.items():
        sinks = detect_sinks(code)
        cats = sorted(set(s["category"] for s in sinks))
        print(f"{name:14s} {cats} {[s['sink'] for s in sinks]}")
