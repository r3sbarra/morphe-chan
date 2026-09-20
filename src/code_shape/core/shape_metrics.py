#!/usr/bin/env python
"""shape_metrics.py — NEW shape metrics derived from Morphe-chan's own vector
geometry (self-derived research, see experiments/self_derive_*).

Adds rename-invariant richness metrics that are NOT present in the 45-62 dim
enriched shape today. Derivation (verified in experiments/self_derive_*):
  - The raw enriched vector is variable-length (name-dependent) and unit-normalized,
    so L2 magnitude carries no info; richness lives in the *distribution* of the
    name-INVARIANT dims.
  - SHAPE_ENTROPY (Shannon entropy of the L1-normalized name-invariant dim weights)
    ranks code complexity/richness sensibly: fact=4.79, loop=4.73, bsearch=4.58,
    matmul=4.24, simple-add=3.78 (verified).
  - SHAPE_SPREAD = fraction of name-invariant dims that are nonzero (density).
  - SHAPE_SKEW   = (max - mean)/std of weights (concentration/dominance).

These are computed here and emitted as VAL:SHAPE_* dims by enriched_shape so
downstream (efficiency, vuln, pattern) analysis and any embedding can consume them.

Dependency-free (stdlib only). Uses the fixed GLOBAL_KEYS from the self-derived
name-invariant embedding to stay rename-invariant.
"""
import math

# Name-INVARIANT global dims (excludes PARAM:<name>:/VAR:<name>: name-dependent dims).
# Same set used by experiments/self_derive_fixedembed.py.
GLOBAL_KEYS = [
    "PRIM:LOOP","PRIM:BRANCH","PRIM:RECURSE","PRIM:ARITH_ADD","PRIM:ARITH_SUB",
    "PRIM:ARITH_MUL","PRIM:ARITH_DIV","PRIM:ARITH_MOD","PRIM:COMPARE_EQ",
    "PRIM:COMPARE_NE","PRIM:COMPARE_GT","PRIM:COMPARE_LT","PRIM:COMPARE_GE",
    "PRIM:COMPARE_LE","PRIM:ASSIGN","PRIM:RETURN","PRIM:READ","PRIM:WRITE",
    "PRIM:AGGREGATE","PRIM:FILTER","PRIM:SORT","PRIM:SEARCH","PRIM:STATE",
    "EFF:EFF_COMPLEXITY","EFF:EFF_LOOPS","EFF:EFF_NESTING","EFF:EFF_METHOD_CALLS",
    "EFF:EFF_THREADED","EFF:EFF_ALLOC","EFF:EFF_RECURSION","EFF:EFF_REPEATED",
    "FLOW:ARITH","IN:PARAM","IN:CONSTANT","OUT:RETURN",
    "VAL:FLOW_DEPTH","VAL:BRANCHING","VAL:COUPLING","VAL:RISK","VAL:SEVERITY",
    "PROP:NUM","PROP:LIST","PROP:DICT","PROP:MUTABLE","PROP:TRANSFORM",
    "PROP:BRANCHES","PROP:LOOPS","PROP:HANDLES_ERRORS","PROP:INPUTS","PROP:OUTPUTS",
    "PROP:SIDE_EFFECTS","PROP:IO",
    "GRAPH:FUNCTIONS","GRAPH:CALLS","GRAPH:DATA_EDGES","GRAPH:MAX_FANOUT",
    "GRAPH:MAX_FANIN","GRAPH:AVG_VARS","GRAPH:AVG_EDGES","GRAPH:COMPLEXITY",
    "GRAPH:BRANCHES","GRAPH:LOOPS","GRAPH:RECURSION","GRAPH:CYCLES",
    "TAINT:PARAM",
    "PARAM_COUNT","VAR_COUNT","TYPE_DIVERSITY","UNTYPED","MUTATION",
    # Newly-wired STATE/DATA/CTRL/IFACE/RES dims (new_shape_dims) — carry
    # verified signal (cyclomatic, statefulness, exception handling, arity).
    "STATE:MUTATES","STATE:GLOBAL","STATE:PURE","STATE:INSTANCE",
    "DATA:NESTED","DATA:HETEROGENEOUS","DATA:LARGE","DATA:TRANSFORM",
    "CTRL:CYCLOMATIC","CTRL:DEEP_NESTING","CTRL:EARLY_RETURNS","CTRL:EXCEPTIONS",
    "IFACE:ARITY","IFACE:TYPED","IFACE:DEFAULTS","IFACE:RETURN_TYPE","IFACE:VARIADIC",
    "RES:IO","RES:NETWORK","RES:MEMORY","RES:COMPUTE","RES:CONCURRENCY",
]


def shape_metrics(vec: dict) -> dict:
    """Return {'VAL:SHAPE_ENTROPY':..., 'VAL:SHAPE_SPREAD':..., 'VAL:SHAPE_SKEW':...}
    computed over the name-invariant GLOBAL_KEYS present in the (raw) enriched vec.

    vec should be the RAW (pre-L2-normalization) enriched shape so the entropy is
    computed on actual signal magnitudes. All three metrics are dimensionless and
    rename-invariant.
    """
    vals = [abs(vec.get(k, 0.0)) for k in GLOBAL_KEYS]
    vals = [v for v in vals if v != 0.0]
    n = len(GLOBAL_KEYS)
    if not vals or n == 0:
        return {"VAL:SHAPE_ENTROPY": 0.0, "VAL:SHAPE_SPREAD": 0.0, "VAL:SHAPE_SKEW": 0.0}
    total = sum(vals)
    if total <= 0:
        return {"VAL:SHAPE_ENTROPY": 0.0, "VAL:SHAPE_SPREAD": float(len(vals)) / n, "VAL:SHAPE_SKEW": 0.0}
    # Shannon entropy (bits) over L1-normalized present dims
    p = [v / total for v in vals]
    H = -sum(x * math.log2(x) for x in p)
    spread = float(len(vals)) / n
    mean = total / n
    sd = math.sqrt(sum((v - mean) ** 2 for v in (vals + [0.0] * (n - len(vals)))) / n) if n > 1 else 0.0
    mx = max(vals)
    skew = (mx - mean) / sd if sd else 0.0
    return {
        "VAL:SHAPE_ENTROPY": round(H, 4),
        "VAL:SHAPE_SPREAD": round(spread, 4),
        "VAL:SHAPE_SKEW": round(skew, 4),
    }


if __name__ == "__main__":
    from code_shape.core.enriched_shape import _raw_enriched
    for code in [
        "def add(a, b):\n    return a + b",
        "def fact(n):\n    if n <= 1:\n        return 1\n    return n * fact(n - 1)",
        "def mm(A, B):\n    n = len(A)\n    return [[sum(A[i][k]*B[k][j] for k in range(n)) for j in range(n)] for i in range(n)]",
    ]:
        raw = _raw_enriched(code)
        print(shape_metrics(raw))
