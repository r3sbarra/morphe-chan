#!/usr/bin/env python
"""rust.py — Rust language adapter."""
import re
from .base import LanguageAdapter


class RustAdapter(LanguageAdapter):
    name = "rust"
    def_pattern = r"fn\s+(\w+)\s*\("
    loop_patterns = [r"\bfor\b", r"\bwhile\b", r"\bloop\b"]
    branch_patterns = [r"\bif\b", r"\belse\b", r"\bmatch\b"]
    write_patterns = [r"println!", r"\bprint!"]
    read_patterns = [r"\bread_line", r"\bread_to_string"]

    def detect(self, code):
        return "fn " in code or "let mut" in code or "println!" in code or "impl " in code

    # Rust uses a tail expression (no semicolon) as the implicit return: a fn
    # body whose last statement before `}` is a bare expression. `let` bindings
    # ALWAYS need a `;` in Rust, so an unsemicoloned final statement is a
    # genuine tail-return expression.
    # Two patterns: one for single-line `{ expr }` and one for multi-line
    # `{\\n ... \\n expr \\n}` — both exclude let/return/if/for/while/loop/match/
    # println!/print! and require the expression not end with `;`.
    tail_return_patterns = [
        # single-line: fn ... { expr }
        r"fn\s+\w+[^\n]*\{[ \t]*(?!let\b|return\b|if\b|for\b|while\b|loop\b|match\b|else\b|println!|print!)(?<![;{}:])[^\n;{}]+(?<!;)\}",
        # multi-line: fn ... { ... \n expr \n }
        r"fn\s+\w+[^\{]*\{(?:.|\n)*?\n[ \t]*(?!let\b|return\b|if\b|for\b|while\b|loop\b|match\b|else\b|println!|print!)([^\n;{}]+(?<!;))\n[ \t]*\}",
    ]

    def extract_calls(self, body):
        body_no_def = "\n".join(l for l in body.splitlines()
                                if not re.match(r"^\s*fn\b", l))
        return [m.group(1) for m in re.finditer(r"\b(\w+)\s*\(", body_no_def)
                if m.group(1) not in self._SKIP_CALLS]