"""Accuracy guard: labeled clone-detection property test.

True semantic clones must score HIGHER than non-clones (including
polarity-conflict and parity-style non-clones) on Morphe-chan's similarity
measures. This is a lightweight, dependency-free version of the fuller
benchmarks/clone_eval.py -- it locks the core separation property so accuracy
regressions are caught by the test suite.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from code_shape.core.code_shape_core import true_similarity


# (code_a, code_b, label)  label=1 clone, 0 non-clone
PAIRS = [
    # clones: renamed vars / same algorithm
    ("def add(a, b):\n    return a + b",
     "def sum(x, y):\n    return x + y", 1),
    ("def total(nums):\n    acc = 0\n    for n in nums:\n        acc += n\n    return acc",
     "def sum_list(items):\n    s = 0\n    for i in items:\n        s += i\n    return s", 1),
    # non-clones: opposite operations / different behavior
    ("def add(a, b):\n    return a + b",
     "def subtract(a, b):\n    return a - b", 0),
    ("def is_even(n):\n    return n % 2 == 0",
     "def is_odd(n):\n    return n % 2 == 1", 0),
]


def test_clones_outrank_nonclones():
    clone_scores = [true_similarity(a, b, "python", None) for a, b, l in PAIRS if l == 1]
    nonclone_scores = [true_similarity(a, b, "python", None) for a, b, l in PAIRS if l == 0]
    # Every real clone must out-score every non-clone.
    assert min(clone_scores) > max(nonclone_scores), \
        (sorted(clone_scores), sorted(nonclone_scores))
