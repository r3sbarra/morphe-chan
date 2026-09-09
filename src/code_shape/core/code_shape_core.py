#!/usr/bin/env python
"""code_shape_core.py — Code-agnostic core with language adapters + recursive
primitive decomposition.

The core of the shape research, made truly code-agnostic:

1. LANGUAGE ADAPTERS — each language has an adapter in `adapters/` that maps
   its syntax to a COMMON primitive vocabulary. The core is language-agnostic;
   adapters handle syntax. Add a language by adding a file to `adapters/`.

2. RECURSIVE DECOMPOSITION — a function's TRUE shape is not just its own
   primitives, but the recursive composition of its callees' shapes. A function
   that calls a loop-heavy helper inherits that loop structure.

Dependency-free (stdlib only).
"""
import math
from typing import Dict, List

from ..adapters import ADAPTERS, PRIMITIVES, LanguageAdapter


def get_adapter(code: str, lang: str = None) -> LanguageAdapter:
    """Get the adapter for a language (or detect from code)."""
    if lang:
        for a in ADAPTERS:
            if a.name == lang.lower():
                return a
    # detect: score by detect() hits, prefer more specific
    best = None
    best_score = 0
    for a in ADAPTERS:
        if a.detect(code):
            score = 1 + (0.5 if a.name in ("typescript", "cpp", "csharp") else 0)
            if score > best_score:
                best = a
                best_score = score
    return best or ADAPTERS[0]  # fallback to Python


def recursive_shape(code: str, lang: str = None, depth: int = 0, max_depth: int = 5) -> Dict[str, int]:
    """Recursively decompose a program into its TRUE shape.

    A function's shape = its own primitives + the recursive composition of its
    callees' shapes (weighted by depth). This captures the transitive structure.
    """
    adapter = get_adapter(code, lang)
    functions = adapter.extract_functions(code)
    if not functions:
        return adapter.decompose(code)

    total: Dict[str, int] = {p: 0 for p in PRIMITIVES}
    for name, body in functions.items():
        own = adapter.decompose(body)
        for p, c in own.items():
            total[p] += c
        if depth < max_depth:
            for callee in adapter.extract_calls(body):
                if callee in functions and callee != name:
                    callee_shape = recursive_shape(functions[callee], lang, depth + 1, max_depth)
                    for p, c in callee_shape.items():
                        total[p] += int(c * (0.5 ** (depth + 1)))
    return total


def true_shape_vector(code: str, lang: str = None) -> Dict[str, float]:
    """Normalized TRUE shape vector (recursive decomposition)."""
    counts = recursive_shape(code, lang)
    norm = math.sqrt(sum(v * v for v in counts.values()))
    if norm == 0:
        return {p: 0.0 for p in PRIMITIVES}
    return {p: round(counts[p] / norm, 4) for p in PRIMITIVES}


def cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    keys = set(a) | set(b)
    dot = sum(a.get(k, 0) * b.get(k, 0) for k in keys)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def true_similarity(code_a: str, code_b: str, lang_a: str = None, lang_b: str = None) -> float:
    """Cosine similarity between two TRUE shape vectors."""
    return cosine(true_shape_vector(code_a, lang_a), true_shape_vector(code_b, lang_b))


def shape(code: str, lang: str = None) -> str:
    """Human-readable shape = dominant primitives."""
    counts = recursive_shape(code, lang)
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    top = [p for p, c in ranked if c > 0][:5]
    return ">".join(top) if top else "EMPTY"


def list_languages() -> List[str]:
    """List all supported languages."""
    return [a.name for a in ADAPTERS]


# ── Self-test ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    py = "def sum_list(nums):\n    total = 0\n    for n in nums:\n        total += n\n    return total"
    js = "function sumList(nums) {\n    let total = 0;\n    for (let n of nums) {\n        total += n;\n    }\n    return total;\n}"
    java = "int sumList(int[] nums) {\n    int total = 0;\n    for (int n : nums) {\n        total += n;\n    }\n    return total;\n}"

    print("=== Supported languages ===")
    print(", ".join(list_languages()))

    print("\n=== Adapter detection ===")
    for code, lang in [(py, "python"), (js, "javascript"), (java, "java")]:
        a = get_adapter(code, lang)
        print(f"  {lang:10s} -> adapter: {a.name}")

    print("\n=== True shape (recursive) ===")
    print(f"  py sum:   {shape(py, 'python')}")
    print(f"  js sum:   {shape(js, 'javascript')}")
    print(f"  java sum: {shape(java, 'java')}")

    print("\n=== Cross-language true similarity ===")
    print(f"  py vs js:   {true_similarity(py, js, 'python', 'javascript'):.3f}")
    print(f"  py vs java: {true_similarity(py, java, 'python', 'java'):.3f}")
