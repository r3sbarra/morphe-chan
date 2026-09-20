#!/usr/bin/env python
"""code_vector_similarity.py — Prototype demonstrating 'code as geometric vector'.

Thesis being tested:
  Code snippets can be represented as high-dimensional vectors where each
  dimension is a property (token/feature presence), and vector operations
  (cosine similarity) enable code analysis (clone detection).

This is a pure-computation, dependency-free prototype (stdlib only) so it can
be registered as a verified karyon-chans tool and reused.

Design:
  - vectorize(code) -> dict of token->count (bag-of-tokens, TF-style)
  - cosine(a, b)   -> float similarity in [0,1]
  - clone_score(a, b) -> similarity with a threshold decision
  - detect_clones(snippets, threshold) -> list of (i, j, score) clone pairs
"""
import math
import re
from typing import Dict, List, Tuple

_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+|[^\sA-Za-z0-9_]")


def tokenize(code: str) -> List[str]:
    """Split code into tokens (identifiers, numbers, operators, keywords)."""
    return _TOKEN_RE.findall(code)


def vectorize(code: str) -> Dict[str, int]:
    """Build a bag-of-tokens vector (dict of token -> count)."""
    vec: Dict[str, int] = {}
    for tok in tokenize(code):
        vec[tok] = vec.get(tok, 0) + 1
    return vec


def cosine(a: Dict[str, int], b: Dict[str, int]) -> float:
    """Cosine similarity between two token-count vectors, in [0, 1]."""
    if not a or not b:
        return 0.0
    keys = set(a) | set(b)
    dot = sum(a.get(k, 0) * b.get(k, 0) for k in keys)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def vectorize_structural(code: str) -> Dict[str, int]:
    """Structural bag-of-tokens: replace identifiers with a placeholder so
    renamed-variable clones still match (captures the 'shape' of the code).
    This is the 'compound shape' view: structure matters more than names."""
    # Replace identifiers (word tokens that are not keywords/numbers) with a
    # single structural placeholder, preserving operators/keywords/numbers.
    KEYWORDS = {"def", "return", "if", "else", "elif", "for", "while",
                "in", "and", "or", "not", "import", "from", "class",
                "lambda", "pass", "break", "continue", "True", "False",
                "None", "print", "len", "range"}
    toks = tokenize(code)
    vec: Dict[str, int] = {}
    for t in toks:
        key = t if (t in KEYWORDS or t.isdigit() or not t.isidentifier()) else "<id>"
        vec[key] = vec.get(key, 0) + 1
    return vec


def clone_score(code_a: str, code_b: str, structural: bool = False) -> float:
    """Similarity score between two code snippets (0..1).

    structural=True uses the structural vector (identifiers normalized), which
    better captures semantic clones (renamed variables).

    Either way, a semantic-polarity penalty is applied so snippets using
    opposite operations (e.g. `a + b` vs `a - b`) are not scored as clones.
    """
    base = (
        cosine(vectorize_structural(code_a), vectorize_structural(code_b))
        if structural
        else cosine(vectorize(code_a), vectorize(code_b))
    )
    from .agnostic_shape import decompose
    from .polarity import combined_similarity_penalty
    return combined_similarity_penalty(base, decompose(code_a), decompose(code_b), code_a, code_b)


def detect_clones(snippets: List[str], threshold: float = 0.7, structural: bool = False) -> List[Tuple[int, int, float]]:
    """Return all (i, j, score) pairs above the clone threshold.

    Vectors are precomputed once (O(n) tokenizations) instead of re-tokenizing
    inside the O(n^2) pair loop, which makes large batches much faster.
    """
    vecs = [
        (vectorize_structural(s) if structural else vectorize(s))
        for s in snippets
    ]
    pairs: List[Tuple[int, int, float]] = []
    n = len(vecs)
    for i in range(n):
        vi = vecs[i]
        for j in range(i + 1, n):
            s = cosine(vi, vecs[j])
            if s >= threshold:
                pairs.append((i, j, round(s, 4)))
    return pairs


# ── Self-test / demo ────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Three snippets: two near-identical (clone), one different.
    s1 = "def add(a, b):\n    return a + b"
    s2 = "def add(x, y):\n    return x + y"          # renamed params -> clone
    s3 = "def quicksort(arr):\n    if len(arr) <= 1:\n        return arr"

    print("== raw bag-of-tokens (names matter) ==")
    print("cosine(s1,s2) =", round(clone_score(s1, s2), 4), "(clone expected)")
    print("cosine(s1,s3) =", round(clone_score(s1, s3), 4), "(different expected)")
    print("cosine(s2,s3) =", round(clone_score(s2, s3), 4))
    pairs = detect_clones([s1, s2, s3], threshold=0.7)
    print("clones detected (raw):", pairs)

    print("== structural (identifiers normalized) ==")
    print("cosine(s1,s2) =", round(clone_score(s1, s2, structural=True), 4), "(clone expected)")
    print("cosine(s1,s3) =", round(clone_score(s1, s3, structural=True), 4), "(different expected)")
    print("cosine(s2,s3) =", round(clone_score(s2, s3, structural=True), 4))
    pairs_s = detect_clones([s1, s2, s3], threshold=0.7, structural=True)
    print("clones detected (structural):", pairs_s)
