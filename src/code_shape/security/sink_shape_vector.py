#!/usr/bin/env python
"""sink_shape_vector.py — Data-driven sink classification via shape vectors.
VECTOR approach: each call gets a semantic-role vector computed from its name
tokens + argument context, and the category is the argmax.

Instead of hardcoding `"exec" -> CODE_EXEC`, we compute how much a call name
"looks like" each sink role using a small set of SEMANTIC PRIMITIVES (the
atomic danger signals). The role vector is the shape of the sink.

This is extensible: new sink categories are added by defining their semantic
primitives, not by enumerating every dangerous function name.

Dependency-free (stdlib only).
"""
import math
import re
from typing import Dict, List

# ── Semantic primitives per sink role (the ATOMIC danger signals) ──────────
# These are the minimal semantic components; a call's role is the weighted
# sum of the primitives present in its name + args.
ROLE_PRIMITIVES = {
    "CODE_EXEC": ["exec", "system", "eval", "shell", "popen", "spawn", "fork",
                  "invoke", "command", "process", "run", "lookup", "jndi", "ognl"],
    "SQL": ["query", "select", "insert", "update", "delete", "sql", "execute"],
    "FILE": ["open", "read", "write", "file", "path", "unlink", "remove"],
    "RENDER": ["render", "html", "template", "markup", "innerhtml", "append",
               "paint", "draw", "content", "inner", "outer", "write_html", "insert"],
    "DESERIALIZE": ["load", "unserialize", "deserialize", "pickle", "yaml",
                    "marshal", "parse", "readobject", "unpack", "decode",
                    "hydrate", "restore", "unwrap"],
    "MEMORY": ["memcpy", "strcpy", "strcat", "sprintf", "buffer", "slice",
               "substring", "index", "offset"],
}

# Argument context signals (what the args suggest)
ARG_SIGNALS = {
    "CODE_EXEC": [r"[\"'][^\"']*(?:;|&&|\|\||`|>|>>|rm |cat |curl |bash |sh )"],
    "SQL": [r"[\"']SELECT\b", r"[\"']INSERT\b", r"[\"']UPDATE\b", r"[\"']DELETE\b"],
    "FILE": [r"[\"'](?:/|\./|\.\./|~/)", r"[\"']\w+\.(?:txt|log|json|xml|html)"],
    "RENDER": [r"[\"']<[^\"']*>", r"[\"'](?:<div|<span|<p|<a )"],
    "DESERIALIZE": [r"[\"'](?:pickle|yaml|json|xml|base64)[\"']"],
}


def _tokens(name: str) -> List[str]:
    """Split a call name into semantic tokens (camelCase, snake_case)."""
    # snake_case and camelCase splitting
    parts = re.split(r"[_\s]+", name)
    toks = []
    for p in parts:
        # split camelCase
        toks.extend(re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+", p))
    return [t.lower() for t in toks if t]


def role_vector(name: str, args: str = "") -> Dict[str, float]:
    """Compute the semantic-role vector of a call (how much it looks like each
    sink role). Returns {role: score}."""
    toks = _tokens(name)
    name_str = " ".join(toks)
    scores: Dict[str, float] = {}
    for role, prims in ROLE_PRIMITIVES.items():
        score = 0.0
        for prim in prims:
            if prim in name_str:
                score += 1.0
        # argument context adds signal
        for sig in ARG_SIGNALS.get(role, []):
            if re.search(sig, args, re.IGNORECASE):
                score += 0.5
        if score > 0:
            scores[role] = score
    return scores


def classify_sink(name: str, args: str = "") -> Dict:
    """Classify a call as a sink by its role vector (argmax)."""
    rv = role_vector(name, args)
    if not rv:
        return {"is_sink": False, "role": None, "vector": {}}
    role = max(rv, key=rv.get)
    return {"is_sink": True, "role": role, "vector": rv, "score": rv[role]}


def sink_shape(code: str) -> Dict[str, float]:
    """Sink-shape of a code snippet: normalized role-vector distribution."""
    vec: Dict[str, float] = {}
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
        # extract args
        open_p = code.find("(", m.start())
        close_p = code.find(")", open_p) if open_p != -1 else -1
        args = code[open_p + 1:close_p] if open_p != -1 and close_p != -1 else ""
        cls = classify_sink(name, args)
        if cls["is_sink"]:
            vec[f"SINK:{cls['role']}"] = vec.get(f"SINK:{cls['role']}", 0) + 1
    norm = math.sqrt(sum(v * v for v in vec.values()))
    if norm == 0:
        return {}
    return {k: round(v / norm, 4) for k, v in vec.items()}


# ── Self-test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    calls = [
        ("os.system", "'ls ' + cmd"),
        ("db.execute", "'SELECT * FROM users WHERE name = ' + name"),
        ("open", "'/var/www/' + f"),
        ("render_template", "'<div>' + name"),
        ("pickle.loads", "data"),
        ("execute_ognl", "content_type"),
        ("jndi.lookup", "msg"),
        ("dangerous_exec", "data"),
        ("run_command", "cmd"),
        ("add", "a, b"),
    ]
    print("=== Data-driven sink classification (role vectors) ===")
    for name, args in calls:
        cls = classify_sink(name, args)
        print(f"{name:18s} role={cls['role']} vector={cls['vector']}")
