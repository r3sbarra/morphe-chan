#!/usr/bin/env python
"""shape_translator.py — Shape-based code translation.
code between languages:

  1. DECOMPOSE source code to its shape (language-agnostic primitive vector)
  2. ASSEMBLE that shape in a TARGET language using per-language templates

The shape is the bridge: same behavior in any language produces the same shape,
so translating = decompose(source) -> assemble(shape, target_lang).

Supported targets: python, go, rust, javascript, java (templates for common
primitives: sum/loop, max/branch, filter, sort, add/arith).

Dependency-free (stdlib only).
"""
import re
from typing import Dict, List, Optional

from code_shape.core.code_shape_core import shape as get_shape, recursive_shape, get_adapter

# ── Per-language templates keyed by (primitive, language) ───────────────────
# Each template is a list of (line, indent_level) or a callable.
TEMPLATES: Dict[str, Dict[str, List[str]]] = {
    "python": {
        "LOOP": ["for n in nums:"],
        "AGGREGATE": ["    total += n"],
        "ASSIGN": ["total = 0"],
        "RETURN": ["return total"],
        "BRANCH": ["if a > b:"],
        "COMPARE_GT": ["    return a"],
        "ARITH_ADD": ["    return a + b"],
        "ARITH_MUL": ["    return a * b"],
        "FILTER": ["    if n % 2 == 0:"],
        "SORT": ["return sorted(arr)"],
        "SEARCH": ["return arr.index(x)"],
    },
    "go": {
        "LOOP": ["for _, n := range nums {"],
        "AGGREGATE": ["    total += n"],
        "ASSIGN": ["total := 0"],
        "RETURN": ["return total"],
        "BRANCH": ["if a > b {"],
        "COMPARE_GT": ["    return a"],
        "ARITH_ADD": ["return a + b"],
        "ARITH_MUL": ["return a * b"],
        "FILTER": ["    if n%2 == 0 {"],
        "SORT": ["sort.Ints(arr)", "return arr"],
        "SEARCH": ["return arr[i]"],
    },
    "rust": {
        "LOOP": ["for n in nums {"],
        "AGGREGATE": ["    total += n;"],
        "ASSIGN": ["let mut total = 0;"],
        "RETURN": ["total"],
        "BRANCH": ["if a > b {"],
        "COMPARE_GT": ["    return a;"],
        "ARITH_ADD": ["a + b"],
        "ARITH_MUL": ["a * b"],
        "FILTER": ["    if n % 2 == 0 {"],
        "SORT": ["arr.sort();", "arr"],
        "SEARCH": ["arr.iter().position(|&x| x == target)"],
    },
    "javascript": {
        "LOOP": ["for (let n of nums) {"],
        "AGGREGATE": ["    total += n;"],
        "ASSIGN": ["let total = 0;"],
        "RETURN": ["return total;"],
        "BRANCH": ["if (a > b) {"],
        "COMPARE_GT": ["    return a;"],
        "ARITH_ADD": ["return a + b;"],
        "ARITH_MUL": ["return a * b;"],
        "FILTER": ["    if (n % 2 === 0) {"],
        "SORT": ["return arr.sort((a,b) => a-b);"],
        "SEARCH": ["return arr.indexOf(x);"],
    },
    "java": {
        "LOOP": ["for (int n : nums) {"],
        "AGGREGATE": ["    total += n;"],
        "ASSIGN": ["int total = 0;"],
        "RETURN": ["return total;"],
        "BRANCH": ["if (a > b) {"],
        "COMPARE_GT": ["    return a;"],
        "ARITH_ADD": ["return a + b;"],
        "ARITH_MUL": ["return a * b;"],
        "FILTER": ["    if (n % 2 == 0) {"],
        "SORT": ["Arrays.sort(arr);", "return arr;"],
        "SEARCH": ["return Arrays.asList(arr).indexOf(x);"],
    },
}

