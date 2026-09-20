#!/usr/bin/env python
"""self_derive_dimreduction.py — Deliver the ~intrinsic-dim fixed-length enriched
embedding for Morphe-chan, derived purely from its own vector geometry.

Findings to act on (from self_derive_corpus/fixedembed/family_embedding):
  - enriched shape is variable-length (up to 179 dims), ~85% sparse, unit-normalized
  - ~25 intrinsic dims (participation ratio)
  - full-space cosine saturates; family-total coarse-graining over-corrects
  - the info lives WITHIN primitive families, at per-primitive granularity

Method here: PCA-free, dependency-free **collinear-dim reduction** —
  1. Build fixed-length name-invariant embedding (92 dims) across a corpus.
  2. Compute the pairwise |Pearson| correlation matrix over the corpus.
  3. Greedily merge/reject dims that are near-perfectly redundant (|r|>0.95)
     keeping the highest-variance representative per cluster.
  4. Emit a reduced spec (kept keys) + validate discrimination improves.
Also re-derives the correlation graph = a "dimension dependency map" of Morphe-chan,
usable to identify which shape dims are mathematically redundant by construction.
"""
import sys, os, math, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
exec(open(os.path.join(os.path.dirname(__file__), 'self_derive_fixedembed.py')).read().split('def main')[0])

CORPUS = {
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
    "max_list": "def ml(items):\n    m=items[0]\n    for i in items:\n        if i>m:\n            m=i\n    return m",
    "contains": "def c(h,n):\n    for x in h:\n        if x==n: return True\n    return False",
    "count": "def ct(t):\n    from collections import Counter\n    return Counter(t)",
    "parse_csv": "def pc(d):\n    rows=[]\n    for line in d.split('\\n'):\n        rows.append(line.split(','))\n    return rows",
    "weak_crypto": "def enc(x):\n    from Crypto.Cipher import DES\n    return DES.new(b'12345678').encrypt(x)",
    "xss": "def r(n):\n    return '<div>'+n+'</div>'",
    "stateful": "class C:\n    def __init__(s):\n        s.c=0\n    def inc(s):\n        s.c+=1\n        return s.c",
    "deep": "def v(cfg):\n    if cfg:\n        for k in cfg:\n            if k:\n                return k\n    return None",
    "log": "def log(msg):\n    print(msg)",
    "generator": "def gen(n):\n    for i in range(n):\n        yield i*i",
    "fib_loop": "def fib(n):\n    a,b=0,1\n    for _ in range(n):\n        a,b=b,a+b\n    return a",
    "binary_add": "def ab(a,b):\n    return bin(int(a,2)+int(b,2))[2:]",
    "dedupe2": "def uq(items):\n    seen=set()\n    out=[]\n    for i in items:\n        if i not in seen:\n            seen.add(i)\n            out.append(i)\n    return out",
    "readlines": "def rl(path):\n    with open(path) as f:\n        return f.readlines()",
    "str_ops": "def norm(s):\n    return s.strip().lower().replace(' ','_')",
    "dict_get": "def g(d, k):\n    return d.get(k, None)",
    "two_loops": "def mm2(A,B):\n    n=len(A)\n    return [[sum(A[i][k]*B[k][j] for k in range(n)) for j in range(n)] for i in range(n)]",
    "try_except": "def safe(fn, x):\n    try:\n        return fn(x)\n    except Exception as e:\n        return None",
    "nested_data": "def cfg2():\n    return {'a': [1,2], 'b': {'c': 3}}",
    "recurse_tree": "def walk(t):\n    if not t:\n        return 0\n    return 1 + walk(t.left) + walk(t.right)",
}

