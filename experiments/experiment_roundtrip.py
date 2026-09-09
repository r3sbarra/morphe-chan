#!/usr/bin/env python
"""experiment_roundtrip.py — Decompose-assemble round-trip fidelity.
  1. DECOMPOSE code to its shape (primitive vector)
  2. ASSEMBLE code back from the shape (via the synthesizer)
  3. MEASURE how much structure is preserved (round-trip fidelity)

This validates whether the shape is a faithful intermediate representation:
if decompose(assemble(decompose(code))) ≈ decompose(code), the shape captures
the essential structure.

Also tests shape-based code search: index a set of functions by shape, retrieve
the most similar to a query (behavioral code search).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from code_shape.core.code_shape_core import shape, true_shape_vector, true_similarity
from code_shape.synthesis.code_synthesizer import synthesize, verify_roundtrip


def roundtrip_fidelity(code: str, lang: str = "python") -> dict:
    """Decompose -> assemble -> re-decompose, measure shape preservation."""
    # 1. decompose
    orig_shape = shape(code, lang)
    orig_vec = true_shape_vector(code, lang)
    # 2. assemble from the shape (use the dominant primitives as the target)
    target = ">".join(orig_shape.split(">")[:4])  # top 4 primitives
    assembled = synthesize(target)
    if assembled is None:
        return {"ok": False, "error": "synthesis failed", "orig_shape": orig_shape}
    # 3. re-decompose the assembled code
    new_shape = shape(assembled, lang)
    new_vec = true_shape_vector(assembled, lang)
    # 4. measure fidelity: how much of the original shape is in the assembled?
    orig_prims = set(orig_shape.split(">"))
    new_prims = set(new_shape.split(">"))
    overlap = len(orig_prims & new_prims) / len(orig_prims) if orig_prims else 0
    sim = true_similarity(code, assembled, lang, lang)
    return {
        "ok": True,
        "orig_shape": orig_shape,
        "assembled_shape": new_shape,
        "primitive_overlap": round(overlap, 2),
        "vector_similarity": round(sim, 2),
        "assembled_code": assembled,
    }


def shape_search(index: list, query: str, lang: str = "python", top_k: int = 3) -> list:
    """Search a code index by shape similarity (behavioral code search)."""
    scored = []
    for code in index:
        s = true_similarity(query, code, lang, lang)
        scored.append((s, code))
    scored.sort(key=lambda x: -x[0])
    return scored[:top_k]


if __name__ == "__main__":
    print("=== Round-trip fidelity (decompose -> assemble -> re-decompose) ===")
    samples = {
        "sum": "def sum_list(nums):\n    total = 0\n    for n in nums:\n        total += n\n    return total",
        "max": "def max2(a, b):\n    if a > b:\n        return a\n    return b",
        "evens": "def evens(nums):\n    return [n for n in nums if n % 2 == 0]",
    }
    for name, code in samples.items():
        rt = roundtrip_fidelity(code)
        print(f"\n{name}: orig={rt['orig_shape']} assembled={rt['assembled_shape']} "
              f"overlap={rt['primitive_overlap']} sim={rt['vector_similarity']}")
        if rt["ok"]:
            print(f"  assembled:\n{rt['assembled_code']}")

    print("\n=== Shape-based code search (behavioral retrieval) ===")
    index = [
        "def sum_list(nums):\n    total = 0\n    for n in nums:\n        total += n\n    return total",
        "def add(a, b):\n    return a + b",
        "def max2(a, b):\n    if a > b:\n        return a\n    return b",
        "def evens(nums):\n    return [n for n in nums if n % 2 == 0]",
        "def sort_asc(arr):\n    return sorted(arr)",
    ]
    query = "def total(values):\n    acc = 0\n    for v in values:\n        acc += v\n    return acc"
    results = shape_search(index, query)
    print(f"query: {query.splitlines()[0]}")
    for s, code in results:
        print(f"  sim={s:.3f}: {code.splitlines()[0]}")
