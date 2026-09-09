#!/usr/bin/env python
"""agnostic_shape.py — CODE-AGNOSTIC shape model.

Key idea: primitives are detected by SEMANTIC ROLE, not language syntax.
Language-specific keywords are mapped to a common primitive vocabulary:

  LOOP      : for / while / foreach / for( / do / repeat
  BRANCH    : if / else / switch / case / ternary (?:)
  RECURSE   : function calling itself (name appears in body)
  ARITH     : + - * / % (operators are language-agnostic)
  COMPARE   : == != < > <= >= (operators are language-agnostic)
  ASSIGN    : = += -= *= (operators are language-agnostic)
  RETURN    : return / return; / => (arrow)
  CALL      : function/method call (identifier followed by paren)
  READ      : input / read / get / param / open
  WRITE     : print / console.log / System.out / write / emit
  AGGREGATE : sum / reduce / accumulate / total
  FILTER    : filter / where / select / comprehension
  SORT      : sort / sorted / orderBy
  SEARCH    : find / indexOf / search / contains / includes
  STATE     : mutation of a variable (assign + reuse)

The vector shape is the normalized distribution of these primitives. Two
functions in DIFFERENT languages with the same behavior have similar shapes.

Dependency-free (stdlib only).
"""
import math
import re
from typing import Dict, List, Tuple

# Language-agnostic primitive rules. Each maps to a common primitive.
# Patterns are matched against normalized text (lowercased, whitespace-collapsed).
AGNOSTIC_RULES: List[Tuple[str, List[str]]] = [
    # loops — language-agnostic keywords
    ("LOOP",     ["for ", "while ", "foreach", "for(", "do ", "repeat", " for("]),
    # branches
    ("BRANCH",   ["if ", "else", "switch", "case ", "? :", " ? ", "elif", "else if"]),
    # recursion — function name appears in its own body (detected separately)
    ("RECURSE",  ["recurs", "factorial(", "fibonacci("]),
    # arithmetic operators (language-agnostic)
    ("ARITH_ADD",[" + ", "++", "+= "]),
    ("ARITH_SUB",[" - ", "--", "-= "]),
    ("ARITH_MUL",[" * ", "*="]),
    ("ARITH_DIV",[" / ", "/="]),
    ("ARITH_MOD",[" % ", "%="]),
    # comparison operators (language-agnostic)
    ("COMPARE_EQ",["==", "===", "equal"]),
    ("COMPARE_NE",["!=", "!==", "not equal"]),
    ("COMPARE_GT",[" > ", "greater"]),
    ("COMPARE_LT",[" < ", "less"]),
    ("COMPARE_GE",[" >= ", ">="]),
    ("COMPARE_LE",[" <= ", "<="]),
    # assignment
    ("ASSIGN",   ["=", "+=", "-=", "*=", "/="]),
    # return / output
    ("RETURN",   ["return", "=>", "yield"]),
    # I/O
    ("READ",     ["read", "get", "input", "open", "param", "receive", "scanf", "cin"]),
    ("WRITE",    ["print", "console.log", "system.out", "write", "emit", "send", "printf", "cout"]),
    # aggregate / filter / sort / search
    ("AGGREGATE",["sum", "reduce", "accumulate", "total", "count"]),
    ("FILTER",   ["filter", "where", "select", "comprehension"]),
    ("SORT",     ["sort", "sorted", "orderby", "order_by"]),
    ("SEARCH",   ["find", "indexof", "search", "contains", "includes", "locate"]),
    # state mutation (assign + reuse)
    ("STATE",    ["+=", "-=", "append", "push", "add", "set", "mutate"]),
]

# Language-agnostic dimension order.
DIMS = ["LOOP", "BRANCH", "RECURSE", "ARITH_ADD", "ARITH_SUB", "ARITH_MUL",
        "ARITH_DIV", "ARITH_MOD", "COMPARE_EQ", "COMPARE_NE", "COMPARE_GT",
        "COMPARE_LT", "COMPARE_GE", "COMPARE_LE", "ASSIGN", "RETURN",
        "READ", "WRITE", "AGGREGATE", "FILTER", "SORT", "SEARCH", "STATE"]


def _norm(code: str) -> str:
    return re.sub(r"\s+", " ", code).lower()


