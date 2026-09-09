#!/usr/bin/env python
"""multilang_shape.py — Multi-language code shape decomposition.

operators) is mapped to a common primitive vocabulary, so the same behavior in
any language produces the same shape.

Supported languages (13+):
  Python, JavaScript, TypeScript, Java, C, C++, C#, Go, Rust, Ruby, PHP,
  Swift, Kotlin

The decomposition detects primitives by SEMANTIC ROLE using language-agnostic
patterns (operators are universal; control-flow keywords are mapped per
language family). This is the same principle as agnostic_shape.py but with
explicit per-language syntax coverage.

Dependency-free (stdlib only).
"""
import math
import re
from typing import Dict, List, Tuple

# ── Language detection ─────────────────────────────────────────────────────
LANG_HINTS: List[Tuple[str, List[str]]] = [
    ("python",   ["def ", "elif", "print(", "import ", "self."]),
    ("typescript", [": string", ": number", ": number[]", "interface ", "type ", "const ", "let ", "=>"]),
    ("javascript", ["function ", "=>", "console.log", "let ", "const ", "var ", "document."]),
    ("java",     ["public ", "class ", "System.out", "void main", "import java", "int[]", "String[]"]),
    ("c",        ["#include", "printf(", "int main", "malloc", "stdio.h", "int ", "char "]),
    ("cpp",      ["#include", "std::", "cout", "int main", "->", "iostream", "vector"]),
    ("csharp",   ["using System", "Console.WriteLine", "public class", "namespace", "Console.Write", "foreach", "int[]", "string[]"]),
    ("go",       ["package ", "func ", "fmt.Println", ":= ", "go func"]),
    ("rust",     ["fn ", "let mut", "println!", "impl ", "->"]),
    ("ruby",     ["def ", "end", "puts ", "require ", "do |"]),
    ("php",      ["<?php", "function ", "echo ", "$", "->"]),
    ("swift",    ["func ", "print(", "let ", "var ", "import Foundation"]),
    ("kotlin",   ["fun ", "println(", "val ", "var ", "package "]),
]


def detect_language(code: str) -> str:
    """Detect the programming language of a code snippet."""
    scores = {lang: 0 for lang, _ in LANG_HINTS}
    for lang, hints in LANG_HINTS:
        for h in hints:
            if h in code:
                scores[lang] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "unknown"


# ── Per-language syntax → primitive mapping ─────────────────────────────────
# Each language family maps its control-flow/def syntax to common primitives.
# Operators (+, -, *, /, %, ==, <, >) are universal and handled separately.

# Function definition patterns per language
DEF_PATTERNS = {
    "python":   r"(?:def|async def)\s+(\w+)\s*\(",
    "javascript": r"(?:function|const\s+\w+\s*=\s*\(|let\s+\w+\s*=\s*\()\s*(\w+)?\s*\(",
    "typescript": r"(?:function|const\s+\w+\s*=\s*\(|let\s+\w+\s*=\s*\()\s*(\w+)?\s*\(",
    "java":     r"(?:public|private|protected|static)?\s*(?:\w+\s+)*(\w+)\s*\(",
    "c":        r"(?:\w+\s+)+(\w+)\s*\(",
    "cpp":      r"(?:\w+\s+)+(\w+)\s*\(",
    "csharp":   r"(?:public|private|protected|static)?\s*(?:\w+\s+)*(\w+)\s*\(",
    "go":       r"func\s+(\w+)\s*\(",
    "rust":     r"fn\s+(\w+)\s*\(",
    "ruby":     r"def\s+(\w+)",
    "php":      r"function\s+(\w+)\s*\(",
    "swift":    r"func\s+(\w+)\s*\(",
    "kotlin":   r"fun\s+(\w+)\s*\(",
}

# Loop patterns per language
LOOP_PATTERNS = {
    "python":   [r"\bfor\b", r"\bwhile\b"],
    "javascript": [r"\bfor\b", r"\bwhile\b", r"\.forEach\(", r"\.map\("],
    "typescript": [r"\bfor\b", r"\bwhile\b", r"\.forEach\(", r"\.map\("],
    "java":     [r"\bfor\b", r"\bwhile\b", r"\.forEach\("],
    "c":        [r"\bfor\b", r"\bwhile\b", r"\bdo\b"],
    "cpp":      [r"\bfor\b", r"\bwhile\b", r"\bdo\b"],
    "csharp":   [r"\bfor\b", r"\bwhile\b", r"\bforeach\b", r"\bdo\b"],
    "go":       [r"\bfor\b", r"\brange\b"],
    "rust":     [r"\bfor\b", r"\bwhile\b", r"\bloop\b"],
    "ruby":     [r"\bfor\b", r"\bwhile\b", r"\.each\b", r"\bdo\b"],
    "php":      [r"\bfor\b", r"\bwhile\b", r"\bforeach\b"],
    "swift":    [r"\bfor\b", r"\bwhile\b", r"\.forEach\("],
    "kotlin":   [r"\bfor\b", r"\bwhile\b", r"\.forEach\("],
}

