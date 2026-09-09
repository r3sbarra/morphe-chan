#!/usr/bin/env python
"""efficiency_v2.py — Algorithm-aware efficiency evaluation.
DETECTION to get correct complexity for known algorithms.

The loop-count estimator fails on:
  - binary_search: sees while+//2 -> O(n^2), but it's O(log n)
  - merge_sort: sees recursion -> O(n), but it's O(n log n)

The algorithm detector knows the correct complexity. When an algorithm is
detected, use its known complexity; otherwise fall back to the shape-based
estimate.

Dependency-free (stdlib only).
"""
import re
from typing import Dict

from code_shape.analysis.efficiency_shape import efficiency_summary, efficiency_vector
from code_shape.analysis.algorithm_detector import detect_algorithm

# ── Known algorithm complexities ────────────────────────────────────────────
ALGORITHM_COMPLEXITY = {
    "binary_search": "O(log n)",
    "linear_search": "O(n)",
    "bubble_sort": "O(n^2)",
    "merge_sort": "O(n log n)",
    "quick_sort": "O(n log n)",
    "fibonacci": "O(2^n)",
    "factorial": "O(n)",
    "two_sum": "O(n)",
    "binary_tree_traversal": "O(n)",
    "dijkstra": "O((V+E) log V)",
    "knapsack": "O(n*W)",
    "lru_cache": "O(1)",
}


def algorithm_aware_complexity(code: str, lang: str = "python") -> Dict:
    """Get the complexity, using algorithm detection when possible."""
    # 1. try algorithm detection
    det = detect_algorithm(code, lang)
    if det:
        alg = det[0]["algorithm"]
        if alg in ALGORITHM_COMPLEXITY:
            return {
                "complexity": ALGORITHM_COMPLEXITY[alg],
                "algorithm": alg,
                "method": "algorithm_detection",
                "confidence": det[0]["score"],
            }
    # 2. fall back to shape-based estimate
    e = efficiency_summary(code)
    return {
        "complexity": e["complexity"],
        "algorithm": None,
        "method": "shape_estimate",
        "confidence": 0.5,
    }


def algorithm_aware_efficiency(code: str, lang: str = "python") -> Dict:
    """Full efficiency evaluation, algorithm-aware."""
    cx = algorithm_aware_complexity(code, lang)
    e = efficiency_summary(code)
    return {
        **cx,
        "loops": e["loops"],
        "nesting": e["nesting"],
        "threaded": e["threaded"],
        "repeated": e["repeated_computation"],
        "recursive": e["recursive"],
    }


# ── Self-test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    algorithms = {
        "binary_search": "def binary_search(arr, target):\n    low, high = 0, len(arr) - 1\n    while low <= high:\n        mid = (low + high) // 2\n        if arr[mid] == target:\n            return mid\n        elif arr[mid] < target:\n            low = mid + 1\n        else:\n            high = mid - 1\n    return -1",
        "merge_sort": "def merge_sort(arr):\n    if len(arr) <= 1:\n        return arr\n    mid = len(arr) // 2\n    left = merge_sort(arr[:mid])\n    right = merge_sort(arr[mid:])\n    return merge(left, right)",
        "bubble_sort": "def bubble_sort(arr):\n    n = len(arr)\n    for i in range(n):\n        for j in range(0, n - i - 1):\n            if arr[j] > arr[j + 1]:\n                arr[j], arr[j + 1] = arr[j + 1], arr[j]\n    return arr",
        "fibonacci": "def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n - 1) + fibonacci(n - 2)",
        "two_sum": "def two_sum(nums, target):\n    seen = {}\n    for i, num in enumerate(nums):\n        diff = target - num\n        if diff in seen:\n            return [seen[diff], i]\n        seen[num] = i\n    return []",
        "simple_add": "def add(a, b):\n    return a + b",
    }
    print("=== Algorithm-aware efficiency ===")
    for name, code in algorithms.items():
        r = algorithm_aware_efficiency(code)
        print(f"{name:16s} complexity={r['complexity']:10s} method={r['method']} alg={r['algorithm']}")
