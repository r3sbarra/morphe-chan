#!/usr/bin/env python
"""self_derive_fixedembed.py — Derive a FIXED-LENGTH, RENAME-INVARIANT embedding
of Morphe-chan's enriched shape, and validate it.

Problem (self-derived): enriched_shape is variable-length (see self_derive_corpus.py)
because per-variable-name dims PARAM:<name>:<TYPE> / VAR:<name>:<TYPE> expand the
space unboundedly (179 union dims from just 28 samples) and live on the unit
sphere (L2 norm always 1 → magnitude useless).

Solution proposed here: collapse the variable-name dims into RENAME-INVARIANT
counts per TYPE and per ROLE (fixed slots), concatenate the fixed global dims
(non name-dependent), and (optionally) re-weight. Result is a fixed-length vector
valid for cosine across arbitrary snippets.

Validation:
  1. same-shape-different-names   → cosine ≈ 1.0 (rename invariance)
  2. genuinely different shapes   → cosine < threshold (discrimination)
  3. clones (renamed)            → cosine high (clone detection still works)
"""
import sys, os, math, json, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from code_shape.core.enriched_shape import enriched_shape

# Fixed type vocabulary from variable_shape (infer_types types seen in practice)
TYPE_SLOTS = ["NUM", "STR", "LIST", "DICT", "CALLABLE", "BOOL", "UNKNOWN", "MIXED"]
ROLE_SLOTS = ["IN", "OUT", "INOUT"]

# Fixed global dimension keys that are NOT name-dependent (from the 28-corpus union)
GLOBAL_KEYS = [
    # PRIM (structural)
    "PRIM:LOOP","PRIM:BRANCH","PRIM:RECURSE","PRIM:ARITH_ADD","PRIM:ARITH_SUB",
    "PRIM:ARITH_MUL","PRIM:ARITH_DIV","PRIM:ARITH_MOD","PRIM:COMPARE_EQ",
    "PRIM:COMPARE_NE","PRIM:COMPARE_GT","PRIM:COMPARE_LT","PRIM:COMPARE_GE",
    "PRIM:COMPARE_LE","PRIM:ASSIGN","PRIM:RETURN","PRIM:READ","PRIM:WRITE",
    "PRIM:AGGREGATE","PRIM:FILTER","PRIM:SORT","PRIM:SEARCH","PRIM:STATE",
    # EFF
    "EFF:EFF_COMPLEXITY","EFF:EFF_LOOPS","EFF:EFF_NESTING","EFF:EFF_METHOD_CALLS",
    "EFF:EFF_THREADED","EFF:EFF_ALLOC","EFF:EFF_RECURSION","EFF:EFF_REPEATED",
    # FLOW / IN / OUT / VAL / PROP / GRAPH / TAINT globals (as emitted)
    "FLOW:ARITH","IN:PARAM","IN:CONSTANT","OUT:RETURN",
    "VAL:FLOW_DEPTH","VAL:BRANCHING","VAL:COUPLING","VAL:RISK","VAL:SEVERITY",
    "PROP:NUM","PROP:LIST","PROP:DICT","PROP:MUTABLE","PROP:TRANSFORM",
    "PROP:BRANCHES","PROP:LOOPS","PROP:HANDLES_ERRORS","PROP:INPUTS","PROP:OUTPUTS",
    "PROP:SIDE_EFFECTS","PROP:IO",
    "GRAPH:FUNCTIONS","GRAPH:CALLS","GRAPH:DATA_EDGES","GRAPH:MAX_FANOUT",
    "GRAPH:MAX_FANIN","GRAPH:AVG_VARS","GRAPH:AVG_EDGES","GRAPH:COMPLEXITY",
    "GRAPH:BRANCHES","GRAPH:LOOPS","GRAPH:RECURSION","GRAPH:CYCLES",
    "TAINT:PARAM",
    # scalar aggregates
    "PARAM_COUNT","VAR_COUNT","TYPE_DIVERSITY","UNTYPED","MUTATION",
]

def _slot_key(k, prefix, slots):
    """Given a dim key like 'PARAM:x:LIST' or 'VAR:total:ROLE:OUT', return slot name."""
    if k.startswith(prefix):
        rest = k[len(prefix):]  # ':x:LIST' or ':total:NUM' etc
        parts = [p for p in rest.split(':') if p]
        # parts[0]=name, parts[1:]=type-or-ROLE-flag
        for i, p in enumerate(parts):
            if p == "ROLE" and i+1 < len(parts):
                r = parts[i+1]
                if r in ROLE_SLOTS:
                    return ("role", r)
        # otherwise it's a type in parts[1]
        if len(parts) >= 2:
            t = parts[1]
            if t in TYPE_SLOTS:
                return ("type", t)
        if len(parts) >= 1:
            tl = parts[1] if len(parts)>=2 else parts[0]
            return ("type", tl if tl in TYPE_SLOTS else "UNKNOWN")
    return None