# Branch patterns per language
BRANCH_PATTERNS = {
    "python":   [r"\bif\b", r"\belif\b", r"\belse\b"],
    "javascript": [r"\bif\b", r"\belse\b", r"\bswitch\b", r"\?.*:"],
    "typescript": [r"\bif\b", r"\belse\b", r"\bswitch\b", r"\?.*:"],
    "java":     [r"\bif\b", r"\belse\b", r"\bswitch\b", r"\?.*:"],
    "c":        [r"\bif\b", r"\belse\b", r"\bswitch\b", r"\?.*:"],
    "cpp":      [r"\bif\b", r"\belse\b", r"\bswitch\b", r"\?.*:"],
    "csharp":   [r"\bif\b", r"\belse\b", r"\bswitch\b", r"\?.*:"],
    "go":       [r"\bif\b", r"\belse\b", r"\bswitch\b"],
    "rust":     [r"\bif\b", r"\belse\b", r"\bmatch\b"],
    "ruby":     [r"\bif\b", r"\belsif\b", r"\belse\b", r"\bcase\b"],
    "php":      [r"\bif\b", r"\belseif\b", r"\belse\b", r"\bswitch\b"],
    "swift":    [r"\bif\b", r"\belse\b", r"\bswitch\b"],
    "kotlin":   [r"\bif\b", r"\belse\b", r"\bwhen\b"],
}

# Return patterns per language
RETURN_PATTERNS = {
    "python":   [r"\breturn\b"],
    "javascript": [r"\breturn\b", r"=>"],
    "typescript": [r"\breturn\b", r"=>"],
    "java":     [r"\breturn\b"],
    "c":        [r"\breturn\b"],
    "cpp":      [r"\breturn\b"],
    "csharp":   [r"\breturn\b"],
    "go":       [r"\breturn\b"],
    "rust":     [r"\breturn\b"],
    "ruby":     [r"\breturn\b"],
    "php":      [r"\breturn\b"],
    "swift":    [r"\breturn\b"],
    "kotlin":   [r"\breturn\b"],
}

# I/O patterns per language
IO_PATTERNS = {
    "python":   {"READ": [r"\binput\(", r"\bopen\(", r"\bread\("], "WRITE": [r"\bprint\("]},
    "javascript": {"READ": [r"\breadFile", r"\bgetElementById", r"\bfetch\("], "WRITE": [r"console\.log", r"\bdocument\.write"]},
    "typescript": {"READ": [r"\breadFile", r"\bfetch\("], "WRITE": [r"console\.log"]},
    "java":     {"READ": [r"Scanner", r"\breadLine", r"\bnextInt"], "WRITE": [r"System\.out\.print"]},
    "c":        {"READ": [r"\bscanf", r"\bfread", r"\bgetchar"], "WRITE": [r"\bprintf"]},
    "cpp":      {"READ": [r"\bcin", r"\bscanf", r"\bfread"], "WRITE": [r"\bcout", r"\bprintf"]},
    "csharp":   {"READ": [r"Console\.ReadLine", r"\bRead\("], "WRITE": [r"Console\.Write"]},
    "go":       {"READ": [r"\bScan", r"\bReadFile", r"\bReadString"], "WRITE": [r"fmt\.Print"]},
    "rust":     {"READ": [r"\bread_line", r"\bread_to_string"], "WRITE": [r"println!", r"\bprint!"]},
    "ruby":     {"READ": [r"\bgets", r"\bFile\.read"], "WRITE": [r"\bputs", r"\bprint"]},
    "php":      {"READ": [r"\$_GET", r"\$_POST", r"\bfopen"], "WRITE": [r"\becho", r"\bprint"]},
    "swift":    {"READ": [r"\breadLine", r"\bread\("], "WRITE": [r"\bprint\("]},
    "kotlin":   {"READ": [r"\breadLine", r"\breadln"], "WRITE": [r"\bprintln"]},
}

# Universal operators (language-agnostic)
ARITH_OPS = [("ARITH_ADD", r" \+ "), ("ARITH_SUB", r" - "), ("ARITH_MUL", r" \* "),
             ("ARITH_DIV", r" / "), ("ARITH_MOD", r" % ")]
COMPARE_OPS = [("COMPARE_EQ", r"==|==="), ("COMPARE_NE", r"!=|!=="),
               ("COMPARE_GT", r" > "), ("COMPARE_LT", r" < "),
               ("COMPARE_GE", r">="), ("COMPARE_LE", r"<=")]

