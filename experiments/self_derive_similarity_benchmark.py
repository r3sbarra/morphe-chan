#!/usr/bin/env python
"""self_derive_similarity_benchmark.py — Benchmark Morphe-chan's clone-detection
methods on the labeled clone corpus, comparing the EXISTING true_similarity
baseline vs the NEW fixed/merged enriched embeddings derived in this research.

Question: do the derived rename-invariant embeddings give better clone-vs-nonclone
separation than the structural bag-of-tokens + polarity baseline?

Metrics: mean similarity on true-clone pairs vs false pairs (separation gap), and
a simple classification accuracy at the best threshold on each method's score.
"""
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from clone_corpus import CORPUS
from code_shape.core.code_shape_core import true_similarity
from code_shape.core.fixed_shape import fixed_enriched_shape, merged_enriched_shape


def cos(a, b):
    keys = set(a) | set(b)
    dot = sum(a.get(k, 0.0) * b.get(k, 0.0) for k in keys)
    na = math.sqrt(sum(x * x for x in a.values()))
    nb = math.sqrt(sum(x * x for x in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def score_fixed(a, b):
    return cos(fixed_enriched_shape(a), fixed_enriched_shape(b))


def score_merged(a, b):
    return cos(merged_enriched_shape(a), merged_enriched_shape(b))


def score_prim(a, b, lang="python"):
    # PRIM:* subspace only — the language-invariant core (self-derived)
    from code_shape.core.enriched_shape import enriched_shape
    def pv(code, lg):
        s = enriched_shape(code, lg)
        return {k: v for k, v in s.items() if k.startswith("PRIM:") and v not in (0, 0.0)}
    return cos(pv(a, lang), pv(b, lang))


def eval_method(name, scorer):
    true_scores = []
    false_scores = []
    for a, b, is_clone, _ in CORPUS:
        s = scorer(a, b)
        (true_scores if is_clone else false_scores).append(s)
    mt = sum(true_scores) / len(true_scores)
    mf = sum(false_scores) / len(false_scores)
    gap = mt - mf
    # best-threshold classification accuracy
    all_scores = sorted(set(true_scores + false_scores), reverse=True)
    best_acc = 0.0
    best_t = None
    for t in all_scores:
        acc = (sum(1 for s in true_scores if s >= t) +
               sum(1 for s in false_scores if s < t)) / len(CORPUS)
        if acc > best_acc:
            best_acc, best_t = acc, t
    print(f"\n=== {name} ===")
    print(f"  true-clone mean: {mt:.3f}   false mean: {mf:.3f}   separation gap: {gap:+.3f}")
    print(f"  min(true)={min(true_scores):.3f} max(false)={max(false_scores):.3f}")
    print(f"  best-threshold acc: {best_acc:.0%} @ {best_t:.3f}")
    return gap, best_acc


if __name__ == "__main__":
    print(f"clone corpus: {len(CORPUS)} pairs "
          f"({sum(1 for c in CORPUS if c[2])} clones, "
          f"{sum(1 for c in CORPUS if not c[2])} non-clones)\n")
    eval_method("true_similarity (structural+polarity) baseline", true_similarity)
    eval_method("fixed_enriched_shape (92-dim, derived)", score_fixed)
    eval_method("merged_enriched_shape (80-dim, derived)", score_merged)
    eval_method("PRIM:* subspace only (language-invariant core)", score_prim)
