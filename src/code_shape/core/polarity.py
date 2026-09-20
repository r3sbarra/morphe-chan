#!/usr/bin/env python
"""polarity.py — Semantic polarity penalty for code similarity.

Opposite operations are NOT clones: `a + b` and `a - b` share almost all
tokens but do opposite things. A pure cosine similarity over primitive
counts (or bag-of-tokens) gives such pairs a high score; this module applies
a penalty when two code snippets use semantically opposite operations, so
increment-only code doesn't masquerade as decrement-only code.

Operates on the 23-dim primitive count vocabulary shared by the adapters and
the code-agnostic shape model.

Dependency-free (stdlib only).
"""

from typing import Dict, Tuple

# Opposite-operation pairs within the same category. A snippet using one and
# the other using its counterpart is a semantic polarity conflict.
POLARITY_OPPOSITES: Tuple[Tuple[str, str], ...] = (
    ("ARITH_ADD", "ARITH_SUB"),
    ("ARITH_MUL", "ARITH_DIV"),
    ("COMPARE_GT", "COMPARE_LT"),
    ("COMPARE_GE", "COMPARE_LE"),
    ("COMPARE_EQ", "COMPARE_NE"),
    ("READ", "WRITE"),
)

# Per-conflict penalty magnitude.
_CONFLICT_PENALTY = 0.35
_MAX_PENALTY = 0.5


def polarity_penalty(vec_a: Dict[str, int], vec_b: Dict[str, int]) -> float:
    """Return a penalty in [0, _MAX_PENALTY] if the two primitive-count vectors
    use opposite operations. A snippet that only returns (no opposite ops)
    gets 0."""
    penalty = 0.0
    for op_a, op_b in POLARITY_OPPOSITES:
        if vec_a.get(op_a, 0) > 0 and vec_b.get(op_b, 0) > 0:
            penalty += _CONFLICT_PENALTY
        if vec_a.get(op_b, 0) > 0 and vec_b.get(op_a, 0) > 0:
            penalty += _CONFLICT_PENALTY
    return min(_MAX_PENALTY, penalty)


def polarity_adjusted(base: float, penalty: float) -> float:
    """Subtract a polarity penalty from a base similarity (clamped to 0)."""
    return max(0.0, base - penalty)


# ── Literal (constant) disagreement penalty ────────────────────────────────
# Two snippets that use the same operators but on DIFFERENT constants are
# usually NOT clones: `n % 2 == 0` (is_even) vs `n % 2 == 1` (is_odd) share
# every primitive (ARITH_MOD + COMPARE_EQ + RETURN) yet do opposite things.
# Comparing the numeric literals used with comparison/arithmetic operators
# catches this class of false clone.
_LITERAL_DISAGREEMENT_PENALTY = 0.30
_LITERAL_MAX_PENALTY = 0.45


def _literal_context(code: str):
    """Return the set of numeric literals that appear as operands of
    comparison or arithmetic operators (roughly: next/prev token context),
    plus the bare modulo/compare constants. Uses the agnostic tokenizer so
    strings/comments are stripped."""
    from .agnostic_shape import _tokenize
    toks = _tokenize(code)
    literals = set()
    n = len(toks)
    for i, t in enumerate(toks):
        if t.isdigit() or (t.startswith("-") and t[1:].isdigit()) or "." in t and t.replace(".", "", 1).isdigit():
            # numeric literal; is it near a compare/arith operator?
            near = False
            for j in (i - 1, i + 1):
                if 0 <= j < n and toks[j] in ("==", "!=", ">", "<", ">=", "<=", "%", "+", "-", "*", "/"):
                    near = True
            # also bare comparison constants are operands (e.g. `% 2`, `== 0`)
            if near:
                literals.add(t)
    return literals


def literal_disagreement_penalty(code_a: str, code_b: str) -> float:
    """Return a penalty in [0, _LITERAL_MAX_PENALTY] if both snippets use
    comparison/arithmetic operators but on overlapping-but-different numeric
    constants (e.g. `% 2` vs `% 3`, `== 0` vs `== 1`). Identical constant sets
    → no penalty (renamed-var clones keep their literals)."""
    la = _literal_context(code_a)
    lb = _literal_context(code_b)
    if not la or not lb:
        return 0.0
    common = la & lb
    if common == la and common == lb:
        return 0.0  # same constants
    return min(_LITERAL_MAX_PENALTY, _LITERAL_DISAGREEMENT_PENALTY)


def combined_similarity_penalty(base: float, vec_a: Dict[str, int], vec_b: Dict[str, int],
                                code_a: str, code_b: str) -> float:
    """Combine the polarity and literal-disagreement penalties and subtract
    from a base similarity (clamped to 0). This is the unified entry point for
    similarity scorers that have both the primitive vectors and the raw code."""
    penalty = polarity_penalty(vec_a, vec_b)
    penalty = max(penalty, literal_disagreement_penalty(code_a, code_b))
    return polarity_adjusted(base, penalty)
