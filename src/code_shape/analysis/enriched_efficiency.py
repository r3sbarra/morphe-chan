#!/usr/bin/env python
"""enriched_efficiency.py — Derive efficiency from the enriched shape.
function's efficiency, combining:

  ALGORITHM  — known algorithm complexity (binary_search=O(log n), merge_sort=O(n log n))
  DATA       — data structure complexity (nested data = more work)
  CTRL       — control flow complexity (cyclomatic, nesting)
  RES        — resource usage (I/O, network, compute, concurrency)
  EFF        — the existing efficiency dims (loops, threading)

The enriched efficiency is a weighted combination of these signals, giving a
more accurate complexity estimate than loop-count alone.

Dependency-free (stdlib only).
"""
import re
from typing import Dict

from code_shape.analysis.algorithm_detector import detect_algorithm
from code_shape.core.new_shape_dims import new_shape_dims
from code_shape.analysis.efficiency_shape import efficiency_summary

# ── Known algorithm complexities ────────────────────────────────────────────
ALGORITHM_COMPLEXITY = {
    "binary_search": "O(log n)", "linear_search": "O(n)",
    "bubble_sort": "O(n^2)", "merge_sort": "O(n log n)",
    "quick_sort": "O(n log n)", "fibonacci": "O(2^n)",
    "factorial": "O(n)", "two_sum": "O(n)",
    "binary_tree_traversal": "O(n)", "dijkstra": "O((V+E) log V)",
    "knapsack": "O(n*W)", "lru_cache": "O(1)",
}

# ── Complexity class ordering ────────────────────────────────────────────────
COMPLEXITY_ORDER = ["O(1)", "O(log n)", "O(n)", "O(n log n)", "O(n^2)", "O(n^3)", "O(2^n)"]


def _complexity_rank(cx: str) -> int:
    """Rank a complexity class (higher = worse)."""
    for i, c in enumerate(COMPLEXITY_ORDER):
        if cx == c:
            return i
    return len(COMPLEXITY_ORDER)  # unknown = worst


def enriched_efficiency(code: str, lang: str = "python") -> Dict:
    """Derive efficiency from the enriched shape."""
    # 1. algorithm detection (known complexity)
    algs = detect_algorithm(code, lang)
    alg_cx = None
    if algs:
        alg = algs[0]["algorithm"]
        if alg in ALGORITHM_COMPLEXITY:
            alg_cx = ALGORITHM_COMPLEXITY[alg]

    # 2. new shape dims (data, ctrl, res)
    dims = new_shape_dims(code)

    # 3. existing efficiency
    eff = efficiency_summary(code)

    # 4. derive efficiency
    if alg_cx:
        # algorithm known -> use its complexity
        complexity = alg_cx
        method = "algorithm"
    else:
        # derive from shape signals
        base = eff["complexity"]
        # data structure complexity boosts
        if dims.get("DATA:NESTED", 0):
            base = _bump(base)
        # nested LOOPS boost (not nested ifs — branching is O(1))
        if eff["nesting"] >= 2:
            base = _bump(base)
        # resource compute boosts
        if dims.get("RES:COMPUTE", 0):
            base = _bump(base)
        complexity = base
        method = "shape"

    return {
        "complexity": complexity,
        "method": method,
        "algorithm": algs[0]["algorithm"] if algs else None,
        "loops": eff["loops"],
        "nesting": eff["nesting"],
        "data_nested": bool(dims.get("DATA:NESTED", 0)),
        "deep_nesting": bool(dims.get("CTRL:DEEP_NESTING", 0)),
        "resource_compute": bool(dims.get("RES:COMPUTE", 0)),
        "rank": _complexity_rank(complexity),
    }


def _bump(cx: str) -> str:
    """Bump a complexity class up one level (worse)."""
    rank = _complexity_rank(cx)
    if rank < len(COMPLEXITY_ORDER) - 1:
        return COMPLEXITY_ORDER[rank + 1]
    return cx


# ── Self-test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    cases = {
        "binary_search": "def binary_search(arr, target):\n    low, high = 0, len(arr) - 1\n    while low <= high:\n        mid = (low + high) // 2\n        if arr[mid] == target:\n            return mid\n        elif arr[mid] < target:\n            low = mid + 1\n        else:\n            high = mid - 1\n    return -1",
        "merge_sort": "def merge_sort(arr):\n    if len(arr) <= 1:\n        return arr\n    mid = len(arr) // 2\n    left = merge_sort(arr[:mid])\n    right = merge_sort(arr[mid:])\n    return merge(left, right)",
        "nested_data": "def process(data):\n    result = []\n    for item in data:\n        for sub in item['items']:\n            result.append(sub)\n    return result",
        "simple": "def add(a, b):\n    return a + b",
        "deep_nested": "def classify(x):\n    if x > 0:\n        if x > 10:\n            if x > 100:\n                return 'huge'\n            return 'big'\n        return 'small'\n    return 'neg'",
    }
    print("=== Enriched efficiency (from shape) ===")
    for name, code in cases.items():
        r = enriched_efficiency(code)
        print(f"{name:14s} complexity={r['complexity']:10s} method={r['method']} alg={r['algorithm']}")
