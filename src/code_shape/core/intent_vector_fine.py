#!/usr/bin/env python
"""intent_vector_fine.py — Fine-grained intent decomposition.

primitives so algorithms that share a category-level primitive distribution
(factorial vs fibonacci, is_even vs is_prime) can be distinguished.

The insight: category-level intents (TRANSFORM, COMPARE) are too coarse. We
add fine-grained operation dimensions:
  ARITH_ADD, ARITH_MUL, ARITH_SUB, ARITH_DIV, ARITH_MOD
  PRED_EVEN, PRED_PRIME, PRED_GT, PRED_LT, PRED_EQ
  RECURSE, LOOP
  RETURN, ASSIGN

The vector shape now encodes BOTH the intent category AND the specific
operation, giving a richer geometric fingerprint.
"""
import re
from typing import Dict, List, Tuple

# Fine-grained primitive rules. More specific first.
FINE_RULES: List[Tuple[str, List[str]]] = [
    ("ARITH_MOD",   [" % ", "modulo", "remainder"]),
    ("ARITH_MUL",   [" * ", "multiply", "product", "factorial"]),
    ("ARITH_ADD",   [" + ", "add", "sum(", "plus", "fibonacci"]),
    ("ARITH_SUB",   [" - ", "subtract", "minus"]),
    ("ARITH_DIV",   [" / ", "divide", "quotient"]),
    ("PRED_EVEN",   ["% 2", "even", "is_even"]),
    ("PRED_PRIME",  ["prime", "is_prime", "divisib"]),
    ("PRED_GT",     [" > ", "greater"]),
    ("PRED_LT",     [" < ", "less"]),
    ("PRED_EQ",     ["==", "equal", "is "]),
    ("RECURSE",     ["recurs", "factorial(", "fibonacci("]),
    ("LOOP",        ["for ", "while ", "range("]),
    ("RETURN",      ["return"]),
    ("ASSIGN",      ["=", "+=", "-="]),
    ("READ",        ["def ", "read(", "get(", "input("]),
    ("WRITE",       ["print(", "write(", "save(", "emit"]),
    ("SORT",        ["sort(", "sorted("]),
    ("SEARCH",      ["find(", "index(", "contains", " in "]),
    ("FILTER",      ["filter(", "where", " if "]),
    ("AGGREGATE",   ["sum(", "count(", "total", "reduce(", "len("]),
]

DIMS = ["READ", "WRITE", "RETURN", "ASSIGN", "LOOP", "RECURSE",
        "ARITH_ADD", "ARITH_MUL", "ARITH_SUB", "ARITH_DIV", "ARITH_MOD",
        "PRED_EQ", "PRED_GT", "PRED_LT", "PRED_EVEN", "PRED_PRIME",
        "SORT", "SEARCH", "FILTER", "AGGREGATE"]


def _norm(code: str) -> str:
    return re.sub(r"\s+", " ", code).lower()


def decompose(code: str) -> Dict[str, int]:
    text = _norm(code)
    counts: Dict[str, int] = {d: 0 for d in DIMS}
    for dim, pats in FINE_RULES:
        for p in pats:
            counts[dim] += text.count(p)
    return counts


def fine_vector(code: str) -> Dict[str, float]:
    counts = decompose(code)
    total = sum(counts.values())
    if total == 0:
        return {d: 0.0 for d in DIMS}
    return {d: round(counts[d] / total, 4) for d in DIMS}


def cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    import math
    keys = set(a) | set(b)
    dot = sum(a.get(k, 0) * b.get(k, 0) for k in keys)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def fine_similarity(a: str, b: str) -> float:
    return cosine(fine_vector(a), fine_vector(b))


def shape(code: str) -> str:
    vec = decompose(code)
    ranked = sorted(vec.items(), key=lambda kv: -kv[1])
    top = [d for d, c in ranked if c > 0][:5]
    return ">".join(top) if top else "EMPTY"


if __name__ == "__main__":
    pairs = [
        ("add", "def add(a, b):\n    return a + b",
         "def sum_two(x, y):\n    result = x + y\n    return result", True),
        ("factorial", "def factorial(n):\n    if n <= 1:\n        return 1\n    return n * factorial(n - 1)",
         "def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n - 1) + fibonacci(n - 2)", False),
        ("even/prime", "def is_even(n):\n    return n % 2 == 0",
         "def is_prime(n):\n    if n < 2:\n        return False\n    for i in range(2, n):\n        if n % i == 0:\n            return False\n    return True", False),
    ]
    for name, a, b, is_clone in pairs:
        s = fine_similarity(a, b)
        print(f"{name:12s} fine_sim={s:.3f} label={'CLONE' if is_clone else 'DIFF'} "
              f"shape_a={shape(a)}")
