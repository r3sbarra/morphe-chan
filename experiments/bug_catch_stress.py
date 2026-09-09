#!/usr/bin/env python
"""Bug-catching stress test for Morphē-chan's type-aware shape analysis.

Feeds deliberately buggy code (swapped params, type mismatches, wrong arg
order, wrong types) through `cascading_type_flow` and reports what's caught.

This is a *diagnostic* harness — it documents the system's current detection
capabilities and limitations, not a pass/fail gate.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from code_shape.core.variable_shape import cascading_type_flow, infer_types

CASES = [
    {
        "name": "swapped_unnamed_numeric",
        "desc": "divide(2,10) vs divide(10,2) — both NUM, order swapped",
        "code": (
            "def divide(numerator, denominator):\n"
            "    return numerator / denominator\n"
            "def main():\n"
            "    return divide(2, 10)\n"
        ),
        "expect": "semantic swap (type-identical, NOT detectable)",
    },
    {
        "name": "swapped_type_mismatch",
        "desc": "format_user(30, 'Alice') — INT passed to STR param",
        "code": (
            "def format_user(name, age):\n"
            "    return name + str(age)\n"
            "def main():\n"
            "    return format_user(30, 'Alice')\n"
        ),
        "expect": "type error (INT->STR) — DETECTABLE",
    },
    {
        "name": "wrong_type_arg",
        "desc": "process_list(42) — INT passed to LIST param",
        "code": (
            "def process_list(items):\n"
            "    return len(items)\n"
            "def main():\n"
            "    return process_list(42)\n"
        ),
        "expect": "type error (INT->LIST) — DETECTABLE",
    },
    {
        "name": "correct_call",
        "desc": "process_list([1,2,3]) — correct",
        "code": (
            "def process_list(items):\n"
            "    return len(items)\n"
            "def main():\n"
            "    return process_list([1, 2, 3])\n"
        ),
        "expect": "no error — correct",
    },
    {
        "name": "string_where_number",
        "desc": "add(1, 'x') — STR passed to NUM param",
        "code": (
            "def add(a, b):\n"
            "    return a + b\n"
            "def main():\n"
            "    return add(1, 'x')\n"
        ),
        "expect": "type error (STR->NUM) — DETECTABLE",
    },
    {
        "name": "dict_where_list",
        "desc": "sum_items({'a':1}) — DICT passed to LIST param",
        "code": (
            "def sum_items(items):\n"
            "    return sum(items)\n"
            "def main():\n"
            "    return sum_items({'a': 1})\n"
        ),
        "expect": "type error (DICT->LIST) — DETECTABLE",
    },
    {
        "name": "cascading_type_error",
        "desc": "main passes INT to helper which expects STR (via propagation)",
        "code": (
            "def helper(text):\n"
            "    return text.upper()\n"
            "def main():\n"
            "    x = 42\n"
            "    return helper(x)\n"
        ),
        "expect": "type error (INT->STR) — DETECTABLE",
    },
    {
        "name": "correct_cascading",
        "desc": "main passes STR to helper which expects STR",
        "code": (
            "def helper(text):\n"
            "    return text.upper()\n"
            "def main():\n"
            "    x = 'hello'\n"
            "    return helper(x)\n"
        ),
        "expect": "no error — correct",
    },
]


def main():
    print("=" * 70)
    print("Morphē-chan bug-catching stress test")
    print("=" * 70)
    caught = 0
    total_detectable = 0
    for case in CASES:
        cf = cascading_type_flow(case["code"])
        types = infer_types(case["code"])
        n_errors = cf["type_errors"]
        n_swapped = len(cf["swapped_params"])
        detectable = "DETECTABLE" in case["expect"]
        if detectable:
            total_detectable += 1
        is_caught = (n_errors > 0 or n_swapped > 0)
        if detectable and is_caught:
            caught += 1
        status = "✓ CAUGHT" if is_caught else ("✗ MISSED" if detectable else "· n/a")
        print(f"\n[{status}] {case['name']}")
        print(f"    {case['desc']}")
        print(f"    expect: {case['expect']}")
        print(f"    types: { {k: v for k, v in types.items() if k != '__return__'} }")
        print(f"    type_errors={n_errors} swapped={n_swapped}")
        for c in cf["calls"]:
            print(f"      {c['caller']}->{c['callee']}({c['arg']}->{c['param']}) "
                  f"{c['arg_bucket']}->{c['param_bucket']}")
    print("\n" + "=" * 70)
    print(f"Detectable bugs caught: {caught}/{total_detectable}")
    print("=" * 70)


if __name__ == "__main__":
    main()