# Function signature templates per language
SIG_TEMPLATES = {
    "python": "def {name}({params}):",
    "go": "func {name}({params}) {ret} {{",
    "rust": "fn {name}({params}) -> {ret} {{",
    "javascript": "function {name}({params}) {{",
    "java": "public static {ret} {name}({params}) {{",
}

# Closing brace per language
CLOSE = {"python": "", "go": "}", "rust": "}", "javascript": "}", "java": "}"}


def _params_from_shape(shape_str: str) -> List[str]:
    """Infer params from the shape (LOOP/AGGREGATE -> nums; BRANCH/COMPARE -> a,b)."""
    if "LOOP" in shape_str or "AGGREGATE" in shape_str or "FILTER" in shape_str:
        return ["nums"]
    if "BRANCH" in shape_str or "COMPARE" in shape_str:
        return ["a", "b"]
    if "SORT" in shape_str:
        return ["arr"]
    if "SEARCH" in shape_str:
        return ["arr", "x"]
    return ["a", "b"]


def _ret_type(shape_str: str, lang: str) -> str:
    if lang == "go":
        return "int" if "AGGREGATE" in shape_str or "ARITH" in shape_str else "[]int"
    if lang == "rust":
        return "i32" if "AGGREGATE" in shape_str or "ARITH" in shape_str else "Vec<i32>"
    if lang == "java":
        return "int" if "AGGREGATE" in shape_str or "ARITH" in shape_str else "int[]"
    return ""


def translate(code: str, target_lang: str, name: str = "fn") -> Optional[str]:
    """Translate code to a target language via the shape IR.

    decompose(source) -> shape -> assemble(shape, target_lang).
    """
    # 1. decompose to shape
    shape_str = get_shape(code)
    prims = shape_str.split(">")
    if not prims:
        return None

    # 2. assemble in target language
    tpls = TEMPLATES.get(target_lang)
    if not tpls:
        return None
    params = _params_from_shape(shape_str)
    ret = _ret_type(shape_str, target_lang)
    sig = SIG_TEMPLATES[target_lang].format(name=name, params=", ".join(params), ret=ret)

    # skip spurious primitives (SEARCH from 'in' in loops, STATE from '+=')
    SKIP = {"SEARCH", "STATE", "FILTER"} if "LOOP" in prims else set()
    lines = [sig]
    indent = "    "
    for p in prims:
        if p in SKIP:
            continue
        if p in tpls:
            for t in tpls[p]:
                # indent loop-body lines deeper
                if p in ("AGGREGATE", "FILTER") and "LOOP" in prims:
                    lines.append("        " + t.strip())
                else:
                    lines.append(indent + t)
    if CLOSE[target_lang]:
        lines.append("}")
    return "\n".join(lines)


def translate_and_verify(code: str, target_lang: str, name: str = "fn") -> Dict:
    """Translate and verify the shape is preserved in the target language."""
    translated = translate(code, target_lang, name)
    if translated is None:
        return {"ok": False, "error": "translation failed"}
    # verify: re-decompose the translated code, check shape overlap
    new_shape = get_shape(translated, target_lang)
    orig_shape = get_shape(code)
    orig_prims = set(orig_shape.split(">"))
    new_prims = set(new_shape.split(">"))
    overlap = len(orig_prims & new_prims) / len(orig_prims) if orig_prims else 0
    return {
        "ok": overlap >= 0.5,
        "orig_shape": orig_shape,
        "translated_shape": new_shape,
        "overlap": round(overlap, 2),
        "translated": translated,
    }


# ── Self-test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Python sum -> translate to Go/Rust/JS/Java
    py_sum = "def sum_list(nums):\n    total = 0\n    for n in nums:\n        total += n\n    return total"
    print("=== Shape-based translation: Python sum -> other languages ===")
    for lang in ["go", "rust", "javascript", "java"]:
        res = translate_and_verify(py_sum, lang)
        print(f"\n--- {lang} ---")
        print(res["translated"])
        print(f"shape: {res['orig_shape']} -> {res['translated_shape']} (overlap {res['overlap']})")
