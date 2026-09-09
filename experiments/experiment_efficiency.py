#!/usr/bin/env python
"""experiment_efficiency.py — Validate efficiency shape model on labeled
efficiency-different code.

  - serial vs threaded (same intent, different efficiency)
  - O(1) vs O(n) vs O(n^2) (different complexity)
  - efficient vs inefficient (repeated computation)
"""
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(TOOLS))
from code_shape.analysis.efficiency_shape import efficiency_vector, efficiency_similarity, efficiency_summary

# (name, code, expected_complexity, threaded)
CASES = [
    ("serial-loop", '''
def decrement_serial(n):
    x = n
    for i in range(1000000):
        x -= 1
    return x
''', "O(n)", False),
    ("threaded-loop", '''
import threading

def decrement_parallel(n):
    x = n
    def worker():
        nonlocal x
        for i in range(1000000):
            x -= 1
    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return x
''', "O(n)", True),
    ("nested-loop", '''
def matrix_sum(m):
    total = 0
    for row in m:
        for cell in row:
            total += cell
    return total
''', "O(n^2)", False),
    ("simple", '''
def add(a, b):
    return a + b
''', "O(1)", False),
    ("repeated-call", '''
def slow_sum(nums):
    total = 0
    for n in nums:
        total += len(nums)
    return total
''', "O(n)", False),
]


def main():
    print("=== Efficiency Shape Model Validation ===")
    print(f"{'case':16s} {'complexity':8s} {'threaded':8s} {'loops':>5s} {'nest':>4s} {'calls':>5s}")
    for name, code, exp_cx, exp_th in CASES:
        s = efficiency_summary(code)
        cx_ok = s["complexity"] == exp_cx
        th_ok = s["threaded"] == exp_th
        print(f"{name:16s} {s['complexity']:8s} {str(s['threaded']):8s} {s['loops']:>5d} {s['nesting']:>4d} {s['method_calls']:>5d}  "
              f"cx={'OK' if cx_ok else 'XX'} th={'OK' if th_ok else 'XX'}")

    print("\n=== Efficiency similarity (should separate) ===")
    pairs = [
        ("serial-loop", "threaded-loop", "same intent, diff eff"),
        ("serial-loop", "nested-loop", "diff complexity"),
        ("serial-loop", "simple", "diff complexity"),
        ("nested-loop", "simple", "diff complexity"),
        ("serial-loop", "repeated-call", "efficient vs inefficient"),
    ]
    code = {name: c for name, c, _, _ in CASES}
    for a, b, label in pairs:
        s = efficiency_similarity(code[a], code[b])
        print(f"{a:14s} vs {b:14s} ({label:24s}): {s:.3f}")

if __name__ == "__main__":
    main()
