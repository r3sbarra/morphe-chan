#!/usr/bin/env python
"""new_shape_dims.py — Genuinely new shape dimensions.

  STATE:<dim>   — statefulness (pure vs impure, mutation, global state)
  DATA:<dim>    — data structure complexity (nested, heterogeneous, size)
  CTRL:<dim>    — control flow complexity (cyclomatic, nesting depth)
  IFACE:<dim>   — function interface (params, return types, arity)
  RES:<dim>     — resource usage (I/O, memory, network, compute)

These capture aspects of code the existing 48-dim shape doesn't:
  - STATE: is the function pure (no side effects) or impure (mutates)?
  - DATA: does it use nested/heterogeneous data structures?
  - CTRL: how complex is the control flow (cyclomatic)?
  - IFACE: what's the function signature (arity, return types)?
  - RES: does it use I/O, memory, network, or heavy compute?

Dependency-free (stdlib only).
"""
import math
import re
from typing import Dict


def state_dims(code: str) -> Dict[str, float]:
    """Statefulness: pure vs impure, mutation, global state."""
    dims = {}
    # mutation (assignment to existing var, +=, etc.)
    if re.search(r"\w+\s*\+=\s*|\w+\s*-=\s*|\.append\s*\(|\.add\s*\(|\.update\s*\(", code):
        dims["STATE:MUTATES"] = 1
    # global/nonlocal
    if re.search(r"^\s*global\s+\w+|^\s*nonlocal\s+\w+", code, re.MULTILINE):
        dims["STATE:GLOBAL"] = 1
    # pure (no mutation, no I/O, no print)
    if not re.search(r"\w+\s*\+=\s*|\.append\s*\(|print\s*\(|open\s*\(|requests\.", code):
        dims["STATE:PURE"] = 1
    # class/instance state
    if re.search(r"self\.\w+\s*=|this\.\w+\s*=", code):
        dims["STATE:INSTANCE"] = 1
    return dims


def data_dims(code: str) -> Dict[str, float]:
    """Data structure complexity: nested, heterogeneous, size."""
    dims = {}
    # nested data (list of dicts, dict of lists)
    if re.search(r"\[\s*\{|\[\s*\[|\{\s*\[|\{\s*\{", code):
        dims["DATA:NESTED"] = 1
    # heterogeneous (mixed types)
    if re.search(r"\[\s*[\"']\w+[\"']\s*,\s*\d+", code):
        dims["DATA:HETEROGENEOUS"] = 1
    # large data (range, large literals)
    if re.search(r"range\s*\(\s*\d{3,}|\[\s*\d{3,}", code):
        dims["DATA:LARGE"] = 1
    # data transformation (map/filter/reduce/comprehension)
    if re.search(r"\.map\s*\(|\.filter\s*\(|\.reduce\s*\(|\[.*for.*in", code):
        dims["DATA:TRANSFORM"] = 1
    return dims


def control_dims(code: str) -> Dict[str, float]:
    """Control flow complexity: cyclomatic, nesting depth."""
    dims = {}
    # cyclomatic (branches + loops + returns)
    branches = len(re.findall(r"\bif\b|\belse\b|\belif\b|\bswitch\b|\bcase\b", code))
    loops = len(re.findall(r"\bfor\b|\bwhile\b", code))
    returns = len(re.findall(r"\breturn\b", code))
    cyclomatic = branches + loops + returns
    if cyclomatic:
        dims["CTRL:CYCLOMATIC"] = cyclomatic
    # deep nesting
    if re.search(r"if\s+.*:\s*\n\s*if\s+.*:\s*\n\s*if\s+", code):
        dims["CTRL:DEEP_NESTING"] = 1
    # early returns (multiple returns)
    if returns > 1:
        dims["CTRL:EARLY_RETURNS"] = returns
    # exception handling
    if re.search(r"try\s*:|except\s+|catch\s*\(|finally\s*:", code):
        dims["CTRL:EXCEPTIONS"] = 1
    return dims


def interface_dims(code: str) -> Dict[str, float]:
    """Function interface: params, return types, arity."""
    dims = {}
    m = re.search(r"(?:def|function|func|fun)\s+\w+\s*\(([^)]*)\)", code)
    if m:
        params = [p.strip() for p in m.group(1).split(",") if p.strip()]
        dims["IFACE:ARITY"] = len(params)
        # typed params
        if any(":" in p for p in params):
            dims["IFACE:TYPED"] = 1
        # default params
        if any("=" in p for p in params):
            dims["IFACE:DEFAULTS"] = 1
    # return type annotation
    if re.search(r"->\s*\w+", code):
        dims["IFACE:RETURN_TYPE"] = 1
    # variadic
    if re.search(r"\*args|\*\*kwargs|\.\.\.", code):
        dims["IFACE:VARIADIC"] = 1
    return dims


def resource_dims(code: str) -> Dict[str, float]:
    """Resource usage: I/O, memory, network, compute."""
    dims = {}
    if re.search(r"\bopen\s*\(|\.read\s*\(|\.write\s*\(|readFile|writeFile", code):
        dims["RES:IO"] = 1
    if re.search(r"requests\.|urlopen|\.get\s*\(|\.post\s*\(|fetch\s*\(", code):
        dims["RES:NETWORK"] = 1
    if re.search(r"\[\s*\]\s*\*|list\s*\(\s*\w+\s*\)|\.copy\s*\(|deepcopy", code):
        dims["RES:MEMORY"] = 1
    if re.search(r"for\s+.*:\s*\n\s*for\s+|recurs|factorial\(|fibonacci\(", code):
        dims["RES:COMPUTE"] = 1
    if re.search(r"thread|Thread|async|await|multiprocess|Pool\s*\(", code):
        dims["RES:CONCURRENCY"] = 1
    return dims


def new_shape_dims(code: str) -> Dict[str, float]:
    """All new shape dimensions."""
    dims = {}
    for fn in (state_dims, data_dims, control_dims, interface_dims, resource_dims):
        dims.update(fn(code))
    return dims


def extended_shape(code: str, lang: str = "python") -> Dict[str, float]:
    """Extended shape: existing enriched + new dimensions."""
    from code_shape.core.enriched_shape import enriched_shape
    vec = enriched_shape(code, lang)
    vec.update(new_shape_dims(code))
    # normalize
    norm = math.sqrt(sum(x * x for x in vec.values()))
    if norm == 0:
        return {}
    return {k: round(v / norm, 4) for k, v in vec.items()}


# ── Self-test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    code = "def process_user(request):\n    data = request.json\n    name = data.get('name', '')\n    if not name:\n        return {'error': 'missing'}\n    db.execute('INSERT INTO users (name) VALUES (?)', (name,))\n    return {'status': 'ok'}"
    print("=== New shape dimensions ===")
    dims = new_shape_dims(code)
    for k, v in sorted(dims.items()):
        print(f"  {k}: {v}")
    print(f"\nnew dims: {len(dims)}")
    print(f"extended total: {len(extended_shape(code))}")
