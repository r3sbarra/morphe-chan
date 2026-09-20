#!/usr/bin/env python
"""fixed_shape.py — Fixed-length, rename-invariant re-embedding of the
enriched shape (self-derived; see experiments/self_derive_* and
research/SELF_DERIVATION_2026-09-20.md).

Problem it solves (verified): `enriched_shape` is variable-length because it
emits per-variable-NAME dims `PARAM:<name>:<TYPE>` / `VAR:<name>:<TYPE>` plus a
conditional `TAINT:PARAM`; across a corpus the key union grows unboundedly
(179 dims from 28 samples), ~85% sparse, and every vector is L2-normalized to
the unit sphere (so magnitude is meaningless and full-space cosine saturates).

This module projects the enriched vector onto a FIXED coordinate system:
  - the name-INVARIANT global dims (GLOBAL_KEYS, kept at per-primitive
    granularity — the self-derived finding is that the discriminating signal
    lives WITHIN primitive families, so we do NOT coarse-grain to family totals),
  - plus fixed per-TYPE and per-ROLE aggregate slots that collapse the
    variable-name dims (rename-invariant by construction).

Result: a fixed-length vector valid for cosine across arbitrary snippets, with
clone detection preserved and (in the reduction experiments) better
discrimination than the full sparse space. Exposed as a Morphe-chan feature so
downstream (embeddings, similarity, ML features) can operate in one
rename-invariant space.

Dependency-free (stdlib only).
"""
import math
from typing import Dict

from .enriched_shape import enriched_shape
from .shape_metrics import GLOBAL_KEYS

# Fixed type vocabulary from variable_shape's inferred types.
TYPE_SLOTS = ["NUM", "STR", "LIST", "DICT", "CALLABLE", "BOOL", "UNKNOWN", "MIXED"]
ROLE_SLOTS = ["IN", "OUT", "INOUT"]

# Canonical dimension order: global dims first, then PARAM_TYPE / PARAM_ROLE /
# VAR_TYPE / VAR_ROLE aggregate slots.
FIXED_DIMS = (
    list(GLOBAL_KEYS)
    + [f"PARAM\uf8fftype:{t}" for t in TYPE_SLOTS]
    + [f"PARAM\uf8ffrole:{r}" for r in ROLE_SLOTS]
    + [f"VAR\uf8fftype:{t}" for t in TYPE_SLOTS]
    + [f"VAR\uf8ffrole:{r}" for r in ROLE_SLOTS]
)


def _slot_key(dim_key: str, prefix: str):
    """Given a raw dim like 'PARAM:x:LIST' / 'VAR:total:ROLE:OUT', return
    ('type', slot) or ('role', slot), or None if not a name-dependent dim."""
    if not dim_key.startswith(prefix):
        return None
    parts = [p for p in dim_key[len(prefix):].split(":") if p]
    if not parts:
        return None
    for i, p in enumerate(parts):
        if p == "ROLE" and i + 1 < len(parts):
            r = parts[i + 1]
            if r in ROLE_SLOTS:
                return ("role", r)
    if len(parts) >= 2:
        t = parts[1]
        if t in TYPE_SLOTS:
            return ("type", t)
    return ("type", "UNKNOWN")


def fixed_enriched_shape(code: str, lang: str = "python") -> Dict[str, float]:
    """Fixed-length, rename-invariant enriched shape (defaults to unit-L2,
    matching Morphe-chan convention)."""
    raw = enriched_shape(code, lang)
    out: Dict[str, float] = {}
    # name-invariant global dims, at per-primitive granularity
    for k in GLOBAL_KEYS:
        out[k] = float(raw.get(k, 0.0))
    # collapse variable-name dims into fixed type/role slots
    for prefix in ("PARAM", "VAR"):
        for kind, slot in ([("type", t) for t in TYPE_SLOTS]
                           + [("role", r) for r in ROLE_SLOTS]):
            total = 0.0
            for k, v in raw.items():
                sk = _slot_key(k, prefix + ":")
                if sk and sk[0] == kind and sk[1] == slot:
                    total += float(v)
            out[f"{prefix}\uf8ff{kind}:{slot}"] = total
    # unit-L2 normalize (direction-only, same convention as enriched_shape)
    norm = math.sqrt(sum(v * v for v in out.values()))
    if norm == 0:
        return {k: 0.0 for k in FIXED_DIMS}
    return {k: round(out.get(k, 0.0) / norm, 6) for k in FIXED_DIMS}


def fixed_dim_count() -> int:
    """Number of dims in the fixed, rename-invariant embedding."""
    return len(FIXED_DIMS)


# Structural r=1.00 redundant groups (self-derived, definitionally identical
# signals — safe to merge; see self_derive_dimreduction.py). These are the ONLY
# dims proven mergeable without hurting clone detection (unsupervised PCA is NOT
# safe — see self_derive_intrinsic.py negative result).
STRUCTURAL_MERGES = {
    "VAL:RISK": "VAL:SEVERITY",
    "PARAM_COUNT": "PROP:INPUTS",
    "PARAM\uf8ffrole:IN": "PROP:INPUTS",
    "VAR\uf8ffrole:OUT": "VAR_COUNT",
    "PROP:SIDE_EFFECTS": "PRIM:WRITE",
    "GRAPH:DATA_EDGES": "GRAPH:CALLS",
    "GRAPH:MAX_FANOUT": "GRAPH:CALLS",
    "GRAPH:MAX_FANIN": "GRAPH:CALLS",
    "GRAPH:RECURSION": "GRAPH:CALLS",
    "GRAPH:CYCLES": "GRAPH:CALLS",
    "GRAPH:BRANCHES": "GRAPH:CALLS",
    "GRAPH:LOOPS": "GRAPH:CALLS",
}


def merged_enriched_shape(code: str, lang: str = "python") -> Dict[str, float]:
    """Fixed-length + structurally-merged enriched shape.

    Collapses the r=1.00 definitionally-redundant dims (verified safe: clone
    similarity is preserved at ~0.99+, unrelated functions stay well-separated)
    for a smaller fixed embedding. Fewer dims than `fixed_enriched_shape` with
    equivalent clone/discrimination behavior.
    """
    v = fixed_enriched_shape(code, lang)
    out: Dict[str, float] = {}
    for k, val in v.items():
        canon = STRUCTURAL_MERGES.get(k, k)
        out[canon] = out.get(canon, 0.0) + val
    n = math.sqrt(sum(x * x for x in out.values()))
    if n > 0:
        out = {k: round(x / n, 6) for k, x in out.items()}
    return out


if __name__ == "__main__":
    a = fixed_enriched_shape("def add(a, b):\n    return a + b")
    b = fixed_enriched_shape("def sum_list(nums):\n    total = 0\n    for n in nums:\n        total += n\n    return total")
    c = fixed_enriched_shape("def accumulate(entries):\n    acc = 0\n    for e in entries:\n        acc += e\n    return acc")
    print(f"fixed dims: {fixed_dim_count()}")
    print(f"add -> loop (unrelated-ish) cosine via dims: {len(a)} vs {len(b)} keys equal")
    keys = list(a.keys())
    def cos(x, y):
        return sum(v * y.get(k, 0) for k, v in x.items())
    print(f"  <add, loop_sum>      = {cos(a, b):.3f}")
    print(f"  <loop, rename-clone> = {cos(b, c):.3f}  (should be ~1.0: rename-invariant)")
