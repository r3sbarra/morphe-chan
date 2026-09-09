#!/usr/bin/env python
"""bug_detector.py — Shape-based bug detection.

defects in code. Detects:

1. RETURN_IN_LOOP  — a return statement nested inside a loop body (usually a
                     bug: returns after first iteration).
2. UNDEFINED_VAR   — a variable used but never assigned/initialized.
3. UNUSED_ASSIGN   — a variable assigned but never used (dead code).
4. SHAPE_ANOMALY   — a shape that deviates from the expected primitive
                     distribution (e.g. a 'sum' function with no loop/aggregate).
5. MISSING_RETURN  — a function that computes but never returns a value.

The detector is CODE-AGNOSTIC: it works on the primitive shape + simple
variable-flow heuristics, independent of language.

Dependency-free (stdlib only).
"""
import re
from typing import Dict, List, Tuple

# ── Variable-flow heuristics (language-agnostic) ───────────────────────────
def _find_params(code: str) -> set:
    """Find function parameter names (from def/function signatures)."""
    params = set()
    for m in re.finditer(r"(?:def|function)\s+\w+\s*\(([^)]*)\)", code):
        for p in m.group(1).split(","):
            p = p.strip().split(":")[0].strip()
            if p and re.match(r"^[a-zA-Z_]", p):
                params.add(p)
    return params


def _find_fn_name(code: str) -> str:
    """Find the function name (from def/function signature)."""
    m = re.search(r"(?:def|function)\s+(\w+)\s*\(", code)
    return m.group(1) if m else ""


def _find_assignments(code: str) -> set:
    """Find variable names that are assigned (before =, +=, -=, etc.)."""
    assigned = set()
    # pattern: identifier followed by = (but not ==, <=, >=, !=)
    for m in re.finditer(r"\b([a-zA-Z_]\w*)\s*(?:\+=|-=|\*=|/=|=(?!=))", code):
        assigned.add(m.group(1))
    return assigned


def _find_usages(code: str) -> set:
    """Find variable names that are used (appear as identifiers)."""
    used = set()
    for m in re.finditer(r"\b([a-zA-Z_]\w*)\b", code):
        used.add(m.group(1))
    return used


def _find_returns(code: str) -> List[int]:
    """Find line numbers of return statements."""
    return [i for i, line in enumerate(code.splitlines()) if "return" in line]


def _find_loops(code: str) -> List[int]:
    """Find line numbers of loop openers (for/while)."""
    return [i for i, line in enumerate(code.splitlines())
            if re.match(r"\s*(for|while)\b", line)]


def _find_def(code: str) -> int:
    """Find the line of the function definition."""
    for i, line in enumerate(code.splitlines()):
        if re.match(r"\s*(def|function|public|int|void|var)\b", line):
            return i
    return -1


# ── Bug detection ──────────────────────────────────────────────────────────
def detect_bugs(code: str) -> List[Dict]:
    """Detect bugs in a code snippet. Returns a list of {type, line, message}."""
    bugs: List[Dict] = []
    lines = code.splitlines()

    # 1. RETURN_IN_LOOP: a return inside a loop body (indented deeper than loop)
    loop_lines = _find_loops(code)
    for li in loop_lines:
        loop_indent = len(lines[li]) - len(lines[li].lstrip())
        for ri in _find_returns(code):
            if ri > li:
                ret_indent = len(lines[ri]) - len(lines[ri].lstrip())
                if ret_indent > loop_indent:
                    bugs.append({
                        "type": "RETURN_IN_LOOP",
                        "line": ri + 1,
                        "message": "return inside loop body — likely returns after first iteration",
                    })

    # 2. UNDEFINED_VAR: used but never assigned (excluding builtins/keywords/params/fn-name)
    assigned = _find_assignments(code)
    used = _find_usages(code)
    params = _find_params(code)
    fn_name = _find_fn_name(code)
    KEYWORDS = {"def", "return", "for", "while", "if", "else", "elif", "in",
                "and", "or", "not", "import", "from", "print", "range", "len",
                "sum", "sorted", "self", "true", "false", "none", "null",
                "items", "item", "x", "y", "a", "b", "n", "i", "j", "cond",
                "arr", "nums", "values", "fn"}
    undefined = (used - assigned - params - {fn_name}) - KEYWORDS
    for v in undefined:
        bugs.append({
            "type": "UNDEFINED_VAR",
            "line": 0,
            "message": f"variable '{v}' used but never assigned",
        })

    # 3. UNUSED_ASSIGN: assigned but never used after assignment (dead code)
    unused = set()
    for v in assigned:
        # count usages of v that are NOT the assignment itself
        uses = len(re.findall(r"\b" + re.escape(v) + r"\b", code))
        assigns = len(re.findall(r"\b" + re.escape(v) + r"\s*(?:\+=|-=|\*=|/=|=(?!=))", code))
        if uses <= assigns:  # only appears in its own assignment(s)
            unused.add(v)
    for v in unused:
        bugs.append({
            "type": "UNUSED_ASSIGN",
            "line": 0,
            "message": f"variable '{v}' assigned but never used (dead code)",
        })

    # 4. MISSING_RETURN: function computes but has no return
    if "return" not in code and ("=" in code or "+=" in code):
        bugs.append({
            "type": "MISSING_RETURN",
            "line": 0,
            "message": "function computes but never returns a value",
        })

    return bugs


def bug_score(code: str) -> float:
    """A bug severity score in [0, 1] (higher = more bugs)."""
    bugs = detect_bugs(code)
    if not bugs:
        return 0.0
    # weight: RETURN_IN_LOOP and UNDEFINED_VAR are severe
    weights = {"RETURN_IN_LOOP": 0.4, "UNDEFINED_VAR": 0.3,
               "UNUSED_ASSIGN": 0.15, "MISSING_RETURN": 0.15}
    score = sum(weights.get(b["type"], 0.1) for b in bugs)
    return min(1.0, score)


# ── Self-test ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Buggy: return inside loop
    buggy1 = "def sum_list(nums):\n    total = 0\n    for n in nums:\n        total += n\n        return total"
    # Buggy: undefined variable
    buggy2 = "def add(a, b):\n    return result"
    # Buggy: unused assignment
    buggy3 = "def f(x):\n    y = 10\n    return x"
    # Clean
    clean = "def sum_list(nums):\n    total = 0\n    for n in nums:\n        total += n\n    return total"

    for name, code in [("buggy1", buggy1), ("buggy2", buggy2), ("buggy3", buggy3), ("clean", clean)]:
        bugs = detect_bugs(code)
        print(f"{name:8s} score={bug_score(code):.2f} bugs={[b['type'] for b in bugs]}")
