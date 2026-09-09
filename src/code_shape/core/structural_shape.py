#!/usr/bin/env python
"""structural_shape.py — Structural shape (AST-like, preserves nesting/order).
COUNT vector, represent code as a TREE of primitives that preserves NESTING
and ORDERING.

A structural shape is a tree:
  node = {primitive, children: [node, ...]}

  e.g. sum:
    ASSIGN
    LOOP
      AGGREGATE
    RETURN

This preserves the structural arrangement that the flat shape loses, enabling
faithful assembly (translation + round-trip).

Dependency-free (stdlib only).
"""
import re
from typing import Dict, List, Optional

# ── Structural shape extraction (indentation-based) ────────────────────────
# Map a line to a primitive based on its content.
def _classify_line(line: str) -> str:
    s = line.strip()
    if re.match(r"(for|while)\b", s):
        return "LOOP"
    if re.match(r"(if|elif|else|switch|case)\b", s):
        return "BRANCH"
    if re.match(r"(def|function|func|fun)\b", s):
        return "DEF"
    if re.match(r"return\b", s):
        return "RETURN"
    if re.match(r"(print|console\.log|puts|echo|println)\b", s):
        return "WRITE"
    if re.match(r"(input|read|get|open)\b", s):
        return "READ"
    if re.search(r"\+=", s) or re.search(r"=\s*\w+\s*\+", s):
        return "AGGREGATE"
    if re.search(r"\+", s):
        return "ARITH_ADD"
    if re.search(r"\*", s):
        return "ARITH_MUL"
    if re.search(r"<|>|==|!=", s):
        return "COMPARE"
    if re.search(r"=\s*0|=\s*\[|=\s*\{", s):
        return "ASSIGN"
    if re.search(r"\.append|\.push|\.add", s):
        return "STATE"
    if re.search(r"sort|sorted", s):
        return "SORT"
    if re.search(r"find|index|contains|search", s):
        return "SEARCH"
    if re.search(r"filter|where", s):
        return "FILTER"
    return "EXPR"


def structural_shape(code: str) -> Dict:
    """Extract the structural shape (tree of primitives) from code.

    Returns a tree: {primitive, children: [...]}. Indentation determines nesting.
    """
    lines = code.splitlines()
    # build a stack of (indent, node)
    root = {"primitive": "ROOT", "children": []}
    stack = [(0, root)]
    for line in lines:
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        prim = _classify_line(line)
        node = {"primitive": prim, "children": []}
        # pop stack to find parent (last node with indent < current)
        while stack and stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1] if stack else root
        parent["children"].append(node)
        stack.append((indent, node))
    return root


def shape_to_string(node: Dict, depth: int = 0) -> str:
    """Serialize a structural shape to a string (for comparison)."""
    prim = node["primitive"]
    if not node["children"]:
        return prim
    inner = ",".join(shape_to_string(c, depth + 1) for c in node["children"])
    return f"{prim}({inner})"


def structural_signature(code: str) -> str:
    """Human-readable structural shape signature."""
    return shape_to_string(structural_shape(code))


# ── Structural shape comparison ─────────────────────────────────────────────
def structural_similarity(code_a: str, code_b: str) -> float:
    """Compare two structural shapes (tree edit similarity)."""
    ta = structural_shape(code_a)
    tb = structural_shape(code_b)
    return _tree_sim(ta, tb)


def _tree_sim(a: Dict, b: Dict) -> float:
    """Recursive tree similarity: primitive match + child similarity."""
    if a["primitive"] != b["primitive"]:
        return 0.0
    if not a["children"] and not b["children"]:
        return 1.0
    # match children greedily (order-preserving)
    ca, cb = a["children"], b["children"]
    if not ca or not cb:
        return 0.0
    # dynamic programming LCS-like over children
    n, m = len(ca), len(cb)
    dp = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            match = _tree_sim(ca[i - 1], cb[j - 1])
            dp[i][j] = max(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1] + match)
    return dp[n][m] / max(n, m)


# ── Structural assembly (from shape tree to code) ──────────────────────────
# Per-primitive code templates (Python-flavored)
ASSEMBLE = {
    "DEF": "def fn(nums):",
    "ASSIGN": "total = 0",
    "LOOP": "for n in nums:",
    "AGGREGATE": "total += n",
    "RETURN": "return total",
    "BRANCH": "if a > b:",
    "COMPARE": "return a",
    "ARITH_ADD": "return a + b",
    "ARITH_MUL": "return a * b",
    "WRITE": "print(total)",
    "READ": "data = input()",
    "SORT": "return sorted(arr)",
    "SEARCH": "return arr.index(x)",
    "FILTER": "if n % 2 == 0:",
    "STATE": "out.append(n)",
    "EXPR": "pass",
}


def assemble(tree: Dict, indent: str = "") -> str:
    """Assemble code from a structural shape tree (preserves nesting/order)."""
    lines = []
    for child in tree.get("children", []):
        prim = child["primitive"]
        tpl = ASSEMBLE.get(prim, "pass")
        lines.append(indent + tpl)
        if child["children"]:
            lines.append(assemble(child, indent + "    "))
    return "\n".join(lines)


def structural_roundtrip(code: str) -> Dict:
    """Decompose to structural shape, assemble back, measure fidelity."""
    tree = structural_shape(code)
    sig = shape_to_string(tree)
    assembled = assemble(tree)
    # re-decompose the assembled code
    new_sig = structural_signature(assembled)
    sim = structural_similarity(code, assembled)
    return {
        "signature": sig,
        "assembled_signature": new_sig,
        "similarity": round(sim, 2),
        "assembled": assembled,
    }


# ── Self-test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    sum_fn = "def sum_list(nums):\n    total = 0\n    for n in nums:\n        total += n\n    return total"
    max_fn = "def max2(a, b):\n    if a > b:\n        return a\n    return b"

    print("=== Structural shapes ===")
    for name, code in [("sum", sum_fn), ("max", max_fn)]:
        print(f"{name}: {structural_signature(code)}")

    print("\n=== Structural round-trip ===")
    for name, code in [("sum", sum_fn), ("max", max_fn)]:
        rt = structural_roundtrip(code)
        print(f"\n{name}: sig={rt['signature']}")
        print(f"  assembled:\n{rt['assembled']}")
        print(f"  re-sig={rt['assembled_signature']} sim={rt['similarity']}")

    print("\n=== Structural similarity ===")
    print(f"sum vs max: {structural_similarity(sum_fn, max_fn):.2f}")
    print(f"sum vs sum: {structural_similarity(sum_fn, sum_fn):.2f}")
