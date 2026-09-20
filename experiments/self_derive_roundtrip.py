#!/usr/bin/env python
"""self_derive_roundtrip.py — Derive round-trip fidelity data from Morphe-chan's
OWN synthesizer: synthesize code from a target shape vector, re-analyze, and
measure how much of the shape survives. This quantifies the consistency between
Morphe-chan's synthesis and analysis components (a self-consistency data table).

Also cross-language: synthesize a shape in each language the synthesizer
supports, re-analyze in THAT language, and check shape preservation — deriving
per-language synthesis fidelity (which languages preserve more shape).
"""
import sys, os, math, itertools
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from code_shape.synthesis.code_synthesizer import synthesize, verify_roundtrip, parse_shape
from code_shape.core.code_shape_core import get_adapter

# All single primitives + a set of representative composite shapes
SINGLES = ["ASSIGN","RETURN","READ","WRITE","ARITH_ADD","ARITH_SUB","COMPARE_GT",
           "LOOP","BRANCH","AGGREGATE","SEARCH","STATE"]
COMPOSITES = [
    "READ>LOOP>ARITH_ADD>ASSIGN>RETURN",
    "READ>BRANCH>COMPARE_GT>RETURN",
    "READ>LOOP>ARITH_MOD>FILTER>RETURN",
    "LOOP>COMPARE_EQ>BRANCH>RETURN",
    "READ>AGGREGATE>ARITH_ADD>RETURN",
]

print("=== single-primitive synthesis fidelity (python) ===")
fails = []
for p in SINGLES:
    try:
        code = synthesize(p)
        if code is None:
            print(f"  {p:12s} NO TEMPLATE"); continue
        rt = verify_roundtrip(p)
        if not rt["ok"]:
            fails.append((p, rt["actual"]))
        print(f"  {p:12s} actual={rt['actual']:30s} overlap={rt['overlap']}")
    except Exception as e:
        print(f"  {p:12s} ERR {e}")
if fails:
    print("  SINGLE-PRIMITIVE FAILURES:", fails)

print("\n=== composite-shape round-trip fidelity (python) ===")
for s in COMPOSITES:
    rt = verify_roundtrip(s)
    status = "OK " if rt["ok"] else "FAIL"
    print(f"  [{status}] {s}\n        -> actual={rt['actual']} overlap={rt['overlap']}")

# Cross-language synthesis fidelity
print("\n=== cross-language synthesis fidelity ===")
LANGS = ["python","js","go","java","rust","ruby"]
for lang in LANGS:
    ad = get_adapter(lang, lang)
    ok_c = 0
    total = 0
    examples = {}
    for s in COMPOSITES:
        try:
            code = synthesize(s, lang)
        except Exception as e:
            code = None
        if code is None:
            examples[s] = "NO-TEMPLATE"
            continue
        total += 1
        try:
            actual_shape = ad.shape(code) if hasattr(ad, "shape") else None
        except Exception:
            actual_shape = None
        # fall back to agnostic decompose->shape
        from code_shape.core.agnostic_shape import decompose, shape as gshape
        try:
            actual = gshape(code)
        except Exception as e:
            actual = "ERR:" + str(e)
        target = set(parse_shape(s))
        actual_set = set(actual.split(">")) if isinstance(actual, str) else set()
        overlap = len(target & actual_set)/len(target) if target else 0
        if overlap >= 0.5:
            ok_c += 1
        examples[s] = f"{actual} ov={overlap:.2f}"
    print(f"  {lang:8s} fidelity={ok_c}/{total} {examples}")

print("\nwrote round-trip fidelity data (above)")
