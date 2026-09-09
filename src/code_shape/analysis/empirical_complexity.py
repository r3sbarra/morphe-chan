#!/usr/bin/env python
"""empirical_complexity.py — Empirical complexity measurement.
instead of statically estimating complexity from loop counts.

Approach:
  1. Run a function on increasing input sizes (n = 10, 20, 40, 80, ...)
  2. Measure execution time at each size
  3. Fit the scaling to estimate the empirical complexity class
     (O(1), O(log n), O(n), O(n log n), O(n^2), O(n^3))

This is more accurate than static loop-count estimation, which can't detect
hidden complexity (e.g. a loop that calls an O(n) function inside = O(n^2)).

Dependency-free (stdlib only).
"""
import time
from typing import Callable, Dict, List, Optional


def measure_scaling(fn: Callable, input_gen: Callable, sizes: List[int] = None,
                    repeats: int = 3) -> Dict:
    """Measure a function's execution time across input sizes.

    fn: the function to measure
    input_gen: generates an input of size n
    Returns {size: avg_time_seconds}.
    """
    if sizes is None:
        sizes = [10, 20, 40, 80, 160, 320]
    timings = {}
    for n in sizes:
        inp = input_gen(n)
        # warmup
        try:
            fn(inp)
        except Exception:
            pass
        times = []
        for _ in range(repeats):
            t0 = time.perf_counter()
            try:
                fn(inp)
            except Exception:
                pass
            times.append(time.perf_counter() - t0)
        timings[n] = sum(times) / len(times)
    return timings


def estimate_complexity(timings: Dict[int, float]) -> str:
    """Estimate the empirical complexity class from timing data.

    Fits log(t) vs log(n) to estimate the exponent (slope):
      slope ~ 0  -> O(1)
      slope ~ 0.5 -> O(sqrt n)
      slope ~ 1  -> O(n)
      slope ~ 1.1-1.3 -> O(n log n)
      slope ~ 2  -> O(n^2)
      slope ~ 3  -> O(n^3)
    """
    import math
    sizes = sorted(timings.keys())
    # use sizes where time > 0
    pts = [(math.log(n), math.log(max(t, 1e-9))) for n, t in timings.items() if t > 0]
    if len(pts) < 2:
        return "UNKNOWN"
    # linear regression on log-log
    n = len(pts)
    sx = sum(p[0] for p in pts)
    sy = sum(p[1] for p in pts)
    sxx = sum(p[0] * p[0] for p in pts)
    sxy = sum(p[0] * p[1] for p in pts)
    denom = n * sxx - sx * sx
    if denom == 0:
        return "UNKNOWN"
    slope = (n * sxy - sx * sy) / denom

    if slope < 0.3:
        return "O(1)"
    if slope < 0.7:
        return "O(sqrt n)"
    if slope < 1.2:
        return "O(n)"
    if slope < 1.6:
        return "O(n log n)"
    if slope < 2.5:
        return "O(n^2)"
    return "O(n^3)"


def compare_complexity(code_a: str, code_b: str, input_gen: Callable,
                       fn_name: str = None) -> Dict:
    """Compare the empirical complexity of two code snippets."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from code_shape.analysis.exec_verifier import extract_function

    fa = extract_function(code_a, fn_name)
    fb = extract_function(code_b, fn_name)
    if fa is None or fb is None:
        return {"error": "function not extractable"}

    ta = measure_scaling(fa, input_gen)
    tb = measure_scaling(fb, input_gen)
    ca = estimate_complexity(ta)
    cb = estimate_complexity(tb)
    return {
        "code_a_complexity": ca,
        "code_b_complexity": cb,
        "code_a_timings": {k: round(v, 6) for k, v in ta.items()},
        "code_b_timings": {k: round(v, 6) for k, v in tb.items()},
    }


# ── Self-test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # O(n) sum vs O(n^2) nested
    o1 = "def sum_list(nums):\n    total = 0\n    for n in nums:\n        total += n\n    return total"
    o2 = "def nested_sum(nums):\n    total = 0\n    for a in nums:\n        for b in nums:\n            total += a * b\n    return total"

    def gen(n):
        return list(range(n))

    print("=== Empirical complexity measurement ===")
    res = compare_complexity(o1, o2, gen)
    print(f"O(n) sum:     {res['code_a_complexity']}")
    print(f"O(n^2) nested: {res['code_b_complexity']}")
    print(f"  sum timings: {res['code_a_timings']}")
    print(f"  nested timings: {res['code_b_timings']}")
