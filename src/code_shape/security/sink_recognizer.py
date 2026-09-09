#!/usr/bin/env python
"""sink_recognizer.py — Recognize dangerous sinks by semantic role.
is a function whose name/behavior indicates a SECURITY-SENSITIVE capability.
When fed untrusted input, it becomes a vulnerability.

Instead of a fixed sink list, this recognizes sinks by SEMANTIC ROLE (name
patterns + context), so it can flag arbitrary dangerous functions like
`execute_ognl`, `jndi.lookup`, `run_command`, etc.

Sink categories (what makes a sink dangerous):
  CODE_EXEC   — executes code/commands (eval, exec, system, subprocess, ognl, jndi)
  SQL         — queries a database (execute, query, select, insert, update)
  FILE        — accesses the filesystem (open, read, write, file)
  RENDER      — renders untrusted content (innerHTML, document.write, html)
  DESERIALIZE — deserializes data (pickle, yaml, load, unserialize)
  MEMORY      — unsafe memory access (array index, slice, buffer)

Dependency-free (stdlib only).
"""
import re
from typing import Dict, List, Set

# ── Sink semantic-role patterns ─────────────────────────────────────────────
# Each category: name patterns that indicate the dangerous capability.
SINK_ROLES = {
    "CODE_EXEC": [
        r"\beval\s*\(", r"\bexec\s*\(", r"os\.system", r"system\s*\(",
        r"subprocess\.(?:call|run|Popen|check_output)", r"Runtime\.getRuntime\(\)\.exec",
        r"ProcessBuilder", r"ognl", r"jndi\.lookup", r"lookup\s*\(",
        r"run_command", r"execute_command", r"shell_exec", r"passthru",
        r"popen", r"proc_open", r"system\s*\(", r"backtick",
    ],
    "SQL": [
        r"\.execute\s*\(", r"\.query\s*\(", r"createQuery", r"rawQuery",
        r"SELECT\s+.*\bFROM\b", r"INSERT\s+INTO", r"UPDATE\s+\w+\s+SET",
        r"DELETE\s+FROM", r"\.prepareStatement", r"\.createStatement",
    ],
    "FILE": [
        r"\bopen\s*\(", r"fopen\s*\(", r"readFile", r"writeFile", r"\.read\s*\(",
        r"\.write\s*\(", r"file_get_contents", r"file_put_contents", r"unlink",
        r"os\.remove", r"os\.path\.join", r"Path\s*\(", r"new\s+File\s*\(",
    ],
    "RENDER": [
        r"innerHTML", r"document\.write", r"\.html\s*\(", r"render\s*\(",
        r"\.appendChild", r"insertAdjacentHTML", r"outerHTML", r"v-html",
    ],
    "DESERIALIZE": [
        r"pickle\.loads", r"pickle\.load\s*\(", r"yaml\.load\s*\(", r"yaml\.load",
        r"unserialize\s*\(", r"ObjectInputStream", r"readObject", r"marshal\.loads",
        r"json\.loads\s*\([^)]*object_hook", r"load\s*\([^)]*Loader",
    ],
    "MEMORY": [
        r"\[\s*\w+\s*\]", r"\[\s*\w+\s*:\s*\w+\s*\]", r"memcpy", r"strcpy",
        r"strcat", r"sprintf", r"buffer\[", r"\.substring\s*\(", r"\.slice\s*\(",
    ],
}

# Sink impact (for exploitability)
SINK_IMPACT = {
    "CODE_EXEC": 1.0, "SQL": 1.0, "DESERIALIZE": 0.9,
    "MEMORY": 0.9, "FILE": 0.8, "RENDER": 0.7,
}


def recognize_sinks(code: str) -> List[Dict]:
    """Recognize dangerous sinks in code by semantic role.

    Returns [{category, sink, impact, match}] for each recognized sink.
    """
    sinks = []
    for category, patterns in SINK_ROLES.items():
        for pat in patterns:
            for m in re.finditer(pat, code, re.IGNORECASE):
                # extract the sink name (the function/identifier)
                sink = m.group(0).strip()
                sinks.append({
                    "category": category,
                    "sink": sink[:40],
                    "impact": SINK_IMPACT[category],
                    "match": m.group(0),
                })
    # dedupe by (category, sink)
    seen = set()
    unique = []
    for s in sinks:
        key = (s["category"], s["sink"])
        if key not in seen:
            seen.add(key)
            unique.append(s)
    return unique


def is_dangerous_sink(code: str) -> bool:
    """True if the code contains any recognized dangerous sink."""
    return len(recognize_sinks(code)) > 0


def sink_shape(code: str) -> Dict[str, float]:
    """Sink-aware shape: which sink categories are present (part of the shape)."""
    import math
    sinks = recognize_sinks(code)
    vec: Dict[str, float] = {}
    for s in sinks:
        vec[f"SINK:{s['category']}"] = vec.get(f"SINK:{s['category']}", 0) + s["impact"]
    norm = math.sqrt(sum(v * v for v in vec.values()))
    if norm == 0:
        return {}
    return {k: round(v / norm, 4) for k, v in vec.items()}


# ── Self-test on real CVE sinks ─────────────────────────────────────────────
if __name__ == "__main__":
    # Real CVE sinks that the fixed-list detector MISSED
    real_sinks = {
        "struts-ognl": "def handle(request):\n    ct = request.headers['Content-Type']\n    return execute_ognl(ct)",
        "log4shell": "def log(msg):\n    return jndi.lookup(msg)",
        "heartbleed": "def heartbeat(payload, length):\n    return payload[0:length]",
        "webmin": "def change(user, newpass):\n    return os.system('echo ' + newpass)",
        "drupal": "def process(form):\n    return eval(form['mail'])",
        "citrix": "def get(request):\n    name = request.args['name']\n    return db.execute('SELECT * FROM users WHERE name = ' + name)",
    }
    print("=== Sink recognition on real CVE sinks ===")
    for name, code in real_sinks.items():
        sinks = recognize_sinks(code)
        cats = sorted(set(s["category"] for s in sinks))
        print(f"{name:12s} sinks={cats} shape={sorted(sink_shape(code).keys())}")
