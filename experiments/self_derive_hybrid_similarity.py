#!/usr/bin/env python
"""self_derive_hybrid_similarity.py — Find a clone-detection scorer that beats the
83% structural baseline, by combining it with the PRIM:* enriched signal.

From self_derive_similarity_benchmark.py: baseline true_similarity (structural+
polarity)=83%, PRIM-only enriched cosine=71% but with HIGHER true-clone mean
(0.774 vs 0.855). Hypothesis: blending the two (structural catches structure,
PRIM:* adds the enriched primitive distribution) can beat either alone.

Searches the blend weight alpha (and optional polarity application) for the best
best-threshold classification accuracy, then reports the winner.
"""
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from clone_corpus import CORPUS
from code_shape.core.code_shape_core import true_similarity
from code_shape.core.enriched_shape import enriched_shape
from code_shape.core.polarity import combined_similarity_penalty
from code_shape.core.code_shape_core import recursive_shape, true_shape_vector


def prim_cos(a, b, lang="python"):
    def pv(c, l):
        s = enriched_shape(c, l)
        return {k: v for k, v in s.items() if k.startswith("PRIM:") and v not in (0, 0.0)}
    pa, pb = pv(a, lang), pv(b, lang)
    keys = set(pa) | set(pb)
    dot = sum(pa.get(k, 0.0) * pb.get(k, 0.0) for k in keys)
    na = math.sqrt(sum(x * x for x in pa.values()))
    nb = math.sqrt(sum(x * x for x in pb.values()))
    return dot / (na * nb) if na and nb else 0.0


def eval_at(alpha, apply_polarity_prim):
    """Blend: score = alpha*true_similarity + (1-alpha)*prim_cos.
    Optionally apply polarity penalty to the prim_cos component."""
    trues, falses = [], []
    for a, b, is_clone, _ in CORPUS:
        ts = true_similarity(a, b)
        pc = prim_cos(a, b)
        if apply_polarity_prim:
            ca, cb = recursive_shape(a), recursive_shape(b)
            pc = combined_similarity_penalty(pc, dict(ca), dict(cb), a, b)
        s = alpha * ts + (1 - alpha) * pc
        (trues if is_clone else falses).append(s)
    all_s = sorted(set(trues + falses), reverse=True)
    best_acc, best_t = 0.0, None
    for t in all_s:
        acc = (sum(1 for x in trues if x >= t) + sum(1 for x in falses if x < t)) / len(CORPUS)
        if acc > best_acc:
            best_acc, best_t = acc, t
    return best_acc, (sum(trues) / len(trues)), (sum(falses) / len(falses))


def main():
    print("clone corpus:", len(CORPUS), "pairs")
    if __name__ == "__main__":
        # baseline
        ba, bmt, bmf = eval_at(1.0, False)
        print(f"\nbaseline (alpha=1.0, pure structural):  acc={ba:.0%}  true-m={bmt:.3f} false-m={bmf:.3f}")

        print("\nalpha sweep (blend structural + PRIM):")
        best = (0, 0.0, None)
        for alpha in [0.0, 0.2, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
            acc, mt, mf = eval_at(alpha, False)
            print(f"  alpha={alpha:.1f}  acc={acc:.0%}  true-m={mt:.3f} false-m={mf:.3f}")
            if acc > best[1]:
                best = (alpha, acc, (mt, mf))
        print(f"\nBEST blend: alpha={best[0]:.1f} -> acc={best[1]:.0%}")

        print("\nwith polarity penalty on PRIM component:")
        for alpha in [0.0, 0.4, 0.6, 0.8]:
            acc, mt, mf = eval_at(alpha, True)
            print(f"  alpha={alpha:.1f}  acc={acc:.0%}  true-m={mt:.3f} false-m={mf:.3f}")


if __name__ == "__main__":
    main()
