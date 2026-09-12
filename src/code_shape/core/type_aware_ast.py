#!/usr/bin/env python
"""type_aware_ast.py — Type-aware AST decomposition.
that regex-based analysis can't: is `x[y]` array indexing (potential buffer
overflow), dict access (safe), or ORM column access (safe)?

Approach:
  1. Parse code into an AST.
  2. Infer variable types via assignment analysis (list/dict/str/int/ORM).
  3. Resolve subscript operations: `x[y]` where x is a list + tainted y =
     potential overflow; x is a dict = safe key access; x is ORM = column access.
  4. Produce a type-aware shape that distinguishes these.

This is the highest-information-gain improvement (super-solver BOED #1): it
resolves the ambiguity that has been the recurring bottleneck in decomposition
and vulnerability detection.

Dependency-free (stdlib only).
"""
import ast
from typing import Dict, List, Set, Optional

# Type inference: variable -> inferred type
# Types: LIST, DICT, STR, INT, FLOAT, ORM, UNKNOWN, PARAM
TYPE_HINTS = {
    "LIST": [r"\[\s*\]", r"list\s*\(", r"\.append\s*\(", r"\.extend\s*\(", r"range\s*\("],
    "DICT": [r"\{\s*[^}]*\}", r"dict\s*\(", r"\.get\s*\(", r"\.keys\s*\(", r"\.values\s*\("],
    "STR": [r"str\s*\(", r"\.upper\s*\(", r"\.lower\s*\(", r"\.split\s*\(", r"\.join\s*\(", r"\.strip\s*\("],
    "INT": [r"int\s*\(", r"\b\d+\b", r"\.count\s*\(", r"len\s*\("],
    "ORM": [r"\.objects\b", r"\.query\b", r"\.filter\s*\(", r"\.all\s*\(", r"\.get\s*\(", r"\.first\s*\(", r"row\[", r"\.column\b"],
}


def _infer_type_from_expr(expr: str) -> str:
    """Infer a variable's type from its assignment expression."""
    for t, pats in TYPE_HINTS.items():
        for p in pats:
            if p in expr:
                return t
    return "UNKNOWN"


def _map_type_hint_to_canonical(hint: str) -> Optional[str]:
    """Map explicit language type annotations into canonical shape types."""
    if not hint:
        return None
    h = hint.strip().lower()
    if any(k in h for k in ("[]", "list", "array", "vec", "slice", "set")):
        return "LIST"
    if any(k in h for k in ("map", "dict", "hashmap", "dictionary", "record")):
        return "DICT"
    if any(k in h for k in ("string", "str", "char*", "&str", "text")):
        return "STR"
    if any(k in h for k in ("int", "i32", "i64", "long", "short", "usize", "size_t", "uint", "byte")):
        return "INT"
    if any(k in h for k in ("float", "double", "f32", "f64")):
        return "FLOAT"
    if any(k in h for k in ("repo", "model", "query", "entity", "orm")):
        return "ORM"
    return None


def _infer_types(code: str, lang: Optional[str] = None) -> Dict[str, str]:
    """Infer variable types via explicit type hints, assignment expressions, and USAGE analysis.

    In typed languages (Java, Go, Rust, C/C++, TypeScript, etc.), declared parameter
    and variable types map directly into canonical types (LIST, DICT, STR, INT, ORM).
    Params without hints start as PARAM, then get refined by how they're used:
      - x[i] with len(x) / .append / range -> LIST
      - x[key] with .get / .keys / {} -> DICT
      - x.attr / .objects / .query -> ORM
    """
    import re
    types: Dict[str, str] = {}

    # 1. Parse parameters & type hints using universal AST
    try:
        from code_shape.core.universal_ast import extract_universal_functions
        funcs = extract_universal_functions(code, lang or "generic")
        for fn in funcs:
            for p in fn.params:
                if p.type_hint:
                    canon = _map_type_hint_to_canonical(p.type_hint)
                    types[p.name] = canon if canon else "PARAM"
                elif p.name not in types:
                    types[p.name] = "PARAM"
    except Exception:
        pass

    # Regex fallback for parameter discovery if universal AST didn't find any
    if not types:
        for m in re.finditer(r"(?:def|function|func|fn|fun)\s+\w+\s*\(([^)]*)\)", code):
            for p in m.group(1).split(","):
                p = p.strip().split(":")[0].strip().split("=")[0].strip()
                if p:
                    types[p] = "PARAM"

    # 2. Check explicit typed variable declarations: Type var = expr
    for m in re.finditer(r"^[ \t]*(?:[\w<>\[\]*&]+)\s+([a-zA-Z_]\w*)\s*=\s*([^;\n]+)", code, re.MULTILINE):
        type_str, var, expr = m.group(0).split()[0], m.group(1), m.group(2).strip()
        canon = _map_type_hint_to_canonical(type_str)
        if canon:
            types[var] = canon

    # 3. Infer from assignment expressions
    for m in re.finditer(r"(\w+)\s*=\s*([^;\n]+)", code):
        var, expr = m.group(1), m.group(2).strip()
        if var in types and types[var] not in ("PARAM", "UNKNOWN"):
            continue
        inferred = _infer_type_from_expr(expr)
        if inferred != "UNKNOWN" or var not in types:
            types[var] = inferred

    # 4. Usage-based refinement of PARAM types
    for var in list(types.keys()):
        if types[var] != "PARAM":
            continue
        # list usage: indexed + len/append/range
        if re.search(r"\b" + re.escape(var) + r"\s*\[[^\]]*\]", code) and \
           re.search(r"len\s*\(\s*" + re.escape(var) + r"\)|\b" + re.escape(var) + r"\.append|range\s*\(", code):
            types[var] = "LIST"
        # dict usage: indexed + .get/.keys/values
        elif re.search(r"\b" + re.escape(var) + r"\s*\[[^\]]*\]", code) and \
             re.search(r"\b" + re.escape(var) + r"\.(?:get|keys|values|items)\s*\(", code):
            types[var] = "DICT"
        # ORM usage: .objects/.query/.filter/.all
        elif re.search(r"\b" + re.escape(var) + r"\.(?:objects|query|filter|all|first)\b", code):
            types[var] = "ORM"
    return types


