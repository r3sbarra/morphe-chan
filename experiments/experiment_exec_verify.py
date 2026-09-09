#!/usr/bin/env python
"""experiment_exec_verify.py — Full pipeline: static shape analysis (pre-filter)
+ execution verification (soundness) for bug detection.
  1. Static shape analysis flags structural bugs (fast, high precision)
  2. Execution verification catches semantic bugs (off-by-one) that static misses
  3. Builtin-equivalence recognized via execution

This resolves the recall ceiling identified in earlier experiments.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from code_shape.analysis.bug_detector import bug_score, detect_bugs
from code_shape.analysis.exec_verifier import verify_semantic, builtin_equivalent

# (name, code, test_cases, has_bug)
CASES = [
    # Structural bugs (static catches)
    ("return-in-loop", "def sum_list(nums):\n    total = 0\n    for n in nums:\n        total += n\n        return total",
     [{"args": [[1, 2, 3]], "expected": 6}], True),
    ("undefined-var", "def add(a, b):\n    return result",
     [{"args": [1, 2], "expected": 3}], True),
    # Semantic bug (static MISSES, execution catches)
    ("off-by-one", "def count_evens(nums):\n    count = 0\n    for n in nums:\n        if n % 2 == 0:\n            count += 1\n    return count + 1",
     [{"args": [[1, 2, 3, 4]], "expected": 2}, {"args": [[2, 4]], "expected": 2}], True),
    # Clean (both pass)
    ("clean-sum", "def sum_list(nums):\n    total = 0\n    for n in nums:\n        total += n\n    return total",
     [{"args": [[1, 2, 3]], "expected": 6}, {"args": [[5, 5]], "expected": 10}], False),
    ("clean-count", "def count_evens(nums):\n    count = 0\n    for n in nums:\n        if n % 2 == 0:\n            count += 1\n    return count",
     [{"args": [[1, 2, 3, 4]], "expected": 2}, {"args": [[2, 4]], "expected": 2}], False),
]


def main():
    print("=== Full Pipeline: Static Shape + Execution Verification ===")
    print(f"{'case':16s} {'static':>7s} {'exec':>6s} {'detected':9s} {'OK':>3s}")
    tp = fp = fn = tn = 0
    for name, code, tests, has_bug in CASES:
        static = bug_score(code) > 0
        exec_res = verify_semantic(code, tests)
        exec_caught = not exec_res["correct"]
        # detected = static OR exec (either catches it)
        detected = static or exec_caught
        ok = detected == has_bug
        if detected and has_bug: tp += 1
        elif detected and not has_bug: fp += 1
        elif not detected and has_bug: fn += 1
        else: tn += 1
        print(f"{name:16s} {str(static):>7s} {str(exec_caught):>6s} {str(detected):9s} {'OK' if ok else 'XX':>3s}")

    prec = tp / (tp + fp) if (tp + fp) else 0
    rec = tp / (tp + fn) if (tp + fn) else 0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0
    print(f"\nFull pipeline: Precision={prec:.2f} Recall={rec:.2f} F1={f1:.2f} ({tp}TP {fp}FP {fn}FN {tn}TN)")
    print("(static alone missed off-by-one; execution catches it)")

    print("\n=== Builtin-equivalence via execution ===")
    sum_builtin = "def total(nums):\n    return sum(nums)"
    sum_manual = "def total(nums):\n    acc = 0\n    for n in nums:\n        acc += n\n    return acc"
    eq = builtin_equivalent(sum_builtin, sum_manual, [{"args": [[1, 2, 3]], "expected": 6}])
    print(f"sum() vs manual loop equivalent: {eq['equivalent']}")


if __name__ == "__main__":
    main()
