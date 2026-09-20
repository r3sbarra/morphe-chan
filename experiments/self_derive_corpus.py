#!/usr/bin/env python
"""self_derive_corpus.py — Self-referential analysis of Morphe-chan's shape vectors.

Builds a diverse corpus of code functions, computes enriched_shape for each,
projects them onto the union dimension space (fixed-length matrix), and mines:
  1. intrinsic dimensionality (effective rank / PCA variance retention)
  2. pairwise correlations between dim families (PRIM/EFF/PROP/VAL/GRAPH)
  3. redundancy: how much of the 60+ dims is actual information
  4. candidate composite metrics (L2 norm as "shape size"/complexity proxy, etc.)

Zero external deps (stdlib only + code_shape internals).
"""
import sys, os, math, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from code_shape.core.enriched_shape import enriched_shape

# A deliberately diverse corpus covering many shape families.
CORPUS = {
    "add":             "def add(a, b):\n    return a + b",
    "sub":             "def sub(a, b):\n    return a - b",
    "mul":             "def mul(a, b):\n    return a * b",
    "div":             "def div(a, b):\n    return a / b",
    "sum_list":        "def sum_list(nums):\n    total = 0\n    for n in nums:\n        total += n\n    return total",
    "max_list":        "def max_list(items):\n    m = items[0]\n    for i in items:\n        if i > m:\n            m = i\n    return m",
    "contains":        "def contains(haystack, needle):\n    for x in haystack:\n        if x == needle:\n            return True\n    return False",
    "bsearch":         "def bsearch(arr, target):\n    lo, hi = 0, len(arr) - 1\n    while lo <= hi:\n        mid = (lo + hi) // 2\n        if arr[mid] == target:\n            return mid\n        elif arr[mid] < target:\n            lo = mid + 1\n        else:\n            hi = mid - 1\n    return -1",
    "quicksort":       "def qsort(arr):\n    if len(arr) <= 1:\n        return arr\n    pivot = arr[0]\n    less = [x for x in arr[1:] if x <= pivot]\n    greater = [x for x in arr[1:] if x > pivot]\n    return qsort(less) + [pivot] + qsort(greater)",
    "rec_fact":        "def fact(n):\n    if n <= 1:\n        return 1\n    return n * fact(n - 1)",
    "count_chars":     "def count_chars(text):\n    from collections import Counter\n    return Counter(text)",
    "read_file":       "def read_file(path):\n    with open(path) as f:\n        return f.read()",
    "sql_insert":      "def insert_user(db, name):\n    return db.execute('INSERT INTO users(name) VALUES(?)', (name,))",
    "http_get":        "def fetch(url):\n    import requests\n    return requests.get(url).json()",
    "log":             "def log(msg):\n    print(msg)",
    "parse_csv":       "def parse_csv(data):\n    rows = []\n    for line in data.split('\\n'):\n        rows.append(line.split(','))\n    return rows",
    "stateful_counter":"class Counter:\n    def __init__(self):\n        self.count = 0\n    def inc(self):\n        self.count += 1\n        return self.count",
    "deep_nest":       "def validate(cfg):\n    if cfg:\n        for key in cfg:\n            if key in cfg[key]:\n                for v in cfg[key][key]:\n                    return v\n    return None",
    "vuln_sqli":       "def user(name):\n    return db.execute('SELECT * FROM users WHERE name = ' + name)",
    "vuln_xss":        "def render(name):\n    return '<div>' + name + '</div>'",
    "weak_crypto":     "def enc(x):\n    from Crypto.Cipher import DES\n    return DES.new(b'12345678').encrypt(x)",
    "mutate":          "def add_all(d, pairs):\n    for k, v in pairs:\n        d[k] = v\n    return d",
    "generator":       "def gen(n):\n    for i in range(n):\n        yield i * i",
    "fib_loop":        "def fib(n):\n    a, b = 0, 1\n    for _ in range(n):\n        a, b = b, a + b\n    return a",
    "matrix_mult":     "def matmul(A, B):\n    n = len(A)\n    C = [[0]*n for _ in range(n)]\n    for i in range(n):\n        for j in range(n):\n            for k in range(n):\n                C[i][j] += A[i][k]*B[k][j]\n    return C",
    "binary_add":      "def add_bin(a, b):\n    return bin(int(a,2) + int(b,2))[2:]",
    "dedupe":          "def dedupe(items):\n    return list(dict.fromkeys(items))",
    "chunk":           "def chunk(items, n):\n    return [items[i:i+n] for i in range(0, len(items), n)]",
}


