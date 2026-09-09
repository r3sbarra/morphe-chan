#!/usr/bin/env python
"""efficiency_shape.py — Shape efficiency/performance detection.

Internal methods and operations drive part of the dimensional shape:

  EFF_LOOPS        — number of loop constructs (for/while)
  EFF_NESTING      — max loop nesting depth (O(n) vs O(n^2) vs O(n^3))
  EFF_METHOD_CALLS — density of method calls (overhead per operation)
  EFF_THREADED     — concurrency (thread/parallel/async) vs serial
  EFF_ALLOC        — allocations (list/dict/object creation, memory pressure)
  EFF_RECURSION    — recursion (stack depth risk)
  EFF_REPEATED     — repeated computation (same call in a loop = recompute)
  EFF_COMPLEXITY   — estimated time complexity class (O(1)/O(n)/O(n^2)/O(n^3))

The efficiency vector is a separate dimension set that can be combined with
the intent/shape vectors. Two functions with the SAME intent but different
efficiency (serial vs threaded loop) have different efficiency shapes.

Dependency-free (stdlib only).
"""
import math
import re
from typing import Dict, List, Tuple

# ── Efficiency primitive detection ─────────────────────────────────────────
def _count_loops(code: str) -> int:
    """Count loop constructs (for/while)."""
    return len(re.findall(r"\b(for|while)\b", code))


def _max_nesting(code: str) -> int:
    """Max loop nesting depth (count of nested for/while, ignoring nested defs)."""
    lines = code.splitlines()
    max_depth = 0
    cur = 0
    for line in lines:
        stripped = line.strip()
        if re.match(r"(for|while)\b", stripped):
            cur += 1
            max_depth = max(max_depth, cur)
        elif stripped.startswith("def") or stripped.startswith("function"):
            # nested function def resets loop context (it's a new scope)
            cur = 0
        elif stripped and not stripped.startswith(("for", "while", "if", "else", "elif", "return", "break", "continue", "import", "from")):
            # a statement at lower indent than current loop closes it
            indent = len(line) - len(line.lstrip())
            if cur > 0 and indent <= 4 * (cur - 1):
                cur = max(0, cur - 1)
    return max_depth


def _count_method_calls(code: str) -> int:
    """Count method calls (obj.method(...) or builtin calls)."""
    return len(re.findall(r"\b\w+\.\w+\s*\(|\b\w+\s*\(", code))


def _is_threaded(code: str) -> bool:
    """Detect concurrency (thread/parallel/async/multiprocessing)."""
    t = code.lower()
    return any(k in t for k in ["thread", "parallel", "async", "await", "multiprocess", "concurrent", "pool", "concurrent.futures"])


def _count_allocations(code: str) -> int:
    """Count allocations (list/dict/set/object creation)."""
    return len(re.findall(r"\[\]|\{\}|list\(|dict\(|set\(|new\s+\w+", code))


def _is_recursive(code: str) -> bool:
    """Detect recursion (function calls itself)."""
    m = re.search(r"(?:def|function)\s+(\w+)\s*\(", code)
    if not m:
        return False
    name = m.group(1)
    body = code[code.find(m.group(0)) + len(m.group(0)):]
    return body.count(name) >= 1


def _repeated_computation(code: str) -> int:
    """Detect repeated computation: a method call inside a loop body."""
    lines = code.splitlines()
    in_loop = False
    repeated = 0
    for line in lines:
        stripped = line.strip()
        if re.match(r"(for|while)\b", stripped):
            in_loop = True
        elif in_loop and re.search(r"\w+\.\w+\s*\(|\w+\s*\(", stripped):
            repeated += 1
    return repeated


def _complexity_class(code: str) -> str:
    """Estimate time complexity class from loop nesting + recursion.

    Threaded code: the per-worker loop is still O(n) (parallelism doesn't
    change the class, just the constant). Nested defs don't add nesting.
    """
    if _is_recursive(code):
        return "O(2^n)" if "fib" in code.lower() else "O(n)"
    if _is_threaded(code):
        # threaded: complexity is the deepest loop inside a worker, not the
        # thread-management loops (for t in threads is O(num_threads), constant)
        return "O(n)" if _count_loops(code) > 0 else "O(1)"
    # count only top-level loop nesting (ignore loops inside nested defs)
    lines = code.splitlines()
    max_depth = 0
    cur = 0
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("def") or stripped.startswith("function"):
            cur = 0
        elif re.match(r"(for|while)\b", stripped):
            cur += 1
            max_depth = max(max_depth, cur)
        elif stripped and not stripped.startswith(("for", "while", "if", "else", "elif", "return", "break", "continue", "import", "from")):
            indent = len(line) - len(line.lstrip())
            if cur > 0 and indent <= 4 * (cur - 1):
                cur = max(0, cur - 1)
    if max_depth >= 3:
        return "O(n^3)"
    if max_depth == 2:
        return "O(n^2)"
    # hidden O(n^2): string concat in loop (out = out + c) or len() in loop
    if max_depth == 1 and (_string_concat_in_loop(code) or _len_in_loop(code)):
        return "O(n^2)"
    if max_depth == 1:
        return "O(n)"
    return "O(1)"


