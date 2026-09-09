#!/usr/bin/env python
"""experiment_shape_model.py — Full evaluation of the improved shape model on
the 24-pair labeled corpus, compared against prior methods.

  RAW token, STRUCTURAL token, COARSE intent, FINE intent, SHAPE model
on the 24-pair corpus. Reports precision/recall/F1 at multiple thresholds.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "src"
SCRATCH = ROOT / "scratch"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(SCRATCH))

from clone_corpus import CORPUS
from code_shape.core.code_vector_similarity import clone_score as token_clone
from code_shape.core.intent_vector import intent_similarity
from code_shape.core.intent_vector_fine import fine_similarity
from code_shape.core.shape_model import shape_similarity


def evaluate(score_fn, threshold):
    tp = fp = fn = tn = 0
    for a, b, is_clone, _ in CORPUS:
        s = score_fn(a, b)
        pred = s >= threshold
        if pred and is_clone: tp += 1
        elif pred and not is_clone: fp += 1
        elif not pred and is_clone: fn += 1
        else: tn += 1
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": round(prec, 3), "recall": round(rec, 3), "f1": round(f1, 3)}


def main():
    n_true = sum(1 for c in CORPUS if c[2])
    n_false = len(CORPUS) - n_true
    print("=== Shape Model Evaluation on %d-pair corpus (%d clones, %d diff) ===" % (
        len(CORPUS), n_true, n_false))

    methods = {
        "RAW token":      lambda a, b: token_clone(a, b, structural=False),
        "STRUCTURAL tok": lambda a, b: token_clone(a, b, structural=True),
        "COARSE intent":  intent_similarity,
        "FINE intent":    fine_similarity,
        "SHAPE model":    shape_similarity,
    }

    print(f"\n{'Method':16s} {'thr':>4s} {'prec':>6s} {'rec':>6s} {'F1':>6s}")
    for name, fn in methods.items():
        best = None
        for thr in (0.4, 0.5, 0.6, 0.7, 0.8):
            r = evaluate(fn, thr)
            if best is None or r["f1"] > best[1]["f1"]:
                best = (thr, r)
        print(f"{name:16s} {best[0]:>4.1f} {best[1]['precision']:>6.3f} {best[1]['recall']:>6.3f} {best[1]['f1']:>6.3f}  (best F1)")

    print("\n=== SHAPE model per-pair scores (thr=0.7) ===")
    for i, (a, b, is_clone, lbl) in enumerate(CORPUS):
        s = shape_similarity(a, b)
        pred = "clone" if s >= 0.7 else "diff"
        mark = "OK" if (pred == "clone") == is_clone else "XX"
        print(f"  {i:2d} {mark} [{lbl:16s}] shape={s:.3f} label={'CLONE' if is_clone else 'DIFF '} pred={pred}")


if __name__ == "__main__":
    main()
