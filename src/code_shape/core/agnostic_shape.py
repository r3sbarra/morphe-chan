#!/usr/bin/env python
"""agnostic_shape.py — CODE-AGNOSTIC shape model.

Key idea: primitives are detected by SEMANTIC ROLE, not language syntax.
Language-specific keywords are mapped to a common primitive vocabulary:

  LOOP      : for / while / foreach / for( / do / repeat
  BRANCH    : if / else / switch / case / ternary (?:)
  RECURSE   : function calling itself (name appears in body)
  ARITH     : + - * / % (operators are language-agnostic)
  COMPARE   : == != < > <= >= (operators are language-agnostic)
  ASSIGN    : = += -= *= (operators are language-agnostic)
  RETURN    : return / return; / => (arrow)
  CALL      : function/method call (identifier followed by paren)
  READ      : input / read / get / param / open
  WRITE     : print / console.log / System.out / write / emit
  AGGREGATE : sum / reduce / accumulate / total
  FILTER    : filter / where / select / comprehension
  SORT      : sort / sorted / orderBy
  SEARCH    : find / indexOf / search / contains / includes
  STATE     : mutation of a variable (assign + reuse)

The vector shape is the normalized distribution of these primitives. Two
functions in DIFFERENT languages with the same behavior have similar shapes.

Dependency-free (stdlib only).
"""
import math
import re
from typing import Dict, List, Tuple

# Language-agnostic primitive rules. Each maps to a common primitive.
# Patterns are matched against normalized text (lowercased, whitespace-collapsed).
AGNOSTIC_RULES: List[Tuple[str, List[str]]] = [
    # loops — language-agnostic keywords
    ("LOOP",     ["for ", "while ", "foreach", "for(", "do ", "repeat", " for("]),
    # branches
    ("BRANCH",   ["if ", "else", "switch", "case ", "? :", " ? ", "elif", "else if"]),
    # recursion — function name appears in its own body (detected separately)
    ("RECURSE",  ["recurs", "factorial(", "fibonacci("]),
    # arithmetic operators (language-agnostic)
    ("ARITH_ADD",[" + ", "++", "+= "]),
    ("ARITH_SUB",[" - ", "--", "-= "]),
    ("ARITH_MUL",[" * ", "*="]),
    ("ARITH_DIV",[" / ", "/="]),
    ("ARITH_MOD",[" % ", "%="]),
    # comparison operators (language-agnostic)
    ("COMPARE_EQ",["==", "===", "equal"]),
    ("COMPARE_NE",["!=", "!==", "not equal"]),
    ("COMPARE_GT",[" > ", "greater"]),
    ("COMPARE_LT",[" < ", "less"]),
    ("COMPARE_GE",[" >= ", ">="]),
    ("COMPARE_LE",[" <= ", "<="]),
    # assignment
    ("ASSIGN",   ["=", "+=", "-=", "*=", "/="]),
    # return / output
    ("RETURN",   ["return", "=>", "yield"]),
    # I/O
    ("READ",     ["read", "get", "input", "open", "param", "receive", "scanf", "cin"]),
    ("WRITE",    ["print", "console.log", "system.out", "write", "emit", "send", "printf", "cout"]),
    # aggregate / filter / sort / search
    ("AGGREGATE",["sum", "reduce", "accumulate", "total", "count"]),
    ("FILTER",   ["filter", "where", "select", "comprehension"]),
    ("SORT",     ["sort", "sorted", "orderby", "order_by"]),
    ("SEARCH",   ["find", "indexof", "search", "contains", "includes", "locate"]),
    # state mutation (assign + reuse)
    ("STATE",    ["+=", "-=", "append", "push", "add", "set", "mutate"]),
]

# Language-agnostic dimension order.
DIMS = ["LOOP", "BRANCH", "RECURSE", "ARITH_ADD", "ARITH_SUB", "ARITH_MUL",
        "ARITH_DIV", "ARITH_MOD", "COMPARE_EQ", "COMPARE_NE", "COMPARE_GT",
        "COMPARE_LT", "COMPARE_GE", "COMPARE_LE", "ASSIGN", "RETURN",
        "READ", "WRITE", "AGGREGATE", "FILTER", "SORT", "SEARCH", "STATE"]


# Comment / string literal markers handled by the lexer. Used to strip
# contents so keywords/operators inside literals never count as primitives.
_COMMENT_MARKERS = {
    "#", "//", "/*", "*/", "<!--", "-->", "\"", "'", "`", "\"\"\"", "'''",
}

# Longest-match-first operator table so `<=` never also fires `<` or `=`.
# Keys are the operators; longer operators sort first so they win over their
# shorter substrings (e.g. `<=` over `<`, `!=` over `=`).
_OPERATORS = [
    "===", "!==", "**=", "//=", "<<=", ">>=", "&&=", "||=", "??=",
    "<<", ">>", "<=", ">=", "==", "!=", "++", "--", "+=", "-=", "*=",
    "/=", "%=", "**", "//", "->", "=>", "&&", "||", "??", "?:",
    "+", "-", "*", "/", "%", "=", "<", ">", "!", "?", "&", "|", "^", "~",
]
_OPERATORS_SORTED = sorted(_OPERATORS, key=len, reverse=True)

