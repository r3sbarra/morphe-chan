#!/usr/bin/env python
"""shape_model.py — Improved multi-dimensional code vector shape.


1. HIERARCHICAL PRIMITIVES — each primitive is (category, operation, operand):
     TRANSFORM:ARITH:ADD, TRANSFORM:STR:UPPER, ITERATE:LOOP:FOR,
     COMPARE:PRED:GT, AGGREGATE:SUM, SEARCH:INDEX, ...
   This captures intent at multiple granularities.

2. METHOD/TYPE AWARENESS — detects method calls (.upper(), .split(), .index())
   and operand types (str/int/list) so the shape reflects WHAT is operated on.

3. CONTROL-FLOW SHAPE — encodes branch/loop/recursion structure as a signature.

4. COMPARISON — weighted cosine + structural overlap (not just flat cosine).

5. COMPOSITION — compose two function shapes/vectors into a compound shape
   (the 'compositing compound shapes' thesis): the compound vector is the
   union of primitives with combined weights, plus a composition signature.

Dependency-free (stdlib only).
"""
import math
import re
from typing import Dict, List, Tuple

# ── 1. Hierarchical primitive extraction ────────────────────────────────────
# Each rule: (category, operation, [patterns])
# Patterns matched against normalized text; more specific first.
HIER_RULES: List[Tuple[str, str, List[str]]] = [
    # arithmetic operations
    ("TRANSFORM", "ARITH_ADD",   [" + ", "add", "sum(", "plus"]),
    ("TRANSFORM", "ARITH_MUL",   [" * ", "multiply", "product", "factorial"]),
    ("TRANSFORM", "ARITH_SUB",   [" - ", "subtract", "minus"]),
    ("TRANSFORM", "ARITH_DIV",   [" / ", "divide", "quotient"]),
    ("TRANSFORM", "ARITH_MOD",   [" % ", "modulo", "remainder"]),
    # string operations
    ("TRANSFORM", "STR_CONCAT",  [" + ", "concat", "join("]),
    ("TRANSFORM", "STR_UPPER",   [".upper()", "uppercase"]),
    ("TRANSFORM", "STR_LOWER",   [".lower()", "lowercase"]),
    ("TRANSFORM", "STR_SPLIT",   [".split(", "split("]),
    ("TRANSFORM", "STR_STRIP",   [".strip(", "strip("]),
    ("TRANSFORM", "STR_FORMAT",  ["format", "f\"", "f'"]),
    # iteration
    ("ITERATE", "LOOP_FOR",      ["for ", "range("]),
    ("ITERATE", "LOOP_WHILE",    ["while "]),
    ("ITERATE", "RECURSE",       ["recurs", "factorial(", "fibonacci("]),
    ("ITERATE", "COMPREHENSION", [" for "]),
    # comparison / predicates
    ("COMPARE", "PRED_EQ",       ["==", "equal", " is "]),
    ("COMPARE", "PRED_GT",       [" > ", "greater"]),
    ("COMPARE", "PRED_LT",       [" < ", "less"]),
    ("COMPARE", "PRED_MOD0",     ["% 2 == 0", "% 2 != 1", "even"]),
    ("COMPARE", "PRED_MOD1",     ["% 2 != 0", "% 2 == 1", "odd"]),
    ("COMPARE", "PRED_PRIME",    ["prime", "divisib"]),
    ("COMPARE", "BRANCH_IF",     ["if ", "else", "elif"]),
    # aggregation — builtin vs manual
    ("AGGREGATE", "BUILTIN_SUM", ["sum("]),
    ("AGGREGATE", "BUILTIN_LEN", ["len("]),
    ("AGGREGATE", "BUILTIN_COUNT",[".count(", "count("]),
    ("AGGREGATE", "MANUAL_ACC",  ["+=", "acc", "total = ", "accumulate"]),
    ("AGGREGATE", "REDUCE",      ["reduce("]),
    # search / sort / filter
    ("SEARCH", "BUILTIN_INDEX",  [".index("]),
    ("SEARCH", "MANUAL_LOOP",    ["for i in range", "locate", "find("]),
    ("SEARCH", "CONTAINS",       ["contains", " in ", "not in"]),
    ("SORT", "SORT",             ["sort(", "sorted("]),
    ("FILTER", "FILTER",         ["filter(", "where", " if "]),
    # state / io
    ("STATE", "ASSIGN",          ["=", "+=", "-="]),
    ("STATE", "MUTATE",          ["append(", "add(", "set("]),
    ("IO", "READ",               ["read(", "get(", "input(", "open(", "def "]),
    ("IO", "WRITE",              ["return", "print(", "write(", "save(", "emit"]),
]

# Operand type detection — CONSERVATIVE: only explicit type indicators, not
# bare variable names (which are too noisy and dominate the vector).
TYPE_RULES: List[Tuple[str, List[str]]] = [
    ("STR",  ["'", '"', "str(", "string", "text", "msg"]),
    ("INT",  ["int(", "number", "count", "counter", "total"]),
    ("LIST", ["list", "arr", "items", "nums", "values", "[]", "range("]),
    ("DICT", ["dict", "map", "key", "value"]),
]


