#!/usr/bin/env python
"""value_flow_shape.py — Value-flow-aware shape: track inputs/outputs through
the vector dimensions.
flow through the primitive dimensions. Instead of just counting operations,
this traces the DATA-FLOW PATH: an input enters (READ), transforms through
primitives (TRANSFORM/AGGREGATE/FILTER), and exits as an output (WRITE/RETURN).

The value-aware shape vector encodes:
  - INPUT dims: what enters (params, user input, constants, env)
  - FLOW dims: how values transform (the path through primitives)
  - OUTPUT dims: what exits (return, write, emit)

This gives a richer shape: two functions with the same op counts but different
data flow (e.g. input->filter->output vs input->transform->output) have
different value-flow shapes.

Dependency-free (stdlib only).
"""
import math
import re
from typing import Dict, List, Optional, Set, Tuple

# ── Input sources ──────────────────────────────────────────────────────────
INPUT_SOURCES = {
    "PARAM": r"(?:def|function|func|fun)\s+\w+\s*\(([^)]*)\)",
    "USER_INPUT": r"\binput\s*\(|\breadline|\bstdin",
    "REQUEST": r"request\.(?:args|form|json|data|params|query)|req\.(?:query|params|body)|ctx\.(?:query|param|body)|\$_GET|\$_POST",
    "ENV": r"os\.environ|getenv",
    "CONSTANT": r"=\s*[\"'][^\"']+[\"']|=\s*\d+",
    "FILE_READ": r"\bopen\s*\([^)]*['\"]r|\.read\s*\(|readFile",
    "DB_READ": r"execute\s*\([^)]*SELECT|query\s*\([^)]*SELECT|fetchone|fetchall",
    "WEB_GET": r"requests\.get|urlopen|fetch\s*\(|\.get\s*\(",
}

# ── Output sinks ────────────────────────────────────────────────────────────
OUTPUT_SINKS = {
    "RETURN": r"\breturn\b",
    "PRINT": r"\bprint\s*\(|console\.log|System\.out|puts\s*|echo\s*|println",
    "FILE_WRITE": r"\.write\s*\(|open\s*\([^)]*['\"][wa]|writeFile",
    "DB_WRITE": r"execute\s*\([^)]*(?:INSERT|UPDATE|DELETE)|commit\s*\(",
    "WEB_POST": r"requests\.post|\.send\s*\(|fetch\s*\([^)]*POST",
    "EMIT": r"\.emit\s*\(|yield\b|\.send\s*\(",
}

# ── Transform primitives (value transformations) ────────────────────────────
TRANSFORMS = {
    "ARITH": r" [+*/-] |%=",
    "CONCAT": r" \+ |join\s*\(|format\s*\(",
    "CAST": r"int\s*\(|str\s*\(|float\s*\(|\.toString|parseInt|Number\s*\(",
    "AGGREGATE": r"sum\s*\(|count\s*\(|reduce\s*\(|len\s*\(",
    "FILTER": r"filter\s*\(|if\s+\w+\s*[<>!=]|comprehension",
    "SORT": r"sort\s*\(|sorted\s*\(|orderBy",
    "SEARCH": r"find\s*\(|index\s*\(|contains|\.indexOf|in\s+\w+",
    "SLICE": r"\[[^\]]*:[^\]]*\]|substring|slice\s*\(",
    "SPLIT": r"\.split\s*\(|split\s*\(",
    "JOIN": r"\.join\s*\(|join\s*\(",
    "MAP": r"\.map\s*\(|map\s*\(",
    "REDUCE": r"\.reduce\s*\(|reduce\s*\(",
}


def _extract_params(code: str) -> Set[str]:
    """Extract function parameter names."""
    params = set()
    for m in re.finditer(INPUT_SOURCES["PARAM"], code):
        for p in m.group(1).split(","):
            p = p.strip().split(":")[0].strip().split("=")[0].strip()
            if p and re.match(r"^[a-zA-Z_]", p):
                params.add(p)
    return params


