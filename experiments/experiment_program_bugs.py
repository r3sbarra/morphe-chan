#!/usr/bin/env python
"""experiment_program_bugs.py — Validate program-level bug detection on labeled
multi-function programs.
"""
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(TOOLS))
from code_shape.analysis.program_bug_detector import detect_program_bugs, program_bug_score

# (name, code, has_bug)
CASES = [
    # Buggy
    ("arity-mismatch", '''
def add(a, b):
    return a + b

def main(x):
    return add(x)
''', True),
    ("missing-callee", '''
def main(x):
    return double(x)
''', True),
    ("unused-fn", '''
def helper(x):
    return x * 2

def main(x):
    return x + 1
''', True),
    ("arity-too-many", '''
def add(a, b):
    return a + b

def main(x):
    return add(x, x, x)
''', True),
    # Clean
    ("clean-2fn", '''
def add(a, b):
    return a + b

def main(x):
    return add(x, x)
''', False),
    ("clean-3fn", '''
def add(a, b):
    return a + b

def double(x):
    return add(x, x)

def main(nums):
    total = 0
    for n in nums:
        total = double(n)
    return total
''', False),
    ("clean-single", '''
def main(nums):
    total = 0
    for n in nums:
        total += n
    return total
''', False),
]


def main():
    print("=== Program-Level Bug Detection Validation ===")
    print(f"{'case':16s} {'score':>6s} {'has_bug':8s} {'detected':9s} {'OK':>3s}")
    tp = fp = fn = tn = 0
    for name, code, has_bug in CASES:
        score = program_bug_score(code)
        detected = score > 0
        ok = detected == has_bug
        if detected and has_bug: tp += 1
        elif detected and not has_bug: fp += 1
        elif not detected and has_bug: fn += 1
        else: tn += 1
        bugs = [b["type"] for b in detect_program_bugs(code)]
        print(f"{name:16s} {score:>6.2f} {str(has_bug):8s} {str(detected):9s} {'OK' if ok else 'XX':>3s} {bugs}")

    prec = tp / (tp + fp) if (tp + fp) else 0
    rec = tp / (tp + fn) if (tp + fn) else 0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0
    print(f"\nPrecision={prec:.2f} Recall={rec:.2f} F1={f1:.2f} ({tp}TP {fp}FP {fn}FN {tn}TN)")


if __name__ == "__main__":
    main()
