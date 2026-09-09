#!/usr/bin/env python
"""experiment_program_shape.py — Validate program decomposition + composite
shape + connection retention on labeled multi-function programs.

  - Same program (should be ~1.0)
  - Same functions, different wiring (should be < same, > different)
  - Different programs (should be low)
"""
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(TOOLS))
from code_shape.core.program_shape import program_shape, program_signature, program_similarity

# Programs
PROG_A = '''
def add(a, b):
    return a + b

def double(x):
    return add(x, x)

def main(nums):
    total = 0
    for n in nums:
        total = double(n)
    return total
'''

PROG_B = '''
def add(a, b):
    return a + b

def double(x):
    return add(x, x)

def main(nums):
    total = 0
    for n in nums:
        total = add(n, n)
    return total
'''

PROG_C = '''
def main(nums):
    total = 0
    for n in nums:
        total += n
    return total
'''

PROG_D = '''
def is_even(n):
    return n % 2 == 0

def count_evens(nums):
    count = 0
    for n in nums:
        if is_even(n):
            count += 1
    return count
'''

# (name_a, name_b, expected_relation)
# same = identical, similar = same fns diff wiring, diff = different program
PAIRS = [
    ("A", "A", "same"),
    ("A", "B", "similar"),  # same fns, diff wiring
    ("A", "C", "diff"),
    ("A", "D", "diff"),
    ("B", "C", "diff"),
    ("C", "D", "diff"),
]
PROGS = {"A": PROG_A, "B": PROG_B, "C": PROG_C, "D": PROG_D}


def main():
    print("=== Program Decomposition + Composite Shape Validation ===")
    print("\nComposite signatures:")
    for name, prog in PROGS.items():
        print(f"  {name}: {program_signature(prog)}")

    print("\nSimilarity matrix:")
    print(f"{'pair':6s} {'sim':>6s} {'expected':8s} {'OK':>3s}")
    correct = 0
    for na, nb, rel in PAIRS:
        s = program_similarity(PROGS[na], PROGS[nb])
        if rel == "same":
            ok = s >= 0.9
        elif rel == "similar":
            ok = 0.5 <= s < 0.9
        else:
            ok = s < 0.7
        correct += ok
        print(f"{na}-{nb:4s} {s:>6.3f} {rel:8s} {'OK' if ok else 'XX':>3s}")
    print(f"\nAccuracy: {correct}/{len(PAIRS)}")


if __name__ == "__main__":
    main()
