#!/usr/bin/env python
"""base.py — LanguageAdapter base class.

The base class for all language adapters. Each adapter maps a programming
language's syntax (def/loop/branch/return/I-O) to a COMMON primitive vocabulary,
so the core is language-agnostic.

Subclasses override the regex patterns and detection heuristics for their
language. The base provides the shared decomposition logic.
"""
import re
from typing import Dict, List

# Common primitive vocabulary (language-agnostic)
PRIMITIVES = ["LOOP", "BRANCH", "RECURSE", "ARITH_ADD", "ARITH_SUB", "ARITH_MUL",
              "ARITH_DIV", "ARITH_MOD", "COMPARE_EQ", "COMPARE_NE", "COMPARE_GT",
              "COMPARE_LT", "COMPARE_GE", "COMPARE_LE", "ASSIGN", "RETURN",
              "READ", "WRITE", "AGGREGATE", "FILTER", "SORT", "SEARCH", "STATE"]


class LanguageAdapter:
    """Base class for language adapters. Maps language syntax to primitives."""
    name = "base"
    # regex patterns per primitive (language-specific)
    def_pattern = r"(?:def|function)\s+(\w+)\s*\("
    loop_patterns = [r"\bfor\b", r"\bwhile\b"]
    branch_patterns = [r"\bif\b", r"\belse\b"]
    return_patterns = [r"\breturn\b"]
    # Implicit/tail-expression returns for languages that use them (Ruby:
    # last expression of a def; Rust: tail expression with no semicolon).
    # Each is a list of (regex, description). Detects a function whose body
    # ends in an expression rather than an explicit `return`. Empty by default;
    # subclasses opt in.
    tail_return_patterns = []
    read_patterns = [r"\binput\(", r"\bopen\(", r"\bread\("]
    write_patterns = [r"\bprint\("]
    assign_patterns = [r"=", r"\+= ", r"-= "]
    aggregate_patterns = [r"\bsum\(", r"\bcount\(", r"\btotal\b"]
    filter_patterns = [r"\bfilter\(", r"\bwhere\b"]
    sort_patterns = [r"\bsort\(", r"\bsorted\("]
    search_patterns = [r"\bfind\(", r"\bindex\(", r"\bcontains\b", r"\bin\b"]
    state_patterns = [r"\+= ", r"-= ", r"\bappend\(", r"\bpush\("]

    def detect(self, code: str) -> bool:
        """Return True if this adapter handles the given code."""
        return False

    def extract_functions(self, code: str) -> Dict[str, str]:
        """Extract functions AND class methods. Returns {name: body}.

        Uses universal AST extraction for exact brace/block boundaries across all languages,
        with fallback to indentation matching for legacy or pseudo-code snippets.
        """
        try:
            from code_shape.core.universal_ast import extract_universal_functions
            funcs = extract_universal_functions(code, self.name)
            if funcs:
                return {f.name: f.full_code for f in funcs}
        except Exception:
            pass

        functions: Dict[str, str] = {}
        lines = code.splitlines()
        current_name = None
        current_lines: List[str] = []
        current_indent = 0
        for line in lines:
            m = re.match(r"^(\s*)" + self.def_pattern, line)
            if m:
                if current_name:
                    functions[current_name] = "\n".join(current_lines)
                current_name = m.group(m.lastindex)
                current_indent = len(m.group(1))
                current_lines = [line]
            elif current_name is not None:
                indent = len(line) - len(line.lstrip())
                if line.strip() and indent <= current_indent:
                    functions[current_name] = "\n".join(current_lines)
                    current_name = None
                    current_lines = []
                else:
                    current_lines.append(line)
        if current_name:
            functions[current_name] = "\n".join(current_lines)
        return functions

    def extract_calls(self, body: str) -> List[str]:
        """Extract called function names from a body (skip the def line)."""
        body_no_def = "\n".join(l for l in body.splitlines()
                                if not re.match(r"^\s*(?:def|function|func|fun)\b", l))
        return [m.group(1) for m in re.finditer(r"\b(\w+)\s*\(", body_no_def)
                if m.group(1) not in self._SKIP_CALLS]

    _SKIP_CALLS = {"if", "for", "while", "return", "print", "range", "len", "sum",
                   "sorted", "open", "int", "str", "list", "set", "dict", "console",
                   "document", "Math", "System", "fmt", "println", "puts", "echo",
                   "printf", "scanf", "malloc", "sizeof", "make", "vec", "File",
                   "Integer", "String", "Array", "List", "Int", "void", "char",
                   "string", "number", "bool", "var", "let", "const", "new"}

    def decompose(self, code: str) -> Dict[str, int]:
        """Decompose code into primitive counts.

        String literals and comments are stripped first so keywords inside
        them (e.g. "for sale", "if needed") don't count as primitives.
        The RAW code is kept for lexer-aware arithmetic so `//` floor division
        isn't mistaken for a comment."""
        raw = code
        code = self._strip_strings_comments(code)
        counts: Dict[str, int] = {p: 0 for p in PRIMITIVES}
        for pat in self.loop_patterns:
            counts["LOOP"] += len(re.findall(pat, code))
        for pat in self.branch_patterns:
            counts["BRANCH"] += len(re.findall(pat, code))
        for pat in self.return_patterns:
            counts["RETURN"] += len(re.findall(pat, code))
        for pat in self.tail_return_patterns:
            # tail-implicit returns: count each match as one RETURN primitive
            counts["RETURN"] += len(re.findall(pat, code))
        for pat in self.read_patterns:
            counts["READ"] += len(re.findall(pat, code))
        for pat in self.write_patterns:
            counts["WRITE"] += len(re.findall(pat, code))
        for pat in self.assign_patterns:
            counts["ASSIGN"] += len(re.findall(pat, code))
        for pat in self.aggregate_patterns:
            counts["AGGREGATE"] += len(re.findall(pat, code))
        for pat in self.filter_patterns:
            counts["FILTER"] += len(re.findall(pat, code))
        for pat in self.sort_patterns:
            counts["SORT"] += len(re.findall(pat, code))
        for pat in self.search_patterns:
            counts["SEARCH"] += len(re.findall(pat, code))
        for pat in self.state_patterns:
            counts["STATE"] += len(re.findall(pat, code))
        # universal operators
        # Arithmetic is count by TOKEN, not spaced-regex, so compact operators
        # (`lo+hi`, `a*b`) count too and `+` inside a string literal (already
        # stripped) never does. This fixes cross-language shape divergence where
        # a spaced-operator regex only fired for the language that used spaces.
        try:
            from code_shape.core.agnostic_shape import _tokenize
            toks = _tokenize(raw)
        except Exception:
            toks = []
        # operand tokens that can border a binary operator (identifiers, numbers,
        # closing brackets). `*p` (pointer deref) and `* 5` (unary) are NOT
        # multiplication, so a `*` only counts as ARITH_MUL when it has an
        # operand-like token on BOTH sides.
        import re as _re
        _KEYWORDS = {"return", "if", "else", "for", "while", "in", "and", "or",
                     "not", "int", "float", "char", "void", "true", "false",
                     "null", "None", "self", "this", "func", "def", "fn", "let",
                     "var", "const", "new", "sizeof", "static", "public", "switch"}

        def _operand(tok):
            if not tok or tok in _KEYWORDS:
                return False
            return bool(_re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_]*|\d+|[)\]}]", tok))
        for i, t in enumerate(toks):
            if t == "+":
                counts["ARITH_ADD"] += 1
            elif t == "-":
                counts["ARITH_SUB"] += 1
            elif t == "*":
                if i > 0 and i + 1 < len(toks) and _operand(toks[i - 1]) and _operand(toks[i + 1]):
                    counts["ARITH_MUL"] += 1
            elif t == "/" or t == "//":
                if i > 0 and i + 1 < len(toks) and _operand(toks[i - 1]) and _operand(toks[i + 1]):
                    counts["ARITH_DIV"] += 1
            elif t == "%":
                if i > 0 and i + 1 < len(toks) and _operand(toks[i - 1]) and _operand(toks[i + 1]):
                    counts["ARITH_MOD"] += 1
            elif t in ("+=", "-=", "*=", "/=", "%=", "++", "--"):
                counts["ARITH_ADD" if t in ("+=", "++") else
                        "ARITH_SUB" if t in ("-=", "--") else
                        "ARITH_MUL" if t == "*=" else
                        "ARITH_DIV" if t == "/=" else "ARITH_MOD"] += 1
        # '*' is NOT multiplication in SELECT * FROM / wildcard imports / generics.
        non_mul = len(_re.findall(r"SELECT\s+\*\s+FROM", code, _re.IGNORECASE))
        counts["ARITH_MUL"] = max(0, counts["ARITH_MUL"] - non_mul)
        for dim, pat in [("COMPARE_EQ", r"==|==="), ("COMPARE_NE", r"!=|!=="),
                         ("COMPARE_GT", r" > "), ("COMPARE_LT", r" < "),
                         ("COMPARE_GE", r">="), ("COMPARE_LE", r"<=")]:
            counts[dim] += len(re.findall(pat, code))
        # recursion
        if self._is_recursive(code):
            counts["RECURSE"] += 1
        return counts

    def _strip_strings_comments(self, code: str) -> str:
        """Remove string literals and comments so keywords inside them don't
        count as primitives. Handles single/double quotes and #/// comments.
        """
        # remove // and # comments (line-based)
        lines = []
        for line in code.splitlines():
            # strip // comment (but not http://)
            idx = line.find("//")
            if idx != -1 and not line[max(0, idx - 1):idx + 2].startswith(":"):
                line = line[:idx]
            # strip # comment (but not inside string)
            idx = line.find("#")
            if idx != -1:
                line = line[:idx]
            lines.append(line)
        code = "\n".join(lines)
        # remove string literals (single and double quoted)
        code = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', '""', code)
        code = re.sub(r"'[^'\\]*(?:\\.[^'\\]*)*'", "''", code)
        return code

    def _is_recursive(self, code: str) -> bool:
        m = re.search(self.def_pattern, code)
        if not m:
            return False
        # The name group may be optional (e.g. anonymous JS functions like
        # `function () {...}` or `const f = function() {...}`) and may not have
        # participated in the match. m.lastindex can then point at a group that
        # didn't match, and m.group() raises IndexError. Anonymous functions
        # have no name to detect recursion by, so return False.
        try:
            name = m.group(m.lastindex)
        except IndexError:
            return False
        if not name:
            return False
        body = code[code.find(m.group(0)) + len(m.group(0)):]
        return body.count(name) >= 1