def main():
    shapes = {}
    dims = set()
    for name, code in CORPUS.items():
        try:
            s = enriched_shape(code)
        except Exception as e:
            print(f"  [skip] {name}: {e}")
            continue
        shapes[name] = s
        dims |= set(s.keys())
    dims = sorted(dims)
    print(f"corpus: {len(shapes)} functions, union dims: {len(dims)}")

    # fixed-length matrix rows x cols
    names = list(shapes.keys())
    D = [[0.0]*len(dims) for _ in names]
    for i, nm in enumerate(names):
        for k, v in shapes[nm].items():
            D[i][dims.index(k)] = float(v)

    # per-dim family assignment
    def fam(k):
        for f in ("PRIM", "EFF", "FLOW", "IN:", "OUT:", "PROP", "VAL", "GRAPH", "TAINT", "PARAM", "VAR", "PARAM_COUNT", "VAR_COUNT", "TYPE_DIVERSITY", "UNTYPED", "MUTATION"):
            if k.startswith(f):
                return f
        return "OTHER"
    fams = [fam(k) for k in dims]
    from collections import Counter
    print("dim families:", dict(Counter(fams)))

    # nonzero density
    nnz = sum(1 for r in D for v in r if v != 0.0)
    total = len(names)*len(dims)
    print(f"sparsity: {100*(1-nnz/total):.1f}% zero (nnz={nnz}/{total})")

    # how many dims are nonzero across corpus
    col_nnz = [sum(1 for r in D if r[j] != 0.0) for j in range(len(dims))]
    always_zero = sum(1 for c in col_nnz if c == 0)
    dead_cols = [dims[j] for j, c in enumerate(col_nnz) if c == 0]
    print(f"dims never nonzero in corpus: {always_zero} {dead_cols[:20]}")

    # correlation of a few representative dims with each other (Pearson)
    import statistics
    def pearson(col_a, col_b):
        n = len(col_a)
        ma, mb = sum(col_a)/n, sum(col_b)/n
        cov = sum((col_a[i]-ma)*(col_b[i]-mb) for i in range(n))
        va = sum((x-ma)**2 for x in col_a)
        vb = sum((x-mb)**2 for x in col_b)
        if va == 0 or vb == 0: return None
        return cov/math.sqrt(va*vb)

    # L2 norm per sample ("shape magnitude")
    norms = [math.sqrt(sum(v*v for v in row)) for row in D]

    # candidate composite: cyclomatic-ish = PROP:BRANCHES + PROP:LOOPS (if present)
    print("\n--- sample norms (shape 'size') ---")
    for nm, nrm in sorted(zip(names, norms), key=lambda x: -x[1])[:8]:
        print(f"  {nm:16s} L2={nrm:6.3f}")

    # Save matrix + metadata for deeper analysis
    out = {
        "corpus_size": len(names),
        "union_dims": len(dims),
        "dims": dims,
        "families": fams,
        "norms": dict(zip(names, norms)),
        "sparsity_pct": round(100*(1-nnz/total),1),
        "shapes": shapes,
    }
    path = os.path.join(os.path.dirname(__file__), '..', 'data', 'self_derive_matrix.json')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\nwrote {path}")

    # intrinsic dimensionality via effective rank (sqrt of trace-based participation ratio)
    # PR of eigenvalues of correlation matrix approx
    # quick effective rank: number of eigvals > 1% of max
    n = len(names)
    # center columns
    cols = []
    for j in range(len(dims)):
        col = [D[i][j] for i in range(n)]
        m = sum(col)/n
        cols.append([x-m for x in col])
    # covariance (dims x dims) — small enough
    cov = [[0.0]*len(dims) for _ in range(len(dims))]
    for a in range(len(dims)):
        for b in range(len(dims)):
            cov[a][b] = sum(cols[a][i]*cols[b][i] for i in range(n)) / (n-1)
    # trace-based participation ratio: (sum diag)^2 / sum sq
    tr = sum(cov[j][j] for j in range(len(dims)))
    tr2 = sum(cov[j][j]**2 for j in range(len(dims)))
    pr = (tr*tr)/tr2 if tr2 else 0
    print(f"\nparticipation ratio (effective intrinsic dim estimate): {pr:.1f} (of {len(dims)} nominal)")


if __name__ == "__main__":
    main()
