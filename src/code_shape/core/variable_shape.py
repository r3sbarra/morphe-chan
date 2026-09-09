#!/usr/bin/env python
"""variable_shape.py — Param & variable shape enrichment with smart type inference.

Morphē-chan's shape model treats code as a geometric vector of *operations*
(primitives, efficiency, flow, patterns...). This module enriches that model
with the *data* dimension: the shapes of the parameters and variables
themselves.

Why it matters:
  - Two functions with identical op counts but different data shapes (one
    takes a `List[int]` and mutates it; the other takes a `Dict[str, Callable]`
    and reads it) are semantically different. Op-only shapes can't see that.
  - Type-aware shapes power better synthesis (compose functions whose
    param/variable types line up) and better bug detection (a `LIST_INDEX`
    on a `DICT` is a type error; a tainted index into a `LIST` is an overflow).

What this module adds:
  1. SMART TYPE INFERENCE — AST-based for Python (annotations, generics,
     assignment RHS, call-return types, usage refinement), regex fallback for
     the other 12 languages. Resolves the "UNKNOWN" flood the old regex-only
     `type_aware_ast._infer_types` produced.
  2. PARAM/VARIABLE SHAPES — per-identifier dimensions:
       PARAM:<name>:<TYPE>   — function parameters (with role: IN/OUT/INOUT)
       VAR:<name>:<TYPE>     — local variables
     plus aggregate dims (VAR_COUNT, PARAM_COUNT, TYPE_DIVERSITY, MUTATION).
  3. CASCADING TYPE PROPAGATION — a variable's type flows through the call
     graph: if `f(x)` passes `x` to `g(y)` and `g` indexes `y`, then `x` is
     likely a LIST. This is the "cascading effect" of types across functions.

Dependency-free (stdlib only).
"""
from __future__ import annotations

import ast
import math
import re
from typing import Any, Dict, List, Optional, Set, Tuple

# ── Canonical type vocabulary ──────────────────────────────────────────────
# Coarse buckets that are language-agnostic and useful for shape comparison.
TYPE_BUCKETS = [
    "INT", "FLOAT", "NUM", "STR", "BOOL", "LIST", "DICT", "SET", "TUPLE",
    "CALLABLE", "CLASS", "ORM", "FILE", "NONE", "UNKNOWN",
]

# Total cross-function type propagations performed by the last _infer_python_types
# call (used by cascading_type_flow to report accurate propagation counts).
_PROPAGATION_COUNT = 0

# Numeric buckets are mutually compatible (INT/FLOAT/NUM are all numbers).
_NUMERIC_BUCKETS = {"INT", "FLOAT", "NUM"}


def _types_compatible(a: str, b: str) -> bool:
    """True if two type buckets are compatible (no type error).

    Numeric buckets (INT/FLOAT/NUM) are mutually compatible. Everything else
    must match exactly (or be UNKNOWN, which is not an error).
    """
    if a == "UNKNOWN" or b == "UNKNOWN":
        return True
    if a == b:
        return True
    if a in _NUMERIC_BUCKETS and b in _NUMERIC_BUCKETS:
        return True
    return False

# Python builtin -> bucket
_PY_BUILTIN_BUCKET = {
    "int": "INT", "float": "FLOAT", "complex": "NUM", "str": "STR",
    "bool": "BOOL", "list": "LIST", "dict": "DICT", "set": "SET",
    "frozenset": "SET", "tuple": "TUPLE", "bytes": "STR", "bytearray": "STR",
    "callable": "CALLABLE", "type": "CLASS", "object": "CLASS",
    "NoneType": "NONE", "None": "NONE",
}

# Call-return type hints: builtin call -> bucket of its return value
_CALL_RETURN_BUCKET = {
    "len": "INT", "int": "INT", "float": "FLOAT", "str": "STR", "bool": "BOOL",
    "list": "LIST", "dict": "DICT", "set": "SET", "tuple": "TUPLE",
    "sum": "NUM", "abs": "NUM", "round": "NUM", "min": "NUM", "max": "NUM",
    "sorted": "LIST", "reversed": "LIST", "enumerate": "LIST", "zip": "LIST",
    "range": "LIST", "open": "FILE", "input": "STR", "repr": "STR",
    "format": "STR", "chr": "STR", "ord": "INT", "hash": "INT",
    "id": "INT", "isinstance": "BOOL", "hasattr": "BOOL",
    "json.loads": "DICT", "json.dumps": "STR",
    "os.environ.get": "STR", "os.getenv": "STR",
    "str.split": "LIST", "str.join": "STR", "str.strip": "STR",
    "str.upper": "STR", "str.lower": "STR", "str.replace": "STR",
    "dict.get": "UNKNOWN", "dict.keys": "LIST", "dict.values": "LIST",
    "dict.items": "LIST", "list.append": "NONE", "list.extend": "NONE",
    "list.pop": "UNKNOWN", "list.index": "INT", "list.count": "INT",
    "set.add": "NONE", "set.union": "SET",
}