# Common primitive dimensions
DIMS = ["LOOP", "BRANCH", "RECURSE", "ARITH_ADD", "ARITH_SUB", "ARITH_MUL",
        "ARITH_DIV", "ARITH_MOD", "COMPARE_EQ", "COMPARE_NE", "COMPARE_GT",
        "COMPARE_LT", "COMPARE_GE", "COMPARE_LE", "RETURN", "READ", "WRITE"]


def _detect_recursion(code: str, lang: str) -> bool:
    """Detect recursion: function name appears in its own body."""
    pat = DEF_PATTERNS.get(lang, r"(?:def|function)\s+(\w+)\s*\(")
    m = re.search(pat, code)
    if not m:
        return False
    name = m.group(1)
    body = code[code.find(m.group(0)) + len(m.group(0)):]
    return body.count(name) >= 1


def decompose(code: str, lang: str = None) -> Dict[str, int]:
    """Decompose code into primitives. Returns {primitive: count}."""
    if lang is None:
        lang = detect_language(code)
    counts: Dict[str, int] = {d: 0 for d in DIMS}

    # loops
    for pat in LOOP_PATTERNS.get(lang, [r"\bfor\b", r"\bwhile\b"]):
        counts["LOOP"] += len(re.findall(pat, code))
    # branches
    for pat in BRANCH_PATTERNS.get(lang, [r"\bif\b", r"\belse\b"]):
        counts["BRANCH"] += len(re.findall(pat, code))
    # return
    for pat in RETURN_PATTERNS.get(lang, [r"\breturn\b"]):
        counts["RETURN"] += len(re.findall(pat, code))
    # I/O
    io = IO_PATTERNS.get(lang, {"READ": [], "WRITE": []})
    for pat in io.get("READ", []):
        counts["READ"] += len(re.findall(pat, code))
    for pat in io.get("WRITE", []):
        counts["WRITE"] += len(re.findall(pat, code))
    # arithmetic (universal)
    for dim, pat in ARITH_OPS:
        counts[dim] += len(re.findall(pat, code))
    # comparison (universal)
    for dim, pat in COMPARE_OPS:
        counts[dim] += len(re.findall(pat, code))
    # recursion
    if _detect_recursion(code, lang):
        counts["RECURSE"] += 1

    return counts


def shape_vector(code: str, lang: str = None) -> Dict[str, float]:
    """Normalized multi-language shape vector."""
    counts = decompose(code, lang)
    norm = math.sqrt(sum(v * v for v in counts.values()))
    if norm == 0:
        return {d: 0.0 for d in DIMS}
    return {d: round(counts[d] / norm, 4) for d in DIMS}


def cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    keys = set(a) | set(b)
    dot = sum(a.get(k, 0) * b.get(k, 0) for k in keys)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def similarity(code_a: str, code_b: str, lang_a: str = None, lang_b: str = None) -> float:
    """Cross-language similarity between two code snippets."""
    return cosine(shape_vector(code_a, lang_a), shape_vector(code_b, lang_b))


def shape(code: str, lang: str = None) -> str:
    """Human-readable shape = dominant primitives."""
    vec = decompose(code, lang)
    ranked = sorted(vec.items(), key=lambda kv: -kv[1])
    top = [d for d, c in ranked if c > 0][:5]
    return ">".join(top) if top else "EMPTY"


# ── Self-test: same behavior in many languages ──────────────────────────────
if __name__ == "__main__":
    # Same behavior (sum a list) in 6 languages
    samples = {
        "python": "def sum_list(nums):\n    total = 0\n    for n in nums:\n        total += n\n    return total",
        "javascript": "function sumList(nums) {\n    let total = 0;\n    for (let n of nums) {\n        total += n;\n    }\n    return total;\n}",
        "java": "int sumList(int[] nums) {\n    int total = 0;\n    for (int n : nums) {\n        total += n;\n    }\n    return total;\n}",
        "go": "func sumList(nums []int) int {\n    total := 0\n    for _, n := range nums {\n        total += n\n    }\n    return total\n}",
        "rust": "fn sum_list(nums: &[i32]) -> i32 {\n    let mut total = 0;\n    for n in nums {\n        total += n;\n    }\n    return total;\n}",
        "ruby": "def sum_list(nums)\n    total = 0\n    nums.each do |n|\n        total += n\n    end\n    return total\nend",
    }
    print("=== Same behavior (sum) in 6 languages ===")
    for lang, code in samples.items():
        print(f"{lang:10s} detected={detect_language(code):10s} shape={shape(code, lang)}")

    print("\n=== Cross-language similarity (should be high) ===")
    langs = list(samples.keys())
    for i in range(len(langs)):
        for j in range(i + 1, len(langs)):
            s = similarity(samples[langs[i]], samples[langs[j]], langs[i], langs[j])
            print(f"{langs[i]:10s} vs {langs[j]:10s}: {s:.3f}")
