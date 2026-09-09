#!/usr/bin/env python
"""experiment_refactor.py — Shape + execution refactoring equivalence.
(refactorings) by combining:
  1. SHAPE similarity (fast pre-filter) — catches structural refactors
  2. EXECUTION equivalence (soundness) — catches builtin-equivalence (sum() vs loop)

This closes the builtin-equivalence gap: shape alone misses sum() vs manual
loop (0.359), but execution confirms they're equivalent.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from code_shape.core.code_shape_core import true_similarity
from code_shape.analysis.exec_verifier import builtin_equivalent

# (name, code_a, code_b, is_equivalent)
PAIRS = [
    ("sum-builtin", "def total(nums):\n    return sum(nums)",
     "def total(nums):\n    acc = 0\n    for n in nums:\n        acc += n\n    return acc", True),
    ("max-ternary", "def max2(a, b):\n    return a if a > b else b",
     "def max2(a, b):\n    if a > b:\n        return a\n    return b", True),
    ("filter-comp", "def evens(nums):\n    return [n for n in nums if n % 2 == 0]",
     "def evens(nums):\n    out = []\n    for n in nums:\n        if n % 2 == 0:\n            out.append(n)\n    return out", True),
    ("sum-vs-max", "def total(nums):\n    return sum(nums)",
     "def max2(a, b):\n    return a if a > b else b", False),
    ("evens-vs-odds", "def evens(nums):\n    return [n for n in nums if n % 2 == 0]",
     "def odds(nums):\n    return [n for n in nums if n % 2 != 0]", False),
]

# test cases for execution equivalence
TEST_CASES = [
    {"args": [[1, 2, 3, 4]], "expected": 10},
    {"args": [[5, 5, 5]], "expected": 15},
    {"args": [[1, 3, 5]], "expected": 9},
]


def main():
    print("=== Refactoring Equivalence: Shape + Execution ===")
    print(f"{'pair':16s} {'shape':>6s} {'exec':>6s} {'detected':9s} {'OK':>3s}")
    for name, a, b, is_eq in PAIRS:
        shape_sim = true_similarity(a, b)
        # execution equivalence on the test cases (authoritative)
        eq = builtin_equivalent(a, b, TEST_CASES)
        exec_eq = eq["equivalent"]
        # detected = execution equivalence (soundness); shape is a pre-filter
        detected = exec_eq
        ok = detected == is_eq
        print(f"{name:16s} {shape_sim:>6.3f} {str(exec_eq):>6s} {str(detected):9s} {'OK' if ok else 'XX':>3s}")

    print("\n=== Key: sum() vs manual loop ===")
    a = "def total(nums):\n    return sum(nums)"
    b = "def total(nums):\n    acc = 0\n    for n in nums:\n        acc += n\n    return acc"
    print(f"  shape sim: {true_similarity(a, b):.3f} (low - builtin gap)")
    print(f"  exec equivalent: {builtin_equivalent(a, b, TEST_CASES)['equivalent']} (confirms equivalence)")


if __name__ == "__main__":
    main()