# Method-name -> bucket for attribute-call inference (obj.method())
_METHOD_BUCKET = {
    "append": "NONE", "extend": "NONE", "pop": "UNKNOWN", "remove": "NONE",
    "insert": "NONE", "index": "INT", "count": "INT", "sort": "NONE",
    "reverse": "NONE", "get": "UNKNOWN", "keys": "LIST", "values": "LIST",
    "items": "LIST", "update": "NONE", "setdefault": "UNKNOWN",
    "upper": "STR", "lower": "STR", "strip": "STR", "split": "LIST",
    "join": "STR", "replace": "STR", "startswith": "BOOL", "endswith": "BOOL",
    "find": "INT", "format": "STR", "add": "NONE", "union": "SET",
    "read": "STR", "readline": "STR", "readlines": "LIST", "write": "INT",
    "close": "NONE", "flush": "NONE", "seek": "NONE",
    "filter": "LIST", "all": "LIST", "first": "UNKNOWN", "get_or_create": "UNKNOWN",
    "objects": "ORM", "query": "ORM", "execute": "UNKNOWN", "commit": "NONE",
    "fetchone": "UNKNOWN", "fetchall": "LIST", "fetchmany": "LIST",
}

# Attribute-name -> bucket (obj.attr)
_ATTR_BUCKET = {
    "objects": "ORM", "query": "ORM", "text": "STR", "name": "STR",
    "id": "INT", "count": "INT", "length": "INT", "size": "INT",
    "status": "INT", "code": "INT", "value": "UNKNOWN", "data": "UNKNOWN",
    "items": "LIST", "keys": "LIST", "values": "LIST",
}


# ── 1. SMART TYPE INFERENCE ────────────────────────────────────────────────
def _bucket_from_annotation(ann: str) -> str:
    """Map a type annotation string to a coarse bucket.

    Handles generics: 'List[int]' -> LIST, 'Dict[str, str]' -> DICT,
    'Optional[int]' -> INT, 'Callable[[int], str]' -> CALLABLE.
    """
    ann = ann.strip()
    if not ann:
        return "UNKNOWN"
    # strip Optional/Union wrappers, keep the first concrete type
    ann = re.sub(r"Optional\[(.*)\]", r"\1", ann)
    ann = re.sub(r"Union\[(.*)\]", r"\1", ann)
    # generic: take the outer container
    base = re.sub(r"\[.*\]", "", ann).strip()
    base = base.split(".")[-1]  # typing.List -> List
    if base in _PY_BUILTIN_BUCKET:
        return _PY_BUILTIN_BUCKET[base]
    # common typing aliases
    if base in ("List", "Sequence", "Iterable", "MutableSequence"):
        return "LIST"
    if base in ("Dict", "Mapping", "MutableMapping", "DefaultDict"):
        return "DICT"
    if base in ("Set", "FrozenSet", "AbstractSet"):
        return "SET"
    if base in ("Tuple",):
        return "TUPLE"
    if base in ("Callable", "FunctionType"):
        return "CALLABLE"
    if base in ("Any",):
        return "UNKNOWN"
    # capitalized name -> likely a class
    if base[:1].isupper():
        return "CLASS"
    return "UNKNOWN"


def _bucket_from_literal(node: ast.AST) -> Optional[str]:
    """Bucket from a literal AST node."""
    if isinstance(node, ast.Constant):
        if node.value is None:
            return "NONE"
        if isinstance(node.value, bool):
            return "BOOL"
        if isinstance(node.value, int):
            return "INT"
        if isinstance(node.value, float):
            return "FLOAT"
        if isinstance(node.value, str):
            return "STR"
        if isinstance(node.value, bytes):
            return "STR"
    if isinstance(node, ast.List):
        return "LIST"
    if isinstance(node, ast.Dict):
        return "DICT"
    if isinstance(node, ast.Set):
        return "SET"
    if isinstance(node, ast.Tuple):
        return "TUPLE"
    if isinstance(node, ast.ListComp) or isinstance(node, ast.SetComp):
        return "LIST"
    if isinstance(node, ast.DictComp):
        return "DICT"
    if isinstance(node, ast.GeneratorExp):
        return "LIST"
    if isinstance(node, ast.Lambda):
        return "CALLABLE"
    return None