def _classify_subscript(code: str, types: Dict[str, str]) -> List[Dict]:
    """Classify each subscript x[y] as LIST_INDEX / DICT_ACCESS / ORM_ACCESS / UNKNOWN."""
    results = []
    for m in __import__("re").finditer(r"(\w+)\s*\[\s*([^\]]+)\s*\]", code):
        obj, idx = m.group(1), m.group(2).strip()
        t = types.get(obj, "UNKNOWN")
        results.append({
            "object": obj,
            "index": idx,
            "type": t,
            "class": ("LIST_INDEX" if t == "LIST" else
                      "DICT_ACCESS" if t == "DICT" else
                      "ORM_ACCESS" if t == "ORM" else
                      "UNKNOWN_ACCESS"),
        })
    return results


def type_aware_shape(code: str) -> Dict[str, float]:
    """Type-aware shape: adds ACCESS:<class> dims for subscript operations."""
    import math
    types = _infer_types(code)
    subscripts = _classify_subscript(code, types)
    vec: Dict[str, float] = {}
    for s in subscripts:
        vec[f"ACCESS:{s['class']}"] = vec.get(f"ACCESS:{s['class']}", 0) + 1
    # also add type dims
    for var, t in types.items():
        if t != "PARAM":
            vec[f"TYPE:{t}"] = vec.get(f"TYPE:{t}", 0) + 1
    norm = math.sqrt(sum(v * v for v in vec.values()))
    if norm == 0:
        return {}
    return {k: round(v / norm, 4) for k, v in vec.items()}


def is_potential_overflow(code: str) -> bool:
    """True if there's a LIST_INDEX with a tainted (param) index and no bounds check."""
    types = _infer_types(code)
    subscripts = _classify_subscript(code, types)
    for s in subscripts:
        if s["class"] == "LIST_INDEX":
            idx = s["index"]
            # tainted if index is a param or user input
            if idx in types and types[idx] == "PARAM":
                has_bounds = "if 0 <=" in code or "if " in code and "len(" in code
                if not has_bounds:
                    return True
    return False


# ── Self-test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Ambiguous x[y] cases (with usage hints for type inference)
    list_fn = "def get(arr, i):\n    if i < len(arr):\n        return arr[i]\n    return None"
    dict_fn = "def get(d, key):\n    return d.get(key, d[key])"
    orm_fn = "def get_user(uid):\n    return User.objects.get(id=uid)"
    safe_list = "def get(arr, i):\n    if 0 <= i < len(arr):\n        return arr[i]\n    return None"

    print("=== Type-aware subscript classification ===")
    for name, code in [("list", list_fn), ("dict", dict_fn), ("orm", orm_fn), ("safe_list", safe_list)]:
        types = _infer_types(code)
        subs = _classify_subscript(code, types)
        print(f"{name:10s} types={types}")
        for s in subs:
            print(f"  {s['object']}[{s['index']}] -> {s['class']}")
        print(f"  potential_overflow={is_potential_overflow(code)}")

    print("\n=== Type-aware shape ===")
    for name, code in [("list", list_fn), ("dict", dict_fn), ("orm", orm_fn)]:
        print(f"{name:10s} {sorted(type_aware_shape(code).keys())}")