def _assignments(code: str) -> Dict[str, str]:
    """Extract variable assignments: {var: rhs_expression}."""
    assigns = {}
    for m in re.finditer(r"(\w+)\s*=\s*([^;\n]+)", code):
        var, rhs = m.group(1), m.group(2).strip()
        if not rhs.startswith(("=", "==", "!=", "<=", ">=")):
            assigns[var] = rhs
    return assigns


def _propagate_taint(code: str, params: Set[str]) -> Dict[str, Set[str]]:
    """Track which variables are tainted (derive from inputs). Returns {var: sources}."""
    taint: Dict[str, Set[str]] = {p: {"PARAM"} for p in params}
    assigns = _assignments(code)
    changed = True
    while changed:
        changed = False
        for var, rhs in assigns.items():
            if var in taint:
                continue
            # check if RHS references a tainted var or an input source
            sources = set()
            for tvar, tsrc in taint.items():
                if re.search(r"\b" + re.escape(tvar) + r"\b", rhs):
                    sources |= tsrc
            for src_name, pat in INPUT_SOURCES.items():
                if src_name == "PARAM":
                    continue
                if re.search(pat, rhs):
                    sources.add(src_name)
            if sources and var not in taint:
                taint[var] = sources
                changed = True
    return taint


def _assignments_ordered(code: str) -> List[tuple]:
    """Assignments in source order: [(var, rhs, line_no)]."""
    out = []
    for i, line in enumerate(code.splitlines(), 1):
        m = re.match(r"\s*(\w+)\s*=\s*(.+)$", line)
        if m and not m.group(2).startswith(("=", "==", "!=", "<=", ">=")):
            out.append((m.group(1), m.group(2).strip(), i))
    return out


def trace_taint_path(code: str, sink_line_expr: str,
                     params: Optional[Set[str]] = None) -> List[str]:
    """Reconstruct the FULL source->...->sink data-flow path (Route Sixty-Sink style).

    Returns an ordered list of hops, e.g.
        ["PARAM:user_input", "payload", "query", "cursor.execute(...)"]
    where each intermediate variable is a real assignment the tainted value
    passes through before reaching the sink expression. Falls back to a
    2-hop [source, sink] if no intermediate assignments exist.
    """
    if params is None:
        params = _extract_params(code)
    taint = _propagate_taint(code, params)
    assigns = _assignments_ordered(code)

    # Which tainted variable(s) feed the sink expression?
    feed_vars = [var for var in taint if re.search(r"\b" + re.escape(var) + r"\b", sink_line_expr)]
    if not feed_vars:
        # Direct source in the sink line itself.
        for src_name in ("REQUEST", "PARAM", "CONSTANT"):
            if re.search(INPUT_SOURCES[src_name], sink_line_expr, re.IGNORECASE):
                return [src_name, sink_line_expr.strip()[:40]]
        return [sink_line_expr.strip()[:40]]

    # For the first feeding var, walk backward through assignments to build
    # the ordered chain from a source down to the var.
    sink_var = feed_vars[0]
    var_sources = taint.get(sink_var, set())
    src_kind = ",".join(sorted(var_sources)) if var_sources else "UNKNOWN"

    # Build an ordered prefix: sources -> intermediate vars -> sink_var
    chain = []
    seen = set()
    for var, rhs, _ln in assigns:
        if var in seen:
            continue
        if var == sink_var:
            break
        # Is this var on the taint path? (It must eventually feed sink_var.)
        if re.search(r"\b" + re.escape(var) + r"\b", sink_line_expr) or \
           any(re.search(r"\b" + re.escape(var) + r"\b", r2) for _v, r2, _l in assigns):
            # Only include vars actually referenced by later path vars.
            if any(re.search(r"\b" + re.escape(var) + r"\b", r3)
                   for v2, r3, _l2 in assigns if v2 != var):
                chain.append(var)
                seen.add(var)
    path = [src_kind] + chain + [sink_var, sink_line_expr.strip()[:40]]
    # Trim trailing empties / collapse duplicates at the front.
    path = [p for p in path if p]
    if len(path) >= 3 and path[0] == path[1]:
        path.pop(1)
    return path


