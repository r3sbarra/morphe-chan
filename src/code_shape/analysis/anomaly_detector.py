#!/usr/bin/env python
"""anomaly_detector.py — Geometric anomaly / outlier detection on Morphe-chan's
enriched shape space (self-derived capability; see
research/SELF_DERIVATION_2026-09-20.md and experiments/self_derive_anomaly.py).

Idea (self-derived): Morphe-chan's enriched shape space is low-dimensional and
unit-sphere. A snippet whose shape vector is a geometric OUTLIER (far from the
centroid of a reference corpus) is structurally exceptional — a candidate code
smell, dead/example code, or unusual logic. This is a shape-native outlier score
not present in Morphe-chan before.

Method:
  - embed each snippet on the PRIM:* subspace (the language-invariant,
    clone-sensitive core found by self_derive_* research);
  - compute the chordal distance from the running centroid;
  - flag snippets beyond mean + k*std as outliers.

Dependency-free (stdlib only).
"""
import math
from typing import Dict, List, Tuple, Optional

from code_shape.core.enriched_shape import enriched_shape


def prim_projection(code: str, lang: str = "python") -> Dict[str, float]:
    """PRIM:* subspace vector (unit-normalized). Only nonzero primitives kept."""
    s = enriched_shape(code, lang)
    p = {k: v for k, v in s.items() if k.startswith("PRIM:") and v not in (0, 0.0, "0", "0.0")}
    n = math.sqrt(sum(v * v for v in p.values()))
    return {k: v / n for k, v in p.items()} if n else p


def _chordal(dist_center: float, keys: List[str]) -> float:
    return dist_center


class AnomalyDetector:
    """Reference-corpus anomaly detector over the PRIM:* shape subspace.

    Build with a corpus of (label, code) snippets; `score(code)` returns how
    structurally anomalous a new snippet is vs that corpus.
    """

    def __init__(self, corpus: List[Tuple[str, str, Optional[str]]], lang: str = "python"):
        # corpus: [(label, code, lang_or_None)]
        self.lang = lang
        self.vecs: List[Tuple[str, Dict[str, float]]] = []
        self.keys: List[str] = []
        for label, code, clang in corpus:
            l = clang or lang
            try:
                v = prim_projection(code, l)
            except Exception:
                continue
            if v:
                self.vecs.append((label, v))
        if self.vecs:
            self.keys = sorted(set(k for _, v in self.vecs for k in v))
            n = len(self.vecs)
            self.centroid = {
                k: sum(v.get(k, 0.0) for _, v in self.vecs) / n for k in self.keys
            }
            self.dists = [self._dist(v) for _, v in self.vecs]
            mu = sum(self.dists) / len(self.dists)
            sd = math.sqrt(sum((d - mu) ** 2 for d in self.dists) / len(self.dists)) if self.dists else 0.0
            self.mean = mu
            self.std = sd
        else:
            self.keys, self.centroid, self.dists, self.mean, self.std = [], {}, [], 0.0, 0.0

    def _dist(self, v: Dict[str, float]) -> float:
        return math.sqrt(sum((v.get(k, 0.0) - self.centroid.get(k, 0.0)) ** 2 for k in self.keys))

    def score(self, code: str, lang: Optional[str] = None) -> float:
        """Anomaly score: chordal distance from the reference centroid (0 = typical)."""
        v = prim_projection(code, lang or self.lang)
        return self._dist(v)

    def is_outlier(self, code: str, k: float = 2.0, lang: Optional[str] = None) -> bool:
        return self.score(code, lang) > self.mean + k * self.std

    def top_outliers(self, code_snippets: List[Tuple[str, str]],
                     k: float = 2.0, lang: Optional[str] = None, limit: int = 10
                     ) -> List[Tuple[str, str, float, bool]]:
        """Score a list of (label, code) and return (label, code, score, is_outlier)."""
        out = []
        for label, code in code_snippets:
            if not code.strip():
                continue
            try:
                s = self.score(code, lang)
                out.append((label, code, round(s, 3), self.is_outlier(code, k, lang)))
            except Exception:
                continue
        out.sort(key=lambda x: -x[2])
        return out[:limit]


def detect_anomalies(functions: List[Tuple[str, str]],
                     reference: List[Tuple[str, str]],
                     k: float = 2.0, lang: str = "python", limit: int = 10):
    """Convenience: build a detector from `reference` corpus, score `functions`.
    Returns top anomalies sorted by score."""
    det = AnomalyDetector([(lbl, code, None) for lbl, code in reference], lang)
    return det.top_outliers(functions, k=k, lang=lang, limit=limit)


if __name__ == "__main__":
    # Self-test on a small corpus
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
    corpus = [("sum", "def f(nums):\n    t=0\n    for n in nums:\n        t+=n\n    return t"),
              ("max", "def f(items):\n    m=items[0]\n    for i in items:\n        if i>m:\n            m=i\n    return m"),
              ("fact", "def f(n):\n    if n<=1: return 1\n    return n*f(n-1)")]
    det = AnomalyDetector([(l, c, None) for l, c in corpus])
    print("typical sum   :", round(det.score(corpus[0][1]), 3))
    print("lookup outlier:", round(det.score("def f(k):\n    return MAP.get(k, 0)"), 3))
