#!/usr/bin/env python
"""Experiment 4: labeled clone-detection eval for Morphe-chan.

Small hand-labeled benchmark (clone / non-clone pairs) to quantify how well
the similarity measures separate real semantic clones from non-clones.
Polarity-conflict pairs (add vs sub) are labeled NON-CLONE -- a good detector
must NOT rank them as clones even though they share nearly all tokens.
"""
import sys
from pathlib import Path
# repo-root-relative src path (portable; no hardcoded user path)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from code_shape.core.code_shape_core import true_similarity
from code_shape.core.code_vector_similarity import clone_score

# --- labeled pairs: (code_a, code_b, label) label=1 clone, 0 non-clone ---
PAIRS = [
    # semantic clones (renamed vars / same algorithm)
    ("def add(a, b):\n    return a + b",
     "def sum(x, y):\n    return x + y", 1),
    ("def total(nums):\n    acc = 0\n    for n in nums:\n        acc += n\n    return acc",
     "def sum_list(items):\n    s = 0\n    for i in items:\n        s += i\n    return s", 1),
    ("def max_of(a, b):\n    if a > b:\n        return a\n    return b",
     "def larger(x, y):\n    if x > y:\n        return x\n    return y", 1),
    # cross-language semantic clone
    ("def clamps(x, lo, hi):\n    if x < lo:\n        return lo\n    if x > hi:\n        return hi\n    return x",
     "function clamp(x, lo, hi) {\n    if (x < lo) return lo;\n    if (x > hi) return hi;\n    return x;\n}", 1),
    # non-clones (different behavior)
    ("def add(a, b):\n    return a + b",
     "def subtract(a, b):\n    return a - b", 0),   # polarity conflict
    ("def sum(nums):\n    return sum(nums)",
     "def rev(nums):\n    return nums[::-1]", 0),   # genuinely different
    ("def is_even(n):\n    return n % 2 == 0",
     "def is_odd(n):\n    return n % 2 == 1", 0),   # opposite polarity
    ("def add(a, b):\n    return a + b",
     "def sort(arr):\n    return sorted(arr)", 0),
]


def evaluate(name, scorer):
    scores = []
    for a, b, lbl in PAIRS:
        s = scorer(a, b)
        scores.append((s, lbl))
    ranked = sorted(scores, key=lambda t: -t[0])
    # best threshold ~ separates clones (1) from non-clones (0) by ROC
    best = None
    for thr in sorted({s for s, _ in scores}):
        pred = [1 if sc >= thr else 0 for sc, _ in scores]
        tp = sum(1 for (sc, l), p in zip(scores, pred) if l == 1 and p)
        fp = sum(1 for (sc, l), p in zip(scores, pred) if l == 0 and p)
        fn = sum(1 for (sc, l), p in zip(scores, pred) if l == 1 and not p)
        prec = tp / (tp + fp) if tp + fp else 0
        rec = tp / (tp + fn) if tp + fn else 0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
        if best is None or f1 > best[1]:
            best = (thr, f1, prec, rec, tp, fp, fn)
    print(f"\n[{name}] best-F1@{best[0]:.3f}: F1={best[1]:.3f} P={best[2]:.3f} R={best[3]:.3f} (tp={best[4]} fp={best[5]} fn={best[6]})")
    print("  per-pair scores:")
    for (s, l) in scores:
        print(f"    {'CLONE' if l else 'non  '} score={s:.3f}")
    return best


print("=== true_similarity (with polarity penalty) ===")
evaluate("true_similarity", lambda a, b: true_similarity(a, b, "python", None))

print("\n=== clone_score raw (with polarity penalty) ===")
evaluate("clone_score", lambda a, b: clone_score(a, b))

# Demonstrate the polarity penalty is REQUIRED: a variant without it.
from code_shape.core.code_shape_core import true_shape_vector, cosine
def true_sim_no_polarity(a, b):
    return cosine(true_shape_vector(a, "python"), true_shape_vector(b, None))

print("\n=== true_similarity WITHOUT polarity (all else same) ===")
evaluate("no-polarity", lambda a, b: true_sim_no_polarity(a, b))