def _output_vars(code: str, taint: Dict[str, Set[str]]) -> List[Tuple[str, Set[str]]]:
    """Find output expressions and which tainted vars feed them."""
    outputs = []
    for m in re.finditer(r"\breturn\b\s*([^;\n]+)", code):
        expr = m.group(1).strip()
        srcs = set()
        for var, tsrc in taint.items():
            if re.search(r"\b" + re.escape(var) + r"\b", expr):
                srcs |= tsrc
        outputs.append(("RETURN", expr, srcs))
    for m in re.finditer(r"\bprint\s*\(([^)]*)\)|console\.log\s*\(([^)]*)\)", code):
        expr = (m.group(1) or m.group(2) or "").strip()
        srcs = set()
        for var, tsrc in taint.items():
            if re.search(r"\b" + re.escape(var) + r"\b", expr):
                srcs |= tsrc
        outputs.append(("PRINT", expr, srcs))
    return outputs


def _flow_dims(code: str) -> Dict[str, int]:
    """Lexer-aware transform detection.

    Strings and comments are stripped so a literal `+`/`*` inside a string
    never counts as arithmetic. Arithmetic counts distinct operator tokens
    so `a=b+c` (no spaces) still fires. String-method transforms
    (.strip/.upper/.lower/.replace/...) are captured as STRING_TRANSFORM.
    """
    from code_shape.core.agnostic_shape import _tokenize, _strip_strings_and_comments
    stripped = _strip_strings_and_comments(code)
    toks = _tokenize(code)
    flow: Dict[str, int] = {}

    def bump(op: str, by: int = 1) -> None:
        flow[op] = flow.get(op, 0) + by

    arith_ops = ("+", "-", "*", "/", "%")
    for t in toks:
        if t in arith_ops:
            bump("ARITH")
        elif t in ("+=", "-=", "*=", "/=", "%="):
            bump("ARITH")
    # concatenation: str-join / format / adjacent `+` on strings (approx)
    for i, t in enumerate(toks):
        if t == "join" and (i == 0 or toks[i - 1] == "."):
            bump("CONCAT")
        elif t == "format":
            bump("CONCAT")
    # casts
    for t in toks:
        if t in ("int", "str", "float", "bool", "complex", "Number", "parseInt", "parseFloat", "toString"):
            bump("CAST")
    # aggregate / filter / sort / search / map / reduce
    for t in toks:
        if t in ("sum", "count", "reduce", "len", "min", "max"):
            bump("AGGREGATE")
        elif t in ("filter", "where"):
            bump("FILTER")
        elif t in ("sort", "sorted", "orderBy"):
            bump("SORT")
        elif t in ("find", "index", "contains", "includes", "search", "indexOf"):
            bump("SEARCH")
        elif t == "map":
            bump("MAP")
        elif t == "reduce":
            bump("REDUCE")
    # string-method transforms (on a receiver) + slicing/substring
    string_methods = {"upper", "lower", "strip", "lstrip", "rstrip", "replace",
                      "split", "join", "capitalize", "casefold", "substring",
                      "replaceAll", "trim", "padStart", "padEnd", "title"}
    for i, t in enumerate(toks):
        if t == "split" and (i == 0 or toks[i - 1] == "."):
            bump("SPLIT")
        elif t in ("substring", "slice") and (i == 0 or toks[i - 1] == "."):
            bump("SLICE")
        elif t in string_methods:
            bump("STRING_TRANSFORM")
    # simple list/string slice `a[1:3]` on stripped source
    if re.search(r"\[[^\]]*:[^\]]*\]", stripped):
        bump("SLICE")
    # list/dict comprehension `[x for ... if ...]` is a filter
    if re.search(r"\[.*\bfor\b.*\bif\b", stripped):
        bump("FILTER")
    return flow


