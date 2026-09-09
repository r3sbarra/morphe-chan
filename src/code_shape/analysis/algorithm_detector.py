#!/usr/bin/env python
"""algorithm_detector.py — Detect algorithms from shape sequence vectors.
from their SHAPE SEQUENCE signatures.

Each algorithm has a characteristic shape sequence (the primitive vector):
  - binary_search: ASSIGN>BRANCH>ARITH_ADD>ARITH_SUB (halving)
  - linear_search: LOOP>BRANCH>COMPARE_EQ
  - bubble_sort:   LOOP>LOOP (nested)
  - merge_sort:    RECURSE>COMPARE_LE (halving recursion)
  - quick_sort:    BRANCH>LOOP>SEARCH (partition)
  - fibonacci:     RECURSE>ARITH_ADD
  - factorial:     RECURSE>ARITH_MUL
  - two_sum:       SEARCH>LOOP>BRANCH (hash map)

The detector matches a code snippet's shape sequence against known algorithm
signatures, scoring by primitive overlap + distinguishing features.

Dependency-free (stdlib only).
"""
import re
from typing import Dict, List

from code_shape.core.code_shape_core import shape as get_shape, recursive_shape
from code_shape.core.structural_shape import structural_signature

# ── Algorithm shape signatures ──────────────────────────────────────────────
# Each: (name, key_primitives, distinguishing_features)
ALGORITHMS = [
    ("binary_search", ["LOOP", "BRANCH", "ARITH_ADD", "ARITH_SUB"],
     {"halving": r"//\s*2|>>\s*1|\(low\s*\+\s*high\)\s*//\s*2"}),
    ("linear_search", ["LOOP", "BRANCH", "COMPARE_EQ"],
     {"linear": r"for\s+\w+\s+in\s+range\s*\(\s*len"}),
    ("bubble_sort", ["LOOP", "LOOP", "BRANCH", "COMPARE_GT"],
     {"nested_loop": r"for\s+.*:\s*\n\s*for\s+"}),
    ("merge_sort", ["RECURSE", "BRANCH", "COMPARE_LE"],
     {"halving": r"len\s*\([^)]*\)\s*//\s*2", "merge": r"merge\s*\("}),
    ("quick_sort", ["BRANCH", "LOOP", "SEARCH", "RECURSE"],
     {"pivot": r"pivot", "partition": r"\[x for x in"}),
    ("fibonacci", ["RECURSE", "ARITH_ADD", "BRANCH"],
     {"fib": r"fibonacci\s*\(\s*n\s*-\s*1\s*\)\s*\+\s*fibonacci"}),
    ("factorial", ["RECURSE", "ARITH_MUL", "BRANCH"],
     {"fact": r"n\s*\*\s*factorial"}),
    ("two_sum", ["SEARCH", "LOOP", "BRANCH", "ASSIGN"],
     {"hashmap": r"seen\s*=|diff\s*=\s*target"}),
    ("binary_tree_traversal", ["RECURSE", "BRANCH", "SEARCH"],
     {"tree": r"\.left\b|\.right\b|node\.val|root\.left|root\.right"}),
    ("dijkstra", ["LOOP", "BRANCH", "ASSIGN", "SEARCH"],
     {"dist": r"dist\s*=|distance\s*=|heapq"}),
    ("knapsack", ["LOOP", "LOOP", "BRANCH", "ASSIGN"],
     {"dp": r"dp\s*=|capacity|weight"}),
    ("lru_cache", ["BRANCH", "ASSIGN", "SEARCH"],
     {"cache": r"cache\s*=|lru|OrderedDict"}),
]


def detect_algorithm(code: str, lang: str = "python") -> List[Dict]:
    """Detect algorithms in a code snippet from its shape sequence.

    Requires at least one DISTINGUISHING FEATURE to hit (shape alone is not
    enough) — this prevents framework methods that coincidentally match the
    shape from false-positiving.
    """
    shape_str = get_shape(code, lang)
    prims = set(shape_str.split(">"))
    results = []
    for name, key_prims, features in ALGORITHMS:
        # score by key primitive overlap
        overlap = len(set(key_prims) & prims) / len(key_prims)
        # count distinguishing feature hits
        feature_hits = 0
        for feat, pat in features.items():
            if re.search(pat, code, re.IGNORECASE):
                feature_hits += 1
        # REQUIRE at least one feature hit (shape alone is not enough)
        if feature_hits == 0:
            continue
        score = 0.5 * overlap + 0.5 * min(1.0, feature_hits / max(1, len(features)))
        if score >= 0.5:
            results.append({
                "algorithm": name,
                "score": round(score, 2),
                "shape": shape_str,
                "features_hit": feature_hits,
            })
    results.sort(key=lambda x: -x["score"])
    return results


def algorithm_signature(code: str, lang: str = "python") -> str:
    """Human-readable algorithm signature."""
    det = detect_algorithm(code, lang)
    if not det:
        return "UNKNOWN"
    return f"{det[0]['algorithm']} ({det[0]['score']})"


# ── Self-test ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    algorithms = {
        "binary_search": "def binary_search(arr, target):\n    low, high = 0, len(arr) - 1\n    while low <= high:\n        mid = (low + high) // 2\n        if arr[mid] == target:\n            return mid\n        elif arr[mid] < target:\n            low = mid + 1\n        else:\n            high = mid - 1\n    return -1",
        "bubble_sort": "def bubble_sort(arr):\n    n = len(arr)\n    for i in range(n):\n        for j in range(0, n - i - 1):\n            if arr[j] > arr[j + 1]:\n                arr[j], arr[j + 1] = arr[j + 1], arr[j]\n    return arr",
        "merge_sort": "def merge_sort(arr):\n    if len(arr) <= 1:\n        return arr\n    mid = len(arr) // 2\n    left = merge_sort(arr[:mid])\n    right = merge_sort(arr[mid:])\n    return merge(left, right)",
        "fibonacci": "def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n - 1) + fibonacci(n - 2)",
        "factorial": "def factorial(n):\n    if n <= 1:\n        return 1\n    return n * factorial(n - 1)",
        "two_sum": "def two_sum(nums, target):\n    seen = {}\n    for i, num in enumerate(nums):\n        diff = target - num\n        if diff in seen:\n            return [seen[diff], i]\n        seen[num] = i\n    return []",
        "simple_add": "def add(a, b):\n    return a + b",
    }
    print("=== Algorithm detection from shape sequences ===")
    for name, code in algorithms.items():
        det = detect_algorithm(code)
        top = det[0]["algorithm"] if det else "UNKNOWN"
        print(f"{name:16s} -> {top} (score={det[0]['score'] if det else 0})")