def main():
    names = list(CORPUS.keys())
    fe = {k: fixed_embedding(v) for k, v in CORPUS.items()}
    keys = list(fe[names[0]].keys())
    n = len(names)
    # matrix rows=corpus, cols=dims
    M = [[fe[nm][k] for k in keys] for nm in names]

    # variance per dim
    def colvar(j):
        col = [M[i][j] for i in range(n)]
        m = sum(col)/n
        return sum((x-m)**2 for x in col)/n
    vars_ = [colvar(j) for j in range(len(keys))]

    def pear(a, b):
        ca, cb = [M[i][a] for i in range(n)], [M[i][b] for i in range(n)]
        ma, mb = sum(ca)/n, sum(cb)/n
        cov = sum((ca[i]-ma)*(cb[i]-mb) for i in range(n)) / n   # FIXED: /n
        va, vb = colvar(a), colvar(b)
        if va == 0 or vb == 0: return 0.0
        return cov/math.sqrt(va*vb)

    # greedy correlation clustering
    THRESH = 0.90
    kept = []
    dropped = []
    for j in range(len(keys)):
        if vars_[j] == 0:  # constant dim — no signal
            dropped.append((keys[j], 0.0, "constant"))
            continue
        # check redundancy vs already-kept
        red = False
        for kk in kept:
            r = abs(pear(kk, j))
            if r > THRESH:
                # keep the higher-variance one
                if vars_[j] > vars_[kk]:
                    dropped.append((keys[kk], r, f"redundant-with {keys[j]} r={r:.2f}"))
                    kept.remove(kk)
                    kept.append(j)
                else:
                    dropped.append((keys[j], r, f"redundant-with {keys[kk]} r={r:.2f}"))
                red = True
                break
        if not red:
            kept.append(j)

    print(f"nominal dims: {len(keys)}, kept: {len(kept)}, dropped: {len(dropped)}")
    print("\n--- dropped (redundant/constant) ---")
    for k, r, why in sorted(dropped, key=lambda x: -x[1])[:30]:
        print(f"  {k:28s} {why}")

    # build reduced embedding: subset of fixed keys
    kept_keys = [keys[j] for j in kept]
    def reduced_embedding(code):
        fek = fixed_embedding(code)
        out = {k: fek.get(k, 0.0) for k in kept_keys}
        nrm = math.sqrt(sum(v*v for v in out.values()))
        if nrm > 0:
            out = {k: v/nrm for k, v in out.items()}
        return out

    # validate discrimination vs 92-dim fixed
    print(f"\nkept dims: {len(kept_keys)}")
    tests = [
        ("add vs fileio", "def add(a,b): return a+b", "def rf(p):\n    with open(p) as f:\n        return f.read()", "<0.6"),
        ("add vs matmul", "def add(a,b): return a+b", "def mm(A,B):\n    n=len(A)\n    C=[[0]*n for _ in range(n)]\n    for i in range(n):\n        for j in range(n):\n            for k in range(n):\n                C[i][j]+=A[i][k]*B[k][j]\n    return C", "<0.5"),
        ("add vs its clone", "def add(a,b): return a+b", "def x(a,b): return a+b", ">0.95"),
        ("bsearch vs clone", "def bs(arr,t):\n    lo,hi=0,len(arr)-1\n    while lo<=hi:\n        m=(lo+hi)//2\n        if arr[m]==t: return m\n        elif arr[m]<t: lo=m+1\n        else: hi=m-1\n    return -1",
            "def find(items,key):\n    low,high=0,len(items)-1\n    while low<=high:\n        mid=(low+high)//2\n        if items[mid]==key: return mid\n        elif items[mid]<key: low=mid+1\n        else: high=mid-1\n    return -1", ">0.97"),
    ]
    print(f"\n--- reduced-embedding validation (len={len(kept_keys)}) ---")
    for label, a, b, want in tests:
        ca = cosine(fixed_embedding(a), fixed_embedding(b)) if False else cosine(reduced_embedding(a), reduced_embedding(b))
        print(f"  {label:18s} cos={ca:.3f} want {want}")

    # save reduction spec
    spec = {"kept_dims": kept_keys, "n_kept": len(kept_keys), "n_nominal": len(keys),
            "threshold": THRESH, "dropped_detail": [{"dim": k, "reason": why} for k, r, why in dropped]}
    with open(os.path.join(os.path.dirname(__file__), '..', 'data', 'dim_reduction_spec.json'), 'w') as f:
        json.dump(spec, f, indent=2)
    print("\nwrote data/dim_reduction_spec.json")

if __name__ == "__main__":
    main()
