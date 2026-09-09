#!/usr/bin/env python
"""experiment_program_synthesis.py — Validate program synthesis from composite
shapes: synthesize from spec, verify functions + call graph round-trip.
"""
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(TOOLS))
from code_shape.synthesis.program_synthesizer import synthesize_program, verify_program

# Multiple composite-shape specs
SPECS = [
    {
        "name": "add-double-main",
        "spec": {
            "functions": {
                "add":    {"shape": "ARITH_ADD>RETURN", "params": ["a", "b"], "calls": []},
                "double": {"shape": "RETURN>STATE", "params": ["x"], "calls": ["add"]},
                "main":   {"shape": "LOOP>AGGREGATE>RETURN", "params": ["nums"], "calls": ["double"]},
            }
        },
    },
    {
        "name": "max-min",
        "spec": {
            "functions": {
                "max2": {"shape": "BRANCH>COMPARE_GT>RETURN", "params": ["a", "b"], "calls": []},
                "main": {"shape": "RETURN>STATE", "params": ["x", "y"], "calls": ["max2"]},
            }
        },
    },
    {
        "name": "even-count",
        "spec": {
            "functions": {
                "is_even":    {"shape": "BRANCH>ARITH_MOD>RETURN", "params": ["n"], "calls": []},
                "count_evens": {"shape": "AGGREGATE>ASSIGN>LOOP>RETURN", "params": ["nums"], "calls": ["is_even"]},
            }
        },
    },
]


def main():
    print("=== Program Synthesis from Composite Shape ===")
    for item in SPECS:
        name = item["name"]
        spec = item["spec"]
        code = synthesize_program(spec)
        if code is None:
            print(f"{name:16s} SYNTHESIS FAILED")
            continue
        v = verify_program(code, spec)
        # also check it's executable
        try:
            ns = {}
            exec(code, ns)
            exec_ok = True
        except Exception as e:
            exec_ok = f"ERR: {e}"
        print(f"{name:16s} fns={v['functions_match']} graph={v['graph_match']} exec={exec_ok}")
        if not v["ok"]:
            print(f"  target_fns={v['target_functions']} actual={v['actual_functions']}")
            print(f"  target_graph={v['target_graph']} actual={v['actual_graph']}")


if __name__ == "__main__":
    main()