def _bucket_from_call(node: ast.Call) -> Optional[str]:
    """Bucket from a function call: builtin return type or method name."""
    func = node.func
    # builtin call: len(x), int(x), str(x)...
    if isinstance(func, ast.Name):
        name = func.id
        if name in _CALL_RETURN_BUCKET:
            return _CALL_RETURN_BUCKET[name]
        # constructor of a known class
        if name[:1].isupper():
            return "CLASS"
        return None
    # method call: obj.method(...)
    if isinstance(func, ast.Attribute):
        attr = func.attr
        # str.split, dict.get, list.append...
        if attr in _METHOD_BUCKET:
            return _METHOD_BUCKET[attr]
        # obj.objects / obj.query (ORM)
        if attr in ("objects", "query"):
            return "ORM"
        return None
    return None


def _bucket_from_binop(node: ast.BinOp) -> Optional[str]:
    """Bucket from a binary operation result."""
    if isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.FloorDiv, ast.Pow)):
        # string concat -> STR; else numeric
        if isinstance(node.left, ast.Constant) and isinstance(node.left.value, str):
            return "STR"
        if isinstance(node.right, ast.Constant) and isinstance(node.right.value, str):
            return "STR"
        return "NUM"
    if isinstance(node.op, (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
                             ast.Is, ast.IsNot, ast.In, ast.NotIn)):
        return "BOOL"
    return None


def _bucket_from_expr(node: ast.AST) -> Optional[str]:
    """Infer a coarse type bucket from any expression AST node."""
    if node is None:
        return None
    lit = _bucket_from_literal(node)
    if lit:
        return lit
    if isinstance(node, ast.Call):
        return _bucket_from_call(node)
    if isinstance(node, ast.BinOp):
        return _bucket_from_binop(node)
    if isinstance(node, ast.UnaryOp):
        return _bucket_from_expr(node.operand)
    if isinstance(node, ast.BoolOp):
        return "BOOL"
    if isinstance(node, ast.Compare):
        return "BOOL"
    if isinstance(node, ast.Subscript):
        # x[i] — result type depends on x; caller resolves via env
        return None
    if isinstance(node, ast.Attribute):
        if node.attr in _ATTR_BUCKET:
            return _ATTR_BUCKET[node.attr]
        return None
    if isinstance(node, ast.Name):
        return None  # resolved via env
    if isinstance(node, ast.IfExp):
        return _bucket_from_expr(node.body) or _bucket_from_expr(node.orelse)
    if isinstance(node, ast.Dict):
        return "DICT"
    if isinstance(node, ast.List):
        return "LIST"
    if isinstance(node, ast.Set):
        return "SET"
    if isinstance(node, ast.Tuple):
        return "TUPLE"
    return None


