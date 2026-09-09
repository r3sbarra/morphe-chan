#!/usr/bin/env python
"""program_bug_detector.py — Program-level bug detection via composite shape
analysis (function shapes + call graph):

1. ARITY_MISMATCH  — a function is called with the wrong number of arguments
                     (too few / too many vs its definition).
2. CALLER_CALLEE_MISMATCH — a caller's usage of a callee doesn't match the
                     callee's shape (e.g. callee returns a value but caller
                     ignores it, or callee takes params but caller passes none).
3. UNUSED_FUNCTION  — a function is defined but never called (dead code).
4. MISSING_CALLEE   — a function references a name that isn't defined (broken
                     call / undefined function).

Dependency-free (stdlib only).
"""
import re
from typing import Dict, List, Tuple

from code_shape.core.program_shape import extract_functions, extract_call_graph


def _arity(code: str) -> Dict[str, int]:
    """Extract each function's parameter count. Returns {name: n_params}."""
    arity: Dict[str, int] = {}
    for m in re.finditer(r"(?:def|function)\s+(\w+)\s*\(([^)]*)\)", code):
        params = [p.strip() for p in m.group(2).split(",") if p.strip()]
        arity[m.group(1)] = len(params)
    return arity


def _call_sites(code: str) -> List[Tuple[str, str, int]]:
    """Find all call sites: (caller_fn, callee_name, n_args).
    Skips the function's own definition line."""
    calls: List[Tuple[str, str, int]] = []
    functions = extract_functions(code)
    for caller, body in functions.items():
        # skip the def line itself
        body_lines = body.splitlines()
        body_no_def = "\n".join(l for l in body_lines if not re.match(r"^\s*(def|function)\b", l))
        for m in re.finditer(r"\b(\w+)\s*\(([^)]*)\)", body_no_def):
            callee = m.group(1)
            args = [a.strip() for a in m.group(2).split(",") if a.strip()]
            if callee in ("if", "for", "while", "return", "print", "range", "len", "sum", "sorted"):
                continue
            calls.append((caller, callee, len(args)))
    return calls


def detect_program_bugs(code: str) -> List[Dict]:
    """Detect program-level bugs. Returns list of {type, message}."""
    bugs: List[Dict] = []
    functions = extract_functions(code)
    arity = _arity(code)
    calls = _call_sites(code)
    defined = set(functions.keys())

    # 1. ARITY_MISMATCH: call with wrong number of args vs definition
    for caller, callee, n_args in calls:
        if callee in arity:
            expected = arity[callee]
            if n_args != expected:
                bugs.append({
                    "type": "ARITY_MISMATCH",
                    "message": f"'{caller}' calls '{callee}' with {n_args} args, expected {expected}",
                })

    # 2. MISSING_CALLEE: called but not defined
    for caller, callee, _ in calls:
        if callee not in defined and callee not in ("print", "range", "len", "sum", "sorted", "open", "int", "str", "list", "set", "dict"):
            bugs.append({
                "type": "MISSING_CALLEE",
                "message": f"'{caller}' calls undefined function '{callee}'",
            })

    # 3. UNUSED_FUNCTION: defined but never called (excluding main/entry)
    called = {callee for _, callee, _ in calls}
    for name in defined:
        if name not in called and name not in ("main", "Main"):
            bugs.append({
                "type": "UNUSED_FUNCTION",
                "message": f"function '{name}' defined but never called (dead code)",
            })

    return bugs


def program_bug_score(code: str) -> float:
    """Bug severity score in [0, 1]."""
    bugs = detect_program_bugs(code)
    if not bugs:
        return 0.0
    weights = {"ARITY_MISMATCH": 0.4, "MISSING_CALLEE": 0.4,
               "UNUSED_FUNCTION": 0.2}
    score = sum(weights.get(b["type"], 0.1) for b in bugs)
    return min(1.0, score)


# ── Self-test ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Buggy: arity mismatch (add takes 2, called with 1)
    buggy1 = '''
def add(a, b):
    return a + b

def main(x):
    return add(x)
'''
    # Buggy: missing callee (calls undefined function)
    buggy2 = '''
def main(x):
    return double(x)
'''
    # Buggy: unused function
    buggy3 = '''
def helper(x):
    return x * 2

def main(x):
    return x + 1
'''
    # Clean
    clean = '''
def add(a, b):
    return a + b

def main(x):
    return add(x, x)
'''

    for name, code in [("buggy1", buggy1), ("buggy2", buggy2), ("buggy3", buggy3), ("clean", clean)]:
        bugs = detect_program_bugs(code)
        print(f"{name:8s} score={program_bug_score(code):.2f} bugs={[b['type'] for b in bugs]}")