# Token pattern: identifiers, numbers, operators (longest-first), punctuation.
_TOK_RE = re.compile(
    r"[A-Za-z_][A-Za-z0-9_]*"   # identifier / keyword
    r"|\d+(?:\.\d+)?"          # number
    r"|(?:" + "|".join(re.escape(op) for op in _OPERATORS_SORTED) + r")"
    r"|[()\[\]{},;:.\\]"       # punctuation
)


def _norm(code: str) -> str:
    return re.sub(r"\s+", " ", code).lower()


def _strip_strings_and_comments(code: str) -> str:
    """Remove string literal contents and comment regions so they never
    contribute phantom primitives. Handles #// line comments, /* */ and
    <!-- --> block comments, and single/double/triple/backtick quotes with
    common backslash escapes. Literal contents are replaced by spaces so
    source positions (and thus operator tokenization) stay intact."""
    s = code
    # Triple-quoted strings first (they can span lines).
    for tq in ("\"\"\"", "'''"):
        i = 0
        while True:
            i = s.find(tq, i)
            if i < 0:
                break
            j = s.find(tq, i + 3)
            if j < 0:
                break
            s = s[: i + 3] + " " * (j - (i + 3)) + s[j:]
            i = j + 3

    out = []
    i = 0
    n = len(s)
    block_comment = None  # None | "/*" | "<!--"
    while i < n:
        c = s[i]
        two = s[i:i + 2]
        four = s[i:i + 4]

        # Close an open block comment.
        if block_comment:
            close = "-->" if block_comment == "<!--" else "*/"
            if s[i:i + len(close)] == close:
                out.append(" " * len(close))
                block_comment = None
                i += len(close)
            else:
                out.append(" ")
                i += 1
            continue

        # Open a block comment.
        if two == "/*":
            out.append("  ")
            block_comment = "/*"
            i += 2
            continue
        if four == "<!--":
            out.append("    ")
            block_comment = "<!--"
            i += 4
            continue

        # Line comments (only outside strings). NB: `//` is a comment only when
        # preceded by a non-operand (start of line / punctuation) — so Python
        # floor division (`a // b`, `(a)//2`) and C `//=` survive, but `// note`
        # and `} // note` are comments. `#` is always a comment.
        prev_is_operand = False
        if two == "//":
            j = i - 1
            while j >= 0 and s[j] in " \t":
                j -= 1
            # comment iff the char before // is NOT an operand (identifier,
            # number, closing paren/bracket, dot). Empty (line start) or a
            # punctuation like `;`/`}` => comment.
            prev_is_operand = j >= 0 and (s[j].isalnum() or s[j] in "._)]")
        if c == "#" or (two == "//" and not prev_is_operand):
            # Skip to end of line.
            j = s.find("\n", i)
            if j < 0:
                out.append(" " * (n - i))
                break
            out.append(" " * (j - i))
            i = j
            continue

        # String literal.
        if c in ('\"', "'", "`"):
            quote = c
            out.append(c)
            i += 1
            while i < n:
                if s[i] == "\\":  # escaped char: blank it and the escape
                    out.append("  ")
                    i += 2
                    continue
                if s[i] == quote:
                    out.append(quote)
                    i += 1
                    break
                out.append(" ")
                i += 1
            continue

        out.append(c)
        i += 1

    return "".join(out)


def _tokenize(code: str) -> List[str]:
    """Tokenize code into identifiers, numbers, operators, and punctuation.
    Comments and string contents are stripped first."""
    stripped = _strip_strings_and_comments(code)
    return _TOK_RE.findall(stripped)


def _detect_recursion(code: str) -> bool:
    """Detect recursion: a function name that appears in its own body."""
    m = re.search(r"(?:def|function|public\s+\w+\s+\w+|int|void|var)\s+(\w+)\s*\(", code)
    if not m:
        return False
    name = m.group(1)
    # count occurrences of the name in the body (after the def line)
    body = code[code.find(m.group(0)) + len(m.group(0)):]
    return body.count(name) >= 1