def fixed_embedding(code):
    """Return fixed-length dict embedding (rename-invariant)."""
    s = enriched_shape(code)
    out = {}
    # 1. global name-independent dims
    for k in GLOBAL_KEYS:
        out[k] = float(s.get(k, 0.0))
    # 2. collapse PARAM:VAR: name dims into type/role counts (fixed slots)
    #    value semantics: sum of the per-name contributions.
    for prefix in ("PARAM", "VAR"):
        for slot_kind, slot in [("type", t) for t in TYPE_SLOTS] + [("role", r) for r in ROLE_SLOTS]:
            key = f"{prefix}\uf8ff{slot_kind}:{slot}"
            total = 0.0
            for k, v in s.items():
                sk = _slot_key(k, prefix + ":", TYPE_SLOTS)
                if sk and sk[0] == slot_kind and sk[1] == slot:
                    total += float(v)
            out[key] = total
    # 3. normalize to unit L2 (direction-only, matches Morphe-chan convention)
    nrm = math.sqrt(sum(v*v for v in out.values()))
    if nrm <= 0:
        return out
    return {k: v/nrm for k, v in out.items()}


def cosine(a, b):
    keys = set(a) | set(b)
    dot = sum(a.get(k,0.0)*b.get(k,0.0) for k in keys)
    na = math.sqrt(sum(v*v for v in a.values()))
    nb = math.sqrt(sum(v*v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot/(na*nb)


def main():
    print(f"fixed embedding length: {len(fixed_embedding('def a(x): return x'))} dims (fixed, rename-invariant)")

    # --- rename invariance: same shape, different var names ---
    pairs = [
        ("sum_list", "def sum_list(nums):\n    total=0\n    for n in nums:\n        total+=n\n    return total",
         "def accumulate(entries):\n    acc=0\n    for e in entries:\n        acc+=e\n    return acc", 0.99),
        ("bsearch", "def bsearch(arr,target):\n    lo,hi=0,len(arr)-1\n    while lo<=hi:\n        m=(lo+hi)//2\n        if arr[m]==target:\n            return m\n        elif arr[m]<target:\n            lo=m+1\n        else:\n            hi=m-1\n    return -1",
         "def find(items,key):\n    low,high=0,len(items)-1\n    while low<=high:\n        mid=(low+high)//2\n        if items[mid]==key:\n            return mid\n        elif items[mid]<key:\n            low=mid+1\n        else:\n            high=mid-1\n    return -1", 0.99),
    ]
    print("\n--- rename invariance (expect ~1.0) ---")
    for label, a, b, exp in pairs:
        c = cosine(fixed_embedding(a), fixed_embedding(b))
        print(f"  {label:10s} cos={c:.3f} (target>{exp}) {'OK' if c>=exp else 'FAIL'}")

    # --- discrimination: unrelated shapes (expect < 0.5) ---
    diffs = [
        ("add_vs_fileio", "def add(a,b): return a+b", "def rf(p):\n    with open(p) as f:\n        return f.read()"),
        ("fact_vs_http", "def fact(n):\n    if n<=1: return 1\n    return n*fact(n-1)", "def fetch(u):\n    import requests\n    return requests.get(u).json()"),
    ]
    print("\n--- discrimination: unrelated (expect low) ---")
    for label, a, b in diffs:
        c = cosine(fixed_embedding(a), fixed_embedding(b))
        print(f"  {label:16s} cos={c:.3f} (want <0.6) {'OK' if c<0.6 else 'low-discrim'}")

    # --- clone detection: renamed clone of a loop+if ---
    clone_a = "def max_list(items):\n    m=items[0]\n    for i in items:\n        if i>m:\n            m=i\n    return m"
    clone_b = "def min_max(values):\n    best=values[0]\n    for v in values:\n        if v>best:\n            best=v\n    return best"   # near-clone
    c = cosine(fixed_embedding(clone_a), fixed_embedding(clone_b))
    print(f"\n  clone pair       cos={c:.3f} (want >0.8) {'OK' if c>0.8 else 'check'}")

    # report effective length stability across corpus
    corpus = {
        "add": "def add(a,b): return a+b",
        "loop": "def loop(n):\n    s=0\n    for i in range(n):\n        s+=i\n    return s",
        "deep": "def w(cfg):\n    if cfg:\n        for k in cfg:\n            if k:\n                return k\n    return None",
        "http": "def f(u):\n    import requests\n    return requests.get(u)",
    }
    lens = {k: len(fixed_embedding(v)) for k, v in corpus.items()}
    print("\n  fixed-length stability:", len(set(lens.values())) == 1, "->", lens)


if __name__ == "__main__":
    main()
