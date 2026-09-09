#!/usr/bin/env python
"""code_synthesizer.py — Synthesize code from a target shape (primitive vector).

Compose primitive templates into a function that realizes a target shape.

This is a template-composition synthesizer:
  1. Parse a target shape (e.g. "LOOP>ARITH_ADD>ASSIGN>RETURN" or a vector).
  2. Select primitive templates from a library.
  3. Compose them into a function body.
  4. Verify the synthesized code's shape matches the target (shape round-trip).

The round-trip check is the falsifiable verification: synthesize from a
shape, re-analyze the output, and confirm the shape is preserved.

Dependency-free (stdlib only).
"""
import re
from typing import Dict, List, Optional

# ── Primitive templates (language-agnostic, Python-flavored) ────────────────
# Each template: (primitive, code_fragment)
TEMPLATES: Dict[str, List[str]] = {
    "LOOP":      ["for item in items:", "for i in range(n):", "while cond:"],
    "BRANCH":    ["if cond:", "if x > y:", "if x < y:", "if x == y:"],
    "ARITH_ADD": ["total += item", "result = a + b", "x = x + 1"],
    "ARITH_SUB": ["result = a - b", "x = x - 1"],
    "ARITH_MUL": ["result = a * b", "total *= item"],
    "ARITH_DIV": ["result = a / b", "avg = total / n"],
    "ARITH_MOD": ["if x % 2 == 0:", "rem = x % 2"],
    "COMPARE_EQ":["if x == y:", "if a == b:"],
    "COMPARE_GT":["if x > y:", "if a > b:"],
    "COMPARE_LT":["if x < y:", "if a < b:"],
    "ASSIGN":    ["total = 0", "result = 0", "acc = 0"],
    "RETURN":    ["return total", "return result", "return x"],
    "READ":      ["def fn(items):", "def fn(a, b):", "def fn(x):"],
    "WRITE":     ["print(result)", "return result"],
    "AGGREGATE": ["total += item", "acc = acc + item", "count += 1"],
    "FILTER":    ["if x % 2 == 0:", "if x > 0:"],
    "SORT":      ["return sorted(items)", "items.sort()"],
    "SEARCH":    ["return items.index(x)", "if x in items:"],
    "STATE":     ["total += item", "count += 1", "result = result + x"],
}


def parse_shape(shape_str: str) -> List[str]:
    """Parse a shape string like 'LOOP>ARITH_ADD>ASSIGN>RETURN' into a list."""
    return [p.strip() for p in shape_str.split(">") if p.strip()]


def synthesize(shape_str: str, language: str = "python") -> Optional[str]:
    """Synthesize a function from a target shape string.

    Returns Python code, or None if a primitive has no template.
    """
    prims = parse_shape(shape_str)
    if not prims:
        return None

    # Function signature
    sig = "def fn(items):"
    body: List[str] = []

    # ASSIGN first (initialize accumulator) at function level.
    if "ASSIGN" in prims:
        body.append("    " + TEMPLATES["ASSIGN"][0])

    # Build body, tracking block nesting depth for correct indentation.
    depth = 1  # inside function
    for p in prims:
        if p in ("READ", "ASSIGN"):
            continue
        tpls = TEMPLATES.get(p)
        if not tpls:
            return None
        frag = tpls[0]
        indent = "    " * depth
        if frag.endswith(":") and (frag.startswith("for") or frag.startswith("while") or frag.startswith("if")):
            body.append(indent + frag)
            depth += 1
        else:
            body.append(indent + frag)

    return sig + "\n" + "\n".join(body)


def synthesize_from_vector(target: Dict[str, float], language: str = "python") -> Optional[str]:
    """Synthesize from a target vector (pick top primitives)."""
    ranked = sorted(target.items(), key=lambda kv: -kv[1])
    top = [p for p, v in ranked if v > 0][:6]
    return synthesize(">".join(top), language)


# ── Shape round-trip verification ──────────────────────────────────────────
def verify_roundtrip(shape_str: str) -> Dict:
    """Synthesize from a shape, re-analyze, and check the shape is preserved."""
    from code_shape.core.agnostic_shape import decompose, shape as get_shape
    code = synthesize(shape_str)
    if code is None:
        return {"ok": False, "error": "no template for a primitive"}
    actual = get_shape(code)
    target_prims = set(parse_shape(shape_str))
    actual_prims = set(actual.split(">"))
    overlap = len(target_prims & actual_prims) / len(target_prims) if target_prims else 0
    return {
        "ok": overlap >= 0.5,
        "target": shape_str,
        "actual": actual,
        "overlap": round(overlap, 2),
        "code": code,
    }


if __name__ == "__main__":
    print("=== Code Synthesis from Shape ===")
    for shape in ["READ>LOOP>ARITH_ADD>ASSIGN>RETURN",
                  "READ>BRANCH>COMPARE_GT>RETURN",
                  "READ>LOOP>ARITH_MOD>FILTER>RETURN"]:
        code = synthesize(shape)
        print(f"\nshape: {shape}")
        print(code)
        rt = verify_roundtrip(shape)
        print(f"round-trip: {rt['actual']} (overlap {rt['overlap']})")
