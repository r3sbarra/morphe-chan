#!/usr/bin/env python
"""program_synthesizer.py — Synthesize a program from a target composite shape
+ call graph.

Compose functions into a program that realizes a target composite shape
(function shapes + call graph).

Input spec (JSON):
  {
    "functions": {
      "add":    {"shape": "ARITH_ADD>RETURN", "params": ["a", "b"]},
      "double": {"shape": "RETURN>STATE", "params": ["x"], "calls": ["add"]},
      "main":   {"shape": "LOOP>AGGREGATE>RETURN", "params": ["nums"], "calls": ["double"]}
    }
  }

The synthesizer:
  1. For each function, picks a body template matching its shape.
  2. Wires calls according to the call graph (callee invoked with its params).
  3. Emits a valid Python program.
  4. Verifies by re-analyzing: program_shape() should match the target
     (functions present, call graph preserved).

Dependency-free (stdlib only).
"""
import json
from typing import Dict, List, Optional

from code_shape.core.program_shape import program_shape, extract_call_graph


# ── Body templates keyed by shape signature ─────────────────────────────────
# Each template is a list of (line, is_block) where is_block opens a nested scope.
BODY_TEMPLATES: Dict[str, List[str]] = {
    "ARITH_ADD>RETURN": ["return a + b"],
    "ARITH_MUL>RETURN": ["return a * b"],
    "ARITH_SUB>RETURN": ["return a - b"],
    "ARITH_DIV>RETURN": ["return a / b"],
    "RETURN>STATE":     ["return add(x, x)"],
    "LOOP>AGGREGATE>RETURN": [
        "total = 0",
        "for n in nums:",
        "    total = double(n)",
        "return total",
    ],
    "LOOP>ARITH_ADD>RETURN": [
        "total = 0",
        "for n in nums:",
        "    total += n",
        "return total",
    ],
    "BRANCH>COMPARE_GT>RETURN": [
        "if a > b:",
        "    return a",
        "return b",
    ],
    "BRANCH>ARITH_MOD>RETURN": [
        "if n % 2 == 0:",
        "    return True",
        "return False",
    ],
    "AGGREGATE>ASSIGN>LOOP>RETURN": [
        "count = 0",
        "for n in nums:",
        "    if is_even(n):",
        "        count += 1",
        "return count",
    ],
}


def _default_body(shape: str, params: List[str]) -> List[str]:
    """Fallback body for an unknown shape: return a param."""
    if params:
        return [f"return {params[0]}"]
    return ["return None"]


def synthesize_program(spec: Dict) -> Optional[str]:
    """Synthesize a program from a composite-shape spec. Returns Python code.

    Call-graph aware: when a function's body template references a callee, the
    actual callee name from the spec's call graph is substituted.
    """
    functions = spec.get("functions", {})
    if not functions:
        return None

    out: List[str] = []
    for name, fspec in functions.items():
        shape = fspec.get("shape", "")
        params = fspec.get("params", [])
        calls = fspec.get("calls", [])

        sig = f"def {name}({', '.join(params)}):"
        out.append(sig)

        body = BODY_TEMPLATES.get(shape, _default_body(shape, params))
        # Substitute the actual callee name into the body if it references one.
        # Templates use a placeholder like 'add' or 'is_even'; replace with the
        # first callee from the call graph.
        if calls:
            callee = calls[0]
            body = [line.replace("add", callee).replace("is_even", callee) for line in body]
        for line in body:
            out.append("    " + line)
        out.append("")

    return "\n".join(out).rstrip() + "\n"


def verify_program(code: str, spec: Dict) -> Dict:
    """Verify synthesized program: functions present + call graph preserved."""
    ps = program_shape(code)
    target_fns = set(spec.get("functions", {}).keys())
    actual_fns = set(ps["functions"].keys())
    fn_ok = target_fns == actual_fns

    # call graph check
    target_graph = {name: fspec.get("calls", []) for name, fspec in spec.get("functions", {}).items()}
    actual_graph = ps["graph"]
    graph_ok = True
    for name, callees in target_graph.items():
        if set(actual_graph.get(name, [])) != set(callees):
            graph_ok = False

    return {
        "ok": fn_ok and graph_ok,
        "functions_match": fn_ok,
        "graph_match": graph_ok,
        "target_functions": sorted(target_fns),
        "actual_functions": sorted(actual_fns),
        "target_graph": target_graph,
        "actual_graph": actual_graph,
    }


# ── Self-test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Target: a program with add, double, main (main calls double, double calls add)
    spec = {
        "functions": {
            "add":    {"shape": "ARITH_ADD>RETURN", "params": ["a", "b"], "calls": []},
            "double": {"shape": "RETURN>STATE", "params": ["x"], "calls": ["add"]},
            "main":   {"shape": "LOOP>AGGREGATE>RETURN", "params": ["nums"], "calls": ["double"]},
        }
    }
    code = synthesize_program(spec)
    print("=== Synthesized program ===")
    print(code)
    print("=== Verification ===")
    print(verify_program(code, spec))
