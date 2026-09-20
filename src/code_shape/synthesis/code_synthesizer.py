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
    "ARITH_ADD": ["result = a + b", "x = x + 1"],
    "ARITH_SUB": ["result = a - b", "x = x - 1"],
    "ARITH_MUL": ["result = a * b", "total *= item"],
    "ARITH_DIV": ["result = a / b", "avg = total / n"],
    "ARITH_MOD": ["if x % 2 == 0:", "rem = x % 2"],
    "COMPARE_EQ":["if x == y:", "if a == b:"],
    "COMPARE_GT":["if x > y:", "if a > b:"],
    "COMPARE_LT":["if x < y:", "if a < b:"],
    "ASSIGN":    ["total = 0", "result = 0", "acc = 0"],
    "RETURN":    ["return total", "return result", "return x"],
    "READ":      ["data = open('f').read()", "data = read()", "data = input()"],
    "WRITE":     ["print(result)", "return result"],
    "AGGREGATE": ["total += item", "acc = acc + item", "count += 1"],
    "FILTER":    ["result = filter(items, pred)", "if x % 2 == 0:", "if x > 0:"],
    "SORT":      ["return sorted(items)", "items.sort()"],
    "SEARCH":    ["result = find(items, x)", "result = items.index(x)", "if x in items:"],
    "STATE":     ["total += item", "count += 1", "result = result + x"],
}

# JavaScript-flavored templates for the same primitives (language-aware synth; self-derived
# fix for the synthesizer ignoring its `language` arg). Kept parallel to TEMPLATES so the
# same shape string synthesizes into either Python or JS.
JS_TEMPLATES: Dict[str, List[str]] = {
    "LOOP":      ["for (const item of items) {", "for (let i = 0; i < n; i++) {", "while (cond) {"],
    "BRANCH":    ["if (cond) {", "if (x > y) {", "if (x < y) {", "if (x === y) {"],
    "ARITH_ADD": ["result = a + b", "x = x + 1"],
    "ARITH_SUB": ["result = a - b", "x = x - 1"],
    "ARITH_MUL": ["result = a * b", "total *= item"],
    "ARITH_DIV": ["result = a / b", "avg = total / n"],
    "ARITH_MOD": ["if (x % 2 === 0) {", "rem = x % 2"],
    "COMPARE_EQ":["if (x === y) {", "if (a === b) {"],
    "COMPARE_GT":["if (x > y) {", "if (a > b) {"],
    "COMPARE_LT":["if (x < y) {", "if (a < b) {"],
    "ASSIGN":    ["let total = 0", "let result = 0", "let acc = 0"],
    "RETURN":    ["return total;", "return result;", "return x;"],
    "READ":      ["const data = fs.readFileSync('f', 'utf8')", "const data = read()", "const data = input()"],
    "WRITE":     ["console.log(result)", "return result;"],
    "AGGREGATE": ["total += item", "acc = acc + item", "count += 1"],
    "FILTER":    ["result = items.filter(pred)", "if (x % 2 === 0) {", "if (x > 0) {"],
    "SORT":      ["return items.sort();", "items.sort();"],
    "SEARCH":    ["result = items.findIndex((x) => x === target)", "if (items.includes(x)) {"],
    "STATE":     ["total += item", "count += 1", "result = result + x"],
}


def _lang_kind(language: str) -> str:
    """Return the block-delimiter style: 'colon' (python/ruby) or 'brace' (js/c/...)."""
    return "colon" if language in ("python", "ruby", "go") else "brace"


def parse_shape(shape_str: str) -> List[str]:
    """Parse a shape string like 'LOOP>ARITH_ADD>ASSIGN>RETURN' into a list."""
    return [p.strip() for p in shape_str.split(">") if p.strip()]


def synthesize(shape_str: str, language: str = "python") -> Optional[str]:
    """Synthesize a function from a target shape string in a given language.

    Supports python (default) and js; the `language` arg is now honored (it was
    previously ignored, always emitting Python). Returns code, or None if a
    primitive has no template for the requested language.
    """
    prims = parse_shape(shape_str)
    if not prims:
        return None
    tpls_for = JS_TEMPLATES if language == "js" else TEMPLATES
    kind = _lang_kind(language)

    # Function signature + block close per language.
    if language == "js":
        sig = "function fn(items) {"
        close = "}"
        block_ender = "}"
    else:
        sig = "def fn(items):"
        close = ""
        block_ender = None
    body: List[str] = []

    # ASSIGN first (initialize accumulator) at function level.
    if "ASSIGN" in prims:
        body.append("    " + tpls_for["ASSIGN"][0])

    # Build body, tracking block nesting depth for correct indentation/close.
    depth = 1  # inside function
    for p in prims:
        if p == "ASSIGN":
            continue
        tpls = tpls_for.get(p)
        if not tpls:
            return None
        frag = tpls[0]
        indent = "    " * depth
        # block open: python/ruby use ':'-terminated keywords; js/brace use '{'
        is_block_open = frag.endswith(":") and (
            frag.startswith("for") or frag.startswith("while") or frag.startswith("if")
        ) if kind == "colon" else frag.rstrip().endswith("{")
        if is_block_open:
            body.append(indent + frag)
            depth += 1
        else:
            body.append(indent + frag)

    if language == "js":
        # close inner blocks (deepest->shallowest) then the function itself
        for d in range(depth - 1, -1, -1):
            body.append("    " * d + close)
        result = sig + "\n" + "\n".join(body)
        return result
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
