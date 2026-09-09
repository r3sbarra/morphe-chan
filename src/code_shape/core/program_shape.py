#!/usr/bin/env python
"""program_shape.py — Decompose larger functions/programs into composite
shapes while retaining their connections.

A program is not a flat vector — it is a GRAPH of connected function-shapes.
This module:
  1. DECOMPOSES a program into its component functions.
  2. Computes a code-agnostic shape vector for each function.
  3. EXTRACTS the call graph (which function calls which).
  4. BUILDS a composite program shape = {function shapes} + {connection graph}.

The composite shape preserves BOTH the parts (function shapes) AND the
connections (call relationships), so two programs with the same functions but
different wiring are distinguishable.

Dependency-free (stdlib only).
"""
import re
from typing import Dict, List, Tuple, Optional

from code_shape.core.agnostic_shape import agnostic_vector, agnostic_similarity, shape as fn_shape


# ── 1. Program decomposition ────────────────────────────────────────────────
def extract_functions(code: str) -> Dict[str, str]:
    """Extract top-level functions from a program. Returns {name: body}."""
    functions: Dict[str, str] = {}
    lines = code.splitlines()
    current_name = None
    current_lines: List[str] = []
    current_indent = None

    for line in lines:
        m = re.match(r"^(\s*)(?:def|function)\s+(\w+)\s*\(", line)
        if m:
            # save previous function
            if current_name:
                functions[current_name] = "\n".join(current_lines)
            current_name = m.group(2)
            current_indent = len(m.group(1))
            current_lines = [line]
        elif current_name is not None:
            indent = len(line) - len(line.lstrip())
            if line.strip() and indent <= current_indent:
                # dedent to function level or above -> end of function
                functions[current_name] = "\n".join(current_lines)
                current_name = None
                current_lines = []
            else:
                current_lines.append(line)
    if current_name:
        functions[current_name] = "\n".join(current_lines)
    return functions


# ── 2. Call-graph extraction ───────────────────────────────────────────────
def extract_call_graph(code: str, functions: Dict[str, str]) -> Dict[str, List[str]]:
    """Extract which function calls which. Returns {caller: [callees]}."""
    graph: Dict[str, List[str]] = {name: [] for name in functions}
    for caller, body in functions.items():
        for callee in functions:
            if callee == caller:
                continue
            # callee called if its name appears in caller's body (as a call)
            if re.search(r"\b" + re.escape(callee) + r"\s*\(", body):
                graph[caller].append(callee)
    return graph


# ── 3. Composite program shape ──────────────────────────────────────────────
def program_shape(code: str) -> Dict:
    """Build the composite program shape: function shapes + call graph."""
    functions = extract_functions(code)
    shapes = {name: agnostic_vector(body) for name, body in functions.items()}
    graph = extract_call_graph(code, functions)
    return {
        "functions": functions,
        "shapes": shapes,
        "graph": graph,
        "shape_signatures": {name: fn_shape(body) for name, body in functions.items()},
    }


def program_signature(code: str) -> str:
    """Human-readable composite signature: function shapes + connections."""
    ps = program_shape(code)
    parts = []
    for name, sig in ps["shape_signatures"].items():
        callees = ps["graph"].get(name, [])
        conn = f"->{','.join(callees)}" if callees else ""
        parts.append(f"{name}[{sig}]{conn}")
    return " | ".join(parts)


# ── 4. Program-level comparison ────────────────────────────────────────────
def program_similarity(code_a: str, code_b: str) -> float:
    """Compare two programs by their composite shapes.

    Combines:
      - function-shape similarity (do the parts match?)
      - call-graph similarity (do the connections match?)
    """
    pa = program_shape(code_a)
    pb = program_shape(code_b)
    fa, fb = pa["functions"], pb["functions"]
    ga, gb = pa["graph"], pb["graph"]

    if not fa or not fb:
        return 0.0

    # Function-shape similarity: match functions by name, average shape sim.
    fn_sims = []
    for name in set(fa) & set(fb):
        fn_sims.append(agnostic_similarity(fa[name], fb[name]))
    fn_score = sum(fn_sims) / len(fn_sims) if fn_sims else 0.0

    # Call-graph similarity: Jaccard of edges.
    edges_a = {(c, k) for c, ks in ga.items() for k in ks}
    edges_b = {(c, k) for c, ks in gb.items() for k in ks}
    if edges_a or edges_b:
        inter = len(edges_a & edges_b)
        union = len(edges_a | edges_b)
        graph_score = inter / union if union else 0.0
    else:
        graph_score = 1.0  # both have no calls

    # Weighted: functions 0.6, connections 0.4.
    return 0.6 * fn_score + 0.4 * graph_score


# ── Self-test ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # A small program: main calls helper functions
    prog1 = '''
def add(a, b):
    return a + b

def double(x):
    return add(x, x)

def main(nums):
    total = 0
    for n in nums:
        total = double(n)
    return total
'''
    # Same functions, different wiring (main calls add directly, not double)
    prog2 = '''
def add(a, b):
    return a + b

def double(x):
    return add(x, x)

def main(nums):
    total = 0
    for n in nums:
        total = add(n, n)
    return total
'''
    # Different program (no helpers)
    prog3 = '''
def main(nums):
    total = 0
    for n in nums:
        total += n
    return total
'''

    print("=== Program decomposition ===")
    for name, prog in [("prog1", prog1), ("prog2", prog2), ("prog3", prog3)]:
        ps = program_shape(prog)
        print(f"\n{name}: functions={list(ps['functions'].keys())}")
        print(f"  graph={ps['graph']}")
        print(f"  sig={program_signature(prog)}")

    print("\n=== Program similarity ===")
    print(f"prog1 vs prog2 (same fns, diff wiring): {program_similarity(prog1, prog2):.3f}")
    print(f"prog1 vs prog3 (different program):     {program_similarity(prog1, prog3):.3f}")
    print(f"prog2 vs prog3 (different program):      {program_similarity(prog2, prog3):.3f}")
