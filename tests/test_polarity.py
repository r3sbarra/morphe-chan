"""Regression tests for the semantic-polarity similarity penalty.

Opposite operations (`a + b` vs `a - b`) must NOT be scored as near-clones,
while genuinely identical code must stay high. Confirmed empirically before
the fix: clone_score(add, sub) = 0.938, true_similarity(add, sub) = 0.500.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from code_shape.core.code_vector_similarity import clone_score
from code_shape.core.code_shape_core import true_similarity
from code_shape.core.agnostic_shape import agnostic_similarity


ADD = "def f(a, b):\n    return a + b"
SUB = "def f(a, b):\n    return a - b"
ADD2 = "def g(a, b):\n    return a + b"


def test_clone_score_opposites_penalized():
    assert clone_score(ADD, SUB) < 0.7, clone_score(ADD, SUB)
    assert clone_score(ADD, ADD) > 0.9, clone_score(ADD, ADD)


def test_clone_score_structural_opposites_penalized():
    assert clone_score(ADD, SUB, structural=True) < 0.7


def test_true_similarity_opposites_penalized():
    sim_opp = true_similarity(ADD, SUB)
    sim_same = true_similarity(ADD, ADD2)
    assert sim_same > 0.9, sim_same
    assert sim_opp < sim_same * 0.5, (sim_opp, sim_same)


def test_agnostic_similarity_opposites_penalized():
    assert agnostic_similarity(ADD, SUB) < 0.5
    assert agnostic_similarity(ADD, ADD2) > 0.9


def test_detect_clones_caching_preserves_output():
    from code_shape.core.code_vector_similarity import detect_clones
    s1 = "def add(a, b):\n    return a + b"
    s2 = "def add(x, y):\n    return x + y"
    # Renamed-var clones must match at 1.0 (structural normalization).
    pairs = detect_clones([s1, s2], threshold=0.8, structural=True)
    assert pairs == [(0, 1, 1.0)]

    # Non-clone pair of the same length/arity must not be reported at 1.0.
    s3 = "def sub(a, b):\n    return a - b"
    pairs3 = detect_clones([s1, s3], threshold=0.999, structural=True)
    assert pairs3 == []


def test_literal_disagreement_penalizes_parity_nonclone():
    # is_even vs is_odd: identical primitives but different comparison constant.
    even = "def f(n):\n    return n % 2 == 0"
    odd = "def g(n):\n    return n % 2 == 1"
    raw = true_similarity(even.replace("== 0", "== 0"), odd)
    assert raw < 0.75, raw  # literal disagreement must pull it down


def test_literal_same_constants_no_penalty():
    # Renamed-var clone with same constant must stay high.
    a = "def f(n):\n    return n % 2"
    b = "def g(k):\n    return k % 2"
    assert true_similarity(a, b) > 0.9