def decompose(code: str) -> Dict[str, int]:
    """Extract code-agnostic primitives using a tokenizer (strings/comments
    stripped, longest-first operator matching). Returns {primitive: count}.

    Fixes the old substring-count approach's false positives:
      * no phantom ASSIGN from `=` inside `!=`/`<=`/`>=`/`==`
      * no double-counting of `<=` as both `<` and `<=`
      * no primitives detected from string literals or comments
      * `forEach`/`format` no longer match the `for` keyword (word boundaries)
    """
    toks = _tokenize(code)
    counts: Dict[str, int] = {d: 0 for d in DIMS}
    n = len(toks)

    def bump(dim: str, by: int = 1) -> None:
        counts[dim] = counts.get(dim, 0) + by

    i = 0
    while i < n:
        t = toks[i]
        # ── arithmetic operators ──
        if t == "+":
            bump("ARITH_ADD")
        elif t == "-":
            bump("ARITH_SUB")
        elif t == "*":
            bump("ARITH_MUL")
        elif t == "/":
            bump("ARITH_DIV")
        elif t == "%":
            bump("ARITH_MOD")
        # ── comparison operators ──
        elif t in ("==", "===", "equal"):
            bump("COMPARE_EQ")
        elif t in ("!=", "!==", "not equal"):
            bump("COMPARE_NE")
        elif t in (">", ">="):
            bump("COMPARE_GE" if t == ">=" else "COMPARE_GT")
        elif t in ("<", "<="):
            bump("COMPARE_LE" if t == "<=" else "COMPARE_LT")
        # ── assignment (skip compound/compare operators that contain =) ──
        elif t in ("=",":="):
            bump("ASSIGN")
        # ── control-flow keywords (word boundaries via exact token match) ──
        elif t in ("for", "while", "foreach", "until", "repeat", "do"):
            bump("LOOP")
        elif t in ("if", "else", "elif", "switch", "case", "when"):
            bump("BRANCH")
        elif t in ("return", "yield"):
            bump("RETURN")
        elif t == "=>":
            bump("RETURN")
        # ── I/O / aggregate / filter / sort / search keywords ──
        elif t in ("read", "gets", "getchar", "scanf", "cin", "scanf"):
            bump("READ")
        elif t in ("print", "printf", "println", "puts", "cout", "console.log",
                   "write", "echo"):
            bump("WRITE")
        elif t in ("sum", "reduce", "accumulate", "total", "count"):
            bump("AGGREGATE")
        elif t in ("filter", "where", "select", "distinct"):
            bump("FILTER")
        elif t in ("sort", "sorted", "orderby", "order_by"):
            bump("SORT")
        elif t in ("find", "indexof", "search", "contains", "includes", "locate"):
            bump("SEARCH")
        elif t in ("append", "push", "add", "set", "mutate"):
            bump("STATE")
        # ── compound assignment also implies assignment + state mutation ──
        elif t in ("+=", "-=", "*=", "/=", "%=", "<<=", ">>=", "|=", "&=", "^=", "||=", "&&="):
            bump("ASSIGN")
            bump("STATE")
        i += 1

    if _detect_recursion(code):
        counts["RECURSE"] += 1
    return counts


def agnostic_vector(code: str) -> Dict[str, float]:
    """Normalized code-agnostic shape vector (unit vector)."""
    counts = decompose(code)
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


def agnostic_similarity(code_a: str, code_b: str) -> float:
    """Cosine similarity between two code-agnostic shape vectors, minus a
    polarity-conflict penalty (opposite operations are not clones)."""
    base = cosine(agnostic_vector(code_a), agnostic_vector(code_b))
    from .polarity import combined_similarity_penalty
    return combined_similarity_penalty(base, decompose(code_a), decompose(code_b), code_a, code_b)


def _polarity_penalty(code_a: str, code_b: str) -> float:
    """Backward-compatible wrapper: shared penalty over the two decompose dicts."""
    from .polarity import polarity_penalty as _pp
    return _pp(decompose(code_a), decompose(code_b))


def shape(code: str, top_n: int = 8) -> str:
    """Human-readable shape = dominant primitives (top `top_n` non-zero).

    Widened to 8 (was 5) so composite shapes are not truncated — self-derived:
    a top-5 window capped composite synthesis/round-trip fidelity (avg overlap
    0.83 -> 0.97-1.00 at 7-8).
    """
    vec = decompose(code)
    ranked = sorted(vec.items(), key=lambda kv: -kv[1])
    top = [d for d, c in ranked if c > 0][:top_n]
    return ">".join(top) if top else "EMPTY"


# ── Self-test: cross-language equivalence ───────────────────────────────────
if __name__ == "__main__":
    # Same behavior (sum a list) in 3 languages
    py_sum = "def sum_list(nums):\n    total = 0\n    for n in nums:\n        total += n\n    return total"
    js_sum = "function sumList(nums) {\n    let total = 0;\n    for (let n of nums) {\n        total += n;\n    }\n    return total;\n}"
    java_sum = "int sumList(int[] nums) {\n    int total = 0;\n    for (int n : nums) {\n        total += n;\n    }\n    return total;\n}"

    # Different behavior (filter evens) in Python
    py_evens = "def evens(nums):\n    return [n for n in nums if n % 2 == 0]"

    print("=== Code-agnostic shapes (cross-language) ===")
    for name, code in [("py_sum", py_sum), ("js_sum", js_sum), ("java_sum", java_sum), ("py_evens", py_evens)]:
        print(f"{name:9s} shape={shape(code)}")

    print("\n=== Cross-language similarity ===")
    print(f"py_sum vs js_sum   (same, diff lang): {agnostic_similarity(py_sum, js_sum):.3f}")
    print(f"py_sum vs java_sum (same, diff lang): {agnostic_similarity(py_sum, java_sum):.3f}")
    print(f"js_sum vs java_sum (same, diff lang): {agnostic_similarity(js_sum, java_sum):.3f}")
    print(f"py_sum vs py_evens (different):       {agnostic_similarity(py_sum, py_evens):.3f}")
