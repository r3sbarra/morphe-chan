#!/usr/bin/env python
"""Tests for the fixed-length, rename-invariant enriched re-embedding
(src/code_shape/core/fixed_shape.py) — self-derived from the enriched-shape
vector geometry (see research/SELF_DERIVATION_2026-09-20.md).
"""
import math

from code_shape.core.fixed_shape import (
    fixed_enriched_shape, fixed_dim_count,
    TYPE_SLOTS, ROLE_SLOTS, FIXED_DIMS,
    merged_enriched_shape, STRUCTURAL_MERGES,
)


def _cos(a, b):
    return sum(v * b.get(k, 0.0) for k, v in a.items())


def test_fixed_length_stable_across_diverse_code():
    samples = [
        "def add(a, b):\n    return a + b",
        "def s(n):\n    t = 0\n    for i in range(n):\n        t += i\n    return t",
        "def rf(p):\n    with open(p) as f:\n        return f.read()",
        "def fact(n):\n    if n <= 1:\n        return 1\n    return n * fact(n - 1)",
        "def bs(arr, t):\n    lo, hi = 0, len(arr) - 1\n    while lo <= hi:\n        m = (lo + hi) // 2\n        if arr[m] == t:\n            return m\n        elif arr[m] < t:\n            lo = m + 1\n        else:\n            hi = m - 1\n    return -1",
    ]
    n = fixed_dim_count()
    for code in samples:
        v = fixed_enriched_shape(code)
        assert len(v) == n, f"length {len(v)} != {n}"
        assert set(v.keys()) == set(FIXED_DIMS), "key set must match canonical FIXED_DIMS"


def test_rename_invariance_high_cosine():
    a = fixed_enriched_shape("def sum_list(nums):\n    total = 0\n    for n in nums:\n        total += n\n    return total")
    b = fixed_enriched_shape("def accumulate(entries):\n    acc = 0\n    for e in entries:\n        acc += e\n    return acc")
    assert _cos(a, b) > 0.95


def test_unit_norm():
    v = fixed_enriched_shape("def add(a, b):\n    return a + b")
    nrm = math.sqrt(sum(x * x for x in v.values()))
    assert abs(nrm - 1.0) < 1e-6


def test_no_name_dependent_dims_leak():
    v = fixed_enriched_shape("def foo_x(a, b):\n    return a + b")
    for k in v:
        # no per-variable-name dims may survive
        assert "PARAM:foo_x" not in k and "VAR:a" not in k, k


def test_discrimination_better_than_saturation():
    # straight-line add vs triple-nested matmul should be well-separated (< 0.7)
    add = fixed_enriched_shape("def add(a, b):\n    return a + b")
    mm = fixed_enriched_shape("def mm(A,B):\n    n = len(A)\n    C = [[0]*n for _ in range(n)]\n    for i in range(n):\n        for j in range(n):\n            for k in range(n):\n                C[i][j] += A[i][k]*B[k][j]\n    return C")
    assert _cos(add, mm) < 0.7


def test_merged_is_fixed_and_smaller():
    a = merged_enriched_shape("def add(a, b):\n    return a + b")
    b = merged_enriched_shape("def s(n):\n    t = 0\n    for i in range(n):\n        t += i\n    return t")
    assert len(a) == len(b)
    assert len(a) < fixed_dim_count()  # merged removes structural redundancies
    assert not set(STRUCTURAL_MERGES) & set(a.keys())  # redundant dims gone


def test_merged_preserves_clones():
    a = merged_enriched_shape("def bs(a,t):\n    lo,hi=0,len(a)-1\n    while lo<=hi:\n        m=(lo+hi)//2\n        if a[m]==t: return m\n        elif a[m]<t: lo=m+1\n        else: hi=m-1\n    return -1")
    b = merged_enriched_shape("def find(items,key):\n    low,high=0,len(items)-1\n    while low<=high:\n        mid=(low+high)//2\n        if items[mid]==key: return mid\n        elif items[mid]<key: low=mid+1\n        else: high=mid-1\n    return -1")
    assert _cos(a, b) > 0.95


def test_merged_maintains_discrimination():
    add = merged_enriched_shape("def add(a, b):\n    return a + b")
    mm = merged_enriched_shape("def mm(A,B):\n    n = len(A)\n    C = [[0]*n for _ in range(n)]\n    for i in range(n):\n        for j in range(n):\n            for k in range(n):\n                C[i][j] += A[i][k]*B[k][j]\n    return C")
    assert _cos(add, mm) < 0.7