def _infer_python_types(code: str) -> Dict[str, str]:
    """AST-based type inference for Python.

    Returns {var_name: bucket}. Uses, in priority order:
      1. Type annotations (x: List[int] = ...)
      2. Assignment RHS literal/call/binop
      3. Usage refinement (indexed+len -> LIST, .get/.keys -> DICT, etc.)
      4. Call-argument propagation (f(x) where f indexes x -> x is LIST)
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return _infer_types_regex(code)

    types: Dict[str, str] = {}
    # First pass: annotations + assignments, function by function
    for node in ast.walk(tree):
        # function params with annotations
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for arg in node.args.args:
                if arg.annotation is not None:
                    ann = ast.unparse(arg.annotation)
                    types[arg.arg] = _bucket_from_annotation(ann)
                else:
                    types.setdefault(arg.arg, "UNKNOWN")
            # return annotation
            if node.returns is not None:
                ret = _bucket_from_annotation(ast.unparse(node.returns))
                if ret != "UNKNOWN":
                    types.setdefault("__return__", ret)
        # assignments
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    b = _bucket_from_expr(node.value)
                    if b:
                        types[target.id] = b
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                if node.annotation is not None:
                    types[node.target.id] = _bucket_from_annotation(ast.unparse(node.annotation))
                elif node.value is not None:
                    b = _bucket_from_expr(node.value)
                    if b:
                        types[node.target.id] = b
        elif isinstance(node, ast.AugAssign):
            if isinstance(node.target, ast.Name):
                # x += 1 -> numeric; x += 'a' -> str
                b = _bucket_from_binop(ast.BinOp(left=node.target, op=node.op, right=node.value))
                if b:
                    types[node.target.id] = b
        # for-loop: for x in <iterable> -> iterable is LIST/iterable, x is element
        elif isinstance(node, ast.For):
            if isinstance(node.target, ast.Name):
                types.setdefault(node.target.id, "UNKNOWN")
            # the iterable is a collection (LIST unless it's a dict/set/str)
            if isinstance(node.iter, ast.Name):
                it_var = node.iter.id
                if types.get(it_var) in (None, "UNKNOWN"):
                    # iterating a dict yields keys; but default to LIST
                    types[it_var] = "LIST"
            else:
                it = _bucket_from_expr(node.iter)
                if it:
                    types.setdefault("__iter__", it)

    # Second pass: usage refinement for UNKNOWN vars
    for node in ast.walk(tree):
        # subscript: x[i] — if x is UNKNOWN, check usage hints
        if isinstance(node, ast.Subscript):
            if isinstance(node.value, ast.Name):
                var = node.value.id
                if types.get(var) in (None, "UNKNOWN"):
                    # dict usage: .get/.keys/values/items on var
                    if _has_method(tree, var, ("get", "keys", "values", "items")):
                        types[var] = "DICT"
                    # list usage: len(var) or .append/.extend or range
                    elif _has_method(tree, var, ("append", "extend", "insert", "pop", "remove")) \
                            or _has_len(tree, var):
                        types[var] = "LIST"
                    else:
                        types[var] = "UNKNOWN"
        # attribute call: var.method() — infer var's type from method
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                var = node.func.value.id
                m = node.func.attr
                if m in ("append", "extend", "insert", "pop", "remove", "sort", "reverse", "index", "count"):
                    types[var] = "LIST"
                elif m in ("get", "keys", "values", "items", "setdefault", "update"):
                    types[var] = "DICT"
                elif m in ("upper", "lower", "strip", "split", "join", "replace", "startswith", "endswith", "find", "format"):
                    types[var] = "STR"
                elif m in ("add", "union", "intersection", "difference"):
                    types[var] = "SET"
                elif m in ("objects", "query", "filter", "all", "first", "get_or_create"):
                    types[var] = "ORM"
                elif m in ("read", "readline", "readlines", "write", "close", "seek", "flush"):
                    types[var] = "FILE"
        # len(var) -> var is a sized collection (LIST)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == "len" and node.args and isinstance(node.args[0], ast.Name):
            var = node.args[0].id
            if types.get(var) in (None, "UNKNOWN"):
                types[var] = "LIST"
        # sum(var) / sorted(var) / list(var) -> var is an iterable (LIST)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id in ("sum", "sorted", "list", "set", "tuple", "reversed", "enumerate", "zip") \
                and node.args and isinstance(node.args[0], ast.Name):
            var = node.args[0].id
            if types.get(var) in (None, "UNKNOWN"):
                types[var] = "LIST"
        # for x in var -> var is a collection
        if isinstance(node, ast.For) and isinstance(node.iter, ast.Name):
            var = node.iter.id
            if types.get(var) in (None, "UNKNOWN"):
                types[var] = "LIST"
        # arithmetic usage: var used in + - * / % -> NUM (unless string concat)
        if isinstance(node, ast.BinOp):
            # string concat: if either side is a str literal/call, the other is STR
            is_str_concat = False
            for operand in (node.left, node.right):
                if isinstance(operand, ast.Constant) and isinstance(operand.value, str):
                    is_str_concat = True
                elif isinstance(operand, ast.Call) and isinstance(operand.func, ast.Name) \
                        and operand.func.id == "str":
                    is_str_concat = True
            for operand in (node.left, node.right):
                if isinstance(operand, ast.Name):
                    var = operand.id
                    if types.get(var) in (None, "UNKNOWN"):
                        types[var] = "STR" if is_str_concat else "NUM"
        # comparison usage: var compared with < > <= >= -> NUM
        if isinstance(node, ast.Compare):
            for operand in [node.left] + list(node.comparators):
                if isinstance(operand, ast.Name):
                    var = operand.id
                    if types.get(var) in (None, "UNKNOWN"):
                        types[var] = "NUM"

    # Third pass: cascading call-argument propagation (iterative, transitive)
    global _PROPAGATION_COUNT
    _PROPAGATION_COUNT = 0
    for _ in range(3):
        _PROPAGATION_COUNT += _propagate_call_types(tree, types)

    return types

def _has_method(tree: ast.AST, var: str, methods: Tuple[str, ...]) -> bool:
    """True if `var.<method>(` appears anywhere in the tree."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == var \
                    and node.func.attr in methods:
                return True
    return False


