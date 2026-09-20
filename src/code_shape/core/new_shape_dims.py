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

Detection is LEXER-AWARE: it reuses the agnostic_shape tokenizer, which strips
string literals and comments, so keywords/operators inside them never produce
phantom dims (e.g. `print(` in a comment no longer kills STATE:PURE, `if` inside
a string no longer counts cyclomatic, and `data.get("x")` no longer parses as a
network call).

Dependency-free (stdlib only).
"""
import math
import re
from typing import Dict, List

from .agnostic_shape import _strip_strings_and_comments, _tokenize


def _tokens(code: str) -> List[str]:
    """Tokens with strings/comments stripped (never phantom primitives)."""
    return _tokenize(code)


def _text(code: str) -> str:
    """Stripped source (strings/comments removed) for whitespace-level checks."""
    return _strip_strings_and_comments(code)


def state_dims(code: str) -> Dict[str, float]:
    """Statefulness: pure vs impure, mutation, global state (lexer-aware)."""
    toks = _tokens(code)
    dims: Dict[str, float] = {}
    # mutation: compound-assign, or method-call mutation (.append/.add/.update)
    compound = any(t in ("+=", "-=", "*=", "/=", "%=", "<<=", ">>=", "|=", "&=", "^=") for t in toks)
    mut_method = any(
        toks[i] == "." and i + 1 < len(toks) and toks[i + 1] in ("append", "add", "update", "extend", "insert", "remove", "pop", "set", "push", "put")
        for i in range(len(toks) - 1)
    )
    if compound or mut_method:
        dims["STATE:MUTATES"] = 1
    # global/nonlocal (stripped source so a comment can't fake it)
    if re.search(r"^\s*(?:global|nonlocal)\s+\w+", _text(code), re.MULTILINE):
        dims["STATE:GLOBAL"] = 1
    # pure: no mutation, no I/O, no network, no print — but NOT for empty/trivial
    # code (no function = vacuously pure, which inflates the enriched vector).
    stripped = _text(code)
    io_net = re.search(r"\b(?:open|read|write|print|printf|requests|urlopen|fetch)\s*\(", stripped)
    has_fn = re.search(r"\b(?:def|function|func|fun|fn)\s+\w+\s*\(", stripped)
    if has_fn and not (compound or mut_method or io_net):
        dims["STATE:PURE"] = 1
    # class/instance state
    for i in range(len(toks) - 2):
        if toks[i] in ("self", "this") and toks[i + 1] == "." and toks[i + 2] == "=":
            dims["STATE:INSTANCE"] = 1
    return dims


def data_dims(code: str) -> Dict[str, float]:
    """Data structure complexity: nested, heterogeneous, size (lexer-aware)."""
    toks = _tokens(code)
    dims: Dict[str, float] = {}
    stripped = _text(code)
    # nested data (list of dicts, dict of lists, etc.) — token-level
    if any(
        toks[i] == "[" and i + 1 < len(toks) and toks[i + 1] in ("{", "[")
        or toks[i] == "{" and i + 1 < len(toks) and toks[i + 1] in ("[", "{")
        for i in range(len(toks) - 1)
    ):
        dims["DATA:NESTED"] = 1
    # heterogeneous: a literal list mixing a string and a number
    if re.search(r"\[\s*[\"']\w+[\"']\s*,\s*\d+", stripped):
        dims["DATA:HETEROGENEOUS"] = 1
    # large data (range with big bound, big literal)
    if re.search(r"\brange\s*\(\s*\d{3,}|\[\s*\d{3,}", stripped):
        dims["DATA:LARGE"] = 1
    # data transformation (map/filter/reduce/comprehension)
    if any(
        toks[i] == "." and i + 1 < len(toks) and toks[i + 1] in ("map", "filter", "reduce")
        or toks[i] == "for" and i + 1 < len(toks) and toks[i + 1] == "in"
        for i in range(len(toks) - 1)
    ):
        dims["DATA:TRANSFORM"] = 1
    return dims


def control_dims(code: str) -> Dict[str, float]:
    """Control flow complexity: cyclomatic, nesting depth (lexer-aware)."""
    toks = _tokens(code)
    dims: Dict[str, float] = {}
    branches = sum(1 for t in toks if t in ("if", "else", "elif", "switch", "case", "when"))
    loops = sum(1 for t in toks if t in ("for", "while", "foreach", "until", "repeat"))
    returns = sum(1 for t in toks if t in ("return", "yield"))
    cyclomatic = branches + loops + returns
    if cyclomatic:
        dims["CTRL:CYCLOMATIC"] = cyclomatic
    # deep nesting: three consecutive indented if/for blocks (stripped source)
    if re.search(r"^(?:\s*(?:if|for|while).*\n){3}", _text(code), re.MULTILINE):
        dims["CTRL:DEEP_NESTING"] = 1
    # early returns
    if returns > 1:
        dims["CTRL:EARLY_RETURNS"] = returns
    # exception handling
    if any(t in ("try", "except", "finally", "catch", "throw") for t in toks):
        dims["CTRL:EXCEPTIONS"] = 1
    return dims


def interface_dims(code: str) -> Dict[str, float]:
    """Function interface: params, return types, arity (lexer-aware)."""
    stripped = _text(code)
    dims: Dict[str, float] = {}
    m = re.search(r"(?:def|function|func|fun)\s+\w+\s*\(([^)]*)\)", stripped)
    if m:
        params = [p.strip() for p in m.group(1).split(",") if p.strip()]
        dims["IFACE:ARITY"] = len(params)
        if any(":" in p for p in params):
            dims["IFACE:TYPED"] = 1
        if any("=" in p for p in params):
            dims["IFACE:DEFAULTS"] = 1
    # return type annotation
    toks = _tokens(code)
    if "->" in toks:
        dims["IFACE:RETURN_TYPE"] = 1
    # variadic
    if any(t in ("*args", "**kwargs") for t in toks) and any(t in ("args", "kwargs") for t in toks):
        dims["IFACE:VARIADIC"] = 1
    return dims


def resource_dims(code: str) -> Dict[str, float]:
    """Resource usage: I/O, memory, network, compute (lexer-aware)."""
    toks = _tokens(code)
    dims: Dict[str, float] = {}
    # I/O: literal file/stream operations (open/read/write/readFile/writeFile)
    io = any(t in ("open", "read", "readline", "readlines", "write", "readFile", "writeFile", "close", "flush") for t in toks)
    io |= any(toks[i] == "." and i + 1 < len(toks) and toks[i + 1] in ("read", "write", "readline", "readlines", "close")
              for i in range(len(toks) - 1))
    if io:
        dims["RES:IO"] = 1
    # NETWORK: only when the call base is a known HTTP/network object — NOT .get on a dict,
    # and NOT a variable literally named `request` (Django/Flask request object is not I/O).
    net_base = {"requests", "urllib", "urlopen", "fetch", "axios", "http", "https", "websocket", "aiohttp", "httpx", "session"}
    net = False
    for i in range(len(toks) - 1):
        if toks[i] in net_base and toks[i + 1] == ".":
            net = True
        if toks[i] == "fetch" and i + 1 < len(toks) and toks[i + 1] == "(":
            net = True
        if toks[i] in ("urlopen",) and i + 1 < len(toks) and toks[i + 1] != ".":
            # bare urlopen( — a network entry point (requests.get handled via base above)
            net = True
    if net:
        dims["RES:NETWORK"] = 1
    # MEMORY: list replication, copies, big buffers
    mem = any(
        toks[i] == "[" and i + 2 < len(toks) and toks[i + 1] == "]" and toks[i + 2] == "*"
        or toks[i] in ("deepcopy", "copy", "list", "buffer", "alloc")
        for i in range(len(toks))
    )
    if mem:
        dims["RES:MEMORY"] = 1
    # COMPUTE: nested loops or recursion
    loops = sum(1 for t in toks if t in ("for", "while", "foreach", "until", "repeat"))
    rec = any(t in ("recurs",) for t in toks)
    if loops >= 2:
        dims["RES:COMPUTE"] = 1
    # CONCURRENCY
    if any(t in ("thread", "async", "await", "multiprocess", "parallel", "goroutine") for t in toks) or \
       any(toks[i] == "." and i + 1 < len(toks) and toks[i + 1] in ("start", "join", "launch") for i in range(len(toks) - 1)):
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