def _detect_recursion(code: str) -> bool:
    """Detect recursion: a function name that appears in its own body."""
    m = re.search(r"(?:def|function|public\s+\w+\s+\w+|int|void|var)\s+(\w+)\s*\(", code)
    if not m:
        return False
    name = m.group(1)
    # count occurrences of the name in the body (after the def line)
    body = code[code.find(m.group(0)) + len(m.group(0)):]
    return body.count(name) >= 1


def decompose(code: str) -> Dict[str, int]:
    """Extract code-agnostic primitives. Returns {primitive: count}."""
    text = _norm(code)
    counts: Dict[str, int] = {d: 0 for d in DIMS}
    for dim, pats in AGNOSTIC_RULES:
        for p in pats:
            counts[dim] += text.count(p)
    if _detect_recursion(code):
        counts["RECURSE"] += 1
    return counts


def agnostic_vector(code: str) -> Dict[str, float]:
    """Normalized code-agnostic shape vector (unit vector)."""
    counts = decompose(code)
    norm = math.sqrt(sum(v * v for v in counts.values()))
    if norm == 0:
        return {d: 0.0 for d in DIMS}
    return {d: round(counts[d] / norm, 4) for d in DIMS}


def cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    keys = set(a) | set(b)
    dot = sum(a.get(k, 0) * b.get(k, 0) for k in keys)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def agnostic_similarity(code_a: str, code_b: str) -> float:
    """Cosine similarity between two code-agnostic shape vectors, minus a
    polarity-conflict penalty (opposite operations are not clones)."""
    base = cosine(agnostic_vector(code_a), agnostic_vector(code_b))
    penalty = _polarity_penalty(code_a, code_b)
    return max(0.0, base - penalty)


# Opposite-operation pairs (semantic opposites within the same category).
_POLARITY_OPPOSITES = [
    ("ARITH_ADD", "ARITH_SUB"),
    ("ARITH_MUL", "ARITH_DIV"),
    ("COMPARE_GT", "COMPARE_LT"),
    ("COMPARE_GE", "COMPARE_LE"),
    ("COMPARE_EQ", "COMPARE_NE"),
]


def _polarity_penalty(code_a: str, code_b: str) -> float:
    """Penalty in [0, 0.5] if the two snippets use opposite operations."""
    ha = decompose(code_a)
    hb = decompose(code_b)
    penalty = 0.0
    for op_a, op_b in _POLARITY_OPPOSITES:
        if ha.get(op_a, 0) > 0 and hb.get(op_b, 0) > 0:
            penalty += 0.35
        if ha.get(op_b, 0) > 0 and hb.get(op_a, 0) > 0:
            penalty += 0.35
    return min(0.5, penalty)


def shape(code: str) -> str:
    """Human-readable shape = dominant primitives."""
    vec = decompose(code)
    ranked = sorted(vec.items(), key=lambda kv: -kv[1])
    top = [d for d, c in ranked if c > 0][:5]
    return ">".join(top) if top else "EMPTY"


# ── Self-test: cross-language equivalence ───────────────────────────────────
if __name__ == "__main__":
    # Same behavior (sum a list) in 3 languages
    py_sum = "def sum_list(nums):\n    total = 0\n    for n in nums:\n        total += n\n    return total"
    js_sum = "function sumList(nums) {\n    let total = 0;\n    for (let n of nums) {\n        total += n;\n    }\n    return total;\n}"
    java_sum = "int sumList(int[] nums) {\n    int total = 0;\n    for (int n : nums) {\n        total += n;\n    }\n    return total;\n}"

    # Different behavior (filter evens) in Python
    py_evens = "def evens(nums):\n    return [n for n in nums if n % 2 == 0]"

    print("=== Code-agnostic shapes (cross-language) ===")
    for name, code in [("py_sum", py_sum), ("js_sum", js_sum), ("java_sum", java_sum), ("py_evens", py_evens)]:
        print(f"{name:9s} shape={shape(code)}")

    print("\n=== Cross-language similarity ===")
    print(f"py_sum vs js_sum   (same, diff lang): {agnostic_similarity(py_sum, js_sum):.3f}")
    print(f"py_sum vs java_sum (same, diff lang): {agnostic_similarity(py_sum, java_sum):.3f}")
    print(f"js_sum vs java_sum (same, diff lang): {agnostic_similarity(js_sum, java_sum):.3f}")
    print(f"py_sum vs py_evens (different):       {agnostic_similarity(py_sum, py_evens):.3f}")
