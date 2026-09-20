#!/usr/bin/env python
"""self_derive_selfanalysis.py — Use Morphe-chan on ITS OWN source to derive data.

Novel self-referential application: run the project analyzer over morphe-chan's
own src/code_shape and derive (a) a primitive-density profile (a "shape signature"
data table), (b) a derived formula: SHAPE_ENTROPY and a per-primitive share vector
computed from Morphe-chan's own composite shape, (c) cross-check which dims that
were 'constant/dead' at 28-sample corpus scale are actually ALIVE at real-project
scale — measuring how much of the small-corpus dim-reduction is corpus bias vs real.
"""
import sys, os, math, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from code_shape.core.multilingual_project import analyze_project

res = analyze_project('src/code_shape')
pl = res['per_language']['python']
prims = pl['primitives']
funcs = pl['functions']
files = pl['files']
total_prim = sum(prims.values())

print("=== Morphe-chan analyzing itself (src/code_shape) ===")
print(f"files={files} functions={funcs} total_primitive_occurrences={total_prim}")
print(f"composite_shape={res['composite_shape']}")

# 1. primitive density / share table
dens = {k: round(v/funcs, 3) for k, v in sorted(prims.items(), key=lambda x: -x[1])}
print("\n--- primitive density (count per function) ---")
for k, v in dens.items():
    print(f"  {k:14s} {v:7.3f}")

# 2. Shannon entropy of the primitive share distribution (richness of own shape)
shares = [v/total_prim for v in prims.values() if v > 0]
H = -sum(p*math.log2(p) for p in shares)
maxH = math.log2(len(shares))
print(f"\nprimitive-type entropy H = {H:.3f} bits (max {maxH:.2f}) over {len(shares)} primitive types")

# 3. derived concentration ratios (novel self-formulas)
top1 = max(prims.values())/total_prim            # ASSIGN dominance
top3 = sum(sorted(prims.values(), reverse=True)[:3])/total_prim
evenness = H/maxH if maxH else 0
print(f"top-1 primitive share = {top1:.1%} (dominance)")
print(f"top-3 primitive share = {top3:.1%}")
print(f"evenness = H/maxH = {evenness:.3f} (1=uniform, 0=mono)")


# 4. cross-check: dims 'constant' at 28-sample scale but alive at project scale
alive_here = set(k for k, v in prims.items() if v > 0)
corpus_dead = {"ARITH_MOD", "COMPARE_GE", "COMPARE_NE", "FILTER", "SORT", "COMPARE_GT", "COMPARE_LT"}
confirmed_dead = corpus_dead - alive_here
revived = corpus_dead & alive_here
print("\n=== corpus-scale 'dead' dims vs real-project scale ===")
print(f"confirmed still-dead at project scale: {sorted(confirmed_dead)}")
print(f"REVIVED at project scale (were corpus bias, not truly dead): {sorted(revived)}")
print("=> dim-reduction 'dead dims' are CORPUS-DEPENDENT; dropping them is risky unless ")
print("   validated on a large diverse corpus. The r=1.00 exact redundancies are safe (structural).")

# persist derived self-data
out = {
    "target": "morphe-chan/src/code_shape",
    "files": files, "functions": funcs, "total_primitives": total_prim,
    "composite_shape": res['composite_shape'],
    "primitive_density_per_function": dens,
    "entropy_bits": round(H,3), "evenness": round(evenness,3),
    "top1_share": round(top1,4), "top3_share": round(top3,4),
}
with open(os.path.join(os.path.dirname(__file__), '..', 'data', 'self_analysis_profile.json'), 'w') as f:
    json.dump(out, f, indent=2)
print("\nwrote data/self_analysis_profile.json")
