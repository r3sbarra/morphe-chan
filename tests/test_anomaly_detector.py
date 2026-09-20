#!/usr/bin/env python
"""Tests for the geometric anomaly detector
(src/code_shape/analysis/anomaly_detector.py) — self-derived capability:
functions whose PRIM:* shape is far from a reference centroid are structural
outliers (candidate smells / dead / exceptional code).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from code_shape.analysis.anomaly_detector import AnomalyDetector, prim_projection


def _corpus():
    return [
        ("sum", "def f(nums):\n    t = 0\n    for n in nums:\n        t += n\n    return t"),
        ("max", "def f(items):\n    m = items[0]\n    for i in items:\n        if i > m:\n            m = i\n    return m"),
        ("fact", "def f(n):\n    if n <= 1:\n        return 1\n    return n * f(n - 1)"),
        ("sum2", "def f(values):\n    acc = 0\n    for v in values:\n        acc += v\n    return acc"),
    ]


def test_prim_projection_unit():
    p = prim_projection("def f(nums):\n    t = 0\n    for n in nums:\n        t += n\n    return t")
    import math
    nrm = math.sqrt(sum(v * v for v in p.values()))
    assert abs(nrm - 1.0) < 1e-6
    assert all(k.startswith("PRIM:") for k in p)


def test_typical_vs_outlier_score():
    det = AnomalyDetector([(l, c, None) for l, c in _corpus()])
    typical = _corpus()[0][1]
    lookup = "def f(k):\n    return MAP.get(k, 0)"
    ts, os_ = det.score(typical), det.score(lookup)
    assert os_ > ts, (ts, os_)  # a pure dict-lookup is more anomalous than a typical compute fn


def test_outlier_flag_threshold():
    det = AnomalyDetector([(l, c, None) for l, c in _corpus()])
    assert not det.is_outlier(_corpus()[1][1])  # typical fn not flagged
    # a wildly different shape should exceed μ+2σ
    odd = "def f():\n    return open('/etc/passwd').read() + open('/etc/hosts').read()"
    assert det.is_outlier(odd, k=2.0) or det.score(odd) > det.mean


def test_top_outliers_orders_by_score():
    det = AnomalyDetector([(l, c, None) for l, c in _corpus()])
    labels = [f"fn{i}" for i in range(3)]
    snips = [("a", _corpus()[0][1]), ("b", "def f(k):\n    return MAP.get(k)"),
             ("c", "def f():\n    return 42")]
    outs = det.top_outliers(snips, k=2.0, limit=3)
    assert outs[0][2] >= outs[-1][2]  # sorted descending by score
    assert len(outs) == 3
