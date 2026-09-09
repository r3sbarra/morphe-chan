#!/usr/bin/env python
"""intent_sinks.py — Intent/shape-based sink detection + hardcoded values.
patterns. A sink is dangerous based on its BEHAVIORAL SHAPE:

  - CODE_EXEC intent: input flows to a call that executes (READ -> CALL)
  - SQL intent: string concat flows to a query (CONCAT -> QUERY)
  - FILE intent: input flows to file access (READ -> OPEN)
  - RENDER intent: input flows to HTML output (READ -> RENDER)
  - DESERIALIZE intent: data flows to a load (READ -> LOAD)

Also flags HARDCODED VALUES: secrets (password/api_key/token), dangerous
constants (eval strings, shell commands), and magic numbers.

The shape/intent approach catches sinks with innocuous names that a name-based
detector misses (e.g. a function named `helper` that calls eval).

Dependency-free (stdlib only).
"""
import re
from typing import Dict, List, Set

from code_shape.core.value_flow_shape import _extract_params, _propagate_taint, _output_vars
from code_shape.security.semantic_sinks import detect_sinks, SINK_KEYWORDS

# ── Intent-based sink detection ────────────────────────────────────────────
# A sink is dangerous if its shape shows: tainted input -> dangerous operation.
# We detect the INTENT from the shape (value-flow) + the operation keywords.

# Dangerous operation keywords (what the call does)
# SQL checked first so 'execute'/'query' map to SQL, not CODE_EXEC.
OP_KEYWORDS = {
    "SQL": ["execute", "query", "select", "insert", "update", "delete", "sql"],
    "CODE_EXEC": ["exec", "system", "eval", "ognl", "jndi", "shell", "popen",
                  "command", "process", "spawn", "lookup", "invoke", "run"],
    "FILE": ["open", "read", "write", "file", "fopen", "unlink", "path"],
    "RENDER": ["render", "html", "innerhtml", "write", "template", "markup"],
    "DESERIALIZE": ["pickle", "yaml", "unserialize", "deserialize", "load"],
    "MEMORY": ["memcpy", "strcpy", "strcat", "buffer", "slice", "index"],
}


def detect_intent_sinks(code: str) -> List[Dict]:
    """Detect sinks by INTENT (shape: tainted input -> dangerous op)."""
    sinks = []
    params = _extract_params(code)
    taint = _propagate_taint(code, params)
    tainted_vars = set(taint.keys())

    # find calls and check if they're fed by tainted input
    for m in re.finditer(r"([a-zA-Z_]\w*)\s*\(", code):
        name = m.group(1).lower()
        # skip control-flow
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
        # check if the call is fed by tainted input (on the same line)
        line_start = code.rfind("\n", 0, m.start()) + 1
        line_end = code.find("\n", m.start())
        if line_end == -1:
            line_end = len(code)
        line = code[line_start:line_end]
        tainted_feed = any(re.search(r"\b" + re.escape(v) + r"\b", line) for v in tainted_vars)
        # check if the call name indicates a dangerous op
        for category, keywords in OP_KEYWORDS.items():
            if any(k in name for k in keywords):
                # intent: tainted input -> dangerous op
                if tainted_feed or tainted_vars:
                    sinks.append({
                        "category": category,
                        "sink": m.group(1),
                        "intent": "tainted_input_to_dangerous_op",
                        "tainted": tainted_feed,
                    })
                break
    return sinks


# ── Hardcoded value detection ───────────────────────────────────────────────
HARDCODED_PATTERNS = {
    "SECRET": [r"\b(?:password|passwd|pwd|api_key|apikey|secret|token)\s*=\s*[\"'][^\"']+[\"']",
               r"\b(?:password|passwd|pwd|api_key|apikey|secret|token)\s*[:=]\s*[\"'][^\"']+[\"']",
               r"(?:connect|login|auth|authenticate)\s*\([^)]*[\"'][^\"']+[\"']"],
    "SHELL_CMD": [r"os\.system\s*\(\s*[\"'][^\"']+[\"']", r"system\s*\(\s*[\"'][^\"']+[\"']",
                  r"subprocess\.(?:call|run|Popen)\s*\(\s*[\"'][^\"']+[\"']"],
    "EVAL_STR": [r"eval\s*\(\s*[\"'][^\"']+[\"']", r"exec\s*\(\s*[\"'][^\"']+[\"']"],
    "SQL_STR": [r"execute\s*\(\s*[\"'][^\"']*SELECT", r"query\s*\(\s*[\"'][^\"']*SELECT"],
    "MAGIC_NUMBER": [r"=\s*\d{4,}"],  # large magic numbers
}


def detect_hardcoded(code: str) -> List[Dict]:
    """Detect hardcoded values (secrets, shell cmds, eval strings, SQL)."""
    findings = []
    for htype, patterns in HARDCODED_PATTERNS.items():
        for pat in patterns:
            for m in re.finditer(pat, code):
                line_no = code[:m.start()].count("\n") + 1
                findings.append({
                    "type": htype,
                    "line": line_no,
                    "value": m.group(0).strip()[:40],
                })
    return findings


def combined_sink_detection(code: str) -> Dict:
    """Combine name-based + intent-based sink detection + hardcoded values."""
    name_sinks = detect_sinks(code)
    intent_sinks = detect_intent_sinks(code)
    hardcoded = detect_hardcoded(code)

    # merge name + intent sinks
    all_sinks = []
    seen = set()
    for s in name_sinks + intent_sinks:
        key = (s.get("category"), s.get("sink"))
        if key not in seen:
            seen.add(key)
            all_sinks.append(s)

    return {
        "name_sinks": name_sinks,
        "intent_sinks": intent_sinks,
        "hardcoded": hardcoded,
        "all_sinks": all_sinks,
    }


def sink_intent_shape(code: str) -> Dict[str, float]:
    """Sink-aware shape: which sink categories + hardcoded types are present."""
    import math
    res = combined_sink_detection(code)
    vec: Dict[str, float] = {}
    for s in res["all_sinks"]:
        vec[f"SINK:{s['category']}"] = vec.get(f"SINK:{s['category']}", 0) + 1
    for h in res["hardcoded"]:
        vec[f"HARD:{h['type']}"] = vec.get(f"HARD:{h['type']}", 0) + 1
    norm = math.sqrt(sum(v * v for v in vec.values()))
    if norm == 0:
        return {}
    return {k: round(v / norm, 4) for k, v in vec.items()}


# ── Self-test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    cases = {
        "innocuous-name-eval": "def helper(data):\n    return eval(data)",
        "hardcoded-secret": "def connect():\n    return db.connect(host, user, 'password123')",
        "hardcoded-shell": "def run():\n    return os.system('rm -rf /tmp/x')",
        "tainted-to-query": "def get(request):\n    name = request.args['name']\n    return db.execute('SELECT * FROM users WHERE name = ' + name)",
        "safe": "def add(a, b):\n    return a + b",
    }
    print("=== Intent/shape-based sink detection + hardcoded ===")
    for name, code in cases.items():
        res = combined_sink_detection(code)
        cats = sorted(set(s["category"] for s in res["all_sinks"]))
        hard = [h["type"] for h in res["hardcoded"]]
        print(f"{name:22s} sinks={cats} hardcoded={hard}")
