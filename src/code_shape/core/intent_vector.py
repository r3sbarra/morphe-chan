#!/usr/bin/env python
"""intent_vector.py — Intent-based primitive decomposition of code into a
geometric vector shape.

Instead of tokenizing syntax (bag-of-tokens) or normalizing structure, we
decompose code into PRIMITIVE INTENTS — atomic behaviors the code performs —
and build a vector where each dimension is a primitive. The vector 'shape'
encodes what the code DOES (its intent), not its syntax.

Primitive taxonomy (behavioral intents):
  READ      - read/access data (input, param, load, get)
  WRITE     - write/emit data (return, print, save, append, set)
  COMPARE   - comparison / branching (if, ==, <, >, max, min)
  ITERATE   - loops / repetition (for, while, recursion)
  TRANSFORM - arithmetic / string / data transformation (+, -, *, /, concat)
  AGGREGATE - reduce / accumulate (sum, count, total, reduce)
  FILTER    - select subset (filter, where, comprehension with if)
  SORT      - ordering (sort, sorted, order)
  SEARCH    - lookup / find (find, index, search, contains, in)
  STATE     - state / mutation (assign, +=, store, update, class attr)

The vector is the normalized count of each primitive. Two code snippets with
the same intent distribution have similar vector shapes even if their syntax
differs completely.

Dependency-free (stdlib only).
"""
import re
from typing import Dict, List, Tuple

# Primitive detection rules: keyword/pattern -> primitive dimension.
# Ordered so more specific patterns match first. Patterns are matched against
# normalized text; call-like patterns (with parens) are more precise than bare
# keywords to avoid counting variable names as intents.
PRIMITIVE_RULES: List[Tuple[str, List[str]]] = [
    ("SORT",     ["sort(", "sorted(", "order_by", "argsort", "heapq"]),
    ("SEARCH",   ["find(", ".index(", "search(", "contains", "lookup", "locate", " in ", "match"]),
    ("FILTER",   ["filter(", "where", "select", " if "]),
    ("AGGREGATE",["sum(", "count(", "total", "reduce(", "accumulate", "len("]),
    ("ITERATE",  ["for ", "while ", "recurs", "loop", "each", "repeat", "map("]),
    ("COMPARE",  ["if ", "==", "!=", " < ", " > ", "max(", "min(", "compare", " is "]),
    ("TRANSFORM",[" + ", " - ", " * ", " / ", " % ", "concat", "join(", "format", "str(", "int("]),
    ("READ",     ["read(", "load(", "get(", "input(", "open(", "fetch", "receive", "def "]),
    ("WRITE",    ["return", "print(", "write(", "save(", "append(", "emit", "send(", "output"]),
    ("STATE",    ["+=", "-=", "store", "update", "set(", "assign", "mutate"]),
]

# Canonical dimension order for the vector.
PRIMITIVES = ["READ", "WRITE", "COMPARE", "ITERATE", "TRANSFORM",
              "AGGREGATE", "FILTER", "SORT", "SEARCH", "STATE"]


def _normalize(code: str) -> str:
    return re.sub(r"\s+", " ", code).lower()


def decompose_primitives(code: str) -> Dict[str, int]:
    """Count primitive intents in a code snippet. Returns {primitive: count}."""
    text = _normalize(code)
    counts: Dict[str, int] = {p: 0 for p in PRIMITIVES}
    for prim, patterns in PRIMITIVE_RULES:
        for pat in patterns:
            counts[prim] += text.count(pat)
    return counts


def intent_vector(code: str) -> Dict[str, float]:
    """Normalized intent vector (each dimension in [0,1], sums to 1)."""
    counts = decompose_primitives(code)
    total = sum(counts.values())
    if total == 0:
        return {p: 0.0 for p in PRIMITIVES}
    return {p: round(counts[p] / total, 4) for p, c in counts.items()}


def cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    import math
    keys = set(a) | set(b)
    dot = sum(a.get(k, 0) * b.get(k, 0) for k in keys)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def intent_similarity(code_a: str, code_b: str) -> float:
    """Cosine similarity between two intent vectors."""
    return cosine(intent_vector(code_a), intent_vector(code_b))


def shape(code: str) -> str:
    """Human-readable 'shape' = dominant primitives, e.g. 'READ>TRANSFORM>WRITE'."""
    vec = decompose_primitives(code)
    ranked = sorted(vec.items(), key=lambda kv: -kv[1])
    top = [p for p, c in ranked if c > 0][:4]
    return ">".join(top) if top else "EMPTY"


# ── Self-test / demo ────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Different syntax, SAME intent (read -> transform -> write)
    a = "def add(a, b):\n    return a + b"
    b = "def sum_two(x, y):\n    result = x + y\n    return result"
    # Different intent (iterate + filter + aggregate)
    c = "def count_evens(nums):\n    total = 0\n    for n in nums:\n        if n % 2 == 0:\n            total += 1\n    return total"

    print("=== Intent vectors ===")
    for name, code in [("add", a), ("sum_two", b), ("count_evens", c)]:
        print(f"{name:12s} shape={shape(code):30s} vec={intent_vector(code)}")

    print("\n=== Intent similarity ===")
    print(f"add vs sum_two (same intent):   {intent_similarity(a, b):.3f}")
    print(f"add vs count_evens (different): {intent_similarity(a, c):.3f}")
    print(f"sum_two vs count_evens:         {intent_similarity(b, c):.3f}")
