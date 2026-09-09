#!/usr/bin/env python
"""experiment_bug_detection.py — Validate the shape-based bug detector on a
labeled set of buggy vs clean code.
"""

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(TOOLS))
from code_shape.analysis.bug_detector import detect_bugs, bug_score

# (name, code, has_bug)
CASES = [
    # Buggy
    ("return-in-loop", "def sum_list(nums):\n    total = 0\n    for n in nums:\n        total += n\n        return total", True),
    ("undefined-var", "def add(a, b):\n    return result", True),
    ("unused-assign", "def f(x):\n    y = 10\n    return x", True),
    ("missing-return", "def compute(x):\n    total = x * 2", True),
    ("off-by-one", "def count_evens(nums):\n    count = 0\n    for n in nums:\n        if n % 2 == 0:\n            count += 1\n    return count + 1", True),
    # Clean
    ("clean-sum", "def sum_list(nums):\n    total = 0\n    for n in nums:\n        total += n\n    return total", False),
    ("clean-max", "def max2(a, b):\n    if a > b:\n        return a\n    return b", False),
    ("clean-fact", "def fact(n):\n    if n <= 1:\n        return 1\n    return n * fact(n - 1)", False),
    ("clean-filter", "def evens(nums):\n    return [n for n in nums if n % 2 == 0]", False),
]


def main():
    print("=== Shape-Based Bug Detection Validation ===")
    print(f"{'case':16s} {'score':>6s} {'has_bug':8s} {'detected':9s} {'OK':>3s}")
    tp = fp = fn = tn = 0
    for name, code, has_bug in CASES:
        score = bug_score(code)
        detected = score > 0
        ok = detected == has_bug
        if detected and has_bug: tp += 1
        elif detected and not has_bug: fp += 1
        elif not detected and has_bug: fn += 1
        else: tn += 1
        print(f"{name:16s} {score:>6.2f} {str(has_bug):8s} {str(detected):9s} {'OK' if ok else 'XX':>3s}")

    prec = tp / (tp + fp) if (tp + fp) else 0
    rec = tp / (tp + fn) if (tp + fn) else 0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0
    print(f"\nPrecision={prec:.2f} Recall={rec:.2f} F1={f1:.2f} ({tp}TP {fp}FP {fn}FN {tn}TN)")


if __name__ == "__main__":
    main()
