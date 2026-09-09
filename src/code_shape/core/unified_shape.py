#!/usr/bin/env python
"""unified_shape.py — Unified code shape vector (intent + structure + efficiency).
  - INTENT (what the code does) — from agnostic_shape
  - STRUCTURE (how it's composed) — control-flow + call structure
  - EFFICIENCY (how well it does it) — from efficiency_shape

The unified vector is the concatenation of the three dimension sets, so a
single vector captures the full code shape. This enables richer comparison:
two functions with the same intent but different efficiency are distinguishable
in the unified space.

Dependency-free (stdlib only).
"""
import math
from typing import Dict, List

from code_shape.core.agnostic_shape import agnostic_vector, DIMS as INTENT_DIMS
from code_shape.analysis.efficiency_shape import efficiency_vector, EFF_DIMS


def unified_vector(code: str) -> Dict[str, float]:
    """Unified shape vector = intent dims + efficiency dims (concatenated).

    Efficiency dims are weighted 2x so they aren't diluted by the larger
    intent dim set (23 vs 8).
    """
    intent = agnostic_vector(code)
    eff = efficiency_vector(code)
    vec: Dict[str, float] = {}
    for k, v in intent.items():
        vec[f"I:{k}"] = v
    for k, v in eff.items():
        vec[f"E:{k}"] = 2.0 * v
    return vec


def cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    keys = set(a) | set(b)
    dot = sum(a.get(k, 0) * b.get(k, 0) for k in keys)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def unified_similarity(code_a: str, code_b: str) -> float:
    """Cosine similarity between two unified shape vectors."""
    return cosine(unified_vector(code_a), unified_vector(code_b))


# ── Shape-based clustering ───────────────────────────────────────────────────
def cluster_by_shape(codes: List[str], threshold: float = 0.6) -> List[List[int]]:
    """Cluster code snippets by unified shape similarity (greedy agglomerative).

    Returns a list of clusters, each a list of indices into `codes`.
    Two clusters merge only if the AVERAGE cross-pair similarity >= threshold
    (prevents chaining through weak links).
    """
    n = len(codes)
    clusters: List[List[int]] = [[i] for i in range(n)]
    merged = True
    while merged:
        merged = False
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                if _clusters_mergeable(clusters[i], clusters[j], codes, threshold):
                    clusters[i] = clusters[i] + clusters[j]
                    del clusters[j]
                    merged = True
                    break
            if merged:
                break
    return clusters


def _clusters_mergeable(ci: List[int], cj: List[int], codes: List[str], threshold: float) -> bool:
    """Two clusters merge if the AVERAGE cross-pair similarity >= threshold."""
    sims = []
    for a in ci:
        for b in cj:
            sims.append(unified_similarity(codes[a], codes[b]))
    if not sims:
        return False
    return sum(sims) / len(sims) >= threshold


# ── Self-test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Same intent, different efficiency
    serial = "def sum_list(nums):\n    total = 0\n    for n in nums:\n        total += n\n    return total"
    threaded = "import threading\n\ndef sum_parallel(nums):\n    def worker():\n        pass\n    threads = [threading.Thread(target=worker) for _ in range(4)]\n    return sum(nums)"
    # Different intent
    evens = "def evens(nums):\n    return [n for n in nums if n % 2 == 0]"

    print("=== Unified shape vector ===")
    print("dims:", len(unified_vector(serial)))
    print("intent dims:", len(agnostic_vector(serial)), "efficiency dims:", len(efficiency_vector(serial)))

    print("\n=== Unified similarity ===")
    print(f"serial vs threaded (same intent, diff eff): {unified_similarity(serial, threaded):.3f}")
    print(f"serial vs evens (diff intent):              {unified_similarity(serial, evens):.3f}")

    print("\n=== Shape-based clustering ===")
    codes = [serial, threaded, evens, "def add(a,b):\n    return a+b", "def sum2(x,y):\n    return x+y"]
    clusters = cluster_by_shape(codes, threshold=0.5)
    for c in clusters:
        print(f"  cluster: {c} -> {[codes[i].splitlines()[0][:30] for i in c]}")