def _norm(code: str) -> str:
    return re.sub(r"\s+", " ", code).lower()


def extract_hier(code: str) -> Dict[str, int]:
    """Extract hierarchical primitives: {category:operation: count}."""
    text = _norm(code)
    counts: Dict[str, int] = {}
    for cat, op, pats in HIER_RULES:
        for p in pats:
            c = text.count(p)
            if c:
                key = f"{cat}:{op}"
                counts[key] = counts.get(key, 0) + c
    return counts


def detect_types(code: str) -> Dict[str, int]:
    """Detect operand types present in the code."""
    text = _norm(code)
    types: Dict[str, int] = {}
    for t, pats in TYPE_RULES:
        for p in pats:
            if p in text:
                types[t] = types.get(t, 0) + 1
    return types


def control_flow_signature(code: str) -> str:
    """Encode control-flow structure: sequence of B(ranch)/L(oop)/R(ecurse)."""
    text = _norm(code)
    sig = []
    if "if " in text or "else" in text:
        sig.append("B")
    if "for " in text or "while " in text or "range(" in text:
        sig.append("L")
    if "recurs" in text or "factorial(" in text or "fibonacci(" in text:
        sig.append("R")
    return "".join(sig) if sig else "S"  # S = straight-line


# ── 2. Shape vector ─────────────────────────────────────────────────────────
def shape_vector(code: str) -> Dict[str, float]:
    """Full shape: hierarchical primitives + type dims + control-flow dims,
    normalized to a unit vector."""
    hier = extract_hier(code)
    types = detect_types(code)
    cf = control_flow_signature(code)

    vec: Dict[str, float] = {}
    # hierarchical primitive dims
    for k, v in hier.items():
        vec[f"P:{k}"] = float(v)
    # type dims
    for t, v in types.items():
        vec[f"T:{t}"] = float(v)
    # control-flow dims
    for ch in cf:
        vec[f"C:{ch}"] = vec.get(f"C:{ch}", 0.0) + 1.0

    # normalize to unit vector
    norm = math.sqrt(sum(v * v for v in vec.values()))
    if norm == 0:
        return {}
    return {k: v / norm for k, v in vec.items()}


# ── 3. Comparison ───────────────────────────────────────────────────────────
def cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    keys = set(a) | set(b)
    dot = sum(a.get(k, 0) * b.get(k, 0) for k in keys)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def structural_overlap(a: Dict[str, float], b: Dict[str, float]) -> float:
    """Jaccard-like overlap of non-zero dimensions (how much of the shape is shared)."""
    ka = {k for k, v in a.items() if v > 0}
    kb = {k for k, v in b.items() if v > 0}
    if not ka and not kb:
        return 1.0
    inter = len(ka & kb)
    union = len(ka | kb)
    return inter / union if union else 0.0


def shape_similarity(code_a: str, code_b: str,
                     w_cos: float = 0.6, w_overlap: float = 0.4) -> float:
    """Weighted comparison: cosine (magnitude/direction) + structural overlap
    (which primitives are present), minus a polarity-conflict penalty.

    The P: (primitive) dims carry the specific-operation signal, so we weight
    them more than the generic T:/C: dims when computing cosine.

    Polarity penalty: if both snippets have the SAME category but OPPOSITE
    specific operations (GT vs LT, MOD0 vs MOD1, inc vs reset), the similarity
    is reduced — opposite semantics are not clones.
    """
    va = shape_vector(code_a)
    vb = shape_vector(code_b)
    c = _weighted_cosine(va, vb)
    o = structural_overlap(va, vb)
    base = w_cos * c + w_overlap * o
    penalty = _polarity_penalty(code_a, code_b)
    return max(0.0, base - penalty)


# Opposite-operation pairs within the same category (semantic opposites).
_POLARITY_OPPOSITES = [
    ("COMPARE:PRED_GT", "COMPARE:PRED_LT"),
    ("COMPARE:PRED_MOD0", "COMPARE:PRED_MOD1"),
    ("TRANSFORM:ARITH_ADD", "TRANSFORM:ARITH_SUB"),
    ("TRANSFORM:ARITH_MUL", "TRANSFORM:ARITH_DIV"),
]

# Increment vs reset: both STATE:ASSIGN but opposite semantics.
# Detect via literal patterns: "+= 1" / "= count + 1" (increment) vs "= 0" (reset).

def _polarity_penalty(code_a: str, code_b: str) -> float:
    """Return a penalty in [0, 0.5] if the two snippets use opposite operations
    in the same category (e.g. one uses >, the other <; one increments, the
    other resets)."""
    ha = extract_hier(code_a)
    hb = extract_hier(code_b)
    penalty = 0.0
    for op_a, op_b in _POLARITY_OPPOSITES:
        if ha.get(op_a, 0) > 0 and hb.get(op_b, 0) > 0:
            penalty += 0.25
        if ha.get(op_b, 0) > 0 and hb.get(op_a, 0) > 0:
            penalty += 0.25
    # increment vs reset
    a_inc = _is_increment(code_a)
    b_inc = _is_increment(code_b)
    a_reset = _is_reset(code_a)
    b_reset = _is_reset(code_b)
    if (a_inc and b_reset) or (a_reset and b_inc):
        penalty += 0.3
    return min(0.5, penalty)


