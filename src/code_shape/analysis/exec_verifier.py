#!/usr/bin/env python
"""exec_verifier.py — Execution-based code verification.
on test inputs and checks outputs, catching SEMANTIC bugs (off-by-one, wrong
operator) and BUILTIN-EQUIVALENCE (sum() vs manual loop) that static shape
analysis misses.

This is the TRIZ Feedback principle applied: generate/analyze in shape space,
then EXECUTE and verify against ground truth, feeding the result back.

Dependency-free (stdlib only).
"""
import ast
import traceback
from typing import Callable, Dict, List, Optional


def extract_function(code: str, name: str = None) -> Optional[Callable]:
    """Extract and return a callable function from a code snippet."""
    try:
        ns: Dict = {}
        exec(code, ns)
        if name:
            return ns.get(name)
        # find the first function
        for k, v in ns.items():
            if callable(v) and not k.startswith("_"):
                return v
        return None
    except Exception:
        return None


def run_tests(code: str, test_cases: List[Dict], fn_name: str = None) -> Dict:
    """Run a function against test cases. Each case: {args: [...], expected: ...}.

    Returns {passed, failed, total, failures: [{args, expected, got, error}]}.
    """
    fn = extract_function(code, fn_name)
    if fn is None:
        return {"passed": 0, "failed": len(test_cases), "total": len(test_cases),
                "failures": [{"args": tc.get("args"), "expected": tc.get("expected"),
                              "got": None, "error": "function not extractable"} for tc in test_cases]}

    passed = 0
    failures = []
    for tc in test_cases:
        args = tc.get("args", [])
        expected = tc.get("expected")
        try:
            got = fn(*args)
            if got == expected:
                passed += 1
            else:
                failures.append({"args": args, "expected": expected, "got": got, "error": None})
        except Exception as e:
            failures.append({"args": args, "expected": expected, "got": None,
                             "error": f"{type(e).__name__}: {e}"})
    return {"passed": passed, "failed": len(failures), "total": len(test_cases),
            "failures": failures}


def verify_semantic(code: str, test_cases: List[Dict], fn_name: str = None) -> Dict:
    """Verify a function's SEMANTIC correctness via execution.

    Returns {correct, passed, total, failures}.
    """
    res = run_tests(code, test_cases, fn_name)
    return {
        "correct": res["failed"] == 0,
        "passed": res["passed"],
        "total": res["total"],
        "failures": res["failures"],
    }


def builtin_equivalent(code_a: str, code_b: str, test_cases: List[Dict],
                       fn_a: str = None, fn_b: str = None) -> Dict:
    """Check if two functions are behaviorally equivalent by running both on the
    same test cases and comparing outputs. Catches builtin-vs-manual equivalence
    (sum() vs manual loop) that static shape analysis misses.

    Returns {equivalent, mismatches, total}.
    """
    fa = extract_function(code_a, fn_a)
    fb = extract_function(code_b, fn_b)
    if fa is None or fb is None:
        return {"equivalent": False, "mismatches": len(test_cases), "total": len(test_cases),
                "error": "one or both functions not extractable"}

    mismatches = []
    for tc in test_cases:
        args = tc.get("args", [])
        try:
            ra = fa(*args)
        except Exception as e:
            ra = f"ERR:{e}"
        try:
            rb = fb(*args)
        except Exception as e:
            rb = f"ERR:{e}"
        if ra != rb:
            mismatches.append({"args": args, "a": ra, "b": rb})
    return {"equivalent": len(mismatches) == 0, "mismatches": mismatches, "total": len(test_cases)}


# ── Self-test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Semantic bug: off-by-one (returns count+1)
    buggy = "def count_evens(nums):\n    count = 0\n    for n in nums:\n        if n % 2 == 0:\n            count += 1\n    return count + 1"
    clean = "def count_evens(nums):\n    count = 0\n    for n in nums:\n        if n % 2 == 0:\n            count += 1\n    return count"
    tests = [{"args": [[1, 2, 3, 4]], "expected": 2},
             {"args": [[2, 4, 6]], "expected": 3},
             {"args": [[1, 3, 5]], "expected": 0}]

    print("=== Execution-based verification (catches semantic bugs) ===")
    print("buggy:", verify_semantic(buggy, tests))
    print("clean:", verify_semantic(clean, tests))

    # Builtin equivalence: sum() vs manual loop
    sum_builtin = "def total(nums):\n    return sum(nums)"
    sum_manual = "def total(nums):\n    acc = 0\n    for n in nums:\n        acc += n\n    return acc"
    eq_tests = [{"args": [[1, 2, 3]], "expected": 6},
                {"args": [[5, 5, 5]], "expected": 15},
                {"args": [[]], "expected": 0}]
    print("\n=== Builtin equivalence (sum() vs manual loop) ===")
    print("equivalent:", builtin_equivalent(sum_builtin, sum_manual, eq_tests))