def _string_concat_in_loop(code: str) -> bool:
    """Detect string concatenation inside a loop (hidden O(n^2))."""
    lines = code.splitlines()
    in_loop = False
    for line in lines:
        stripped = line.strip()
        if re.match(r"(for|while)\b", stripped):
            in_loop = True
        elif in_loop and re.search(r"\w+\s*=\s*\w+\s*\+", stripped):
            return True
    return False


def _len_in_loop(code: str) -> bool:
    """Detect len()/count() called inside a loop (redundant O(n) per iter)."""
    lines = code.splitlines()
    in_loop = False
    for line in lines:
        stripped = line.strip()
        if re.match(r"(for|while)\b", stripped):
            in_loop = True
        elif in_loop and re.search(r"len\s*\(|count\s*\(|sum\s*\(", stripped):
            return True
    return False


# ── Efficiency shape vector ─────────────────────────────────────────────────
EFF_DIMS = ["EFF_COMPLEXITY", "EFF_LOOPS", "EFF_NESTING", "EFF_METHOD_CALLS",
            "EFF_THREADED", "EFF_ALLOC", "EFF_RECURSION", "EFF_REPEATED"]


def efficiency_vector(code: str) -> Dict[str, float]:
    """Efficiency shape vector (normalized). Internal methods/ops drive dims.

    Discriminative design: the complexity class and threading are the strongest
    efficiency signals, so they get high weight. Raw counts (loops, calls) are
    secondary.
    """
    cx = _complexity_class(code)
    cx_map = {"O(1)": 0.0, "O(n)": 1.0, "O(n^2)": 2.0, "O(n^3)": 3.0, "O(2^n)": 4.0}
    vec: Dict[str, float] = {
        "EFF_COMPLEXITY": float(cx_map.get(cx, 1.0)),
        "EFF_THREADED": 3.0 if _is_threaded(code) else 0.0,
        "EFF_LOOPS": float(_count_loops(code)),
        "EFF_NESTING": float(_max_nesting(code)),
        "EFF_METHOD_CALLS": float(_count_method_calls(code)),
        "EFF_ALLOC": float(_count_allocations(code)),
        "EFF_RECURSION": 1.0 if _is_recursive(code) else 0.0,
        "EFF_REPEATED": 2.0 * float(_repeated_computation(code)),
    }
    norm = math.sqrt(sum(v * v for v in vec.values()))
    if norm == 0:
        return {d: 0.0 for d in EFF_DIMS}
    return {d: round(vec[d] / norm, 4) for d in EFF_DIMS}


def efficiency_summary(code: str) -> Dict:
    """Human-readable efficiency summary."""
    return {
        "loops": _count_loops(code),
        "nesting": _max_nesting(code),
        "method_calls": _count_method_calls(code),
        "threaded": _is_threaded(code),
        "allocations": _count_allocations(code),
        "recursive": _is_recursive(code),
        "repeated_computation": _repeated_computation(code),
        "complexity": _complexity_class(code),
    }


def cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    keys = set(a) | set(b)
    dot = sum(a.get(k, 0) * b.get(k, 0) for k in keys)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def efficiency_similarity(code_a: str, code_b: str) -> float:
    """Cosine similarity between two efficiency shape vectors."""
    return cosine(efficiency_vector(code_a), efficiency_vector(code_b))


# ── Self-test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Serial loop: subtract 1 a million times
    serial = '''
def decrement_serial(n):
    x = n
    for i in range(1000000):
        x -= 1
    return x
'''
    # Threaded loop: parallel decrement
    threaded = '''
import threading

def decrement_parallel(n):
    x = n
    def worker():
        nonlocal x
        for i in range(1000000):
            x -= 1
    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return x
'''
    # Nested loop: O(n^2)
    nested = '''
def matrix_sum(m):
    total = 0
    for row in m:
        for cell in row:
            total += cell
    return total
'''
    # Simple: O(1)
    simple = '''
def add(a, b):
    return a + b
'''

    print("=== Efficiency shape ===")
    for name, code in [("serial", serial), ("threaded", threaded), ("nested", nested), ("simple", simple)]:
        s = efficiency_summary(code)
        print(f"{name:9s} complexity={s['complexity']:6s} loops={s['loops']} nesting={s['nesting']} "
              f"threaded={s['threaded']} calls={s['method_calls']}")

    print("\n=== Efficiency similarity ===")
    print(f"serial vs threaded (same intent, diff eff): {efficiency_similarity(serial, threaded):.3f}")
    print(f"serial vs nested (diff eff):                 {efficiency_similarity(serial, nested):.3f}")
    print(f"serial vs simple (diff eff):                {efficiency_similarity(serial, simple):.3f}")
    print(f"nested vs simple (diff eff):                 {efficiency_similarity(nested, simple):.3f}")