def _is_increment(code: str) -> bool:
    t = _norm(code)
    return "+=" in t or "+ 1" in t or "+1" in t


def _is_reset(code: str) -> bool:
    t = _norm(code)
    return "= 0" in t or "=0" in t


def _weighted_cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    """Cosine with per-dimension weights: P: (primitive) dims weighted 2x,
    T:/C: (type/control-flow) dims weighted 1x. Emphasizes the specific
    operation over generic structure."""
    def w(k: str) -> float:
        return 2.0 if k.startswith("P:") else 1.0
    keys = set(a) | set(b)
    dot = sum(w(k) * a.get(k, 0) * b.get(k, 0) for k in keys)
    na = math.sqrt(sum(w(k) * v * v for k, v in a.items()))
    nb = math.sqrt(sum(w(k) * v * v for k, v in b.items()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# ── 4. Composition ──────────────────────────────────────────────────────────
def compose(fn_a: str, fn_b: str, mode: str = "pipe") -> Dict[str, float]:
    """Compose two function shapes into a compound shape.

    mode='pipe'  : A then B (sequential) — union of primitives, weights summed.
    mode='branch': A or B (alternative) — union, weights averaged.
    mode='nest'  : B inside A (B called within A) — union, B's primitives weighted
                   higher (inner = more specific).

    Returns the compound shape vector + a composition signature.
    """
    va = extract_hier(fn_a)
    vb = extract_hier(fn_b)
    ta = detect_types(fn_a)
    tb = detect_types(fn_b)
    cfa = control_flow_signature(fn_a)
    cfb = control_flow_signature(fn_b)

    compound: Dict[str, float] = {}
    if mode == "pipe":
        for k, v in va.items():
            compound[f"P:{k}"] = compound.get(f"P:{k}", 0) + v
        for k, v in vb.items():
            compound[f"P:{k}"] = compound.get(f"P:{k}", 0) + v
    elif mode == "branch":
        for k in set(va) | set(vb):
            compound[f"P:{k}"] = (va.get(k, 0) + vb.get(k, 0)) / 2
    elif mode == "nest":
        for k, v in va.items():
            compound[f"P:{k}"] = compound.get(f"P:{k}", 0) + v
        for k, v in vb.items():
            compound[f"P:{k}"] = compound.get(f"P:{k}", 0) + v * 1.5  # inner weighted

    # types
    for k in set(ta) | set(tb):
        compound[f"T:{k}"] = compound.get(f"T:{k}", 0) + (ta.get(k, 0) + tb.get(k, 0))
    # control flow
    for ch in cfa + cfb:
        compound[f"C:{ch}"] = compound.get(f"C:{ch}", 0) + 1.0

    norm = math.sqrt(sum(v * v for v in compound.values()))
    if norm == 0:
        return {}
    return {k: v / norm for k, v in compound.items()}


def compose_signature(fn_a: str, fn_b: str, mode: str = "pipe") -> str:
    """Human-readable compound shape signature."""
    va = extract_hier(fn_a)
    vb = extract_hier(fn_b)
    top_a = sorted(va.items(), key=lambda kv: -kv[1])[:2]
    top_b = sorted(vb.items(), key=lambda kv: -kv[1])[:2]
    sa = "+".join(f"{k.split(':')[1]}" for k, _ in top_a)
    sb = "+".join(f"{k.split(':')[1]}" for k, _ in top_b)
    if mode == "pipe":
        return f"{sa} >> {sb}"
    if mode == "branch":
        return f"{sa} | {sb}"
    return f"{sa}({sb})"


# ── Self-test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    add = "def add(a, b):\n    return a + b"
    sum2 = "def sum_two(x, y):\n    result = x + y\n    return result"
    fact = "def factorial(n):\n    if n <= 1:\n        return 1\n    return n * factorial(n - 1)"
    fib = "def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n - 1) + fibonacci(n - 2)"

    print("=== shape vectors ===")
    for name, code in [("add", add), ("sum2", sum2), ("fact", fact), ("fib", fib)]:
        sv = shape_vector(code)
        top = sorted(sv.items(), key=lambda kv: -kv[1])[:5]
        print(f"{name:6s} cf={control_flow_signature(code):4s} top={[(k, round(v,2)) for k,v in top]}")

    print("\n=== weighted similarity ===")
    print(f"add vs sum2 (clone):   {shape_similarity(add, sum2):.3f}")
    print(f"fact vs fib (diff):    {shape_similarity(fact, fib):.3f}")

    print("\n=== composition ===")
    print(f"pipe  add>>fact:  {compose_signature(add, fact, 'pipe')}")
    print(f"branch add|fact:  {compose_signature(add, fact, 'branch')}")
    print(f"nest  add(fact):  {compose_signature(add, fact, 'nest')}")