def value_flow_shape(code: str) -> Dict[str, float]:
    """Build the value-flow shape vector.

    Dimensions:
      IN:<source>   — input sources present (PARAM, USER_INPUT, REQUEST, ENV, ...)
      FLOW:<op>     — transform primitives the values pass through
      OUT:<sink>    — output sinks (RETURN, PRINT, FILE_WRITE, ...)
      TAINT:<src>   — tainted vars derived from each input source
    """
    vec: Dict[str, float] = {}
    params = _extract_params(code)
    taint = _propagate_taint(code, params)

    # INPUT dims
    for src_name, pat in INPUT_SOURCES.items():
        if src_name == "PARAM":
            if params:
                vec[f"IN:PARAM"] = float(len(params))
        elif re.search(pat, code):
            vec[f"IN:{src_name}"] = 1.0

    # FLOW dims (transforms) — lexer-aware: strings/comments stripped so a
    # spaced-operator regex never matches literal `+`/`*`, compact `a=b+c`
    # (no spaces) still counts as arithmetic, and common string-method
    # transforms (.strip/.upper/.lower/...) are captured.
    flow = _flow_dims(code)
    for op, n in flow.items():
        vec[f"FLOW:{op}"] = vec.get(f"FLOW:{op}", 0) + n

    # OUT dims
    for sink, pat in OUTPUT_SINKS.items():
        n = len(re.findall(pat, code))
        if n:
            vec[f"OUT:{sink}"] = float(n)

    # TAINT dims (which inputs propagate to outputs)
    outputs = _output_vars(code, taint)
    for _, _, srcs in outputs:
        for s in srcs:
            vec[f"TAINT:{s}"] = vec.get(f"TAINT:{s}", 0) + 1.0

    # normalize
    norm = math.sqrt(sum(v * v for v in vec.values()))
    if norm == 0:
        return {}
    return {k: round(v / norm, 4) for k, v in vec.items()}


def cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    keys = set(a) | set(b)
    dot = sum(a.get(k, 0) * b.get(k, 0) for k in keys)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def value_flow_similarity(code_a: str, code_b: str) -> float:
    """Cosine similarity between two value-flow shapes."""
    return cosine(value_flow_shape(code_a), value_flow_shape(code_b))


def flow_path(code: str) -> str:
    """Human-readable data-flow path: IN -> FLOW -> OUT."""
    vec = value_flow_shape(code)
    ins = sorted([k[3:] for k in vec if k.startswith("IN:")], key=lambda k: -vec[f"IN:{k}"])
    flows = sorted([k[5:] for k in vec if k.startswith("FLOW:")], key=lambda k: -vec[f"FLOW:{k}"])
    outs = sorted([k[4:] for k in vec if k.startswith("OUT:")], key=lambda k: -vec[f"OUT:{k}"])
    return f"{'+'.join(ins) or '?'} -> {'>'.join(flows) or '?'} -> {'+'.join(outs) or '?'}"


# ── Self-test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Same op counts, different data flow
    filter_fn = "def process(nums):\n    evens = [n for n in nums if n % 2 == 0]\n    return evens"
    transform_fn = "def process(nums):\n    doubled = [n * 2 for n in nums]\n    return doubled"
    # Input -> transform -> output
    add_fn = "def add(a, b):\n    return a + b"
    # Web input -> db write
    web_fn = "def save(req):\n    name = req.form['name']\n    db.execute('INSERT INTO users (name) VALUES (?)', (name,))\n    return 'ok'"

    print("=== Value-flow shapes ===")
    for name, code in [("filter", filter_fn), ("transform", transform_fn), ("add", add_fn), ("web", web_fn)]:
        print(f"{name:10s} path={flow_path(code)}")
        print(f"  dims: {sorted(value_flow_shape(code).keys())}")

    print("\n=== Value-flow similarity ===")
    print(f"filter vs transform (same op, diff flow): {value_flow_similarity(filter_fn, transform_fn):.3f}")
    print(f"add vs web (diff flow):                   {value_flow_similarity(add_fn, web_fn):.3f}")
