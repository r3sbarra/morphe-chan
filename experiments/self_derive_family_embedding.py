#!/usr/bin/env python
"""self_derive_family_embedding.py — Test whether a COARSE family-level embedding
of the enriched shape fixes the discrimination ceiling found in self_derive_fixedembed.py.

Hypothesis (self-derived): the 92-dim fixed embedding under-discriminates because
unit-normalized sparse vectors saturate cosine. Coarse-graining the dims into their
families (PRIM/EFF/FLOW/PROP/VAL/GRAPH/TYPE-role/... ~14 buckets) keeps the same info
at much lower dimension, de-saturating cosine → better separation of unrelated shapes
while preserving clones.

Also derives NEW composite metrics usable directly by Morphe-chan:
  1. SHAPE_ENTROPY   = Shannon entropy of the L1-normalized dim weights (info content)
  2. SHAPE_SKEW      = (max - mean)/std of dim weights (concentration)
  3. SHAPE_SPREAD    = number of nonzero dims / total (density)
  4. family vector   = per-family L2 aggregates (the coarse embedding)
Validated against: clone pairs (high), unrelated (low), rename (high).
"""
import sys, os, math, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from code_shape.core.enriched_shape import enriched_shape
exec(open(os.path.join(os.path.dirname(__file__), 'self_derive_fixedembed.py')).read().split('def main')[0])  # reuse fixed_embedding + cosine

FAMILIES = ["PRIM", "EFF", "FLOW", "IN", "OUT", "PROP", "VAL", "GRAPH", "TAINT",
            "PARAM_TYPE", "PARAM_ROLE", "VAR_TYPE", "VAR_ROLE", "AGGREGATE"]

def _fam(key):
    if "PARAM\uf8fftype" in key: return "PARAM_TYPE"
    if "PARAM\uf8ffrole" in key: return "PARAM_ROLE"
    if "VAR\uf8fftype" in key: return "VAR_TYPE"
    if "VAR\uf8ffrole" in key: return "VAR_ROLE"
    for f in ["PRIM","EFF","FLOW","IN","OUT","PROP","VAL","GRAPH","TAINT"]:
        if key.startswith(f): return f
    if key in ("PARAM_COUNT","VAR_COUNT","TYPE_DIVERSITY","UNTYPED","MUTATION"):
        return "AGGREGATE"
    return "OTHER"

def family_embedding(code):
    fe = fixed_embedding(code)
    fam = {}
    for k, v in fe.items():
        f = _fam(k)
        fam[f] = fam.get(f, 0.0) + v*v   # L2-accumulate
    # sqrt to get family-level "energy"
    out = {f: math.sqrt(sq) for f, sq in fam.items()}
    nrm = math.sqrt(sum(v*v for v in out.values()))
    if nrm > 0:
        out = {k: v/nrm for k, v in out.items()}
    return out

def shape_metrics(code):
    """New composite metrics derived from the shape vector itself."""
    fe = fixed_embedding(code)
    vals = [abs(v) for v in fe.values()]
    total = sum(vals)
    out = {}
    if total > 0:
        import math as _m
        p = [v/total for v in vals if v > 0]
        out["SHAPE_ENTROPY"] = -sum(x*_m.log2(x) for x in p) if p else 0.0
    else:
        out["SHAPE_ENTROPY"] = 0.0
    nonzero = sum(1 for v in vals if v != 0.0)
    out["SHAPE_SPREAD"] = nonzero / len(vals) if vals else 0.0
    mx = max(vals) if vals else 0.0
    mn = sum(vals)/len(vals) if vals else 0.0
    sd = math.sqrt(sum((v-mn)**2 for v in vals)/len(vals)) if len(vals)>1 else 0.0
    out["SHAPE_SKEW"] = (mx-mn)/sd if sd else 0.0
    out["SHAPE_TOTAL"] = total
    return out


def main():
    corpus = {
        "add": "def add(a,b): return a+b",
        "loop_sum": "def s(n):\n    t=0\n    for i in range(n):\n        t+=i\n    return t",
        "fileio": "def rf(p):\n    with open(p) as f:\n        return f.read()",
        "http": "def f(u):\n    import requests\n    return requests.get(u).json()",
        "fact": "def fact(n):\n    if n<=1: return 1\n    return n*fact(n-1)",
        "bsearch": "def bs(arr,t):\n    lo,hi=0,len(arr)-1\n    while lo<=hi:\n        m=(lo+hi)//2\n        if arr[m]==t: return m\n        elif arr[m]<t: lo=m+1\n        else: hi=m-1\n    return -1",
        "sql": "def u(name):\n    return db.execute('SELECT * FROM users WHERE name = '+name)",
        "matmul": "def mm(A,B):\n    n=len(A)\n    C=[[0]*n for _ in range(n)]\n    for i in range(n):\n        for j in range(n):\n            for k in range(n):\n                C[i][j]+=A[i][k]*B[k][j]\n    return C",
        "dedupe": "def dd(items):\n    return list(dict.fromkeys(items))",
        "gen": "def gen(n):\n    for i in range(n):\n        yield i*i",
    }
    emb = {k: family_embedding(v) for k, v in corpus.items()}
    print(f"family embedding dims: {len(emb['add'])}")
    print("\nfamily vectors dims:", sorted(emb['add'].keys()))

    # clone pair (renamed)
    clone_b = "def min_max(values):\n    best=values[0]\n    for v in values:\n        if v>best:\n            best=v\n    return best"
    print("\n--- family-embedding discrimination (want clones high, unrelated low) ---")
    print(f"  add vs loop_sum       {cosine(emb['add'], emb['loop_sum']):.3f} (loop vs straight — want <0.7)")
    print(f"  add vs fileio         {cosine(emb['add'], emb['fileio']):.3f} (want <0.5)")
    print(f"  add vs matmul         {cosine(emb['add'], emb['matmul']):.3f} (want <0.5)")
    print(f"  add vs its clone      {cosine(emb['add'], family_embedding('def x(a,b): return a+b')):.3f} (want >0.9)")
    print(f"  loop_sum vs clone     {cosine(emb['loop_sum'], family_embedding(clone_b)):.3f} (loop clone — want ~0.9)")

    # --- new composite metrics ---
    print("\n--- new derived shape metrics ---")
    hdr = f"  {'name':9s} {'ENTROPY':>8s} {'SPREAD':>7s} {'SKEW':>6s} {'TOTAL':>7s}"
    print(hdr)
    for k, v in corpus.items():
        m = shape_metrics(v)
        print(f"  {k:9s} {m['SHAPE_ENTROPY']:8.2f} {m['SHAPE_SPREAD']:7.2f} {m['SHAPE_SKEW']:6.2f} {m['SHAPE_TOTAL']:7.2f}")

    # entropy should be a complexity-ish proxy: matmul/complex > add
    print("\n--- entropy as complexity proxy sanity (expect matmul>bsearch>add) ---")
    for k in ["add","loop_sum","bsearch","matmul","fact"]:
        m = shape_metrics(corpus[k])
        print(f"  {k:9s} entropy={m['SHAPE_ENTROPY']:.2f}")

    # save the derived family embedding spec for reuse as a real Morphe-chan feature
    out = {"families": sorted(emb['add'].keys())}
    with open(os.path.join(os.path.dirname(__file__), '..', 'data', 'family_embedding_spec.json'), 'w') as f:
        json.dump(out, f, indent=2)
    print("\nwrote data/family_embedding_spec.json")

if __name__ == "__main__":
    main()