def _has_len(tree: ast.AST, var: str) -> bool:
    """True if `len(var)` appears."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == "len" and node.args and isinstance(node.args[0], ast.Name) \
                and node.args[0].id == var:
            return True
    return False


def _propagate_call_types(tree: ast.AST, types: Dict[str, str]) -> int:
    """Cascading type propagation across the call graph.

    For each call `f(x)` where `f` is a known function in the same file, if
    `f`'s parameter is inferred as a concrete type, propagate that type back
    to the argument `x`. This is the cross-function "cascading effect".

    Returns the number of propagations performed.
    """
    # build {func_name: {param_name: bucket}} from function defs (read CURRENT types)
    func_params: Dict[str, Dict[str, str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            params = {}
            for arg in node.args.args:
                params[arg.arg] = types.get(arg.arg, "UNKNOWN")
            func_params[node.name] = params

    # for each call, propagate
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            fname = node.func.id
            if fname in func_params:
                params = func_params[fname]
                for i, arg in enumerate(node.args):
                    if isinstance(arg, ast.Name):
                        pnames = list(params.keys())
                        if i < len(pnames):
                            pb = params[pnames[i]]
                            if pb != "UNKNOWN" and types.get(arg.id) in (None, "UNKNOWN"):
                                types[arg.id] = pb
                                count += 1
    return count


def _infer_types_regex(code: str) -> Dict[str, str]:
    """Regex fallback for non-Python languages (and Python that won't parse).

    Reuses the existing TYPE_HINTS approach but with the richer bucket set.
    """
    types: Dict[str, str] = {}
    # params
    for m in re.finditer(r"(?:def|function|func|fun)\s+\w+\s*\(([^)]*)\)", code):
        for p in m.group(1).split(","):
            p = p.strip().split(":")[0].strip().split("=")[0].strip()
            if p:
                types[p] = "UNKNOWN"
    # assignments
    for m in re.finditer(r"(\w+)\s*=\s*([^;\n]+)", code):
        var, expr = m.group(1), m.group(2).strip()
        if var in types and types[var] != "UNKNOWN":
            continue
        b = _regex_bucket(expr)
        if b:
            types[var] = b
    # usage refinement
    for var in list(types.keys()):
        if types[var] != "UNKNOWN":
            continue
        if re.search(r"\b" + re.escape(var) + r"\s*\[[^\]]*\]", code) and \
           re.search(r"len\s*\(\s*" + re.escape(var) + r"\)|\b" + re.escape(var) + r"\.(?:append|extend|insert|pop|remove)", code):
            types[var] = "LIST"
        elif re.search(r"\b" + re.escape(var) + r"\s*\[[^\]]*\]", code) and \
             re.search(r"\b" + re.escape(var) + r"\.(?:get|keys|values|items)\s*\(", code):
            types[var] = "DICT"
        elif re.search(r"\b" + re.escape(var) + r"\.(?:objects|query|filter|all|first)\b", code):
            types[var] = "ORM"
        elif re.search(r"\b" + re.escape(var) + r"\.(?:upper|lower|strip|split|join|replace)\s*\(", code):
            types[var] = "STR"
    return types


def _regex_bucket(expr: str) -> Optional[str]:
    """Coarse bucket from a regex expression string."""
    if re.search(r"\[\s*\]|list\s*\(|\.append\s*\(|\.extend\s*\(|range\s*\(", expr):
        return "LIST"
    if re.search(r"\{\s*[^}]*\}|dict\s*\(|\.get\s*\(|\.keys\s*\(", expr):
        return "DICT"
    if re.search(r"str\s*\(|\.upper\s*\(|\.lower\s*\(|\.split\s*\(|\.join\s*\(", expr):
        return "STR"
    if re.search(r"int\s*\(|\b\d+\b|\.count\s*\(|len\s*\(", expr):
        return "INT"
    if re.search(r"float\s*\(|\b\d+\.\d+\b", expr):
        return "FLOAT"
    if re.search(r"\.objects\b|\.query\b|\.filter\s*\(|\.all\s*\(", expr):
        return "ORM"
    if re.search(r"open\s*\(", expr):
        return "FILE"
    if re.search(r"True|False|bool\s*\(", expr):
        return "BOOL"
    return None


def infer_types(code: str, lang: str = "python") -> Dict[str, str]:
    """Public entry: smart type inference for any language."""
    if lang == "python":
        return _infer_python_types(code)
    return _infer_types_regex(code)


# ── 2. PARAM / VARIABLE SHAPES ─────────────────────────────────────────────
def _classify_role(code: str, tree: Optional[ast.AST], var: str, is_param: bool) -> str:
    """Classify a variable's role: IN (read-only), OUT (assigned/returned),
    INOUT (both), or MUT (mutated in place)."""
    if not is_param:
        # locals: assigned then possibly read
        return "OUT"
    # params: check if mutated / reassigned / returned
    if tree is not None:
        mutated = False
        reassigned = False
        returned = False
        for node in ast.walk(tree):
            if isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name) \
                    and node.target.id == var:
                mutated = True
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == var:
                        reassigned = True
            if isinstance(node, ast.Return) and isinstance(node.value, ast.Name) \
                    and node.value.id == var:
                returned = True
        if mutated:
            return "INOUT"
        if reassigned:
            return "INOUT"
        if returned:
            return "IN"
        return "IN"
    # regex fallback
    if re.search(r"\b" + re.escape(var) + r"\s*(\+=|-=|\*=|/=)", code):
        return "INOUT"
    if re.search(r"\b" + re.escape(var) + r"\s*=\s*[^=]", code):
        return "INOUT"
    return "IN"


def variable_shape(code: str, lang: str = "python") -> Dict[str, float]:
    """Param & variable shape vector.

    Dimensions:
      PARAM:<name>:<TYPE>      — each parameter, bucketed type
      PARAM:<name>:ROLE:<role> — parameter role (IN/OUT/INOUT)
      VAR:<name>:<TYPE>        — each local variable, bucketed type
      VAR:<name>:ROLE:<role>   — local variable role
      VAR_COUNT                — number of local variables
      PARAM_COUNT              — number of parameters
      TYPE_DIVERSITY           — distinct type buckets used
      MUTATION                 — number of in-place mutations (aug-assigns)
      UNTYPED                  — number of vars with UNKNOWN type
    """
    types = infer_types(code, lang)
    tree = None
    if lang == "python":
        try:
            tree = ast.parse(code)
        except SyntaxError:
            tree = None

    vec: Dict[str, float] = {}
    params: Set[str] = set()
    locals_: Set[str] = set()

    # collect param names
    if tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for arg in node.args.args:
                    params.add(arg.arg)
    else:
        for m in re.finditer(r"(?:def|function|func|fun)\s+\w+\s*\(([^)]*)\)", code):
            for p in m.group(1).split(","):
                p = p.strip().split(":")[0].strip().split("=")[0].strip()
                if p:
                    params.add(p)

    # collect local vars (assigned names not in params)
    if tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id not in params:
                        locals_.add(t.id)
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name) and node.target.id not in params:
                    locals_.add(node.target.id)
            elif isinstance(node, ast.AugAssign):
                if isinstance(node.target, ast.Name) and node.target.id not in params:
                    locals_.add(node.target.id)
            elif isinstance(node, ast.For):
                if isinstance(node.target, ast.Name) and node.target.id not in params:
                    locals_.add(node.target.id)
    else:
        for m in re.finditer(r"(\w+)\s*=\s*[^;\n]+", code):
            var = m.group(1)
            if var not in params:
                locals_.add(var)

    # param dims
    for p in sorted(params):
        t = types.get(p, "UNKNOWN")
        vec[f"PARAM:{p}:{t}"] = vec.get(f"PARAM:{p}:{t}", 0) + 1
        role = _classify_role(code, tree, p, True)
        vec[f"PARAM:{p}:ROLE:{role}"] = vec.get(f"PARAM:{p}:ROLE:{role}", 0) + 1

    # local var dims
    for v in sorted(locals_):
        t = types.get(v, "UNKNOWN")
        vec[f"VAR:{v}:{t}"] = vec.get(f"VAR:{v}:{t}", 0) + 1
        role = _classify_role(code, tree, v, False)
        vec[f"VAR:{v}:ROLE:{role}"] = vec.get(f"VAR:{v}:ROLE:{role}", 0) + 1

    # aggregate dims
    vec["PARAM_COUNT"] = float(len(params))
    vec["VAR_COUNT"] = float(len(locals_))
    distinct = {t for v, t in types.items() if t != "UNKNOWN"}
    vec["TYPE_DIVERSITY"] = float(len(distinct))
    untyped = sum(1 for v, t in types.items() if t == "UNKNOWN")
    vec["UNTYPED"] = float(untyped)
    # mutation count
    if tree is not None:
        mut = sum(1 for n in ast.walk(tree) if isinstance(n, ast.AugAssign))
    else:
        mut = len(re.findall(r"\w+\s*(\+=|-=|\*=|/=)", code))
    vec["MUTATION"] = float(mut)

    return vec


def variable_shape_normalized(code: str, lang: str = "python") -> Dict[str, float]:
    """L2-normalized variable shape (for cosine comparison)."""
    vec = variable_shape(code, lang)
    norm = math.sqrt(sum(v * v for v in vec.values()))
    if norm == 0:
        return {}
    return {k: round(v / norm, 4) for k, v in vec.items()}


def type_profile(code: str, lang: str = "python") -> Dict[str, float]:
    """Coarse type-profile shape: aggregate dims by type bucket.

    Unlike the per-variable `variable_shape` (which is high-dimensional and
    sparse), this aggregates all params/vars into a compact profile:
      TYPE_PROFILE:<BUCKET>   — count of params+vars of each type
      ROLE_PROFILE:<ROLE>     — count of IN/OUT/INOUT roles
      PARAM_COUNT, VAR_COUNT, TYPE_DIVERSITY, UNTYPED_RATIO, MUTATION

    This is the robust representation for cross-function cosine comparison:
    two functions that both process `List[int]` inputs and return `str` will
    have similar type profiles even if their variable names differ.
    """
    types = infer_types(code, lang)
    tree = None
    if lang == "python":
        try:
            tree = ast.parse(code)
        except SyntaxError:
            tree = None

    params: Set[str] = set()
    locals_: Set[str] = set()
    if tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for arg in node.args.args:
                    params.add(arg.arg)
    else:
        for m in re.finditer(r"(?:def|function|func|fun)\s+\w+\s*\(([^)]*)\)", code):
            for p in m.group(1).split(","):
                p = p.strip().split(":")[0].strip().split("=")[0].strip()
                if p:
                    params.add(p)
    if tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id not in params:
                        locals_.add(t.id)
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name) and node.target.id not in params:
                    locals_.add(node.target.id)
            elif isinstance(node, ast.AugAssign):
                if isinstance(node.target, ast.Name) and node.target.id not in params:
                    locals_.add(node.target.id)
            elif isinstance(node, ast.For):
                if isinstance(node.target, ast.Name) and node.target.id not in params:
                    locals_.add(node.target.id)
    else:
        for m in re.finditer(r"(\w+)\s*=\s*[^;\n]+", code):
            var = m.group(1)
            if var not in params:
                locals_.add(var)

    vec: Dict[str, float] = {}
    # type profile
    for v in params | locals_:
        t = types.get(v, "UNKNOWN")
        vec[f"TYPE_PROFILE:{t}"] = vec.get(f"TYPE_PROFILE:{t}", 0) + 1
    # role profile
    for p in params:
        role = _classify_role(code, tree, p, True)
        vec[f"ROLE_PROFILE:{role}"] = vec.get(f"ROLE_PROFILE:{role}", 0) + 1
    for v in locals_:
        role = _classify_role(code, tree, v, False)
        vec[f"ROLE_PROFILE:{role}"] = vec.get(f"ROLE_PROFILE:{role}", 0) + 1
    # aggregates
    vec["PARAM_COUNT"] = float(len(params))
    vec["VAR_COUNT"] = float(len(locals_))
    distinct = {t for v, t in types.items() if t != "UNKNOWN"}
    vec["TYPE_DIVERSITY"] = float(len(distinct))
    total = len(params) + len(locals_)
    untyped = sum(1 for v, t in types.items() if t == "UNKNOWN")
    vec["UNTYPED_RATIO"] = round(untyped / total, 4) if total else 0.0
    if tree is not None:
        mut = sum(1 for n in ast.walk(tree) if isinstance(n, ast.AugAssign))
    else:
        mut = len(re.findall(r"\w+\s*(\+=|-=|\*=|/=)", code))
    vec["MUTATION"] = float(mut)
    return vec


def type_profile_normalized(code: str, lang: str = "python") -> Dict[str, float]:
    """L2-normalized type profile (compact, robust for comparison)."""
    vec = type_profile(code, lang)
    norm = math.sqrt(sum(v * v for v in vec.values()))
    if norm == 0:
        return {}
    return {k: round(v / norm, 4) for k, v in vec.items()}


# ── 3. CASCADING EFFECTS ───────────────────────────────────────────────────
def cascading_type_flow(code: str, lang: str = "python") -> Dict[str, Any]:
    """Analyze cascading type effects across the call graph.

    Returns a dict describing how types flow between functions:
      {
        'functions': {name: {param: bucket, 'return': bucket}},
        'calls': [{caller, callee, arg, param, arg_bucket, param_bucket, propagated}],
        'propagations': int,   # number of cross-function type propagations
        'type_errors': int,    # arg bucket != param bucket (potential type error)
      }
    """
    if lang != "python":
        return {"functions": {}, "calls": [], "propagations": 0, "type_errors": 0}
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return {"functions": {}, "calls": [], "propagations": 0, "type_errors": 0}

    types = _infer_python_types(code)
    total_propagations = _PROPAGATION_COUNT

    # function signatures
    funcs: Dict[str, Dict[str, Any]] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            sig = {}
            for arg in node.args.args:
                sig[arg.arg] = types.get(arg.arg, "UNKNOWN")
            sig["__return__"] = types.get("__return__", "UNKNOWN")
            funcs[node.name] = sig

    # calls
    calls = []
    propagations = 0
    type_errors = 0
    swapped = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            fname = node.func.id
            if fname in funcs:
                sig = funcs[fname]
                pnames = [k for k in sig if k != "__return__"]
                arg_buckets = []
                for i, arg in enumerate(node.args):
                    if i >= len(pnames):
                        break
                    param = pnames[i]
                    param_bucket = sig.get(param, "UNKNOWN")
                    # infer arg bucket: Name -> env, literal -> literal bucket
                    if isinstance(arg, ast.Name):
                        arg_bucket = types.get(arg.id, "UNKNOWN")
                    else:
                        arg_bucket = _bucket_from_expr(arg) or "UNKNOWN"
                    arg_buckets.append(arg_bucket)
                    propagated = (arg_bucket == "UNKNOWN" and param_bucket != "UNKNOWN")
                    if propagated:
                        propagations += 1
                    if arg_bucket != "UNKNOWN" and param_bucket != "UNKNOWN" \
                            and not _types_compatible(arg_bucket, param_bucket):
                        type_errors += 1
                    calls.append({
                        "caller": _enclosing_func(tree, node),
                        "callee": fname,
                        "arg": ast.unparse(arg) if not isinstance(arg, ast.Name) else arg.id,
                        "param": param,
                        "arg_bucket": arg_bucket,
                        "param_bucket": param_bucket,
                        "propagated": propagated,
                    })
                # swapped-param detection: arg types are a permutation of the
                # param types that doesn't match declared order (e.g. two NUM
                # params where the caller passes them in reverse).
                if len(arg_buckets) >= 2 and len(arg_buckets) == len(pnames):
                    param_buckets = [sig.get(p, "UNKNOWN") for p in pnames]
                    # only consider when all buckets are known and the multiset matches
                    if all(b != "UNKNOWN" for b in arg_buckets + param_buckets):
                        if sorted(arg_buckets) == sorted(param_buckets) \
                                and arg_buckets != param_buckets:
                            swapped.append({
                                "caller": _enclosing_func(tree, node),
                                "callee": fname,
                                "arg_buckets": arg_buckets,
                                "param_buckets": param_buckets,
                            })

    return {
        "functions": funcs,
        "calls": calls,
        "propagations": total_propagations,
        "type_errors": type_errors,
        "swapped_params": swapped,
    }


def _enclosing_func(tree: ast.AST, node: ast.AST) -> str:
    """Find the name of the function enclosing a node."""
    for parent in ast.walk(tree):
        if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(parent):
                if child is node:
                    return parent.name
    return "<module>"


# ── Integration: merge into enriched shape ─────────────────────────────────
def merge_variable_shape(enriched: Dict[str, float], code: str, lang: str = "python",
                         weight: float = 1.0) -> Dict[str, float]:
    """Merge the variable shape into an enriched shape vector.

    The variable dims are added with a configurable weight so they don't get
    swamped by the (large) VAL:FLOW_DEPTH / VAL:BRANCHING dims. Returns a new
    dict (does not mutate `enriched`).
    """
    merged = dict(enriched)
    vs = variable_shape(code, lang)
    for k, v in vs.items():
        merged[k] = merged.get(k, 0) + v * weight
    return merged


# ── Self-test ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    samples = {
        "list_processor": (
            "def process(items, threshold):\n"
            "    result = []\n"
            "    for item in items:\n"
            "        if item > threshold:\n"
            "            result.append(item)\n"
            "    return result"
        ),
        "dict_lookup": (
            "def lookup(config, key):\n"
            "    value = config.get(key, 'default')\n"
            "    return value.upper()"
        ),
        "annotated": (
            "def transform(data: List[int], factor: float) -> List[int]:\n"
            "    out = [x * factor for x in data]\n"
            "    return out"
        ),
        "cascading": (
            "def helper(items):\n"
            "    return len(items)\n"
            "def main(data):\n"
            "    n = helper(data)\n"
            "    return n"
        ),
    }

    print("=== Smart type inference ===")
    for name, code in samples.items():
        types = infer_types(code)
        print(f"{name:16s} {types}")

    print("\n=== Variable shape (normalized) ===")
    for name, code in samples.items():
        vs = variable_shape_normalized(code)
        print(f"{name:16s} {len(vs)} dims")
        for k, v in sorted(vs.items()):
            if v > 0:
                print(f"    {k} = {v:.3f}")

    print("\n=== Cascading type flow ===")
    for name, code in samples.items():
        cf = cascading_type_flow(code)
        if cf["calls"]:
            print(f"{name:16s} propagations={cf['propagations']} type_errors={cf['type_errors']}")
            for c in cf["calls"]:
                print(f"    {c['caller']} -> {c['callee']}({c['arg']}->{c['param']}) "
                      f"{c['arg_bucket']}->{c['param_bucket']} propagated={c['propagated']}")
